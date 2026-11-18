"""Fetch sizes for packages as their rows scroll into view.

PackageKit's package listing carries no size, and asking for details of every
package up front would mean tens of thousands of queries. Rows ask for a size
when they are bound; requests are batched and deduplicated.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from gi.repository import GLib

from parcel.backend.models import Package
from parcel.ui.tasks import Runner

SizeCallback = Callable[[int], None]


class SizeLoader:
    """Batches size lookups and hands them back to the requesting rows."""

    def __init__(
        self,
        fetch: Callable[[Sequence[Package]], Mapping[str, int]],
        runner: Runner,
        batch_size: int = 100,
        delay_ms: int = 100,
    ) -> None:
        self._fetch = fetch
        self._runner = runner
        self._batch_size = batch_size
        self._delay_ms = delay_ms
        self._waiting: dict[str, list[SizeCallback]] = {}
        self._queued: dict[str, Package] = {}
        self._source_id: int | None = None

    def request(self, package: Package, callback: SizeCallback) -> None:
        """Ask for ``package``'s size; ``callback`` may never run on failure."""
        if package.size:
            callback(package.size)
            return
        if not package.package_id:
            return
        self._waiting.setdefault(package.package_id, []).append(callback)
        if package.package_id in self._queued:
            return
        self._queued[package.package_id] = package
        if self._source_id is None:
            self._schedule()

    def _schedule(self) -> None:
        self._source_id = GLib.timeout_add(self._delay_ms, self._flush)

    def _flush(self) -> bool:
        self._source_id = None
        batch = list(self._queued.values())[: self._batch_size]
        for package in batch:
            self._queued.pop(package.package_id, None)
        if self._queued:
            self._schedule()
        if not batch:
            return GLib.SOURCE_REMOVE
        ids = [package.package_id for package in batch]
        self._runner.run(
            lambda: self._fetch(batch),
            self._deliver,
            lambda _error: self._forget(ids),
        )
        return GLib.SOURCE_REMOVE

    def _deliver(self, sizes: Mapping[str, int]) -> None:
        for package_id, size in sizes.items():
            for callback in self._waiting.pop(package_id, ()):
                callback(size)

    def _forget(self, package_ids: Sequence[str]) -> None:
        for package_id in package_ids:
            self._waiting.pop(package_id, None)
