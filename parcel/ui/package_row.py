"""One package row: name, subtitles, action button, and an expandable detail.

Rows are recycled by :class:`Gtk.ListView`, so everything that depends on the
current item is reset in :meth:`PackageRow.bind` and torn down in
:meth:`PackageRow.unbind`. Detail widgets are built on first expansion, not
for every row in a list of tens of thousands.

The header is plain GTK rather than :class:`Adw.ActionRow`: libadwaita only
allows action rows inside a :class:`Gtk.ListBox`, and a list box cannot
virtualize the tens of thousands of packages the Available tab holds.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk, Pango  # noqa: E402

from parcel.backend.models import Package  # noqa: E402
from parcel.ui.package_detail import PackageDetail  # noqa: E402
from parcel.ui.package_item import PackageItem  # noqa: E402


class RowAction(Enum):
    """The single action a row offers, with its icon and styling."""

    INSTALL = ("Install", "folder-download-symbolic", False)
    REMOVE = ("Remove", "user-trash-symbolic", True)
    UPDATE = ("Update", "software-update-available-symbolic", False)

    def __init__(self, label: str, icon_name: str, destructive: bool) -> None:
        self.label = label
        self.icon_name = icon_name
        self.destructive = destructive


class PackageRow(Gtk.Box):
    """A package row that expands to its :class:`PackageDetail`."""

    def __init__(
        self,
        action: RowAction,
        on_action: Callable[[Package], None],
        on_expand: Callable[[Package, Callable[[Package], None]], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.action = action
        self._on_action = on_action
        self._on_expand = on_expand
        self.item: PackageItem | None = None
        self.detail: PackageDetail | None = None
        self._subtitle_binding: GObject.Binding | None = None
        self._expanded_id: str | None = None

        self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for edge in ("top", "bottom", "start", "end"):
            getattr(self.header, f"set_margin_{edge}")(12)

        self.title_label = Gtk.Label(
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
            ellipsize=Pango.EllipsizeMode.END,
        )
        self.subtitle_label = Gtk.Label(
            xalign=0,
            css_classes=["dim-label", "caption"],
            ellipsize=Pango.EllipsizeMode.END,
        )
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        labels.append(self.title_label)
        labels.append(self.subtitle_label)

        self.chevron = Gtk.Image(icon_name="pan-down-symbolic")
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.append(labels)
        content.append(self.chevron)

        self.expand_button = Gtk.Button(
            child=content,
            hexpand=True,
            halign=Gtk.Align.FILL,
            css_classes=["flat"],
            tooltip_text="Show details",
        )
        self.expand_button.connect("clicked", self._toggle)

        self.security_label = Gtk.Label(
            label="Security",
            valign=Gtk.Align.CENTER,
            visible=False,
            css_classes=["caption", "warning"],
            tooltip_text="Security update",
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

        self.header.append(self.expand_button)
        self.header.append(self.security_label)
        self.header.append(self.action_button)
        self.append(self.header)

        self.detail_slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.revealer = Gtk.Revealer(
            child=self.detail_slot,
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
        )
        self.append(self.revealer)
        self.append(Gtk.Separator())

    def bind(self, item: PackageItem) -> None:
        """Point the row at ``item``; called by the list factory."""
        self.item = item
        self.title_label.set_label(item.package.name)
        self._subtitle_binding = item.bind_property(
            "subtitle",
            self.subtitle_label,
            "label",
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.security_label.set_visible(item.security)
        self.revealer.set_reveal_child(False)
        self.chevron.set_from_icon_name("pan-down-symbolic")
        self._set_detail_widget(None)
        self.detail = None
        self._expanded_id = None

    def unbind(self) -> None:
        """Drop bindings before the list recycles the row."""
        if self._subtitle_binding is not None:
            self._subtitle_binding.unbind()
            self._subtitle_binding = None
        self.item = None
        self.detail = None
        self._expanded_id = None
        self.revealer.set_reveal_child(False)
        self.chevron.set_from_icon_name("pan-down-symbolic")
        self._set_detail_widget(None)

    def get_title(self) -> str:
        return self.title_label.get_label()

    def get_subtitle(self) -> str:
        return self.subtitle_label.get_label()

    def _toggle(self, _button: Gtk.Button) -> None:
        revealed = not self.revealer.get_reveal_child()
        self.revealer.set_reveal_child(revealed)
        self.chevron.set_from_icon_name(
            "pan-up-symbolic" if revealed else "pan-down-symbolic"
        )
        if revealed:
            self._ensure_detail()

    def _ensure_detail(self) -> None:
        if self.item is None or self._expanded_id == self.item.package.package_id:
            return
        if not self.item.package.package_id:
            self.detail = PackageDetail(self.item.package)
            self._set_detail_widget(self.detail)
            return
        self._expanded_id = self.item.package.package_id
        self._set_detail_widget(PackageDetail.loading())
        self._on_expand(self.item.package, self._show_detail)

    def _show_detail(self, package: Package) -> None:
        if self.item is None or self.item.package.package_id != package.package_id:
            return
        self.detail = PackageDetail(package)
        self._set_detail_widget(self.detail)

    def _set_detail_widget(self, widget: Gtk.Widget | None) -> None:
        current = self.detail_slot.get_first_child()
        if current is not None:
            self.detail_slot.remove(current)
        if widget is not None:
            self.detail_slot.append(widget)

    def _handle_action(self, _button: Gtk.Button) -> None:
        if self.item is not None:
            self._on_action(self.item.package)
