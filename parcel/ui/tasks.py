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
