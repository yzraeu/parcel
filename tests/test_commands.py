"""Tests for running helper programs without a shell."""

from __future__ import annotations

from sys import executable

import pytest

from parcel.backend.commands import CommandError, SubprocessRunner


def test_runner_returns_standard_output() -> None:
    runner = SubprocessRunner()

    output = runner.run([executable, "-c", "print('hello')"])

    assert output == "hello\n"


def test_runner_raises_with_the_exit_code_and_last_error_line() -> None:
    runner = SubprocessRunner()

    with pytest.raises(CommandError) as raised:
        runner.run(
            [executable, "-c", "import sys; print('bad', file=sys.stderr); sys.exit(3)"]
        )

    assert raised.value.exit_code == 3
    assert "exited with 3" in str(raised.value)
    assert "bad" in str(raised.value)


def test_missing_program_is_a_command_error() -> None:
    runner = SubprocessRunner()

    with pytest.raises(CommandError) as raised:
        runner.run(["/nonexistent/parcel-helper"])

    assert raised.value.exit_code is None
    assert "could not run" in str(raised.value)
