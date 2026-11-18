"""Tests for the blocking-work runners."""

from __future__ import annotations

from gi.repository import GLib

from parcel.ui.tasks import AsyncRunner, SyncRunner


def test_sync_runner_delivers_the_result() -> None:
    results: list[int] = []
    SyncRunner().run(lambda: 21 * 2, results.append)
    assert results == [42]


def test_sync_runner_reports_errors_instead_of_raising() -> None:
    results: list[int] = []
    errors: list[Exception] = []

    def fail() -> int:
        raise RuntimeError("boom")

    SyncRunner().run(fail, results.append, errors.append)

    assert results == []
    assert [str(error) for error in errors] == ["boom"]


def test_sync_runner_swallows_errors_without_a_handler() -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    SyncRunner().run(fail, lambda _result: None)


def test_async_runner_delivers_the_result_on_the_main_loop() -> None:
    loop = GLib.MainLoop()
    results: list[int] = []

    def on_done(value: int) -> None:
        results.append(value)
        loop.quit()

    AsyncRunner().run(lambda: 42, on_done)
    GLib.timeout_add(2000, loop.quit)
    loop.run()

    assert results == [42]


def test_async_runner_reports_errors_on_the_main_loop() -> None:
    loop = GLib.MainLoop()
    errors: list[Exception] = []

    def fail() -> None:
        raise RuntimeError("boom")

    def on_error(error: Exception) -> None:
        errors.append(error)
        loop.quit()

    AsyncRunner().run(fail, lambda _result: None, on_error)
    GLib.timeout_add(2000, loop.quit)
    loop.run()

    assert [str(error) for error in errors] == ["boom"]
