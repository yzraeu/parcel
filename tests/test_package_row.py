"""Tests for a single package row."""

from parcel.backend.models import Package
from parcel.ui.package_detail import PackageDetail
from parcel.ui.package_row import PackageRow, RowAction


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "size": 2048,
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


def test_row_shows_name_version_repo_and_size() -> None:
    row = PackageRow(make_package())
    assert row.get_title() == "firefox"
    assert row.get_subtitle() == "141.0.3-1.fc44 \u00b7 updates \u00b7 2.0 KiB"


def test_version_text_can_show_an_update_transition() -> None:
    row = PackageRow(make_package(), version_text="141.0.3-1.fc44 \u2192 142.0-1.fc44")
    assert row.get_subtitle().startswith("141.0.3-1.fc44 \u2192 142.0-1.fc44")


def test_install_action_icon_and_no_destructive_style() -> None:
    row = PackageRow(make_package(), action=RowAction.INSTALL)
    assert row.action_button.get_icon_name() == "folder-download-symbolic"
    assert row.action_button.get_tooltip_text() == "Install"
    assert not row.action_button.has_css_class("destructive-action")


def test_remove_action_is_destructive() -> None:
    row = PackageRow(make_package(installed=True), action=RowAction.REMOVE)
    assert row.action_button.get_icon_name() == "user-trash-symbolic"
    assert row.action_button.has_css_class("destructive-action")


def test_update_action_icon() -> None:
    row = PackageRow(make_package(), action=RowAction.UPDATE)
    assert row.action_button.get_icon_name() == "software-update-available-symbolic"


def test_action_button_forwards_to_callback() -> None:
    seen: list[Package] = []
    package = make_package()
    row = PackageRow(package, on_action=seen.append)

    row.action_button.emit("clicked")

    assert seen == [package]


def test_action_without_callback_is_harmless() -> None:
    PackageRow(make_package()).action_button.emit("clicked")


def test_row_embeds_the_detail_view_for_its_package() -> None:
    package = make_package(installed=True)
    row = PackageRow(package)

    assert isinstance(row.detail, PackageDetail)
    assert row.detail.package is package


def test_matches_delegates_to_the_package() -> None:
    row = PackageRow(make_package(name="firefox", summary="Web browser"))
    assert row.matches("fire")
    assert not row.matches("gimp")
