"""Tests for the About dialog: identity, links, license, and credits."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel import APP_NAME, __version__  # noqa: E402
from parcel.ui.about import (  # noqa: E402
    APP_AUTHOR,
    APP_ICON,
    APP_ISSUES,
    APP_WEBSITE,
    DEPENDENCIES,
    build_about_dialog,
    show_about,
)


def test_dialog_identifies_parcel_and_its_version() -> None:
    dialog = build_about_dialog()

    assert isinstance(dialog, Adw.AboutDialog)
    assert dialog.get_application_name() == APP_NAME == "Parcel"
    assert dialog.get_application_icon() == APP_ICON
    assert dialog.get_version() == __version__


def test_dialog_credits_the_developer() -> None:
    dialog = build_about_dialog()

    assert dialog.get_developer_name() == APP_AUTHOR == "yzraeu"
    assert dialog.get_developers() == [APP_AUTHOR]


def test_dialog_links_the_project_and_its_issues() -> None:
    dialog = build_about_dialog()

    assert dialog.get_website() == APP_WEBSITE
    assert dialog.get_issue_url() == APP_ISSUES
    assert APP_ISSUES == "https://github.com/yzraeu/parcel/issues"


def test_dialog_carries_the_copyright_and_gpl3_license() -> None:
    dialog = build_about_dialog()

    assert dialog.get_copyright() == "© 2026 yzraeu"
    assert dialog.get_license_type() == Gtk.License.GPL_3_0


def test_dependencies_are_credited_with_their_licenses() -> None:
    required = ("PackageKit", "GTK 4", "libadwaita", "PyGObject")

    for name in required:
        entries = [entry for entry in DEPENDENCIES if entry.startswith(f"{name} (")]
        assert len(entries) == 1, name
        assert entries[0].endswith(")"), entries[0]
        assert "LGPL" in entries[0] or "GPL" in entries[0], entries[0]


def test_show_about_presents_the_dialog_over_the_parent() -> None:
    parent = Gtk.Window()

    dialog = show_about(parent)

    assert isinstance(dialog, Adw.AboutDialog)
    assert dialog.get_application_name() == APP_NAME
    assert dialog.get_visible()
