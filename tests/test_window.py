"""Tests for the main window: tabs, search, and row actions."""

from __future__ import annotations

from pathlib import Path
from subprocess import run
from sys import executable

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel.ui import placeholder  # noqa: E402
from parcel.ui.package_row import PackageRow  # noqa: E402
from parcel.ui.window import PAGE_TITLES, MainWindow  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_window_has_the_four_tabs() -> None:
    window = MainWindow()
    assert window.stack.get_pages().get_n_items() == 4
    assert set(window.rows) == {"installed", "available", "updates"}

    for name, title in PAGE_TITLES.items():
        page = window.stack.get_child_by_name(name)
        assert page is not None, name
        assert window.stack.get_page(page).get_title() == title


def test_tabs_hold_placeholder_rows() -> None:
    window = MainWindow()
    assert len(window.rows["installed"]) == len(placeholder.installed())
    assert len(window.rows["available"]) == len(placeholder.available())
    assert len(window.rows["updates"]) == len(placeholder.updates())
    assert all(
        isinstance(row, PackageRow) for rows in window.rows.values() for row in rows
    )


def test_repos_tab_uses_the_stub_view() -> None:
    window = MainWindow()
    assert isinstance(window.stack.get_child_by_name("repos"), Adw.StatusPage)


def test_window_has_a_search_entry_and_toggle() -> None:
    window = MainWindow()
    assert isinstance(window.search_entry, Gtk.SearchEntry)
    assert window.search_entry.get_placeholder_text() == "Search packages"
    assert window.search_toggle.get_icon_name() == "system-search-symbolic"


def test_search_bar_is_visible_on_launch() -> None:
    window = MainWindow()
    assert window.search_bar.get_search_mode()


def test_search_toggle_controls_the_search_bar() -> None:
    window = MainWindow()

    window.search_toggle.set_active(False)
    assert not window.search_bar.get_search_mode()

    window.search_toggle.set_active(True)
    assert window.search_bar.get_search_mode()


def test_search_filters_rows_across_tabs() -> None:
    window = MainWindow()
    gimp_row = next(
        row for row in window.rows["available"] if row.package.name == "gimp"
    )

    window.search_entry.set_text("gimp")
    window.search_entry.emit("search-changed")

    assert gimp_row.get_visible()
    assert not any(row.get_visible() for row in window.rows["installed"])
    assert not any(
        row.get_visible()
        for row in window.rows["updates"]
        if row.package.name != "gimp"
    )


def test_clearing_search_restores_every_row() -> None:
    window = MainWindow()
    window.apply_filter("gimp")
    window.search_entry.set_text("")
    window.search_entry.emit("search-changed")

    assert all(row.get_visible() for rows in window.rows.values() for row in rows)


def test_action_button_reports_through_a_toast(monkeypatch) -> None:
    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "_show_toast", messages.append)

    row = window.rows["installed"][0]
    row.action_button.emit("clicked")

    assert messages == [f"Remove {row.package.name} is not available in this build."]


def test_window_hosts_content_in_a_toast_overlay() -> None:
    window = MainWindow()
    assert isinstance(window.toast_overlay, Adw.ToastOverlay)
    assert isinstance(window.toast_overlay.get_child(), Adw.ToolbarView)


def test_views_do_not_import_the_packagekit_client() -> None:
    code = """
import sys
import parcel.ui.window

banned = {"parcel.backend.client", "gi.repository.PackageKitGlib"}
assert not banned & set(sys.modules), sorted(banned & set(sys.modules))
"""
    result = run(
        [executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
