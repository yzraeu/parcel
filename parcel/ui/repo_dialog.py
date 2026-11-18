"""The add-repository dialog: choose a path, then confirm the signing key.

The dialog never fetches, writes, or trusts anything by itself. It builds a
:class:`RepoRequest`, asks the window to prepare it, shows the fingerprint the
backend found, and asks the window to install only after the user presses
"Trust and add".
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel.backend.models import (  # noqa: E402
    RepoKind,
    RepoPlan,
    RepoRequest,
)


class AddRepoDialog(Adw.Dialog):
    """Two-path form followed by a fingerprint confirmation page."""

    def __init__(
        self,
        on_prepare: Callable[[RepoRequest], None],
        on_confirm: Callable[[RepoPlan], None],
    ) -> None:
        super().__init__()
        self._on_prepare = on_prepare
        self._on_confirm = on_confirm
        self.plan: RepoPlan | None = None
        self.set_content_width(480)

        self.spinner = Gtk.Spinner(visible=False, valign=Gtk.Align.CENTER)
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Add repository"))
        header.pack_end(self.spinner)

        self.error_label = Gtk.Label(
            xalign=0,
            wrap=True,
            visible=False,
            css_classes=["error"],
        )

        self.mode_stack = Adw.ViewStack()
        self.mode_switcher = Adw.ViewSwitcher(
            stack=self.mode_stack,
            policy=Adw.ViewSwitcherPolicy.NARROW,
            halign=Gtk.Align.CENTER,
        )
        self.mode_stack.add_titled(self._build_copr_page(), "copr", "COPR")
        self.mode_stack.add_titled(self._build_url_page(), "url", "Repository URL")

        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", lambda _button: self.close())
        self.add_button = Gtk.Button(label="Add", css_classes=["suggested-action"])
        self.add_button.connect("clicked", self._add_clicked)
        self.back_button = Gtk.Button(label="Back")
        self.back_button.connect("clicked", self._back_clicked)
        self.trust_button = Gtk.Button(
            label="Trust and add",
            css_classes=["suggested-action"],
        )
        self.trust_button.connect("clicked", self._trust_clicked)

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(self.mode_stack, "form")
        self.content_stack.add_named(self._build_confirm_page(), "confirm")

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
        )
        for edge in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{edge}")(18)
        content.append(self.mode_switcher)
        content.append(self.error_label)
        content.append(self.content_stack)
        content.append(
            _button_row(
                self.cancel_button,
                self.add_button,
                self.back_button,
                self.trust_button,
            )
        )

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(content)
        self.set_child(toolbar)
        self._show_stage("form")
        self.set_busy(False)

    # -- pages -------------------------------------------------------------

    def _build_copr_page(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="COPR project",
            description="Type owner/project, for example yzraeu/starship.",
        )
        self.copr_entry = Adw.EntryRow(title="owner/project")
        group.add(self.copr_entry)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.append(group)
        return page

    def _build_url_page(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Repository URL",
            description=(
                "Parcel reads the signing key from "
                "repodata/repomd.xml.key under this URL."
            ),
        )
        self.name_entry = Adw.EntryRow(title="Name")
        self.url_entry = Adw.EntryRow(title="Base URL")
        self.url_entry.set_text("https://")
        group.add(self.name_entry)
        group.add(self.url_entry)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.append(group)
        return page

    def _build_confirm_page(self) -> Gtk.Widget:
        title = Gtk.Label(
            label="Trust this signing key?",
            xalign=0,
            wrap=True,
            css_classes=["title-2"],
        )
        explanation = Gtk.Label(
            label=(
                "Parcel downloaded this repository's key. Compare the "
                "fingerprint with the one the repository publishes before "
                "trusting it."
            ),
            xalign=0,
            wrap=True,
            css_classes=["dim-label"],
        )
        self.fingerprint_label = Gtk.Label(
            xalign=0,
            wrap=True,
            selectable=True,
            css_classes=["monospace", "heading"],
        )
        self.key_id_label = Gtk.Label(
            xalign=0,
            wrap=True,
            selectable=True,
            css_classes=["dim-label", "caption"],
        )
        self.key_url_label = Gtk.Label(
            xalign=0,
            wrap=True,
            selectable=True,
            css_classes=["dim-label", "caption"],
        )

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.append(title)
        page.append(explanation)
        page.append(self.fingerprint_label)
        page.append(self.key_id_label)
        page.append(self.key_url_label)
        return page

    # -- actions -----------------------------------------------------------

    def current_request(self) -> RepoRequest:
        """Read the form; raises ValueError when a required field is empty."""
        mode = self.mode_stack.get_visible_child_name()
        if mode == "copr":
            copr = self.copr_entry.get_text().strip()
            if not copr:
                raise ValueError("type a COPR project as owner/project")
            return RepoRequest(kind=RepoKind.COPR, copr=copr)
        name = self.name_entry.get_text().strip()
        baseurl = self.url_entry.get_text().strip()
        if not name:
            raise ValueError("the repository needs a name")
        if not baseurl or baseurl == "https://":
            raise ValueError("the repository needs a base URL")
        return RepoRequest(kind=RepoKind.URL, name=name, baseurl=baseurl)

    def show_plan(self, plan: RepoPlan) -> None:
        """Show the fingerprint and wait for the user's trust decision."""
        self.plan = plan
        self.fingerprint_label.set_label(plan.fingerprint_text)
        self.key_id_label.set_label(f"Key ID {plan.key_id}" if plan.key_id else "")
        self.key_url_label.set_label(plan.key_url)
        self._show_stage("confirm")
        self.error_label.set_visible(False)
        self.set_busy(False)

    def show_error(self, error: Exception) -> None:
        self.error_label.set_label(str(error))
        self.error_label.set_visible(True)
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        for button in (
            self.cancel_button,
            self.add_button,
            self.back_button,
            self.trust_button,
        ):
            button.set_sensitive(not busy)
        self.spinner.set_visible(busy)
        self.spinner.set_spinning(busy)

    def _add_clicked(self, _button: Gtk.Button) -> None:
        try:
            request = self.current_request()
        except ValueError as error:
            self.show_error(error)
            return
        self.error_label.set_visible(False)
        self.set_busy(True)
        self._on_prepare(request)

    def _trust_clicked(self, _button: Gtk.Button) -> None:
        if self.plan is None:
            self.show_error(ValueError("there is no repository to add"))
            return
        self.error_label.set_visible(False)
        self.set_busy(True)
        self._on_confirm(self.plan)

    def _back_clicked(self, _button: Gtk.Button) -> None:
        self.plan = None
        self.error_label.set_visible(False)
        self._show_stage("form")
        self.set_busy(False)

    def _show_stage(self, stage: str) -> None:
        confirming = stage == "confirm"
        self.mode_switcher.set_visible(not confirming)
        self.content_stack.set_visible_child_name(stage)
        self.cancel_button.set_visible(not confirming)
        self.add_button.set_visible(not confirming)
        self.back_button.set_visible(confirming)
        self.trust_button.set_visible(confirming)


def _button_row(*buttons: Gtk.Widget) -> Gtk.Widget:
    row = Gtk.Box(spacing=12, halign=Gtk.Align.END)
    for button in buttons:
        row.append(button)
    return row
