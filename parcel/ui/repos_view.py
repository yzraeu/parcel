"""The Repos tab: one row per repository, an add button, and removal.

Rows are plain :class:`Adw.ActionRow` widgets because a system has a handful of
repositories, not tens of thousands of packages. Every button forwards user
intent to the window; this module never touches PackageKit or files.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from parcel.backend.models import Repo  # noqa: E402


class ReposPage(Gtk.Box):
    """Repository list with enable switches and a removal button."""

    def __init__(
        self,
        on_toggle: Callable[[Repo, bool], None],
        on_remove: Callable[[Repo], None],
        on_add: Callable[[], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_toggle = on_toggle
        self._on_remove = on_remove
        self._on_add = on_add
        self.rows: dict[str, Adw.ActionRow] = {}
        self.switches: dict[str, Gtk.Switch] = {}
        self.remove_buttons: dict[str, Gtk.Button] = {}
        self._loading = True

        self.add_button = Gtk.Button(
            label="Add repository",
            valign=Gtk.Align.CENTER,
            css_classes=["suggested-action"],
        )
        self.add_button.connect("clicked", lambda _button: self._on_add())

        header = Gtk.Box(spacing=12)
        header.set_margin_top(12)
        header.set_margin_bottom(6)
        header.set_margin_start(18)
        header.set_margin_end(18)
        header.append(
            Gtk.Label(
                label="Repositories",
                xalign=0,
                hexpand=True,
                css_classes=["title-4"],
            )
        )
        header.append(self.add_button)
        self.append(header)

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        for edge in ("top", "bottom", "start", "end"):
            getattr(self.list_box, f"set_margin_{edge}")(12)

        self.scroller = Gtk.ScrolledWindow(
            child=self.list_box,
            vexpand=True,
            hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        self.empty_page = Adw.StatusPage(
            icon_name="folder-symbolic",
            title="No repositories",
            description="Add a COPR project or a repository URL to get started.",
        )
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.busy_page = Adw.StatusPage(title="Loading repositories\u2026")
        self.busy_page.set_child(self.spinner)
        self.stack = Gtk.Stack()
        self.stack.add_named(self.busy_page, "busy")
        self.stack.add_named(self.scroller, "list")
        self.stack.add_named(self.empty_page, "empty")
        self.stack.set_vexpand(True)
        self.append(self.stack)
        self._refresh()

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._refresh()

    def set_repos(self, repos: Sequence[Repo]) -> None:
        self._clear()
        for repo in repos:
            self._append_row(repo)
        self._loading = False
        self._refresh()

    @property
    def visible_count(self) -> int:
        return len(self.rows)

    def _clear(self) -> None:
        child = self.list_box.get_first_child()
        while child is not None:
            self.list_box.remove(child)
            child = self.list_box.get_first_child()
        self.rows.clear()
        self.switches.clear()
        self.remove_buttons.clear()

    def _append_row(self, repo: Repo) -> None:
        row = Adw.ActionRow(title=repo.name, subtitle=repo.subtitle)
        switch = Gtk.Switch(active=repo.enabled, valign=Gtk.Align.CENTER)
        switch.connect(
            "notify::active",
            lambda widget, _property: self._on_toggle(repo, widget.get_active()),
        )
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        self.rows[repo.repo_id] = row
        self.switches[repo.repo_id] = switch

        if repo.removable:
            button = Gtk.Button(
                icon_name="user-trash-symbolic",
                tooltip_text=f"Remove {repo.name}",
                valign=Gtk.Align.CENTER,
                css_classes=["flat", "destructive-action"],
            )
            button.connect("clicked", lambda _button: self._on_remove(repo))
            row.add_suffix(button)
            self.remove_buttons[repo.repo_id] = button

        self.list_box.append(row)

    def _refresh(self) -> None:
        if self._loading and not self.rows:
            self.busy_page.set_title("Loading repositories\u2026")
            self.busy_page.set_description("Reading the repository configuration.")
            self.spinner.start()
            self.stack.set_visible_child_name("busy")
            return
        self.spinner.stop()
        if self.rows:
            self.stack.set_visible_child_name("list")
            return
        self.empty_page.set_icon_name("folder-symbolic")
        self.empty_page.set_title("No repositories")
        self.empty_page.set_description(
            "Add a COPR project or a repository URL to get started."
        )
        self.stack.set_visible_child_name("empty")
