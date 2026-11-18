"""Tests for the Updates tab."""

from __future__ import annotations

from collections.abc import Callable

from parcel.backend.models import Package, Update
from parcel.ui.package_row import RowAction
from parcel.ui.updates_page import UpdatesPage


def make_update(
    name: str,
    installed: str = "1.0-1.fc44",
    new: str = "2.0-1.fc44",
    security: bool = False,
) -> Update:
    return Update(
        package=Package(
            name=name,
            version=new,
            repo="updates",
            package_id=f"{name};{new};x86_64;updates",
        ),
        installed_version=installed,
        security=security,
    )


def make_page() -> tuple[UpdatesPage, list[tuple[Package, RowAction]], list[bool]]:
    actions: list[tuple[Package, RowAction]] = []
    update_all: list[bool] = []

    def expand(_package: Package, _show: Callable[[Package], None]) -> None:
        return None

    page = UpdatesPage(
        on_action=lambda package, action: actions.append((package, action)),
        on_expand=expand,
        on_update_all=lambda: update_all.append(True),
    )
    return page, actions, update_all


def test_updates_page_uses_the_update_action() -> None:
    page, _actions, _update_all = make_page()
    assert page.action is RowAction.UPDATE


def test_update_all_is_disabled_until_updates_exist() -> None:
    page, _actions, _update_all = make_page()
    assert not page.update_all_button.get_sensitive()

    page.set_updates([make_update("firefox")])

    assert page.update_all_button.get_sensitive()


def test_updates_show_old_to_new_versions_and_security_marks() -> None:
    page, _actions, _update_all = make_page()

    page.set_updates([make_update("firefox", security=True)])
    page.set_loading(False)

    item = page.store.get_item(0)
    assert item.subtitle.startswith("1.0-1.fc44 \u2192 2.0-1.fc44")
    assert item.security


def test_an_empty_update_list_shows_the_up_to_date_state() -> None:
    page, _actions, _update_all = make_page()

    page.set_updates([])
    page.set_loading(False)

    assert page.stack.get_visible_child_name() == "empty"
    assert page.empty_page.get_title() == "Everything is up to date"
    assert not page.update_all_button.get_sensitive()


def test_update_all_button_calls_the_handler() -> None:
    page, _actions, update_all = make_page()

    page.update_all_button.emit("clicked")

    assert update_all == [True]
