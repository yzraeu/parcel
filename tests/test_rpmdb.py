"""Tests for rpm database lookups, using fake headers only."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from parcel.backend.rpmdb import RpmDatabase


class FakeTransactionSet:
    def __init__(self, headers: list[dict[str, Any]]) -> None:
        self.headers = headers
        self.queries: list[tuple[str, str]] = []

    def dbMatch(self, key: str | None = None, value: str | None = None):  # noqa: N802
        if key is None:
            return iter(self.headers)
        self.queries.append((key, value or ""))
        return (header for header in self.headers if _matches(header, key, value))


class FakeRpm:
    def __init__(self, headers: list[dict[str, Any]]) -> None:
        self.transaction = FakeTransactionSet(headers)

    def TransactionSet(self) -> FakeTransactionSet:  # noqa: N802
        return self.transaction


def _matches(header: dict[str, Any], key: str, value: str) -> bool:
    stored = header.get(key)
    if isinstance(stored, (list, tuple)):
        return value in stored
    return stored == value


def header_for(**overrides: Any) -> dict[str, Any]:
    header: dict[str, Any] = {
        "name": "bash",
        "size": 8865529,
        "installtime": 1794285711,
        "filenames": ["/usr/bin/bash", "/etc/bashrc"],
        "providename": ["/bin/sh", "bash"],
        "changelogtext": ["- newest entry", "- older entry"],
        "changelogtime": [1_800_000_000, 1_700_000_000],
        "changelogname": ["Maintainer <m@example.org> - 5.3-2", "Old <o@example.org>"],
    }
    header.update(overrides)
    return header


def test_installed_sizes_maps_names_to_bytes() -> None:
    rpm = FakeRpm([header_for(), header_for(name="glibc", size=0)])
    assert RpmDatabase(rpm).installed_sizes() == {"bash": 8865529, "glibc": 0}


def test_install_date_comes_from_the_header() -> None:
    rpm = FakeRpm([header_for()])
    assert RpmDatabase(rpm).install_date("bash") == datetime.fromtimestamp(1794285711)


def test_install_date_is_none_for_missing_packages_and_zero_times() -> None:
    assert RpmDatabase(FakeRpm([])).install_date("bash") is None
    zero_time = RpmDatabase(FakeRpm([header_for(installtime=0)]))
    assert zero_time.install_date("bash") is None


def test_files_come_from_the_header() -> None:
    rpm = FakeRpm([header_for()])
    assert RpmDatabase(rpm).files("bash") == ("/usr/bin/bash", "/etc/bashrc")
    assert RpmDatabase(FakeRpm([])).files("bash") == ()


def test_required_by_matches_every_provided_capability() -> None:
    dependent = header_for(name="zsh", providename=[], changelogtext=[])
    dependent["requirename"] = ["bash"]
    requires_sh = header_for(name="busybox", providename=[], changelogtext=[])
    requires_sh["requirename"] = ["/bin/sh"]

    rpm = FakeRpm([header_for(), dependent, requires_sh])
    assert RpmDatabase(rpm).required_by("bash") == ("busybox", "zsh")
    assert ("requirename", "/bin/sh") in rpm.transaction.queries


def test_required_by_is_empty_for_missing_packages() -> None:
    assert RpmDatabase(FakeRpm([])).required_by("bash") == ()


def test_changelog_returns_the_newest_entry_with_its_author_line() -> None:
    rpm = FakeRpm([header_for()])
    assert RpmDatabase(rpm).changelog("bash") == (
        "Maintainer <m@example.org> - 5.3-2\n- newest entry"
    )


def test_changelog_picks_the_entry_with_the_latest_date() -> None:
    header = header_for(
        changelogtext=["- middle", "- late entry", "- early"],
        changelogtime=[1_700_000_000, 1_800_000_000, 1_600_000_000],
        changelogname=["a", "b", "c"],
    )
    assert RpmDatabase(FakeRpm([header])).changelog("bash") == "b\n- late entry"


def test_changelog_is_empty_when_absent() -> None:
    assert RpmDatabase(FakeRpm([header_for(changelogtext=[])])).changelog("bash") == ""
    assert RpmDatabase(FakeRpm([])).changelog("bash") == ""
