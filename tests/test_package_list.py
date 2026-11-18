"""Tests for the virtualized package list page."""

from __future__ import annotations

from collections.abc import Callable

from parcel.backend.models import Package
from parcel.ui.package_list import PackageListPage
from parcel.ui.package_row import RowAction


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "summary": "Web browser",
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


def make_page(**kwargs: object) -> PackageListPage:
    actions: list[tuple[Package, RowAction]] = []
    expansions: list[Package] = []

    def expand(package: Package, _show: Callable[[Package], None]) -> None:
        expansions.append(package)

    page = PackageListPage(
        RowAction.INSTALL,
        lambda package, action: actions.append((package, action)),
        expand,
        **kwargs,  # type: ignore[arg-type]
    )
    page.actions = actions  # type: ignore[attr-defined]
    page.expansions = expansions  # type: ignore[attr-defined]
    return page


def test_page_starts_in_its_loading_state() -> None:
    page = make_page()
    assert page.stack.get_visible_child_name() == "empty"
    assert page.empty_page.get_title() == "Loading packages\u2026"


def test_finishing_the_load_shows_the_configured_empty_state() -> None:
    page = make_page(empty_title="No packages", empty_description="Nothing here.")

    page.set_loading(False)

    assert page.stack.get_visible_child_name() == "empty"
    assert page.empty_page.get_title() == "No packages"
    assert page.empty_page.get_description() == "Nothing here."


def test_packages_are_shown_once_loaded() -> None:
    page = make_page()

    page.set_packages([make_package(), make_package(name="gimp")])
    page.set_loading(False)

    assert page.stack.get_visible_child_name() == "list"
    assert page.visible_count == 2
    assert page.action is RowAction.INSTALL


def test_filter_narrows_the_list() -> None:
    page = make_page()
    page.set_packages(
        [
            make_package(name="firefox", summary="Web browser"),
            make_package(name="gimp", summary="Image editor"),
        ]
    )
    page.set_loading(False)

    page.set_filter("gimp")

    assert page.visible_count == 1
    assert page.filter_model.get_item(0).package.name == "gimp"


def test_filter_without_matches_shows_a_search_empty_state() -> None:
    page = make_page(empty_title="No packages")
    page.set_packages([make_package()])
    page.set_loading(False)

    page.set_filter("nothing-like-this")

    assert page.stack.get_visible_child_name() == "empty"
    assert (
        page.empty_page.get_title() == "No packages match \u201cnothing-like-this\u201d"
    )
    assert page.empty_page.get_icon_name() == "system-search-symbolic"


def test_clearing_the_filter_restores_every_row() -> None:
    page = make_page()
    page.set_packages([make_package(), make_package(name="gimp")])
    page.set_loading(False)
    page.set_filter("gimp")

    page.set_filter("")

    assert page.visible_count == 2
    assert page.stack.get_visible_child_name() == "list"


def test_reloading_keeps_existing_rows_on_screen() -> None:
    page = make_page()
    page.set_packages([make_package()])
    page.set_loading(False)

    page.set_loading(True)

    assert page.stack.get_visible_child_name() == "list"


def test_filter_matches_summaries_too() -> None:
    page = make_page()
    page.set_packages([make_package(name="firefox", summary="Web browser")])
    page.set_loading(False)

    page.set_filter("browser")

    assert page.visible_count == 1
