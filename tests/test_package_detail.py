"""Tests for the expanded package detail view."""

from datetime import datetime

from parcel.backend.models import InstallReason, Package
from parcel.ui.package_detail import PackageDetail


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "arch": "x86_64",
        "size": 2048,
        "description": "Firefox is a standalone web browser.",
        "license": "MPL-2.0",
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


def test_available_package_shows_base_facts_only() -> None:
    detail = PackageDetail(make_package())

    assert detail.facts == {
        "License": "MPL-2.0",
        "Size": "2.0 KiB",
        "Repository": "updates",
        "Architecture": "x86_64",
        "Files": "No file list available",
    }


def test_installed_package_adds_install_facts() -> None:
    detail = PackageDetail(
        make_package(
            installed=True,
            install_reason=InstallReason.DEPENDENCY,
            install_date=datetime(2026, 11, 2, 9, 14),
            required_by=("nautilus",),
        )
    )

    assert detail.facts["Installed"] == "2026-11-02"
    assert detail.facts["Reason"] == "installed as a dependency"
    assert detail.facts["Required by"] == "nautilus"


def test_missing_install_date_reads_unknown() -> None:
    detail = PackageDetail(make_package(installed=True))
    assert detail.facts["Installed"] == "unknown"


def test_missing_metadata_does_not_break_the_view() -> None:
    detail = PackageDetail(make_package(license="", description="", arch=""))
    assert detail.facts["License"] == "unknown"
    assert detail.facts["Architecture"] == "unknown"
    assert detail.get_first_child().get_label() == "No description available."


def test_description_is_the_first_child() -> None:
    description = "Firefox is a standalone web browser."
    detail = PackageDetail(make_package(description=description))
    assert detail.get_first_child().get_label() == description


def test_files_are_previewed_with_a_count() -> None:
    files = ("/usr/bin/a", "/usr/bin/b", "/usr/bin/c", "/usr/bin/d")
    detail = PackageDetail(make_package(files=files))
    assert detail.facts["Files"] == "/usr/bin/a, /usr/bin/b, /usr/bin/c (+1 more)"


def test_links_are_only_kept_when_present() -> None:
    detail = PackageDetail(make_package(homepage="https://example.org", source_url=""))
    assert detail.links == {"Homepage": "https://example.org"}
