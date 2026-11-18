"""Application object and process entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from parcel import APP_ID  # noqa: E402
from parcel.ui.window import MainWindow  # noqa: E402


class ParcelApplication(Adw.Application):
    """The Adw.Application behind ``python3 -m parcel``."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = MainWindow(application=self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    return ParcelApplication().run(sys.argv if argv is None else argv)
