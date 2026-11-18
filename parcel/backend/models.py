"""Plain data types shared by the PackageKit client and the views.

No GTK, no PackageKit, no I/O: these objects are safe to build and test
anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


class InstallReason(Enum):
    """Why a package ended up on the system."""

    USER = "installed by you"
    DEPENDENCY = "installed as a dependency"


def format_size(size: int) -> str:
    """Render a byte count as a short human-readable string."""
    if size < 0:
        raise ValueError(f"size must be non-negative, got {size}")
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


@dataclass(frozen=True, slots=True)
class Package:
    """One rpm, installed or available.

    ``package_id`` is PackageKit's ``name;version;arch;repo`` id; it is the
    only way to name a package in a transaction.
    """

    name: str
    version: str
    repo: str
    arch: str = "x86_64"
    size: int = 0
    summary: str = ""
    description: str = ""
    license: str = ""
    installed: bool = False
    install_reason: InstallReason | None = None
    install_date: datetime | None = None
    required_by: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    changelog: str = ""
    homepage: str = ""
    package_id: str = ""

    @property
    def size_text(self) -> str:
        return format_size(self.size) if self.size else "unknown"

    @property
    def repo_label(self) -> str:
        """Short repo name for display; PackageKit prefixes installed repos."""
        repo = self.repo.removeprefix("installed:")
        parts = repo.split(":")
        if parts[0] == "copr" and len(parts) >= 3:
            return f"copr:{parts[-2]}/{parts[-1]}"
        return repo or "unknown"

    @property
    def install_reason_text(self) -> str:
        return self.install_reason.value if self.install_reason else "unknown"

    @property
    def required_by_text(self) -> str:
        if not self.required_by:
            return "Nothing depends on it"
        return ", ".join(self.required_by)

    @property
    def files_text(self) -> str:
        if not self.files:
            return "No file list available"
        preview = ", ".join(self.files[:3])
        hidden = len(self.files) - 3
        return f"{preview} (+{hidden} more)" if hidden > 0 else preview

    def matches(self, query: str) -> bool:
        """True when the package is a match for a search query."""
        term = query.strip().casefold()
        if not term:
            return True
        haystack = (self.name, self.summary, self.repo, self.description)
        return any(term in part.casefold() for part in haystack)


@dataclass(frozen=True, slots=True)
class Repo:
    """One package repository."""

    repo_id: str
    name: str
    enabled: bool = True
    system: bool = False
    baseurl: str = ""
    copr: str = ""

    @property
    def removable(self) -> bool:
        """System repos may be disabled but never removed."""
        return not self.system


@dataclass(frozen=True, slots=True)
class Update:
    """An available update for an installed package."""

    package: Package
    installed_version: str | None = None
    security: bool = False

    @property
    def name(self) -> str:
        return self.package.name

    @property
    def new_version(self) -> str:
        return self.package.version

    @property
    def version_text(self) -> str:
        if self.installed_version:
            return f"{self.installed_version} \u2192 {self.new_version}"
        return self.new_version

    def matches(self, query: str) -> bool:
        term = query.strip().casefold()
        if self.security and "security" in term:
            return True
        return self.package.matches(query)
