"""Updates tab: the package list plus "Update all"."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from parcel.backend.models import Package, Update  # noqa: E402
from parcel.ui.package_item import PackageItem  # noqa: E402
from parcel.ui.package_list import PackageListPage  # noqa: E402
from parcel.ui.package_row import RowAction  # noqa: E402
from parcel.ui.size_loader import SizeLoader  # noqa: E402


class UpdatesPage(PackageListPage):
    """Packages with an update, with a bulk update action."""

    def __init__(
        self,
        on_action: Callable[[Package, RowAction], None],
        on_expand: Callable[[Package, Callable[[Package], None]], None],
        on_update_all: Callable[[], None],
        size_loader: SizeLoader | None = None,
    ) -> None:
        super().__init__(
            action=RowAction.UPDATE,
            on_action=on_action,
            on_expand=on_expand,
            size_loader=size_loader,
            empty_title="Everything is up to date",
            empty_description="No updates are available for your installed packages.",
            empty_icon="software-update-available-symbolic",
        )
        self._on_update_all = on_update_all

        self.update_all_button = Gtk.Button(
            label="Update all",
            valign=Gtk.Align.CENTER,
            sensitive=False,
        )
        header = Gtk.Box(spacing=12)
        header.set_margin_top(12)
        header.set_margin_start(18)
        header.set_margin_end(18)
        header.append(
            Gtk.Label(
                label="Available updates",
                xalign=0,
                hexpand=True,
                css_classes=["title-4"],
            )
        )
        header.append(self.update_all_button)
        self.prepend(header)

        self.update_all_button.connect("clicked", self._update_all_clicked)

    def set_updates(self, updates: Sequence[Update]) -> None:
        self.set_items(
            [
                PackageItem(
                    update.package,
                    version_text=update.version_text,
                    security=update.security,
                )
                for update in updates
            ]
        )
        self.update_all_button.set_sensitive(bool(updates))

    def _update_all_clicked(self, _button: Gtk.Button) -> None:
        self._on_update_all()
