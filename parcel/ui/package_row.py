"""One package row: name, version, repo, size, and its action button."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel.backend.models import Package  # noqa: E402
from parcel.ui.package_detail import PackageDetail  # noqa: E402


class RowAction(Enum):
    """The single action a row offers, with its icon and styling."""

    INSTALL = ("Install", "folder-download-symbolic", False)
    REMOVE = ("Remove", "user-trash-symbolic", True)
    UPDATE = ("Update", "software-update-available-symbolic", False)

    def __init__(self, label: str, icon_name: str, destructive: bool) -> None:
        self.label = label
        self.icon_name = icon_name
        self.destructive = destructive


class PackageRow(Adw.ExpanderRow):
    """A package row that expands to its :class:`PackageDetail`."""

    def __init__(
        self,
        package: Package,
        action: RowAction = RowAction.INSTALL,
        on_action: Callable[[Package], None] | None = None,
        version_text: str | None = None,
    ) -> None:
        super().__init__()
        self.package = package
        self.action = action
        self._on_action = on_action
        self.set_title(package.name)
        self.set_subtitle(
            " \u00b7 ".join(
                (version_text or package.version, package.repo, package.size_text)
            )
        )

        self.action_button = Gtk.Button(
            icon_name=action.icon_name,
            tooltip_text=action.label,
            valign=Gtk.Align.CENTER,
        )
        self.action_button.add_css_class("flat")
        if action.destructive:
            self.action_button.add_css_class("destructive-action")
        self.action_button.connect("clicked", self._handle_action)
        self.add_suffix(self.action_button)

        self.detail = PackageDetail(package)
        self.add_row(
            Adw.PreferencesRow(activatable=False, selectable=False, child=self.detail)
        )

    def _handle_action(self, _button: Gtk.Button) -> None:
        if self._on_action is not None:
            self._on_action(self.package)

    def matches(self, query: str) -> bool:
        return self.package.matches(query)
