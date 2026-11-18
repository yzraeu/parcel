"""Tests for rpm version parsing, comparison, and deduplication."""

import pytest

from parcel.backend.models import Package
from parcel.backend.versioning import compare, dedupe_latest, parse_evr, sort_packages


def make_package(name: str, version: str, arch: str = "x86_64") -> Package:
    return Package(name=name, version=version, repo="fedora", arch=arch)


@pytest.mark.parametrize(
    ("version", "evr"),
    [
        ("1.0-1.fc44", ("0", "1.0", "1.fc44")),
        ("1:2.3-4", ("1", "2.3", "4")),
        ("2.0", ("0", "2.0", "")),
        ("1:2.0", ("1", "2.0", "")),
        ("", ("0", "", "")),
    ],
)
def test_parse_evr(version: str, evr: tuple[str, str, str]) -> None:
    assert parse_evr(version) == evr


def test_compare_orders_versions_numerically() -> None:
    assert compare("10.0-1", "9.0-1") > 0
    assert compare("9.0-1", "10.0-1") < 0
    assert compare("1.0-1", "1.0-1") == 0


def test_compare_respects_epoch_and_release() -> None:
    assert compare("1:1.0-1", "2.0-9") > 0
    assert compare("1.0-2", "1.0-10") < 0


def test_dedupe_keeps_the_newest_version_per_name_and_arch() -> None:
    packages = [
        make_package("firefox", "1.0-1"),
        make_package("firefox", "10.0-1"),
        make_package("firefox", "2.0-1"),
        make_package("firefox", "1.5-1", arch="aarch64"),
    ]

    kept = dedupe_latest(packages)

    assert sorted((p.name, p.arch, p.version) for p in kept) == [
        ("firefox", "aarch64", "1.5-1"),
        ("firefox", "x86_64", "10.0-1"),
    ]


def test_dedupe_keeps_the_first_package_on_a_tie() -> None:
    first = make_package("firefox", "1.0-1")
    second = make_package("firefox", "1.0-1")
    assert dedupe_latest([first, second]) == [first]


def test_sort_packages_is_case_insensitive_by_name_then_arch() -> None:
    packages = [
        make_package("Zlib", "1.0-1", arch="i686"),
        make_package("firefox", "1.0-1", arch="x86_64"),
        make_package("Zlib", "1.0-1", arch="aarch64"),
    ]
    assert [(p.name, p.arch) for p in sort_packages(packages)] == [
        ("firefox", "x86_64"),
        ("Zlib", "aarch64"),
        ("Zlib", "i686"),
    ]
