"""Main window: header bar, search, tab switcher, and the four pages."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GObject, Gtk  # noqa: E402

from parcel.backend.models import Package  # noqa: E402
from parcel.ui import placeholder  # noqa: E402
from parcel.ui.package_row import PackageRow, RowAction  # noqa: E402
from parcel.ui.repos_view import build_repos_view  # noqa: E402

PAGE_TITLES = {
    "installed": "Installed",
    "available": "Available",
    "updates": "Updates",
    "repos": "Repos",
}


class MainWindow(Adw.ApplicationWindow):
    """Parcel's only window at this stage."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(
            title="Parcel",
            default_width=1000,
            default_height=720,
            **kwargs,
        )
        self.rows: dict[str, list[PackageRow]] = {}
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

        header = Adw.HeaderBar()
        header.pack_start(self.search_toggle)
        header.set_title_widget(
            Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        )

        self.toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.add_top_bar(self.search_bar)
        toolbar.set_content(self.stack)
        self.toast_overlay.set_child(toolbar)
        self.set_content(self.toast_overlay)

        self._add_package_page(
            "installed",
            placeholder.installed(),
            RowAction.REMOVE,
            "system-software-install-symbolic",
        )
        self._add_package_page(
            "available",
            placeholder.available(),
            RowAction.INSTALL,
            "package-x-generic-symbolic",
        )
        self._add_updates_page()
        self.stack.add_titled_with_icon(
            build_repos_view(), "repos", PAGE_TITLES["repos"], "folder-symbolic"
        )

        self.search_entry.connect("search-changed", self._on_search_changed)

    def _add_package_page(
        self,
        name: str,
        packages: Sequence[Package],
        action: RowAction,
        icon_name: str,
    ) -> None:
        self._add_rows_page(
            name,
            packages,
            action,
            icon_name,
            version_text=None,
        )

    def _add_updates_page(self) -> None:
        updates = placeholder.updates()
        rows: list[PackageRow] = []
        group = Adw.PreferencesGroup()
        for update in updates:
            row = PackageRow(
                update.package,
                action=RowAction.UPDATE,
                on_action=self._make_action_handler(RowAction.UPDATE),
                version_text=update.version_text,
            )
            rows.append(row)
            group.add(row)
        page = Adw.PreferencesPage()
        page.add(group)
        self.rows["updates"] = rows
        self.stack.add_titled_with_icon(
            page,
            "updates",
            PAGE_TITLES["updates"],
            "software-update-available-symbolic",
        )

    def _add_rows_page(
        self,
        name: str,
        packages: Sequence[Package],
        action: RowAction,
        icon_name: str,
        version_text: str | None,
    ) -> None:
        rows = []
        group = Adw.PreferencesGroup()
        for package in packages:
            row = PackageRow(
                package,
                action=action,
                on_action=self._make_action_handler(action),
                version_text=version_text,
            )
            rows.append(row)
            group.add(row)
        page = Adw.PreferencesPage()
        page.add(group)
        self.rows[name] = rows
        self.stack.add_titled_with_icon(page, name, PAGE_TITLES[name], icon_name)

    def _make_action_handler(self, action: RowAction) -> Callable[[Package], None]:
        def handle(package: Package) -> None:
            self._on_row_action(package, action)

        return handle

    def apply_filter(self, query: str) -> None:
        """Show only rows matching ``query`` in every tab."""
        for rows in self.rows.values():
            for row in rows:
                row.set_visible(row.matches(query))

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self.apply_filter(self.search_entry.get_text())

    def _on_row_action(self, package: Package, action: RowAction) -> None:
        self._show_toast(
            f"{action.label} {package.name} is not available in this build."
        )

    def _show_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))
