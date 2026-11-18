"""Tests for the Repos tab widget."""

from __future__ import annotations

from parcel.backend.models import Repo
from parcel.ui.repos_view import ReposPage

FEDORA = Repo(repo_id="fedora", name="Fedora", system=True)
UPDATES = Repo(repo_id="updates", name="Fedora Updates", enabled=False, system=True)
RPMFUSION = Repo(repo_id="rpmfusion-free", name="RPM Fusion Free")
COPR = Repo(
    repo_id="copr:copr.fedorainfracloud.org:owner:project",
    name="Copr repo for project owned by owner",
)


def make_page() -> ReposPage:
    page = ReposPage(
        on_toggle=lambda repo, enabled: page.toggles.append((repo, enabled)),
        on_remove=lambda repo: page.removals.append(repo),
        on_add=lambda: page.adds.append(True),
    )
    page.toggles = []  # type: ignore[attr-defined]
    page.removals = []  # type: ignore[attr-defined]
    page.adds = []  # type: ignore[attr-defined]
    return page


def test_page_starts_loading() -> None:
    page = make_page()

    assert page.stack.get_visible_child_name() == "empty"
    assert page.empty_page.get_title() == "Loading repositories\u2026"


def test_loaded_repositories_get_a_row_and_a_switch() -> None:
    page = make_page()

    page.set_repos([FEDORA, UPDATES, RPMFUSION])

    assert page.stack.get_visible_child_name() == "list"
    assert page.visible_count == 3
    assert set(page.rows) == {"fedora", "updates", "rpmfusion-free"}
    assert page.switches["fedora"].get_active()
    assert not page.switches["updates"].get_active()
    assert page.rows["rpmfusion-free"].get_subtitle() == "rpmfusion-free"


def test_system_repositories_have_no_remove_button() -> None:
    page = make_page()
    page.set_repos([FEDORA, RPMFUSION])

    assert "fedora" not in page.remove_buttons
    assert "rpmfusion-free" in page.remove_buttons


def test_toggling_a_switch_forwards_the_repository_and_new_state() -> None:
    page = make_page()
    page.set_repos([UPDATES])

    page.switches["updates"].set_active(True)

    assert page.toggles == [(UPDATES, True)]


def test_remove_button_forwards_the_repository() -> None:
    page = make_page()
    page.set_repos([RPMFUSION])

    page.remove_buttons["rpmfusion-free"].emit("clicked")

    assert page.removals == [RPMFUSION]


def test_add_button_forwards_the_intent() -> None:
    page = make_page()

    page.add_button.emit("clicked")

    assert page.adds == [True]


def test_empty_repository_list_has_an_explanation() -> None:
    page = make_page()
    page.set_repos([])

    assert page.stack.get_visible_child_name() == "empty"
    assert page.empty_page.get_title() == "No repositories"
    assert "COPR" in page.empty_page.get_description()


def test_reloading_replaces_old_rows() -> None:
    page = make_page()
    page.set_repos([RPMFUSION, COPR])

    page.set_repos([FEDORA])

    assert page.visible_count == 1
    assert set(page.rows) == {"fedora"}
    assert set(page.switches) == {"fedora"}
