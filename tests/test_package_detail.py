"""Tests for the expanded package detail view."""

from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from parcel.backend.models import InstallReason, Package  # noqa: E402
from parcel.ui.package_detail import PackageDetail  # noqa: E402


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "arch": "x86_64",
        "size": 2048,
        "description": "Firefox is a standalone web browser.",
        "license": "MPL-2.0",
        "homepage": "https://www.mozilla.org/firefox/",
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
    assert detail.facts["Reason"] == "unknown"


def test_nothing_required_by_reads_as_sentence() -> None:
    detail = PackageDetail(make_package(installed=True))
    assert detail.facts["Required by"] == "Nothing depends on it"


def test_long_required_by_lists_are_previewed() -> None:
    required_by = tuple(f"package{index}" for index in range(9))
    detail = PackageDetail(make_package(installed=True, required_by=required_by))

    assert detail.facts["Required by"] == (
        "package0, package1, package2, package3, package4, package5 (+3 more)"
    )


def test_missing_metadata_does_not_break_the_view() -> None:
    detail = PackageDetail(make_package(license="", description="", arch=""))

    assert detail.facts["License"] == "unknown"
    assert detail.facts["Architecture"] == "unknown"
    assert detail.description_label.get_label() == "No description available."


def test_summary_is_used_when_there_is_no_description() -> None:
    detail = PackageDetail(make_package(description="", summary="Web browser"))
    assert detail.description_label.get_label() == "Web browser"


def test_description_is_the_first_child() -> None:
    description = "Firefox is a standalone web browser."
    detail = PackageDetail(make_package(description=description))
    assert detail.get_first_child() is detail.description_label
    assert detail.description_label.get_label() == description


def test_files_are_previewed_with_a_count() -> None:
    files = ("/usr/bin/a", "/usr/bin/b", "/usr/bin/c", "/usr/bin/d")
    detail = PackageDetail(make_package(files=files))
    assert detail.facts["Files"] == "/usr/bin/a, /usr/bin/b, /usr/bin/c (+1 more)"


def test_changelog_is_shown_when_present() -> None:
    detail = PackageDetail(make_package(changelog="Maintainer - 1.0\n- fixed it"))
    assert detail.changelog_label is not None
    assert detail.changelog_label.get_label() == "Maintainer - 1.0\n- fixed it"


def test_changelog_section_is_absent_without_entries() -> None:
    assert PackageDetail(make_package()).changelog_label is None


def test_links_include_fedora_source_and_packages_pages() -> None:
    detail = PackageDetail(make_package())

    assert detail.links == {
        "Homepage": "https://www.mozilla.org/firefox/",
        "Source": "https://src.fedoraproject.org/rpms/firefox",
        "Fedora Packages": "https://packages.fedoraproject.org/pkgs/firefox/",
    }
    assert [button.get_label() for button in detail.link_buttons] == list(detail.links)


def test_links_are_omitted_when_nothing_can_be_derived() -> None:
    detail = PackageDetail(make_package(repo="google-chrome-canary", homepage=""))
    assert detail.links == {}
    assert detail.link_buttons == []


def test_loading_view_shows_a_spinner_and_message() -> None:
    loading = PackageDetail.loading()

    assert isinstance(loading, Gtk.Box)
    assert loading.has_css_class("package-detail-loading")
    children = []
    child = loading.get_first_child()
    while child is not None:
        children.append(child)
        child = child.get_next_sibling()
    assert any(isinstance(widget, Gtk.Spinner) for widget in children)
    assert any(
        isinstance(widget, Gtk.Label) and widget.get_label() == "Loading details\u2026"
        for widget in children
    )
