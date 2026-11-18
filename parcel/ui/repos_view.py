"""Repos tab: placeholder until repo management lands in issue #3."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402


def build_repos_view() -> Adw.StatusPage:
    """Honest placeholder for the Repos tab.

    A factory, not a subclass: libadwaita marks StatusPage final.
    """
    return Adw.StatusPage(
        icon_name="package-x-generic-symbolic",
        title="Repositories",
        description=(
            "Add, remove, and toggle repositories. "
            "Repository management is built in issue #3."
        ),
    )
