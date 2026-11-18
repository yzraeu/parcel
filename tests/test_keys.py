"""Tests for key downloads and fingerprint extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

import parcel.backend.keys as keys
from parcel.backend.commands import CommandError
from parcel.backend.keys import (
    MAX_KEY_BYTES,
    KeyInspector,
    SigningKeyError,
    fetch_key,
    parse_fingerprint,
)

GPG_OUTPUT = """\
tru::1:1700000000:0:3:1:5
pub:u:4096:1:ABCDEF0123456789:1700000000:::::::
fpr:::::::::0123456789ABCDEF0123456789ABCDEF01234567:
uid:::::::::Someone <someone@example.com>:
sub:u:4096:1:1111222233334444:1700000000:::::::
fpr:::::::::89ABCDEF0123456789ABCDEF0123456789ABCDEF:
"""


class FakeRunner:
    def __init__(self, output: str = GPG_OUTPUT, error: Exception | None = None):
        self.output = output
        self.error = error
        self.commands: list[tuple[str, ...]] = []
        self.key_data: bytes | None = None

    def run(self, argv):
        self.commands.append(tuple(argv))
        if self.error is not None:
            raise self.error
        self.key_data = Path(argv[-1]).read_bytes()
        return self.output


def test_inspector_reads_the_primary_fingerprint_and_key_id() -> None:
    runner = FakeRunner()

    info = KeyInspector(runner=runner).inspect(b"-----BEGIN PGP PUBLIC KEY BLOCK-----")

    assert info.fingerprint == "0123456789ABCDEF0123456789ABCDEF01234567"
    assert info.key_id == "ABCDEF0123456789"
    assert runner.key_data == b"-----BEGIN PGP PUBLIC KEY BLOCK-----"
    assert runner.commands[0][0] == "gpg"
    assert "show-only" in runner.commands[0]


def test_inspector_reports_gpg_failures() -> None:
    runner = FakeRunner(error=CommandError("gpg exited with 2", exit_code=2))

    with pytest.raises(SigningKeyError, match="gpg could not read"):
        KeyInspector(runner=runner).inspect(b"not a key")


def test_inspector_rejects_empty_key_data() -> None:
    with pytest.raises(SigningKeyError, match="no key"):
        KeyInspector(runner=FakeRunner()).inspect(b"")


def test_parse_fingerprint_rejects_output_without_one() -> None:
    with pytest.raises(SigningKeyError, match="no fingerprint"):
        parse_fingerprint("pub:u:4096:1:ABCDEF0123456789:1700000000:::::::\n")


def test_fetch_key_rejects_non_http_urls() -> None:
    with pytest.raises(SigningKeyError, match="not a downloadable"):
        fetch_key("file:///etc/passwd")


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.data[:limit]


def test_fetch_key_returns_the_downloaded_bytes(monkeypatch) -> None:
    monkeypatch.setattr(keys, "urlopen", lambda *_args, **_kwargs: FakeResponse(b"KEY"))

    assert fetch_key("https://example.com/pubkey.gpg") == b"KEY"


def test_fetch_key_rejects_an_empty_download(monkeypatch) -> None:
    monkeypatch.setattr(keys, "urlopen", lambda *_args, **_kwargs: FakeResponse(b""))

    with pytest.raises(SigningKeyError, match="empty"):
        fetch_key("https://example.com/pubkey.gpg")


def test_fetch_key_rejects_oversized_downloads(monkeypatch) -> None:
    oversized = b"x" * (MAX_KEY_BYTES + 1)
    monkeypatch.setattr(
        keys, "urlopen", lambda *_args, **_kwargs: FakeResponse(oversized)
    )

    with pytest.raises(SigningKeyError, match="larger than"):
        fetch_key("https://example.com/pubkey.gpg")


def test_fetch_key_reports_network_failures(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(keys, "urlopen", fail)

    with pytest.raises(SigningKeyError, match="could not download"):
        fetch_key("https://example.com/pubkey.gpg")
