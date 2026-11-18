"""PackageKit queries used by Parcel.

This is the only module allowed to talk to PackageKit. Views reach it through
this client; they never import :mod:`gi.repository.PackageKitGlib` themselves.
The module must not import GTK or libadwaita.
"""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("PackageKitGlib", "1.0")

from gi.repository import PackageKitGlib  # noqa: E402

from parcel.backend.models import Package, Update  # noqa: E402

_FILTER_NEWEST = int(PackageKitGlib.FilterEnum.NEWEST)
_FILTER_INSTALLED = int(PackageKitGlib.FilterEnum.INSTALLED)
_FILTER_NOT_SOURCE = int(PackageKitGlib.FilterEnum.NOT_SOURCE)


def _new_pk_client() -> Any:
    """Build the real PackageKit client, lazily: queries are what need D-Bus."""
    return PackageKitGlib.Client()


def _split_package_id(package_id: str) -> tuple[str, str, str, str]:
    """Split a PackageKit id (``name;version;arch;repo``)."""
    parts = package_id.split(";")
    if len(parts) != 4:
        return package_id, "", "", ""
    return parts[0], parts[1], parts[2], parts[3]


def _repo_from_id(package_id: str) -> str:
    return _split_package_id(package_id)[3]


class PackageKitClient:
    """Synchronous PackageKit queries returning Parcel's plain models.

    ``pk_client`` exists so tests can pass a fake; production code leaves it
    unset and gets the daemon-backed client.
    """

    def __init__(self, pk_client: Any = None) -> None:
        self._client = pk_client if pk_client is not None else _new_pk_client()

    def list_installed(self) -> list[Package]:
        """Packages currently installed on the system."""
        results = self._client.get_packages(
            _FILTER_INSTALLED | _FILTER_NEWEST, None, None, None
        )
        return [self._to_package(pkg) for pkg in results.get_package_array()]

    def search(self, query: str) -> list[Package]:
        """Search package names and summaries for ``query``."""
        term = query.strip()
        if not term:
            return []
        results = self._client.search_names(
            _FILTER_NEWEST | _FILTER_NOT_SOURCE, [term], None, None, None
        )
        return [self._to_package(pkg) for pkg in results.get_package_array()]

    def list_updates(self) -> list[Update]:
        """Updates available for installed packages."""
        results = self._client.get_updates(
            _FILTER_NEWEST | _FILTER_NOT_SOURCE, None, None, None
        )
        return [self._to_update(pkg) for pkg in results.get_package_array()]

    @staticmethod
    def _to_package(pkg: Any) -> Package:
        info = pkg.get_info()
        return Package(
            name=pkg.get_name(),
            version=pkg.get_version(),
            repo=_repo_from_id(pkg.get_id()),
            arch=pkg.get_arch(),
            summary=pkg.get_summary(),
            installed=info == PackageKitGlib.InfoEnum.INSTALLED,
        )

    @staticmethod
    def _to_update(pkg: Any) -> Update:
        return Update(
            package=PackageKitClient._to_package(pkg),
            security=pkg.get_info() == PackageKitGlib.InfoEnum.SECURITY,
        )
