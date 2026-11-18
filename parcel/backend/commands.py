"""Run trusted helper programs, never through a shell.

Repository changes need root, so the backend runs ``pkexec`` with an argument
vector. Tests inject a fake runner; no test starts a process. Nothing in this
module builds a command string, so user input can never turn into shell
syntax.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Protocol


class CommandError(RuntimeError):
    """A helper program exited non-zero.

    ``exit_code`` is None when the program could not be started at all.
    """

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class CommandRunner(Protocol):
    """How the backend runs one program and waits for it."""

    def run(self, argv: Sequence[str]) -> str: ...


class SubprocessRunner:
    """Run ``argv`` directly, capturing its output."""

    def run(self, argv: Sequence[str]) -> str:
        try:
            result = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            raise CommandError(f"could not run {argv[0]}: {error}") from error
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            last_line = output.splitlines()[-1] if output else ""
            message = f"{argv[0]} exited with {result.returncode}"
            raise CommandError(
                f"{message}: {last_line}" if last_line else message,
                exit_code=result.returncode,
            )
        return result.stdout
