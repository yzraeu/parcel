"""Confirmation dialog before removing a package."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from parcel.backend.models import Package  # noqa: E402

REMOVE_RESPONSE = "remove"
CANCEL_RESPONSE = "cancel"


def build_remove_dialog(
    package: Package, on_remove: Callable[[], None]
) -> Adw.AlertDialog:
    """Ask before uninstalling; ``on_remove`` runs only on the destructive choice."""
    dialog = Adw.AlertDialog(
        heading=f"Remove {package.name}?",
        body=(
            f"This will uninstall {package.name} {package.version} from your "
            "system. This cannot be undone."
        ),
    )
    dialog.add_response(CANCEL_RESPONSE, "Cancel")
    dialog.add_response(REMOVE_RESPONSE, "Remove")
    dialog.set_response_appearance(REMOVE_RESPONSE, Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response(CANCEL_RESPONSE)
    dialog.set_close_response(CANCEL_RESPONSE)

    def respond(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == REMOVE_RESPONSE:
            on_remove()

    dialog.connect("response", respond)
    return dialog
