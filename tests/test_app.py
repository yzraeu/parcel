"""Tests for the application object and its entry point wiring."""

from __future__ import annotations

import parcel.app as app_module
from parcel import APP_ID


class FakeWindow:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.presented = False

    def present(self) -> None:
        self.presented = True


def test_application_id_matches_the_project() -> None:
    app = app_module.ParcelApplication()
    assert app.get_application_id() == APP_ID


def test_first_activation_builds_and_presents_the_main_window(monkeypatch) -> None:
    created: list[FakeWindow] = []
    client = object()

    def fake_window_factory(**kwargs: object) -> FakeWindow:
        window = FakeWindow(**kwargs)
        created.append(window)
        return window

    monkeypatch.setattr(app_module, "MainWindow", fake_window_factory)
    monkeypatch.setattr(app_module, "PackageKitClient", lambda: client)
    app = app_module.ParcelApplication()
    monkeypatch.setattr(app, "get_active_window", lambda: None)

    app.do_activate()

    assert len(created) == 1
    assert created[0].kwargs == {"application": app, "client": client}
    assert created[0].presented


def test_second_activation_reuses_the_existing_window(monkeypatch) -> None:
    existing = FakeWindow()
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    app = app_module.ParcelApplication()
    monkeypatch.setattr(app, "get_active_window", lambda: existing)

    app.do_activate()

    assert existing.presented


def test_main_runs_the_application_with_the_given_argv(monkeypatch) -> None:
    class FakeApplication:
        def __init__(self) -> None:
            self.argv: list[str] | None = None

        def run(self, argv: list[str] | None = None) -> int:
            self.argv = argv
            return 0

    monkeypatch.setattr(app_module, "ParcelApplication", FakeApplication)
    assert app_module.main(["parcel"]) == 0
