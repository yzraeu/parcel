"""Tests for preparing and installing repositories, with fakes only."""

from __future__ import annotations

from pathlib import Path

import pytest

from parcel.backend.commands import CommandError
from parcel.backend.keys import KeyInfo, SigningKeyError
from parcel.backend.models import RepoKind, RepoPlan, RepoRequest
from parcel.backend.repos import RepoManager

FINGERPRINT = "0123456789ABCDEF0123456789ABCDEF01234567"


class FakeFetcher:
    def __init__(self, data: bytes = b"KEY") -> None:
        self.data = data
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        return self.data


class FakeInspector:
    def __init__(self, fingerprint: str = FINGERPRINT, key_id: str = "KEYID") -> None:
        self.info = KeyInfo(fingerprint=fingerprint, key_id=key_id)
        self.keys: list[bytes] = []

    def inspect(self, key_data: bytes) -> KeyInfo:
        self.keys.append(key_data)
        return self.info


class FakeRunner:
    def __init__(
        self,
        fail_on: tuple[str, ...] | None = None,
        exit_code: int = 1,
    ) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.key_data: bytes | None = None
        self.repo_data: str | None = None
        self.destination: str | None = None
        self._fail_on = fail_on
        self._exit_code = exit_code

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if self._fail_on is not None and command[: len(self._fail_on)] == self._fail_on:
            raise CommandError("helper failed", exit_code=self._exit_code)
        if len(command) > 1 and command[1] == "rpmkeys":
            self.key_data = Path(command[-1]).read_bytes()
        elif len(command) > 1 and command[1] == "install":
            self.repo_data = Path(command[-2]).read_text(encoding="utf-8")
            self.destination = command[-1]
        return ""


def make_manager(
    runner: FakeRunner | None = None,
    fetch: FakeFetcher | None = None,
    inspector: FakeInspector | None = None,
    repo_dir: Path = Path("/etc/yum.repos.d"),
) -> tuple[RepoManager, FakeRunner, FakeFetcher, FakeInspector]:
    runner = runner or FakeRunner()
    fetch = fetch or FakeFetcher()
    inspector = inspector or FakeInspector()
    manager = RepoManager(
        runner=runner,
        fetch=fetch,
        inspector=inspector,
        repo_dir=repo_dir,
    )
    return manager, runner, fetch, inspector


def copr_request(value: str = "owner/project") -> RepoRequest:
    return RepoRequest(kind=RepoKind.COPR, copr=value)


def url_request(
    name: str = "myrepo", baseurl: str = "https://example.com/repo"
) -> RepoRequest:
    return RepoRequest(kind=RepoKind.URL, name=name, baseurl=baseurl)


# -- preparation -----------------------------------------------------------


def test_prepare_copr_builds_a_plan_with_the_downloaded_key() -> None:
    manager, _runner, fetch, inspector = make_manager()

    plan = manager.prepare(copr_request())

    assert fetch.urls == [
        "https://download.copr.fedorainfracloud.org/results/owner/project/pubkey.gpg"
    ]
    assert inspector.keys == [b"KEY"]
    assert plan.repo_id == "copr:copr.fedorainfracloud.org:owner:project"
    assert plan.key_fingerprint == FINGERPRINT
    assert plan.key_id == "KEYID"
    assert plan.key_data == b"KEY"
    assert plan.command == (
        "pkexec",
        "dnf",
        "copr",
        "enable",
        "-y",
        "owner/project",
    )
    assert plan.repo_file.startswith("[copr:copr.fedorainfracloud.org:owner:project]\n")


def test_prepare_url_builds_its_file_and_key_location() -> None:
    manager, _runner, fetch, _inspector = make_manager()

    plan = manager.prepare(url_request())

    assert fetch.urls == ["https://example.com/repo/repodata/repomd.xml.key"]
    assert plan.repo_id == "myrepo"
    assert plan.name == "myrepo"
    assert plan.baseurl == "https://example.com/repo"
    assert plan.key_url == "https://example.com/repo/repodata/repomd.xml.key"
    assert plan.repo_file_name == "parcel-myrepo.repo"
    assert plan.command == ()
    assert "baseurl=https://example.com/repo\n" in plan.repo_file


def test_prepare_rejects_invalid_input_before_downloading() -> None:
    manager, _runner, fetch, _inspector = make_manager()

    with pytest.raises(ValueError):
        manager.prepare(copr_request("not-a-project"))

    assert fetch.urls == []


def test_prepare_rejects_an_unknown_request_kind() -> None:
    manager, _runner, fetch, _inspector = make_manager()

    with pytest.raises(ValueError, match="unknown repository kind"):
        manager.prepare(RepoRequest(kind="weird"))  # type: ignore[arg-type]

    assert fetch.urls == []


# -- installation ----------------------------------------------------------


def test_add_prefers_dnf_copr_and_does_not_write_files() -> None:
    manager, runner, _fetch, _inspector = make_manager()
    plan = manager.prepare(copr_request())

    manager.add(plan)

    assert runner.commands == [
        ("pkexec", "dnf", "copr", "enable", "-y", "owner/project")
    ]


def test_add_falls_back_to_a_repo_file_and_key_import(tmp_path: Path) -> None:
    runner = FakeRunner(
        fail_on=("pkexec", "dnf", "copr", "enable", "-y", "owner/project"),
        exit_code=1,
    )
    manager, _runner, _fetch, _inspector = make_manager(
        runner=runner, repo_dir=tmp_path
    )
    plan = manager.prepare(copr_request())

    manager.add(plan)

    assert [command[1] for command in runner.commands] == [
        "dnf",
        "rpmkeys",
        "install",
    ]
    assert runner.key_data == b"KEY"
    assert runner.repo_data == plan.repo_file
    assert runner.destination == str(
        tmp_path / "_copr:copr.fedorainfracloud.org:owner:project.repo"
    )


def test_add_does_not_fallback_when_authentication_was_dismissed() -> None:
    runner = FakeRunner(
        fail_on=("pkexec", "dnf", "copr", "enable", "-y", "owner/project"),
        exit_code=126,
    )
    manager, _runner, _fetch, _inspector = make_manager(runner=runner)
    plan = manager.prepare(copr_request())

    with pytest.raises(CommandError):
        manager.add(plan)

    assert len(runner.commands) == 1


def test_add_for_a_url_repo_imports_the_key_then_writes_the_file(
    tmp_path: Path,
) -> None:
    manager, runner, _fetch, _inspector = make_manager(repo_dir=tmp_path)
    plan = manager.prepare(url_request())

    manager.add(plan)

    assert [command[1] for command in runner.commands] == ["rpmkeys", "install"]
    assert runner.key_data == b"KEY"
    assert runner.repo_data == plan.repo_file
    assert runner.destination == str(tmp_path / "parcel-myrepo.repo")


def test_add_refuses_a_plan_without_key_material(tmp_path: Path) -> None:
    manager, runner, _fetch, _inspector = make_manager(repo_dir=tmp_path)
    plan = RepoPlan(
        request=url_request(),
        repo_id="myrepo",
        name="myrepo",
        baseurl="https://example.com/repo",
        key_url="https://example.com/repo/repodata/repomd.xml.key",
        key_fingerprint=FINGERPRINT,
        key_id="KEYID",
        repo_file_name="parcel-myrepo.repo",
        repo_file="[myrepo]\nenabled=1\n",
    )

    with pytest.raises(SigningKeyError, match="missing"):
        manager.add(plan)

    assert runner.commands == []
