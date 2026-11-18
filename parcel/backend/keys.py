"""Fetch a repository signing key and read its fingerprint.

The add-repository flow must show a fingerprint before trusting anything, so
the key is downloaded once, inspected with gpg, and then kept as bytes. The
fallback installer imports exactly those bytes instead of downloading again.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from parcel import __version__
from parcel.backend.commands import CommandError, CommandRunner, SubprocessRunner

MAX_KEY_BYTES = 1 << 20
FETCH_TIMEOUT = 20


class SigningKeyError(RuntimeError):
    """The key could not be downloaded or did not contain a fingerprint."""


@dataclass(frozen=True, slots=True)
class KeyInfo:
    """What the confirmation dialog shows about a signing key."""

    fingerprint: str
    key_id: str


def fetch_key(url: str) -> bytes:
    """Download a signing key over HTTP(S), bounded in time and size."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SigningKeyError(f"not a downloadable key URL: {url}")
    request = Request(url, headers={"User-Agent": f"Parcel/{__version__}"})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT) as response:
            data = response.read(MAX_KEY_BYTES + 1)
    except OSError as error:
        raise SigningKeyError(
            f"could not download the key from {url}: {error}"
        ) from error
    if not data:
        raise SigningKeyError(f"the key at {url} is empty")
    if len(data) > MAX_KEY_BYTES:
        raise SigningKeyError(f"the key at {url} is larger than {MAX_KEY_BYTES} bytes")
    return data


class KeyInspector:
    """Read a key's primary fingerprint with gpg's machine-readable output."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        gpg: str = "gpg",
    ) -> None:
        self._runner = runner if runner is not None else SubprocessRunner()
        self._gpg = gpg

    def inspect(self, key_data: bytes) -> KeyInfo:
        if not key_data:
            raise SigningKeyError("there is no key to inspect")
        handle, path = tempfile.mkstemp(prefix="parcel-key-", suffix=".gpg")
        try:
            with os.fdopen(handle, "wb") as key_file:
                key_file.write(key_data)
            output = self._runner.run(
                [
                    self._gpg,
                    "--batch",
                    "--with-colons",
                    "--import-options",
                    "show-only",
                    "--import",
                    path,
                ]
            )
        except CommandError as error:
            raise SigningKeyError(
                f"gpg could not read the repository key: {error}"
            ) from error
        finally:
            os.unlink(path)
        return parse_fingerprint(output)


def parse_fingerprint(output: str) -> KeyInfo:
    """Extract the first ``fpr`` and its ``pub`` key id from gpg output."""
    fingerprint = ""
    key_id = ""
    for line in output.splitlines():
        fields = line.split(":")
        if fields[0] == "pub" and len(fields) > 4:
            key_id = fields[4]
        elif fields[0] == "fpr" and len(fields) > 9 and fields[9]:
            fingerprint = fields[9]
            break
    if not fingerprint:
        raise SigningKeyError("the repository key has no fingerprint")
    return KeyInfo(fingerprint=fingerprint.upper(), key_id=key_id.upper())
