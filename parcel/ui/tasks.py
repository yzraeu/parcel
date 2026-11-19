"""Run blocking backend calls without freezing the GTK main loop.

PackageKit queries and transactions are synchronous; the views hand them to a
runner and only touch widgets from the callbacks, which run on the main
thread. Tests inject :class:`SyncRunner` so no threads are involved.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

from gi.repository import GLib


class Runner(Protocol):
    """How views run blocking work."""

    def run(
        self,
        task: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None: ...


class SyncRunner:
    """Runs tasks immediately; deterministic for tests."""

    def run(
        self,
        task: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        try:
            result = task()
        except Exception as error:
            if on_error is not None:
                on_error(error)
            return
        on_done(result)


class Debouncer:
    """Coalesce rapid calls into one callback after a quiet period.

    ``flush`` runs a pending callback immediately, which keeps search tests
    deterministic without spinning a main loop.
    """

    def __init__(
        self,
        callback: Callable[[], None],
        delay_ms: int = 200,
        add: Callable[[int, Callable[[], bool]], int] | None = None,
        remove: Callable[[int], bool] | None = None,
    ) -> None:
        self._callback = callback
        self._delay_ms = delay_ms
        self._add = add if add is not None else GLib.timeout_add
        self._remove = remove if remove is not None else GLib.source_remove
        self._source: int | None = None

    @property
    def pending(self) -> bool:
        return self._source is not None

    def schedule(self) -> None:
        """Restart the quiet period."""
        self.cancel()
        self._source = self._add(self._delay_ms, self._fire)

    def cancel(self) -> None:
        if self._source is not None:
            self._remove(self._source)
            self._source = None

    def flush(self) -> None:
        """Run a pending callback now."""
        if self._source is not None:
            self.cancel()
            self._callback()

    def _fire(self) -> bool:
        self._source = None
        self._callback()
        return GLib.SOURCE_REMOVE


class AsyncRunner:
    """Runs tasks on a worker thread and delivers results on the main loop."""

    def run(
        self,
        task: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        def deliver(succeeded: bool, payload: Any) -> bool:
            if succeeded:
                on_done(payload)
            elif on_error is not None:
                on_error(payload)
            return GLib.SOURCE_REMOVE

        def work() -> None:
            try:
                result = task()
            except Exception as error:
                GLib.idle_add(deliver, False, error)
            else:
                GLib.idle_add(deliver, True, result)

        threading.Thread(target=work, name="parcel-task", daemon=True).start()
