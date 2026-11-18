# Parcel

A fast, simple, packages-only GUI for dnf on Fedora. Four tabs, a search
box, one button per action. No app-store features: that is GNOME Software's
job.

Status: **v0.1.0 main screen**. Browse, search, install, remove, and update
real packages through PackageKit, with a detail view for every package.
Repository management is issue #3.

## Features

- **Installed** tab: every installed package with its version, repository,
  and installed size, plus a red trash-can button that removes it after a
  confirmation dialog.
- **Available** tab: packages the configured repositories offer that are not
  installed, with an Install button.
- **Updates** tab: one row per update showing `old version → new version`,
  a Security marker when PackageKit reports an advisory, a per-package
  Update button, an **Update all** button, and a badge with the count on the
  tab.
- **Search** in the header filters the tab you are looking at; switching tabs
  applies the same query to the newly selected tab.
- **Package detail** (tap a row): description, license, size, repository,
  architecture, install date, install reason (installed by you vs installed
  as a dependency), reverse dependencies, the installed file list (first few
  with a count), the latest changelog entry, and links to Homepage, Source,
  and the COPR build page or Fedora Packages page.
- Deliberately absent: usage statistics (dnf tracks none) and download counts
  (only COPR publishes them, the Fedora repositories do not).

## Layout

```
parcel/                     # app package
  __init__.py               # name, app id, version
  __main__.py               # entry point for `python3 -m parcel`
  app.py                    # Adw.Application subclass; builds the real client
  backend/                  # PackageKit and system data, never imports GTK
    __init__.py
    client.py               # listings, details, sizes, install/remove/update
    models.py               # plain data classes: Package, Repo, Update
    rpmdb.py                # install dates, files, required-by, changelog
    history.py              # install reasons from the dnf history database
    versioning.py           # rpm version comparison and newest-version dedupe
    links.py                # homepage, source, build page URLs
  ui/                       # GTK views, never calls PackageKit
    __init__.py
    window.py               # header bar, search, tabs, actions, toasts
    package_list.py         # virtualized list page with filtering
    updates_page.py         # Updates tab with Update all
    package_row.py          # one row: name, subtitle, action, expander
    package_item.py         # GObject wrapper for Gio list models
    package_detail.py       # expanded detail view
    size_loader.py          # batched size lookups for visible rows
    confirm_dialog.py       # remove confirmation (destructive response)
    tasks.py                # worker-thread runner (and a synchronous one)
    repos_view.py           # Repos tab placeholder (issue #3)
tests/                      # fakes only; no test touches live D-Bus or rpmdb
Makefile                    # run, test, lint
pyproject.toml              # ruff + pytest config
.github/workflows/ci.yml    # lint + test on push and pull request
data/
  dev.izzy.parcel.desktop
  dev.izzy.parcel.metainfo.xml
```

## Layering rules

These are non-negotiable:

- **Backend never imports GTK.** `parcel/backend` must stay usable from a
  headless session. `tests/test_backend.py` checks this in a fresh
  interpreter.
- **UI never calls PackageKit.** Views render `parcel.backend.models`
  objects and forward user intent; only `parcel.backend.client` talks to
  PackageKit. `tests/test_window.py` checks that importing the UI does not
  pull in the client or `PackageKitGlib`.
- **One responsibility per module.** No god files.
- **Every module has a test.** Tests fake PackageKit, rpm, and dnf history
  and never touch live D-Bus, the rpm database, or the history database.
  Never weaken or delete a test to get CI green.

### Why the client reduces data itself

Some PackageKit builds ignore or renumber the `NEWEST`/`INSTALLED`/
`NOT_INSTALLED` filters on `GetPackages`. The client therefore lists
unfiltered, classifies by `PkInfoEnum`, deduplicates with rpm's version
comparison, and never trusts the filter bitfield. Package listings also carry
no size, so installed sizes come from the rpm database in one pass and
available sizes are fetched in batches for the rows that are actually on
screen.

## Requirements

- Python 3.11 or newer
- PyGObject, GTK 4, libadwaita
- PackageKit and python3-rpm
- A display for the widget tests (CI uses Xvfb)

On Fedora:

```sh
sudo dnf install python3-gobject gtk4 libadwaita PackageKit-glib \
    python3-rpm python3-pytest ruff
```

Install and remove transactions ask for authorization through polkit.

## Run

```sh
make run          # python3 -m parcel
```

The window opens on the Installed tab with data from PackageKit.

## Test and lint

```sh
make test         # pytest; needs a display (CI uses Xvfb)
make lint         # ruff check + ruff format --check
```

Widget tests construct real GTK widgets, so `make test` needs a display.
On a headless machine:

```sh
xvfb-run -a dbus-run-session -- make test
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
