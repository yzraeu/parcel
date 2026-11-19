"""Main window: header bar, search, the four tabs, and package actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GObject, Gtk  # noqa: E402

from parcel import APP_NAME  # noqa: E402
from parcel.backend.models import Package, Repo, RepoPlan, RepoRequest, Update  # noqa: E402
from parcel.ui import tasks  # noqa: E402
from parcel.ui.about import show_about  # noqa: E402
from parcel.ui.confirm_dialog import build_remove_dialog  # noqa: E402
from parcel.ui.package_list import PackageListPage  # noqa: E402
from parcel.ui.package_row import RowAction  # noqa: E402
from parcel.ui.repo_dialog import AddRepoDialog  # noqa: E402
from parcel.ui.repos_view import ReposPage  # noqa: E402
from parcel.ui.size_loader import SizeLoader  # noqa: E402
from parcel.ui.updates_page import UpdatesPage  # noqa: E402

PAGE_TITLES = {
    "installed": "Installed",
    "available": "Available",
    "updates": "Updates",
    "repos": "Repos",
}

# Toast wording per action: in progress, finished, and the verb on failure.
_ACTION_WORDS = {
    RowAction.INSTALL: ("Installing", "Installed", "install"),
    RowAction.REMOVE: ("Removing", "Removed", "remove"),
    RowAction.UPDATE: ("Updating", "Updated", "update"),
}

# The list a row belongs to; busy state only needs to be pushed there.
_ACTION_PAGES = {
    RowAction.INSTALL: "available",
    RowAction.REMOVE: "installed",
    RowAction.UPDATE: "updates",
}

# Which backend call fills a tab. Tabs are fetched on first view.
_PAGE_LOADERS = {
    "installed": "list_installed",
    "available": "list_available",
    "updates": "list_updates",
}


class PackageBackend(Protocol):
    """The slice of the backend client the window needs.

    Keeping it explicit documents the seam: the UI never imports PackageKit.
    """

    def list_installed(self) -> list[Package]: ...

    def list_available(self) -> list[Package]: ...

    def list_updates(
        self, installed_versions: Mapping[str, str] | None = None
    ) -> list[Update]: ...

    def get_detail(self, package: Package) -> Package: ...

    def sizes(self, packages: Sequence[Package]) -> Mapping[str, int]: ...

    def install(self, package: Package) -> None: ...

    def remove(self, package: Package) -> None: ...

    def update(self, packages: Sequence[Package]) -> None: ...

    def list_repos(self) -> list[Repo]: ...

    def prepare_repo(self, request: RepoRequest) -> RepoPlan: ...

    def add_repo(self, plan: RepoPlan) -> None: ...

    def remove_repo(self, repo: Repo) -> None: ...

    def set_repo_enabled(self, repo: Repo, enabled: bool) -> None: ...


class MainWindow(Adw.ApplicationWindow):
    """Parcel's only window at this stage."""

    def __init__(
        self,
        client: PackageBackend,
        runner: tasks.Runner | None = None,
        search_delay_ms: int = 200,
        **kwargs: object,
    ) -> None:
        super().__init__(
            title="Parcel",
            default_width=1000,
            default_height=720,
            **kwargs,
        )
        self.client = client
        self._runner = runner if runner is not None else tasks.AsyncRunner()
        self._size_loader = SizeLoader(client.sizes, self._runner)
        self._updates: list[Update] = []
        self._loaded_pages: set[str] = set()
        self._loading_pages: set[str] = set()
        self._busy_keys: set[str] = set()
        self.search_debouncer = tasks.Debouncer(self._run_search, search_delay_ms)
        self.remove_dialog: Adw.AlertDialog | None = None
        self.add_repo_dialog: AddRepoDialog | None = None
        self.about_dialog: Adw.AboutDialog | None = None

        self.stack = Adw.ViewStack()
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search packages")
        self.search_bar = Gtk.SearchBar()
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_toggle = Gtk.ToggleButton(
            icon_name="system-search-symbolic", tooltip_text="Search"
        )
        self.search_toggle.bind_property(
            "active",
            self.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self.search_toggle.set_active(True)

        self.header = Adw.HeaderBar()
        self.header.pack_start(self.search_toggle)
        self.view_switcher = Adw.ViewSwitcher(
            stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE
        )
        self.header.set_title_widget(self.view_switcher)

        menu = Gio.Menu()
        menu.append(f"About {APP_NAME}", "win.about")
        self.menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Main Menu"
        )
        self.menu_button.update_property([Gtk.AccessibleProperty.LABEL], ["Main Menu"])
        self.header.pack_end(self.menu_button)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._show_about)
        self.add_action(about_action)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(self.header)
        toolbar.add_top_bar(self.search_bar)
        toolbar.set_content(self.stack)
        self.toast_overlay.set_child(toolbar)
        self.set_content(self.toast_overlay)

        self.installed_page = PackageListPage(
            RowAction.REMOVE,
            self._handle_action,
            self._expand,
            self._size_loader,
            empty_title="No packages installed",
            empty_description="PackageKit reports an empty package set.",
        )
        self.available_page = PackageListPage(
            RowAction.INSTALL,
            self._handle_action,
            self._expand,
            self._size_loader,
            empty_title="No packages available",
            empty_description="No repositories offer packages right now.",
        )
        self.updates_page = UpdatesPage(
            self._handle_action,
            self._expand,
            self._update_all,
            self._size_loader,
        )
        self.repos_page = ReposPage(
            self._toggle_repo,
            self._remove_repo,
            self._add_repo,
        )
        self.pages: dict[str, PackageListPage] = {
            "installed": self.installed_page,
            "available": self.available_page,
            "updates": self.updates_page,
        }
        icons = {
            "installed": "system-software-install-symbolic",
            "available": "package-x-generic-symbolic",
            "updates": "software-update-available-symbolic",
        }
        for name, page in self.pages.items():
            self.stack.add_titled_with_icon(page, name, PAGE_TITLES[name], icons[name])
        self.stack.add_titled_with_icon(
            self.repos_page, "repos", PAGE_TITLES["repos"], "folder-symbolic"
        )

        self.search_entry.connect("search-changed", self._on_search_changed)
        self.stack.connect("notify::visible-child-name", self._on_page_changed)

        self._load()

    # -- loading -----------------------------------------------------------

    def _load(self) -> None:
        """Fetch the tab on screen at startup; other tabs load on first view.

        Measured here against live PackageKit (74.5k available packages): the
        unfiltered ``get_packages`` call takes 1381 ms, reducing the installed
        half (including the rpmdb metadata walk) 443 ms, the available half
        277 ms, building 74.5k ``PackageItem``s 82 ms, one ``splice()`` 10 ms,
        and the first list layout about 890 ms. Deferring Available and
        Updates to their first view keeps roughly 1.3 s of build, splice, and
        layout off startup. The unfiltered fetch itself stays: PackageKit's
        server-side filters are not dependable here (see ``client.py``).
        """
        self._load_page("installed")
        self._load_repos()

    def _load_page(self, name: str, force: bool = False) -> None:
        if name in self._loading_pages:
            return
        if not force and name in self._loaded_pages:
            return
        page = self.pages[name]
        self._loading_pages.add(name)
        page.set_loading(True)
        loader = getattr(self.client, _PAGE_LOADERS[name])
        self._runner.run(
            loader,
            lambda data: self._page_loaded(name, data),
            lambda error: self._page_failed(name, error),
        )

    def _page_loaded(self, name: str, data: Any) -> None:
        self._loading_pages.discard(name)
        self._loaded_pages.add(name)
        page = self.pages[name]
        if name == "updates":
            self._updates = list(data)
            page.set_updates(data)
            self.stack.get_page(page).set_badge_number(len(self._updates))
        else:
            page.set_packages(data)
        page.set_loading(False)
        if page is self._current_page():
            page.set_filter(self.search_entry.get_text())

    def _page_failed(self, name: str, error: Exception) -> None:
        self._loading_pages.discard(name)
        self.pages[name].set_loading(False)
        self._show_toast(f"Could not load packages: {error}")

    def _refresh_loaded(self) -> None:
        """Refetch the tabs that have been opened; leave the rest untouched."""
        for name in sorted(self._loaded_pages):
            self._load_page(name, force=True)

    def _load_repos(self) -> None:
        self.repos_page.set_loading(True)
        self._runner.run(
            self.client.list_repos,
            self.repos_page.set_repos,
            self._repos_failed,
        )

    def _repos_failed(self, error: Exception) -> None:
        self.repos_page.set_loading(False)
        self._show_toast(f"Could not load repositories: {error}")

    # -- search ------------------------------------------------------------

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        page = self._current_page()
        if page is None:
            return
        if not self.search_entry.get_text().strip():
            self.search_debouncer.cancel()
            page.set_searching(False)
            page.set_filter("")
            return
        # Show the spinner while the quiet period runs; the filter itself is
        # applied on the main loop after the debounce so typing stays smooth.
        # Re-filtering all 74.5k available rows takes ~70 ms here, hence the
        # 200 ms debounce instead of one pass per keystroke.
        page.set_searching(True)
        self.search_debouncer.schedule()

    def _run_search(self) -> None:
        page = self._current_page()
        if page is not None:
            page.set_searching(False)
            page.set_filter(self.search_entry.get_text())

    def _on_page_changed(self, *_args: object) -> None:
        self.search_debouncer.cancel()
        for page in self.pages.values():
            page.set_searching(False)
        name = self.stack.get_visible_child_name() or ""
        if name in self.pages:
            self._load_page(name)
        self._apply_search_to_current()

    def _current_page(self) -> PackageListPage | None:
        return self.pages.get(self.stack.get_visible_child_name() or "")

    def _apply_search_to_current(self) -> None:
        page = self._current_page()
        if page is not None:
            page.set_filter(self.search_entry.get_text())

    # -- actions -----------------------------------------------------------

    def _handle_action(self, package: Package, action: RowAction) -> None:
        if self._is_busy(package):
            return
        words = _ACTION_WORDS[action]
        page = _ACTION_PAGES[action]
        if action is RowAction.REMOVE:
            self._confirm_remove(package)
        elif action is RowAction.INSTALL:
            self._run([package], words, lambda: self.client.install(package), page)
        elif action is RowAction.UPDATE:
            self._run(
                [package],
                words,
                lambda: self.client.update([package]),
                page,
            )

    def _confirm_remove(self, package: Package) -> None:
        dialog = build_remove_dialog(
            package,
            lambda: self._run(
                [package],
                _ACTION_WORDS[RowAction.REMOVE],
                lambda: self.client.remove(package),
                "installed",
            ),
        )
        self.remove_dialog = dialog
        dialog.present(self)

    def _update_all(self) -> None:
        packages = [update.package for update in self._updates]
        if not packages:
            return
        self.updates_page.set_busy(True)
        self._run(
            packages,
            _ACTION_WORDS[RowAction.UPDATE],
            lambda: self.client.update(packages),
            "updates",
            target="all packages",
            on_finished=lambda: self.updates_page.set_busy(False),
        )

    def _expand(
        self,
        package: Package,
        show_detail: Callable[[Package], None],
    ) -> None:
        def failed(error: Exception) -> None:
            self._show_toast(f"Could not load details for {package.name}: {error}")
            # Show what the list already knows instead of leaving a spinner up.
            show_detail(package)

        self._runner.run(lambda: self.client.get_detail(package), show_detail, failed)

    def _is_busy(self, package: Package) -> bool:
        return package.key in self._busy_keys

    def _set_busy(
        self, packages: Sequence[Package], busy: bool, page_name: str
    ) -> None:
        page = self.pages[page_name]
        for package in packages:
            if busy:
                self._busy_keys.add(package.key)
            else:
                self._busy_keys.discard(package.key)
            page.set_package_busy(package.key, busy)

    def _run(
        self,
        packages: Sequence[Package],
        words: tuple[str, str, str],
        operation: Callable[[], None],
        page_name: str,
        target: str | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        busy, done, verb = words
        name = target or (packages[0].name if packages else "packages")
        # A second click while the first transaction runs must not start it
        # again; the row spinner is feedback, this is the actual guard.
        if not packages or any(self._is_busy(package) for package in packages):
            if on_finished is not None:
                on_finished()
            return
        self._set_busy(packages, True, page_name)
        self._show_toast(f"{busy} {name}\u2026")

        def finish() -> None:
            self._set_busy(packages, False, page_name)
            if on_finished is not None:
                on_finished()

        def completed(_result: object) -> None:
            finish()
            self._transaction_done(done, name)

        def failed(error: Exception) -> None:
            finish()
            self._show_toast(f"Could not {verb} {name}: {error}")

        self._runner.run(operation, completed, failed)

    def _transaction_done(self, done: str, target: str) -> None:
        self._show_toast(f"{done} {target}")
        self._refresh_loaded()

    # -- repositories ------------------------------------------------------

    def _toggle_repo(self, repo: Repo, enabled: bool) -> None:
        self._show_toast(f"{'Enabling' if enabled else 'Disabling'} {repo.name}\u2026")
        self._runner.run(
            lambda: self.client.set_repo_enabled(repo, enabled),
            lambda _result: self._repos_changed(
                f"{'Enabled' if enabled else 'Disabled'} {repo.name}"
            ),
            lambda error: self._repo_action_failed(
                "enable" if enabled else "disable", repo, error
            ),
        )

    def _repos_changed(self, message: str) -> None:
        self._show_toast(message)
        # The available package list and the updates list both depend on the
        # repositories that are enabled.
        self._refresh_loaded()
        self._load_repos()

    def _repo_action_failed(self, verb: str, repo: Repo, error: Exception) -> None:
        self._show_toast(f"Could not {verb} {repo.name}: {error}")
        self._load_repos()

    def _remove_repo(self, repo: Repo) -> None:
        if not repo.removable:
            self._show_toast(
                f"{repo.name} is a system repository and cannot be removed"
            )
            return
        self._show_toast(f"Removing {repo.name}\u2026")
        self._runner.run(
            lambda: self.client.remove_repo(repo),
            lambda _result: self._repo_removed(repo),
            lambda error: self._repo_action_failed("remove", repo, error),
        )

    def _repo_removed(self, repo: Repo) -> None:
        self._show_toast(f"Removed {repo.name}")
        self._refresh_loaded()
        self._load_repos()

    def _add_repo(self) -> None:
        dialog = AddRepoDialog(
            on_prepare=lambda request: self._prepare_repo(dialog, request),
            on_confirm=lambda plan: self._confirm_add_repo(dialog, plan),
        )
        self.add_repo_dialog = dialog
        dialog.present(self)

    def _prepare_repo(self, dialog: AddRepoDialog, request: RepoRequest) -> None:
        self._runner.run(
            lambda: self.client.prepare_repo(request),
            dialog.show_plan,
            dialog.show_error,
        )

    def _confirm_add_repo(self, dialog: AddRepoDialog, plan: RepoPlan) -> None:
        self._runner.run(
            lambda: self.client.add_repo(plan),
            lambda _result: self._repo_added(dialog, plan),
            dialog.show_error,
        )

    def _repo_added(self, dialog: AddRepoDialog, plan: RepoPlan) -> None:
        dialog.close()
        self._show_toast(f"Added {plan.name}")
        self._refresh_loaded()
        self._load_repos()

    def _show_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))

    def _show_about(self, *_args: object) -> None:
        self.about_dialog = show_about(self)
