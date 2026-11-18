"""Read-only lookups in the rpm database.

PackageKit does not expose install dates, file lists, reverse dependencies,
or changelogs, so the backend reads them from the local rpmdb through
python3-rpm. Tests inject a fake module and header objects; no test touches
the live database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import rpm as _rpm


class RpmDatabase:
    """Installed-package metadata from the rpm database."""

    def __init__(self, rpm_module: Any = None) -> None:
        self._rpm = rpm_module if rpm_module is not None else _rpm

    def installed_sizes(self) -> dict[str, int]:
        """Installed size in bytes for every installed package, by name."""
        sizes: dict[str, int] = {}
        for header in self._rpm.TransactionSet().dbMatch():
            sizes[header["name"]] = int(header["size"] or 0)
        return sizes

    def install_date(self, name: str) -> datetime | None:
        header = self._header(name)
        if header is None:
            return None
        stamp = header["installtime"]
        if not stamp:
            return None
        return datetime.fromtimestamp(int(stamp))

    def files(self, name: str) -> tuple[str, ...]:
        header = self._header(name)
        if header is None:
            return ()
        return tuple(header["filenames"] or ())

    def required_by(self, name: str) -> tuple[str, ...]:
        """Installed packages whose requirements are satisfied by ``name``.

        Matches capabilities, not just the package name, so ``/bin/sh``
        consumers of bash are included.
        """
        header = self._header(name)
        if header is None:
            return ()
        transaction = self._rpm.TransactionSet()
        dependents: set[str] = set()
        for capability in header["providename"] or ():
            for dependent in transaction.dbMatch("requirename", capability):
                dependent_name = dependent["name"]
                if dependent_name != name:
                    dependents.add(dependent_name)
        return tuple(sorted(dependents, key=str.casefold))

    def changelog(self, name: str) -> str:
        """The newest changelog entry, author line included."""
        header = self._header(name)
        if header is None:
            return ""
        texts = tuple(header["changelogtext"] or ())
        if not texts:
            return ""
        times = tuple(header["changelogtime"] or ())
        names = tuple(header["changelogname"] or ())
        newest = max(range(len(texts)), key=lambda index: _at(times, index))
        entry = texts[newest].strip()
        author = names[newest].strip() if newest < len(names) else ""
        return f"{author}\n{entry}" if author else entry

    def _header(self, name: str) -> Any | None:
        for header in self._rpm.TransactionSet().dbMatch("name", name):
            return header
        return None


def _at(values: tuple[int, ...], index: int) -> int:
    return values[index] if index < len(values) else 0
