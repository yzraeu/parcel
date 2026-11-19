"""Tests for the blocking-work runners."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import GLib

from parcel.ui.tasks import AsyncRunner, Debouncer, SyncRunner


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


def test_debouncer_runs_only_the_last_scheduled_callback() -> None:
    scheduled: dict[int, Callable[[], bool]] = {}
    calls: list[int] = []
    serial = 0

    def add(delay: int, callback: Callable[[], bool]) -> int:
        nonlocal serial
        serial += 1
        scheduled[serial] = callback
        return serial

    def remove(handle: int) -> bool:
        scheduled.pop(handle, None)
        return True

    debouncer = Debouncer(lambda: calls.append(1), delay_ms=200, add=add, remove=remove)

    debouncer.schedule()
    first = max(scheduled)
    debouncer.schedule()

    assert first not in scheduled
    assert debouncer.pending

    scheduled[max(scheduled)]()
    assert calls == [1]
    assert not debouncer.pending


def test_debouncer_flush_runs_a_pending_callback_now() -> None:
    calls: list[int] = []
    debouncer = Debouncer(lambda: calls.append(1), delay_ms=10_000)

    debouncer.flush()
    assert calls == []

    debouncer.schedule()
    debouncer.flush()

    assert calls == [1]
    assert not debouncer.pending


def test_debouncer_cancel_drops_the_callback() -> None:
    calls: list[int] = []
    debouncer = Debouncer(lambda: calls.append(1), delay_ms=10_000)

    debouncer.schedule()
    debouncer.cancel()
    debouncer.flush()

    assert calls == []
