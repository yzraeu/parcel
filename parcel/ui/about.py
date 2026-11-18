"""About dialog: name, version, links, and the dependency credits."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel import APP_NAME, __version__  # noqa: E402

# Until the app icon ships in the icon theme, the dialog falls back to the
# generic package icon.
APP_ICON = "package-x-generic"
APP_WEBSITE = "https://github.com/yzraeu/parcel"
APP_ISSUES = f"{APP_WEBSITE}/issues"
APP_AUTHOR = "yzraeu"

# Name and license of everything Parcel is built on, shown as one
# acknowledgement section.
DEPENDENCIES = (
    "PackageKit (LGPL-2.1-or-later)",
    "GTK 4 (LGPL-2.1-or-later)",
    "libadwaita (LGPL-2.1-or-later)",
    "PyGObject (LGPL-2.1-or-later)",
)


def build_about_dialog() -> Adw.AboutDialog:
    """Build Parcel's About dialog; the caller decides when to present it."""
    dialog = Adw.AboutDialog(
        application_name=APP_NAME,
        application_icon=APP_ICON,
        developer_name=APP_AUTHOR,
        developers=[APP_AUTHOR],
        version=__version__,
        website=APP_WEBSITE,
        issue_url=APP_ISSUES,
        copyright=f"© 2026 {APP_AUTHOR}",
        license_type=Gtk.License.GPL_3_0,
    )
    dialog.add_acknowledgement_section("Dependencies", list(DEPENDENCIES))
    return dialog


def show_about(parent: Gtk.Window) -> Adw.AboutDialog:
    """Build and present the About dialog over ``parent``."""
    dialog = build_about_dialog()
    dialog.present(parent)
    return dialog
