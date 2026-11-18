"""Main window: header bar, search, the four tabs, and package actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GObject, Gtk  # noqa: E402

from parcel.backend.models import Package, Update  # noqa: E402
from parcel.ui import tasks  # noqa: E402
from parcel.ui.confirm_dialog import build_remove_dialog  # noqa: E402
from parcel.ui.package_list import PackageListPage  # noqa: E402
from parcel.ui.package_row import RowAction  # noqa: E402
from parcel.ui.repos_view import build_repos_view  # noqa: E402
from parcel.ui.size_loader import SizeLoader  # noqa: E402
from parcel.ui.updates_page import UpdatesPage  # noqa: E402

PAGE_TITLES = {
    "installed": "Installed",
    "available": "Available",
    "updates": "Updates",
    "repos": "Repos",
}

# Toast wording per action: in progress, finished, and the verb on failure.
_ACTION_WORDS = {
    RowAction.INSTALL: ("Installing", "Installed", "install"),
    RowAction.REMOVE: ("Removing", "Removed", "remove"),
    RowAction.UPDATE: ("Updating", "Updated", "update"),
}


class PackageBackend(Protocol):
    """The slice of the backend client the window needs.

    Keeping it explicit documents the seam: the UI never imports PackageKit.
    """

    def catalog(self) -> tuple[list[Package], list[Package]]: ...

    def list_updates(
        self, installed_versions: Mapping[str, str] | None = None
    ) -> list[Update]: ...

    def get_detail(self, package: Package) -> Package: ...

    def sizes(self, packages: Sequence[Package]) -> Mapping[str, int]: ...

    def install(self, package: Package) -> None: ...

    def remove(self, package: Package) -> None: ...

    def update(self, packages: Sequence[Package]) -> None: ...


class MainWindow(Adw.ApplicationWindow):
    """Parcel's only window at this stage."""

    def __init__(
        self,
        client: PackageBackend,
        runner: tasks.Runner | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            title="Parcel",
            default_width=1000,
            default_height=720,
            **kwargs,
        )
        self.client = client
        self._runner = runner if runner is not None else tasks.AsyncRunner()
        self._size_loader = SizeLoader(client.sizes, self._runner)
        self._updates: list[Update] = []
        self.remove_dialog: Adw.AlertDialog | None = None

        self.stack = Adw.ViewStack()
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search packages")
        self.search_bar = Gtk.SearchBar()
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_toggle = Gtk.ToggleButton(
            icon_name="system-search-symbolic", tooltip_text="Search"
        )
        self.search_toggle.bind_property(
            "active",
            self.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self.search_toggle.set_active(True)

        self.header = Adw.HeaderBar()
        self.header.pack_start(self.search_toggle)
        self.view_switcher = Adw.ViewSwitcher(
            stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE
        )
        self.header.set_title_widget(self.view_switcher)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(self.header)
        toolbar.add_top_bar(self.search_bar)
        toolbar.set_content(self.stack)
        self.toast_overlay.set_child(toolbar)
        self.set_content(self.toast_overlay)

        self.installed_page = PackageListPage(
            RowAction.REMOVE,
            self._handle_action,
            self._expand,
            self._size_loader,
            empty_title="No packages installed",
            empty_description="PackageKit reports an empty package set.",
        )
        self.available_page = PackageListPage(
            RowAction.INSTALL,
            self._handle_action,
            self._expand,
            self._size_loader,
            empty_title="No packages available",
            empty_description="No repositories offer packages right now.",
        )
        self.updates_page = UpdatesPage(
            self._handle_action,
            self._expand,
            self._update_all,
            self._size_loader,
        )
        self.pages: dict[str, PackageListPage] = {
            "installed": self.installed_page,
            "available": self.available_page,
            "updates": self.updates_page,
        }
        icons = {
            "installed": "system-software-install-symbolic",
            "available": "package-x-generic-symbolic",
            "updates": "software-update-available-symbolic",
        }
        for name, page in self.pages.items():
            self.stack.add_titled_with_icon(page, name, PAGE_TITLES[name], icons[name])
        self.stack.add_titled_with_icon(
            build_repos_view(), "repos", PAGE_TITLES["repos"], "folder-symbolic"
        )

        self.search_entry.connect("search-changed", self._on_search_changed)
        self.stack.connect("notify::visible-child-name", self._on_page_changed)

        self._load()

    # -- loading -----------------------------------------------------------

    def _load(self) -> None:
        for page in self.pages.values():
            page.set_loading(True)
        self._runner.run(self._fetch, self._loaded, self._load_failed)

    def _fetch(self) -> tuple[list[Package], list[Package], list[Update]]:
        installed, available = self.client.catalog()
        versions = {package.name: package.version for package in installed}
        updates = self.client.list_updates(versions)
        return installed, available, updates

    def _loaded(self, data: tuple[list[Package], list[Package], list[Update]]) -> None:
        installed, available, updates = data
        self._updates = list(updates)
        self.installed_page.set_packages(installed)
        self.available_page.set_packages(available)
        self.updates_page.set_updates(updates)
        for page in self.pages.values():
            page.set_loading(False)
        self.stack.get_page(self.updates_page).set_badge_number(len(updates))
        self._apply_search_to_current()

    def _load_failed(self, error: Exception) -> None:
        for page in self.pages.values():
            page.set_loading(False)
        self._show_toast(f"Could not load packages: {error}")

    # -- search ------------------------------------------------------------

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self._apply_search_to_current()

    def _on_page_changed(self, *_args: object) -> None:
        self._apply_search_to_current()

    def _current_page(self) -> PackageListPage | None:
        return self.pages.get(self.stack.get_visible_child_name() or "")

    def _apply_search_to_current(self) -> None:
        page = self._current_page()
        if page is not None:
            page.set_filter(self.search_entry.get_text())

    # -- actions -----------------------------------------------------------

    def _handle_action(self, package: Package, action: RowAction) -> None:
        words = _ACTION_WORDS[action]
        if action is RowAction.REMOVE:
            self._confirm_remove(package)
        elif action is RowAction.INSTALL:
            self._run(package, words, lambda: self.client.install(package))
        elif action is RowAction.UPDATE:
            self._run(
                package,
                words,
                lambda: self.client.update([package]),
            )

    def _confirm_remove(self, package: Package) -> None:
        dialog = build_remove_dialog(
            package,
            lambda: self._run(
                package,
                _ACTION_WORDS[RowAction.REMOVE],
                lambda: self.client.remove(package),
            ),
        )
        self.remove_dialog = dialog
        dialog.present(self)

    def _update_all(self) -> None:
        packages = [update.package for update in self._updates]
        if not packages:
            return
        self._run(
            None,
            _ACTION_WORDS[RowAction.UPDATE],
            lambda: self.client.update(packages),
            target="all packages",
        )

    def _expand(
        self,
        package: Package,
        show_detail: Callable[[Package], None],
    ) -> None:
        def failed(error: Exception) -> None:
            self._show_toast(f"Could not load details for {package.name}: {error}")
            # Show what the list already knows instead of leaving a spinner up.
            show_detail(package)

        self._runner.run(lambda: self.client.get_detail(package), show_detail, failed)

    def _run(
        self,
        package: Package | None,
        words: tuple[str, str, str],
        operation: Callable[[], None],
        target: str | None = None,
    ) -> None:
        busy, done, verb = words
        name = target or (package.name if package is not None else "packages")
        self._show_toast(f"{busy} {name}\u2026")
        self._runner.run(
            operation,
            lambda _result: self._transaction_done(done, name),
            lambda error: self._show_toast(f"Could not {verb} {name}: {error}"),
        )

    def _transaction_done(self, done: str, target: str) -> None:
        self._show_toast(f"{done} {target}")
        self._load()

    def _show_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))
