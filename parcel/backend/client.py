"""PackageKit queries and transactions used by Parcel.

This is the only module allowed to talk to PackageKit. Views reach it through
this client; they never import :mod:`gi.repository.PackageKitGlib` themselves.
The module must not import GTK or libadwaita.

PackageKit's server-side listing filters are not dependable: some builds
ignore them, some renumber them. Everything is listed unfiltered and reduced
here, so the client behaves the same on every PackageKit version.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import gi

gi.require_version("PackageKitGlib", "1.0")

from gi.repository import GLib, PackageKitGlib  # noqa: E402

from parcel.backend.history import HistoryDatabase  # noqa: E402
from parcel.backend.models import (  # noqa: E402
    Package,
    Repo,
    RepoPlan,
    RepoRequest,
    Update,
)
from parcel.backend.repo_files import is_system_repo  # noqa: E402
from parcel.backend.repos import RepoManager  # noqa: E402
from parcel.backend.rpmdb import RpmDatabase  # noqa: E402
from parcel.backend.versioning import (  # noqa: E402
    compare,
    dedupe_latest,
    sort_packages,
)

# No filters: see the module docstring. PackageKit treats 0 as "no filtering".
_NO_FILTERS = 0
_NO_FLAGS = int(PackageKitGlib.TransactionFlagEnum.NONE)
_SOURCE_ARCHES = frozenset({"src", "nosrc"})


class BackendError(RuntimeError):
    """A PackageKit transaction did not succeed."""


def _noop_progress(*_args: object) -> None:
    """PackageKit requires a progress callback even when nobody listens."""


class PackageKitClient:
    """Synchronous PackageKit access returning Parcel's plain models.

    ``pk_client``, ``rpm_db``, and ``history`` exist so tests can pass fakes;
    production code leaves them unset and gets the real implementations.
    """

    def __init__(
        self,
        pk_client: Any = None,
        rpm_db: RpmDatabase | None = None,
        history: HistoryDatabase | None = None,
        repos: RepoManager | None = None,
    ) -> None:
        self._client = pk_client if pk_client is not None else PackageKitGlib.Client()
        self._rpm = rpm_db if rpm_db is not None else RpmDatabase()
        self._history = history if history is not None else HistoryDatabase()
        self._repos = repos if repos is not None else RepoManager()
        # One unfiltered listing feeds both lists; each list is only built when
        # first requested, so startup does not pay for the available catalog.
        self._raw: list[tuple[Any, Any]] | None = None
        self._installed: list[Package] | None = None
        self._available: list[Package] | None = None

    # -- listings ---------------------------------------------------------

    def catalog(self) -> tuple[list[Package], list[Package]]:
        """``(installed, available)`` packages, one entry per name and arch.

        The raw Listing is fetched once and cached; each half is reduced on
        first request. Transactions call :meth:`invalidate`.
        """
        return self.list_installed(), self.list_available()

    def list_installed(self) -> list[Package]:
        """Packages currently installed on the system."""
        if self._installed is None:
            metadata = self._rpm.installed_metadata()
            packages = []
            for pkg, info in self._raw_packages():
                if info != PackageKitGlib.InfoEnum.INSTALLED:
                    continue
                meta = metadata.get(pkg.get_name())
                packages.append(
                    self._to_package(
                        pkg,
                        installed=True,
                        size=meta.size if meta else 0,
                        packager=meta.packager if meta else "",
                        description=meta.description if meta else "",
                    )
                )
            self._installed = sort_packages(dedupe_latest(packages))
        return list(self._installed)

    def list_available(self) -> list[Package]:
        """Packages offered by the configured repositories, not installed."""
        if self._available is None:
            packages = [
                self._to_package(pkg, installed=False, size=0)
                for pkg, info in self._raw_packages()
                if info == PackageKitGlib.InfoEnum.AVAILABLE
            ]
            self._available = sort_packages(dedupe_latest(packages))
        return list(self._available)

    def _raw_packages(self) -> list[tuple[Any, Any]]:
        """Every non-source package from one unfiltered ``get_packages`` call."""
        if self._raw is None:
            results = self._client.get_packages(_NO_FILTERS, None, _noop_progress, None)
            self._raw = [
                (pkg, pkg.get_info())
                for pkg in results.get_package_array()
                if pkg.get_arch() not in _SOURCE_ARCHES
            ]
        return self._raw

    def list_updates(
        self, installed_versions: Mapping[str, str] | None = None
    ) -> list[Update]:
        """Newer versions of installed packages.

        ``installed_versions`` maps package name to installed version; the
        caller usually already has it from :meth:`list_installed`.
        """
        if installed_versions is None:
            installed_versions = {p.name: p.version for p in self.list_installed()}
        results = self._client.get_updates(_NO_FILTERS, None, _noop_progress, None)
        newest: dict[tuple[str, str], Update] = {}
        for pkg in results.get_package_array():
            package = self._to_package(pkg, installed=False, size=0)
            update = Update(
                package=package,
                installed_version=installed_versions.get(package.name),
                security=pkg.get_info() == PackageKitGlib.InfoEnum.SECURITY,
            )
            key = (package.name, package.arch)
            current = newest.get(key)
            if current is None or compare(package.version, current.new_version) > 0:
                newest[key] = update
        return sorted(
            newest.values(),
            key=lambda update: (update.name.casefold(), update.package.arch),
        )

    def invalidate(self) -> None:
        """Forget the cached listings; the next listing hits PackageKit again."""
        self._raw = None
        self._installed = None
        self._available = None

    # -- details ----------------------------------------------------------

    def get_detail(self, package: Package) -> Package:
        """``package`` enriched with everything the detail view shows."""
        details = self._details(package.package_id)
        files = self._files(package.package_id) if package.installed else ()
        install_date = None
        install_reason = None
        required_by: tuple[str, ...] = ()
        if package.installed:
            install_date = self._rpm.install_date(package.name)
            install_reason = self._history.install_reason(package.name)
            required_by = self._rpm.required_by(package.name)
            changelog = self._rpm.changelog(package.name)
        else:
            changelog = self._update_changelog(package.package_id)
        return replace(
            package,
            description=(details.get_description() if details else "")
            or package.description
            or package.summary,
            license=(details.get_license() if details else "") or package.license,
            homepage=(details.get_url() if details else "") or package.homepage,
            size=(details.get_size() if details else 0) or package.size,
            files=files,
            install_date=install_date,
            install_reason=install_reason,
            required_by=required_by,
            changelog=changelog,
        )

    def sizes(self, packages: Sequence[Package]) -> dict[str, int]:
        """Sizes in bytes, keyed by PackageKit id, for the given packages."""
        ids = [package.package_id for package in packages if package.package_id]
        if not ids:
            return {}
        results = self._client.get_details(ids, None, _noop_progress, None)
        sizes: dict[str, int] = {}
        for details in results.get_details_array():
            size = details.get_size()
            if size:
                sizes[details.get_package_id()] = size
        return sizes

    # -- transactions -----------------------------------------------------

    def install(self, package: Package) -> None:
        """Install ``package``. Asks for authorization via polkit."""
        results = self._client.install_packages(
            _NO_FLAGS, [self._package_id(package)], None, _noop_progress, None
        )
        self._check(results, package)
        self.invalidate()

    def remove(self, package: Package) -> None:
        """Uninstall ``package``, without cascading to other packages."""
        results = self._client.remove_packages(
            _NO_FLAGS,
            [self._package_id(package)],
            False,
            False,
            None,
            _noop_progress,
            None,
        )
        self._check(results, package)
        self.invalidate()

    def update(self, packages: Sequence[Package]) -> None:
        """Install the offered versions of ``packages`` in one transaction."""
        ids = [self._package_id(package) for package in packages]
        if not ids:
            raise ValueError("no packages to update")
        results = self._client.update_packages(
            _NO_FLAGS, ids, None, _noop_progress, None
        )
        self._check(results, packages[0])
        self.invalidate()

    # -- repositories -----------------------------------------------------

    def list_repos(self) -> list[Repo]:
        """Every configured repository, distribution repos first."""
        results = self._client.get_repo_list(_NO_FILTERS, None, _noop_progress, None)
        repos = []
        for detail in results.get_repo_detail_array():
            repo_id = detail.get_id()
            repos.append(
                Repo(
                    repo_id=repo_id,
                    name=detail.get_description() or repo_id,
                    enabled=detail.get_enabled(),
                    system=is_system_repo(repo_id),
                    copr=repo_id if repo_id.startswith("copr:") else "",
                )
            )
        return sorted(
            repos,
            key=lambda repo: (not repo.system, repo.name.casefold(), repo.repo_id),
        )

    def prepare_repo(self, request: RepoRequest) -> RepoPlan:
        """Download a new repo's signing key for the UI to show and confirm."""
        return self._repos.prepare(request)

    def add_repo(self, plan: RepoPlan) -> None:
        """Install a repository whose key fingerprint the user confirmed."""
        self._repos.add(plan)
        self.invalidate()

    def set_repo_enabled(self, repo: Repo, enabled: bool) -> None:
        """Turn a repository on or off; packages stay installed either way."""
        results = self._client.repo_enable(
            repo.repo_id, enabled, None, _noop_progress, None
        )
        self._check_exit(results, f"the change to {repo.repo_id}")
        self.invalidate()

    def remove_repo(self, repo: Repo) -> None:
        """Stop using a repository without uninstalling anything from it."""
        if not repo.removable:
            raise BackendError(f"{repo.name} is a system repository")
        results = self._client.repo_remove(
            _NO_FLAGS, repo.repo_id, False, None, _noop_progress, None
        )
        self._check_exit(results, f"the removal of {repo.repo_id}")
        self.invalidate()

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _package_id(package: Package) -> str:
        if not package.package_id:
            raise BackendError(f"{package.name} has no PackageKit id")
        return package.package_id

    @staticmethod
    def _check(results: Any, package: Package) -> None:
        PackageKitClient._check_exit(results, f"the transaction for {package.name}")

    @staticmethod
    def _check_exit(results: Any, what: str) -> None:
        exit_code = results.get_exit_code()
        if exit_code != PackageKitGlib.ExitEnum.SUCCESS:
            raise BackendError(f"PackageKit refused {what} ({exit_code})")

    def _details(self, package_id: str) -> Any | None:
        if not package_id:
            return None
        results = self._client.get_details([package_id], None, _noop_progress, None)
        details = results.get_details_array()
        return details[0] if details else None

    def _files(self, package_id: str) -> tuple[str, ...]:
        if not package_id:
            return ()
        results = self._client.get_files([package_id], None, _noop_progress, None)
        files = results.get_files_array()
        return tuple(files[0].get_files()) if files else ()

    def _update_changelog(self, package_id: str) -> str:
        if not package_id:
            return ""
        try:
            results = self._client.get_update_detail(
                [package_id], None, _noop_progress, None
            )
        except GLib.Error:
            return ""
        details = results.get_update_detail_array()
        return details[0].get_changelog() if details else ""

    @staticmethod
    def _to_package(
        pkg: Any,
        installed: bool,
        size: int,
        packager: str = "",
        description: str = "",
    ) -> Package:
        arch = pkg.get_arch()
        return Package(
            name=pkg.get_name(),
            version=pkg.get_version(),
            repo=pkg.get_id().split(";")[3] if pkg.get_id().count(";") == 3 else "",
            arch=arch,
            size=size,
            summary=pkg.get_summary(),
            description=description,
            packager=packager,
            installed=installed,
            package_id=pkg.get_id(),
        )
