"""Tests for batched, deduplicated size lookups."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from gi.repository import GLib

from parcel.backend.models import Package
from parcel.ui.size_loader import SizeLoader
from parcel.ui.tasks import SyncRunner


def make_package(name: str, size: int = 0, package_id: str | None = None) -> Package:
    return Package(
        name=name,
        version="1.0-1.fc44",
        repo="fedora",
        size=size,
        package_id=package_id
        if package_id is not None
        else f"{name};1.0-1.fc44;x86_64;fedora",
    )


class FakeFetch:
    def __init__(self, sizes: Mapping[str, int] | None = None, error: bool = False):
        self.sizes = dict(sizes or {})
        self.error = error
        self.batches: list[list[str]] = []

    def __call__(self, packages: Sequence[Package]) -> Mapping[str, int]:
        self.batches.append([package.name for package in packages])
        if self.error:
            raise RuntimeError("packagekit is unhappy")
        return {
            package.package_id: self.sizes[package.name]
            for package in packages
            if package.name in self.sizes
        }


def flush(loader: SizeLoader) -> None:
    """Run the queued batch immediately and clean up the timer it may arm."""
    loader._flush()
    if loader._source_id is not None:
        GLib.source_remove(loader._source_id)
        loader._source_id = None


def test_known_size_is_delivered_without_a_query() -> None:
    fetch = FakeFetch()
    sizes: list[int] = []
    SizeLoader(fetch, SyncRunner()).request(
        make_package("gimp", size=2048), sizes.append
    )

    assert sizes == [2048]
    assert fetch.batches == []


def test_packages_without_an_id_are_ignored() -> None:
    fetch = FakeFetch()
    sizes: list[int] = []
    loader = SizeLoader(fetch, SyncRunner())
    loader.request(make_package("gimp", package_id=""), sizes.append)
    flush(loader)

    assert sizes == []
    assert fetch.batches == []


def test_queued_packages_are_fetched_in_one_batch() -> None:
    fetch = FakeFetch({"gimp": 1024, "htop": 2048})
    loader = SizeLoader(fetch, SyncRunner())
    sizes: list[int] = []

    loader.request(make_package("gimp"), sizes.append)
    loader.request(make_package("htop"), sizes.append)
    assert fetch.batches == []

    flush(loader)

    assert fetch.batches == [["gimp", "htop"]]
    assert sizes == [1024, 2048]


def test_repeated_requests_for_one_package_share_the_lookup() -> None:
    fetch = FakeFetch({"gimp": 1024})
    loader = SizeLoader(fetch, SyncRunner())
    sizes: list[int] = []

    loader.request(make_package("gimp"), sizes.append)
    loader.request(make_package("gimp"), sizes.append)
    flush(loader)

    assert fetch.batches == [["gimp"]]
    assert sizes == [1024, 1024]


def test_batches_are_capped_and_the_rest_rescheduled() -> None:
    fetch = FakeFetch({"a": 1, "b": 2, "c": 3})
    loader = SizeLoader(fetch, SyncRunner(), batch_size=2)
    sizes: list[int] = []

    for name in ("a", "b", "c"):
        loader.request(make_package(name), sizes.append)

    flush(loader)
    assert fetch.batches == [["a", "b"]]
    assert sizes == [1, 2]
    assert loader._source_id is None or GLib.source_remove(loader._source_id) is None

    loader._source_id = None
    flush(loader)
    assert fetch.batches == [["a", "b"], ["c"]]
    assert sizes == [1, 2, 3]


def test_fetch_errors_leave_sizes_unknown() -> None:
    fetch = FakeFetch(error=True)
    loader = SizeLoader(fetch, SyncRunner())
    sizes: list[int] = []

    loader.request(make_package("gimp"), sizes.append)
    flush(loader)

    assert sizes == []
    assert fetch.batches == [["gimp"]]


def test_missing_sizes_are_not_reported() -> None:
    fetch = FakeFetch({})
    loader = SizeLoader(fetch, SyncRunner())
    sizes: list[int] = []

    loader.request(make_package("gimp"), sizes.append)
    flush(loader)

    assert sizes == []
