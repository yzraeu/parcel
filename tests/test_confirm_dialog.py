"""Tests for the remove confirmation dialog."""

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from parcel.backend.models import Package  # noqa: E402
from parcel.ui.confirm_dialog import (  # noqa: E402
    CANCEL_RESPONSE,
    REMOVE_RESPONSE,
    build_remove_dialog,
)

PACKAGE = Package(name="firefox", version="141.0.3-1.fc44", repo="updates")


def test_dialog_names_the_package_and_warns_about_the_consequence() -> None:
    dialog = build_remove_dialog(PACKAGE, lambda: None)

    assert dialog.get_heading() == "Remove firefox?"
    assert "uninstall firefox 141.0.3-1.fc44" in dialog.get_body()
    assert "cannot be undone" in dialog.get_body()


def test_remove_is_the_destructive_choice_and_cancel_is_the_default() -> None:
    dialog = build_remove_dialog(PACKAGE, lambda: None)

    assert dialog.get_response_appearance(REMOVE_RESPONSE) == (
        Adw.ResponseAppearance.DESTRUCTIVE
    )
    assert dialog.get_default_response() == CANCEL_RESPONSE
    assert dialog.get_close_response() == CANCEL_RESPONSE


def test_remove_response_runs_the_callback() -> None:
    removed: list[bool] = []
    dialog = build_remove_dialog(PACKAGE, lambda: removed.append(True))

    dialog.emit("response", REMOVE_RESPONSE)

    assert removed == [True]


def test_cancel_response_does_not_remove_anything() -> None:
    removed: list[bool] = []
    dialog = build_remove_dialog(PACKAGE, lambda: removed.append(True))

    dialog.emit("response", CANCEL_RESPONSE)

    assert removed == []
