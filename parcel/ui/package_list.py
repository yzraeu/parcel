"""One tab's package list: virtualized rows, search filtering, empty states.

A :class:`Gtk.ListView` is used instead of a boxed list because the available
tab holds tens of thousands of packages; widgets are created only for rows
that are on screen.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from parcel.backend.models import Package  # noqa: E402
from parcel.ui.package_item import PackageItem  # noqa: E402
from parcel.ui.package_row import PackageRow, RowAction  # noqa: E402
from parcel.ui.size_loader import SizeLoader  # noqa: E402


class PackageListPage(Gtk.Box):
    """A searchable package list with an action per row."""

    def __init__(
        self,
        action: RowAction,
        on_action: Callable[[Package, RowAction], None],
        on_expand: Callable[[Package, Callable[[Package], None]], None],
        size_loader: SizeLoader | None = None,
        empty_title: str = "No packages",
        empty_description: str = "",
        empty_icon: str = "package-x-generic-symbolic",
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.action = action
        self._on_action = on_action
        self._on_expand = on_expand
        self._size_loader = size_loader
        self._empty_title = empty_title
        self._empty_description = empty_description
        self._empty_icon = empty_icon
        self._query = ""
        self._loading = True

        self.store = Gio.ListStore(item_type=PackageItem)
        self.filter_model = Gtk.FilterListModel(model=self.store)
        self.selection = Gtk.NoSelection(model=self.filter_model)
        self.list_view = Gtk.ListView(
            model=self.selection,
            vexpand=True,
            hexpand=True,
        )
        self.list_view.add_css_class("boxed-list")
        for edge in ("top", "bottom", "start", "end"):
            getattr(self.list_view, f"set_margin_{edge}")(12)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind", self._bind_row)
        factory.connect("unbind", self._unbind_row)
        self.list_view.set_factory(factory)

        self.scroller = Gtk.ScrolledWindow(
            child=self.list_view,
            vexpand=True,
            hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        self.empty_page = Adw.StatusPage(
            icon_name=empty_icon,
            title=empty_title,
            description=empty_description,
        )
        self.stack = Gtk.Stack()
        self.stack.add_named(self.scroller, "list")
        self.stack.add_named(self.empty_page, "empty")
        self.append(self.stack)
        self._refresh()

    # -- data ------------------------------------------------------------

    def set_items(self, items: Sequence[PackageItem]) -> None:
        # splice() replaces the whole model in one items-changed signal;
        # appending 75k items one by one makes the list view do 75k rounds of
        # work and stalls startup for half a minute.
        self.store.splice(0, self.store.get_n_items(), list(items))
        self._refresh()

    def set_packages(self, packages: Sequence[Package]) -> None:
        self.set_items([PackageItem(package) for package in packages])

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._refresh()

    def set_filter(self, query: str) -> None:
        """Show only items matching ``query``; an empty query shows everything."""
        self._query = query
        self.filter_model.set_filter(Gtk.CustomFilter.new(self._matches))
        self._refresh()

    @property
    def visible_count(self) -> int:
        return self.filter_model.get_n_items()

    def _matches(self, item: PackageItem) -> bool:
        return item.package.matches(self._query)

    def _refresh(self) -> None:
        if self._loading and self.filter_model.get_n_items() == 0:
            self.empty_page.set_icon_name("content-loading-symbolic")
            self.empty_page.set_title("Loading packages\u2026")
            self.empty_page.set_description("Reading the package list from PackageKit.")
            self.stack.set_visible_child_name("empty")
            return
        has_rows = self.filter_model.get_n_items() > 0
        if has_rows:
            self.stack.set_visible_child_name("list")
            return
        self.empty_page.set_icon_name(
            "system-search-symbolic" if self._query.strip() else self._empty_icon
        )
        if self._query.strip():
            self.empty_page.set_title(f"No packages match \u201c{self._query}\u201d")
            self.empty_page.set_description("Try a different search term.")
        else:
            self.empty_page.set_title(self._empty_title)
            self.empty_page.set_description(self._empty_description)
        self.stack.set_visible_child_name("empty")

    # -- row factory -------------------------------------------------------

    def _setup_row(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        row = PackageRow(
            self.action,
            lambda package: self._on_action(package, self.action),
            self._on_expand,
        )
        item.set_child(row)

    def _bind_row(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        package_item = item.get_item()
        row = item.get_child()
        row.bind(package_item)
        if self._size_loader is not None and not package_item.size:
            self._size_loader.request(package_item.package, package_item.set_size)

    def _unbind_row(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        item.get_child().unbind()
