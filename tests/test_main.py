"""Tests for ``python3 -m parcel``."""

import runpy

import pytest

import parcel.app


def test_running_the_package_invokes_the_app(monkeypatch) -> None:
    monkeypatch.setattr(parcel.app, "main", lambda: 0)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("parcel", run_name="__main__")

    assert excinfo.value.code == 0


def test_exit_code_is_propagated(monkeypatch) -> None:
    monkeypatch.setattr(parcel.app, "main", lambda: 3)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("parcel", run_name="__main__")

    assert excinfo.value.code == 3
