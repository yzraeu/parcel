"""Tests for the Repos tab placeholder."""

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from parcel.ui.repos_view import build_repos_view  # noqa: E402


def test_repos_view_is_a_status_page() -> None:
    view = build_repos_view()
    assert isinstance(view, Adw.StatusPage)


def test_repos_view_states_its_status() -> None:
    view = build_repos_view()
    assert view.get_title() == "Repositories"
    assert view.get_icon_name() == "package-x-generic-symbolic"
    assert "issue #3" in view.get_description()
