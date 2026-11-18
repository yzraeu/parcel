# Parcel

A fast, simple, packages-only GUI for dnf on Fedora. Four tabs, a search
box, one button per action. No app-store features: that is GNOME Software's
job.

Status: **scaffold**. The window, the layering, the backend queries, the
tests, and CI exist; package actions and the Repos tab are built in later
issues.

## Layout

```
parcel/                     # app package
  __init__.py               # name, app id, version
  __main__.py               # entry point for `python3 -m parcel`
  app.py                    # Adw.Application subclass
  backend/                  # PackageKit client, never imports GTK
    __init__.py
    client.py               # search, list installed, list updates
    models.py               # plain data classes: Package, Repo, Update
  ui/                       # GTK views, never calls PackageKit
    __init__.py
    window.py               # main window: header bar, search, tab switcher
    package_row.py          # one package row (name, version, repo, size, action)
    package_detail.py       # expanded detail view for a package
    repos_view.py           # Repos tab placeholder (issue #3)
    placeholder.py          # sample rows until issue #2 wires real data
tests/
  test_models.py
  test_backend.py           # faked PackageKit, no live D-Bus
  test_window.py
  test_package_row.py
  test_package_detail.py
  test_repos_view.py
  test_placeholder.py
  test_app.py
  test_main.py
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
- **Every module has a test.** Tests fake PackageKit and never touch the
  live D-Bus. Never weaken or delete a test to get CI green.

## Requirements

- Python 3.11 or newer
- PyGObject, GTK 4, libadwaita
- PackageKit (only needed for real backend queries, not for tests)

On Fedora:

```sh
sudo dnf install python3-gobject gtk4 libadwaita PackageKit-glib \
    python3-pytest ruff
```

## Run

```sh
make run          # python3 -m parcel
```

The window opens with the four tabs (Installed / Available / Updates /
Repos), the search entry in the header, and placeholder rows. Search
filters every tab as you type.

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
