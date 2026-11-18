"""Tests for the main window: tabs, search, loading, and package actions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from subprocess import run
from sys import executable

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel.backend.models import Package, Update  # noqa: E402
from parcel.ui.confirm_dialog import CANCEL_RESPONSE, REMOVE_RESPONSE  # noqa: E402
from parcel.ui.package_row import RowAction  # noqa: E402
from parcel.ui.tasks import SyncRunner  # noqa: E402
from parcel.ui.window import PAGE_TITLES, MainWindow  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_package(
    name: str,
    version: str = "1.0-1.fc44",
    repo: str = "updates",
    summary: str = "summary",
    description: str = "",
    installed: bool = False,
) -> Package:
    return Package(
        name=name,
        version=version,
        repo=repo,
        summary=summary,
        description=description,
        installed=installed,
        package_id=f"{name};{version};x86_64;{repo}",
    )


FIREFOX = make_package("firefox", installed=True)
FLATPAK = make_package("flatpak", installed=True)
GIMP = make_package("gimp", summary="Image editor")
HTOP = make_package("htop", summary="Process viewer")
NUATILUS_UPDATE = Update(
    package=make_package("nautilus", "48.3-1.fc44"),
    installed_version="48.2-1.fc44",
)
FIREFOX_UPDATE = Update(
    package=make_package("firefox", "142.0-1.fc44", installed=True),
    installed_version="141.0.3-1.fc44",
    security=True,
)


class FakeClient:
    def __init__(
        self,
        installed: Sequence[Package] = (FIREFOX, FLATPAK),
        available: Sequence[Package] = (GIMP, HTOP),
        updates: Sequence[Update] = (FIREFOX_UPDATE, NUATILUS_UPDATE),
        error: Exception | None = None,
    ) -> None:
        self.installed = list(installed)
        self.available = list(available)
        self.updates = list(updates)
        self.error = error
        self.catalog_calls = 0
        self.version_maps: list[Mapping[str, str] | None] = []
        self.detail_requests: list[Package] = []
        self.details: dict[str, Package] = {}
        self.installed_calls: list[Package] = []
        self.removed_calls: list[Package] = []
        self.updated_calls: list[list[Package]] = []

    def catalog(self) -> tuple[list[Package], list[Package]]:
        self.catalog_calls += 1
        if self.error is not None:
            raise self.error
        return list(self.installed), list(self.available)

    def list_updates(
        self, installed_versions: Mapping[str, str] | None = None
    ) -> list[Update]:
        self.version_maps.append(installed_versions)
        return list(self.updates)

    def get_detail(self, package: Package) -> Package:
        self.detail_requests.append(package)
        return self.details.get(package.name, package)

    def sizes(self, packages: Sequence[Package]) -> Mapping[str, int]:
        return {}

    def install(self, package: Package) -> None:
        self.installed_calls.append(package)

    def remove(self, package: Package) -> None:
        self.removed_calls.append(package)

    def update(self, packages: Sequence[Package]) -> None:
        self.updated_calls.append(list(packages))


def make_window(client: FakeClient | None = None, runner=None) -> MainWindow:
    return MainWindow(
        client=client or FakeClient(),
        runner=runner or SyncRunner(),
    )


def test_window_has_the_four_tabs() -> None:
    window = make_window()

    assert window.stack.get_pages().get_n_items() == 4
    for name, title in PAGE_TITLES.items():
        page = window.stack.get_child_by_name(name)
        assert page is not None, name
        assert window.stack.get_page(page).get_title() == title


def test_three_tabs_are_package_lists_and_repos_is_a_stub() -> None:
    window = make_window()

    assert set(window.pages) == {"installed", "available", "updates"}
    assert isinstance(window.stack.get_child_by_name("repos"), Adw.StatusPage)


def test_installed_tab_lists_real_client_data() -> None:
    window = make_window()

    assert window.installed_page.visible_count == 2
    assert window.installed_page.action is RowAction.REMOVE
    assert window.stack.get_visible_child_name() == "installed"


def test_available_tab_lists_not_installed_packages() -> None:
    window = make_window()

    assert window.available_page.visible_count == 2
    assert window.available_page.action is RowAction.INSTALL


def test_updates_tab_has_a_badge_with_the_count() -> None:
    window = make_window()

    page = window.stack.get_page(window.updates_page)
    assert page.get_badge_number() == 2
    assert window.updates_page.visible_count == 2
    assert window.updates_page.action is RowAction.UPDATE


def test_installed_versions_are_handed_to_the_updates_query() -> None:
    client = FakeClient()
    make_window(client)

    assert client.version_maps == [{"firefox": "1.0-1.fc44", "flatpak": "1.0-1.fc44"}]


def test_window_has_the_search_bar_and_show_it_on_launch() -> None:
    window = make_window()

    assert isinstance(window.search_entry, Gtk.SearchEntry)
    assert window.search_entry.get_placeholder_text() == "Search packages"
    assert window.search_toggle.get_icon_name() == "system-search-symbolic"
    assert window.search_bar.get_search_mode()


def test_search_toggle_controls_the_search_bar() -> None:
    window = make_window()

    window.search_toggle.set_active(False)
    assert not window.search_bar.get_search_mode()

    window.search_toggle.set_active(True)
    assert window.search_bar.get_search_mode()


def test_search_filters_only_the_current_tab() -> None:
    window = make_window()

    window.search_entry.set_text("gimp")
    window.search_entry.emit("search-changed")

    assert window.installed_page.visible_count == 0
    assert window.available_page.visible_count == 2
    assert window.updates_page.visible_count == 2


def test_search_applies_to_the_tab_that_gets_selected() -> None:
    window = make_window()
    window.search_entry.set_text("firefox")
    window.search_entry.emit("search-changed")

    window.stack.set_visible_child_name("updates")

    assert window.updates_page.visible_count == 1
    assert window.updates_page.filter_model.get_item(0).package.name == "firefox"


def test_clearing_search_restores_the_current_tab() -> None:
    window = make_window()
    window.search_entry.set_text("gimp")
    window.search_entry.emit("search-changed")

    window.search_entry.set_text("")
    window.search_entry.emit("search-changed")

    assert window.installed_page.visible_count == 2


def test_install_action_updates_through_the_client(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)

    window._handle_action(GIMP, RowAction.INSTALL)

    assert client.installed_calls == [GIMP]
    assert client.catalog_calls == 2


def test_update_action_sends_the_package(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)

    window._handle_action(FIREFOX_UPDATE.package, RowAction.UPDATE)

    assert client.updated_calls == [[FIREFOX_UPDATE.package]]


def test_update_all_sends_every_offered_update(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)

    window._update_all()

    assert client.updated_calls == [[FIREFOX_UPDATE.package, NUATILUS_UPDATE.package]]


def test_remove_asks_for_confirmation_before_uninstalling(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)

    window._handle_action(FIREFOX, RowAction.REMOVE)

    assert client.removed_calls == []
    dialog = window.remove_dialog
    assert dialog is not None
    assert dialog.get_heading() == "Remove firefox?"


def test_confirming_removal_runs_the_transaction(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)
    window._handle_action(FIREFOX, RowAction.REMOVE)

    assert window.remove_dialog is not None
    window.remove_dialog.emit("response", REMOVE_RESPONSE)

    assert client.removed_calls == [FIREFOX]
    assert client.catalog_calls == 2


def test_cancelling_removal_keeps_the_package(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    monkeypatch.setattr(window, "_show_toast", lambda message: None)
    window._handle_action(FIREFOX, RowAction.REMOVE)

    assert window.remove_dialog is not None
    window.remove_dialog.emit("response", CANCEL_RESPONSE)

    assert client.removed_calls == []
    assert client.catalog_calls == 1


def test_failed_transaction_reports_a_toast(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    messages: list[str] = []
    monkeypatch.setattr(window, "_show_toast", messages.append)

    def fail(_package: Package) -> None:
        raise RuntimeError("polkit said no")

    monkeypatch.setattr(client, "install", fail)
    window._handle_action(GIMP, RowAction.INSTALL)

    assert messages == [
        "Installing gimp\u2026",
        "Could not install gimp: polkit said no",
    ]


def test_expanding_a_row_loads_its_detail() -> None:
    client = FakeClient()
    client.details["firefox"] = make_package("firefox", description="A browser")
    window = make_window(client)
    shown: list[Package] = []

    window._expand(FIREFOX, shown.append)

    assert client.detail_requests == [FIREFOX]
    assert [package.description for package in shown] == ["A browser"]


def test_detail_failure_reports_a_toast(monkeypatch) -> None:
    client = FakeClient()
    window = make_window(client)
    messages: list[str] = []
    monkeypatch.setattr(window, "_show_toast", messages.append)

    def fail(_package: Package) -> Package:
        raise RuntimeError("no details")

    monkeypatch.setattr(client, "get_detail", fail)
    shown: list[Package] = []
    window._expand(FIREFOX, shown.append)

    assert messages == ["Could not load details for firefox: no details"]
    assert shown == [FIREFOX]


def test_load_failure_is_reported(monkeypatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        MainWindow, "_show_toast", lambda _self, text: messages.append(text)
    )

    make_window(FakeClient(error=RuntimeError("PackageKit is down")))

    assert messages == ["Could not load packages: PackageKit is down"]


def test_window_hosts_content_in_a_toast_overlay() -> None:
    window = make_window()

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
