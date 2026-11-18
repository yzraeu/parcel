"""Sample rows so the scaffold has something to render.

Issue #2 replaces these with data from :class:`parcel.backend.client.PackageKitClient`.
"""

from __future__ import annotations

from datetime import datetime

from parcel.backend.models import InstallReason, Package, Update


def installed() -> tuple[Package, ...]:
    return (
        Package(
            name="firefox",
            version="141.0.3-1.fc44",
            repo="updates",
            size=112_400_000,
            summary="Web browser",
            description="Firefox is a standalone web browser built on Gecko.",
            license="MPL-2.0 and others",
            installed=True,
            install_reason=InstallReason.USER,
            install_date=datetime(2026, 11, 2, 9, 14),
            required_by=("gnome-initial-setup",),
            files=(
                "/usr/bin/firefox",
                "/usr/lib64/firefox/firefox",
                "/usr/lib64/firefox/libxul.so",
                "/usr/share/applications/firefox.desktop",
            ),
            changelog="Fix a crash when restoring tabs after an update.",
            homepage="https://www.mozilla.org/firefox/",
            source_url="https://src.fedoraproject.org/rpms/firefox",
        ),
        Package(
            name="flatpak",
            version="1.16.1-1.fc44",
            repo="fedora",
            size=7_100_000,
            summary="Application sandboxing and distribution framework",
            description="Flatpak builds and runs sandboxed desktop applications.",
            license="LGPL-2.1-or-later",
            installed=True,
            install_reason=InstallReason.DEPENDENCY,
            install_date=datetime(2026, 10, 21, 17, 44),
            files=("/usr/bin/flatpak", "/usr/lib64/libflatpak.so.0"),
            changelog="Fix installing refs with long IDs.",
            homepage="https://flatpak.org/",
            source_url="https://src.fedoraproject.org/rpms/flatpak",
        ),
        Package(
            name="nautilus",
            version="48.2-1.fc44",
            repo="fedora",
            size=18_900_000,
            summary="File manager for GNOME",
            description="Nautilus is the GNOME file manager.",
            license="GPL-3.0-or-later",
            installed=True,
            install_reason=InstallReason.USER,
            install_date=datetime(2026, 10, 21, 17, 39),
            files=("/usr/bin/nautilus", "/usr/lib64/nautilus"),
            changelog="Improve search performance in large folders.",
            homepage="https://apps.gnome.org/Nautilus/",
            source_url="https://src.fedoraproject.org/rpms/nautilus",
        ),
    )


def available() -> tuple[Package, ...]:
    return (
        Package(
            name="gimp",
            version="3.0.4-1.fc44",
            repo="fedora",
            size=98_300_000,
            summary="GNU Image Manipulation Program",
            description="GIMP is a raster graphics editor.",
            license="GPL-3.0-or-later",
            homepage="https://www.gimp.org/",
            source_url="https://src.fedoraproject.org/rpms/gimp",
        ),
        Package(
            name="htop",
            version="3.4.1-1.fc44",
            repo="fedora",
            size=430_000,
            summary="Interactive process viewer",
            description="htop is an interactive system monitor process viewer.",
            license="GPL-2.0-or-later",
            homepage="https://htop.dev/",
            source_url="https://src.fedoraproject.org/rpms/htop",
        ),
        Package(
            name="ripgrep",
            version="15.1.0-2.fc44",
            repo="updates",
            size=5_200_000,
            summary="Line-oriented search tool",
            description="ripgrep searches directories recursively for a regex pattern.",
            license="MIT AND Unlicense",
            homepage="https://github.com/BurntSushi/ripgrep",
            source_url="https://src.fedoraproject.org/rpms/ripgrep",
        ),
    )


def updates() -> tuple[Update, ...]:
    return (
        Update(
            package=Package(
                name="firefox",
                version="142.0-1.fc44",
                repo="updates",
                size=114_700_000,
                summary="Web browser",
                license="MPL-2.0 and others",
            ),
            installed_version="141.0.3-1.fc44",
            security=True,
        ),
        Update(
            package=Package(
                name="nautilus",
                version="48.3-1.fc44",
                repo="updates",
                size=19_100_000,
                summary="File manager for GNOME",
                license="GPL-3.0-or-later",
            ),
            installed_version="48.2-1.fc44",
        ),
    )
