"""Expanded detail view for one package."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from parcel.backend.links import build_links  # noqa: E402
from parcel.backend.models import Package  # noqa: E402

REQUIRED_BY_PREVIEW = 6


def _heading(text: str) -> Gtk.Label:
    return Gtk.Label(label=text, xalign=0, css_classes=["heading"])


def _preview(names: tuple[str, ...], limit: int) -> str:
    if len(names) <= limit:
        return ", ".join(names)
    shown = ", ".join(names[:limit])
    return f"{shown} (+{len(names) - limit} more)"


class PackageDetail(Gtk.Box):
    """Everything the plan lists for a tapped row, minus what dnf cannot know.

    ``facts`` and ``links`` are exposed for tests; the widget tree is the real
    interface for humans.
    """

    def __init__(self, package: Package) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("package-detail")
        for edge in ("top", "bottom", "start", "end"):
            getattr(self, f"set_margin_{edge}")(12)
        self.package = package
        self.facts: dict[str, str] = {}
        self.links: dict[str, str] = {}

        description = package.description or package.summary
        self.description_label = Gtk.Label(
            label=description or "No description available.",
            xalign=0,
            wrap=True,
            selectable=True,
        )
        self.append(self.description_label)

        facts = [
            ("License", package.license or "unknown"),
            ("Size", package.size_text),
            ("Repository", package.repo_label),
            ("Architecture", package.arch or "unknown"),
        ]
        if package.installed:
            facts.append(("Installed", self._install_date_text(package)))
            facts.append(("Reason", package.install_reason_text))
            facts.append(("Required by", self._required_by_text(package)))
        facts.append(("Files", package.files_text))

        grid = Gtk.Grid(column_spacing=18, row_spacing=6)
        for row, (key, value) in enumerate(facts):
            self.facts[key] = value
            grid.attach(
                Gtk.Label(label=key, xalign=0, css_classes=["dim-label"]), 0, row, 1, 1
            )
            grid.attach(
                Gtk.Label(label=value, xalign=0, wrap=True, selectable=True),
                1,
                row,
                1,
                1,
            )
        self.append(grid)

        self.changelog_label: Gtk.Label | None = None
        if package.changelog:
            self.append(_heading("Latest changes"))
            self.changelog_label = Gtk.Label(
                label=package.changelog, xalign=0, wrap=True, selectable=True
            )
            self.append(self.changelog_label)

        self.link_buttons: list[Gtk.LinkButton] = []
        self.links = dict(build_links(package))
        if self.links:
            link_box = Gtk.Box(spacing=12)
            for label, url in self.links.items():
                button = Gtk.LinkButton(label=label, uri=url)
                self.link_buttons.append(button)
                link_box.append(button)
            self.append(link_box)

    @staticmethod
    def _install_date_text(package: Package) -> str:
        if package.install_date is None:
            return "unknown"
        return package.install_date.strftime("%Y-%m-%d")

    @staticmethod
    def _required_by_text(package: Package) -> str:
        if not package.required_by:
            return "Nothing depends on it"
        return _preview(package.required_by, REQUIRED_BY_PREVIEW)

    @staticmethod
    def loading() -> Gtk.Box:
        """Stand-in shown while the backend collects the details."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.add_css_class("package-detail-loading")
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(12)
        box.append(Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER))
        box.append(Gtk.Label(label="Loading details\u2026", xalign=0))
        return box
