"""Tests for a single package row."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")


from parcel.backend.models import Package  # noqa: E402
from parcel.ui.package_detail import PackageDetail  # noqa: E402
from parcel.ui.package_item import PackageItem  # noqa: E402
from parcel.ui.package_row import PackageRow, RowAction  # noqa: E402


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "size": 2048,
        "package_id": "firefox;141.0.3-1.fc44;x86_64;updates",
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


class Harness:
    def __init__(
        self,
        action: RowAction = RowAction.INSTALL,
        package: Package | None = None,
        item: PackageItem | None = None,
    ) -> None:
        self.actions: list[Package] = []
        self.expansions: list[Package] = []
        self.detail_calls: list[Callable[[Package], None]] = []
        self.row = PackageRow(
            action=action,
            on_action=self.actions.append,
            on_expand=self._expand,
        )
        self.row.bind(item or PackageItem(package or make_package()))

    def _expand(self, package: Package, show_detail: Callable[[Package], None]) -> None:
        self.expansions.append(package)
        self.detail_calls.append(show_detail)


def test_row_shows_name_and_subtitle_from_the_item() -> None:
    harness = Harness()
    assert harness.row.get_title() == "firefox"
    assert harness.row.get_subtitle() == "141.0.3-1.fc44 \u00b7 updates \u00b7 2.0 KiB"


def test_subtitle_updates_when_the_item_size_arrives() -> None:
    item = PackageItem(make_package(size=0))
    harness = Harness(item=item)

    item.set_size(1024**2)

    assert harness.row.get_subtitle() == "141.0.3-1.fc44 \u00b7 updates \u00b7 1.0 MiB"


def test_version_text_can_show_an_update_transition() -> None:
    item = PackageItem(
        make_package(), version_text="141.0.3-1.fc44 \u2192 142.0-1.fc44"
    )
    harness = Harness(item=item)
    assert harness.row.get_subtitle().startswith("141.0.3-1.fc44 \u2192 142.0-1.fc44")


def test_install_action_icon_and_no_destructive_style() -> None:
    harness = Harness(action=RowAction.INSTALL)

    assert harness.row.action_stack.get_visible_child_name() == "icon"
    assert harness.row.action_icon.get_icon_name() == "folder-download-symbolic"
    assert harness.row.action_button.get_tooltip_text() == "Install"
    assert not harness.row.action_button.has_css_class("destructive-action")


def test_remove_action_is_a_destructive_trash_can_icon() -> None:
    harness = Harness(action=RowAction.REMOVE)

    assert harness.row.action_icon.get_icon_name() == "user-trash-symbolic"
    assert harness.row.action_button.has_css_class("destructive-action")


def test_update_action_icon() -> None:
    harness = Harness(action=RowAction.UPDATE)
    assert harness.row.action_icon.get_icon_name() == (
        "software-update-available-symbolic"
    )


def test_security_updates_are_marked() -> None:
    item = PackageItem(make_package(), security=True)
    harness = Harness(item=item)
    assert harness.row.security_label.get_visible()

    plain = Harness(item=PackageItem(make_package()))
    assert not plain.row.security_label.get_visible()


def test_action_button_forwards_the_bound_package() -> None:
    package = make_package()
    harness = Harness(package=package)

    harness.row.action_button.emit("clicked")

    assert harness.actions == [package]


def test_action_without_a_bound_item_is_harmless() -> None:
    row = PackageRow(RowAction.INSTALL, lambda package: None, lambda package, cb: None)
    row.action_button.emit("clicked")


def test_busy_row_shows_a_spinner_and_refuses_clicks() -> None:
    package = make_package()
    harness = Harness(package=package)

    harness.row.set_busy(True)

    assert harness.row.action_stack.get_visible_child_name() == "spinner"
    assert harness.row.action_spinner.get_spinning()
    assert not harness.row.action_button.get_sensitive()

    harness.row.action_button.emit("clicked")
    assert harness.actions == []

    harness.row.set_busy(False)

    assert harness.row.action_stack.get_visible_child_name() == "icon"
    assert not harness.row.action_spinner.get_spinning()
    assert harness.row.action_button.get_sensitive()


def test_item_busy_state_drives_the_bound_row() -> None:
    item = PackageItem(make_package())
    harness = Harness(item=item)

    item.busy = True

    assert harness.row.action_stack.get_visible_child_name() == "spinner"
    assert not harness.row.action_button.get_sensitive()

    item.busy = False

    assert harness.row.action_stack.get_visible_child_name() == "icon"
    assert harness.row.action_button.get_sensitive()


def test_recycled_row_does_not_follow_the_old_item() -> None:
    old_item = PackageItem(make_package())
    harness = Harness(item=old_item)

    harness.row.unbind()
    old_item.busy = True

    assert harness.row.action_stack.get_visible_child_name() == "icon"
    assert not harness.row.action_spinner.get_spinning()


def test_activating_the_row_expands_and_loads_the_detail() -> None:
    package = make_package()
    harness = Harness(package=package)

    harness.row.expand_button.emit("clicked")

    assert harness.row.revealer.get_reveal_child()
    assert harness.expansions == [package]
    loading = harness.row.detail_slot.get_first_child()
    assert loading.has_css_class("package-detail-loading")


def test_detail_replaces_the_loading_view() -> None:
    package = make_package()
    harness = Harness(package=package)
    enriched = make_package(description="Loaded description")

    harness.row.expand_button.emit("clicked")
    harness.detail_calls[0](enriched)

    assert isinstance(harness.row.detail, PackageDetail)
    assert harness.row.detail_slot.get_first_child() is harness.row.detail
    assert harness.row.detail.package == enriched


def test_expansion_is_requested_once_per_package() -> None:
    harness = Harness(package=make_package())

    harness.row.expand_button.emit("clicked")
    harness.row.expand_button.emit("clicked")
    harness.row.expand_button.emit("clicked")

    assert len(harness.expansions) == 1


def test_detail_for_a_recycled_package_is_ignored() -> None:
    harness = Harness(package=make_package())
    harness.row.expand_button.emit("clicked")

    stale = make_package(name="gimp", package_id="gimp;2.0;x86_64;fedora")
    harness.detail_calls[0](stale)

    assert harness.row.detail is None
    assert harness.row.detail_slot.get_first_child() is not None
    assert harness.row.detail_slot.get_first_child().has_css_class(
        "package-detail-loading"
    )


def test_packages_without_an_id_show_their_detail_directly() -> None:
    package = make_package(package_id="")
    harness = Harness(package=package)

    harness.row.expand_button.emit("clicked")

    assert harness.expansions == []
    assert isinstance(harness.row.detail, PackageDetail)
    assert harness.row.detail.package is package


def test_unbind_drops_state_and_stops_subtitle_updates() -> None:
    item = PackageItem(make_package())
    harness = Harness(item=item)
    harness.row.expand_button.emit("clicked")

    harness.row.unbind()
    item.set_size(1024**2)

    assert harness.row.item is None
    assert harness.row.detail is None
    assert not harness.row.revealer.get_reveal_child()
    assert harness.row.detail_slot.get_first_child() is None
    assert harness.row.get_subtitle() == "141.0.3-1.fc44 \u00b7 updates \u00b7 2.0 KiB"
