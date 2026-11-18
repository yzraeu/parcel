"""Tests for the PackageKit client, using fakes only — never live D-Bus."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from subprocess import run
from sys import executable
from typing import Any

import gi
import pytest

gi.require_version("PackageKitGlib", "1.0")

from gi.repository import GLib, PackageKitGlib  # noqa: E402

from parcel.backend.client import BackendError, PackageKitClient  # noqa: E402
from parcel.backend.models import (  # noqa: E402
    InstallReason,
    Package,
    Repo,
    RepoKind,
    RepoPlan,
    RepoRequest,
    Update,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakePackage:
    def __init__(
        self,
        name: str,
        version: str = "1.0-1.fc44",
        arch: str = "x86_64",
        repo: str = "updates",
        info: Any = PackageKitGlib.InfoEnum.AVAILABLE,
        summary: str = "summary",
    ) -> None:
        self.name = name
        self.version = version
        self.arch = arch
        self.repo = repo
        self.info = info
        self.summary = summary

    def get_id(self) -> str:
        return f"{self.name};{self.version};{self.arch};{self.repo}"

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return self.version

    def get_arch(self) -> str:
        return self.arch

    def get_summary(self) -> str:
        return self.summary

    def get_info(self) -> Any:
        return self.info


class FakeDetails:
    def __init__(
        self,
        package_id: str,
        size: int = 0,
        description: str = "",
        license: str = "",
        url: str = "",
    ) -> None:
        self.package_id = package_id
        self.size = size
        self.description = description
        self.license = license
        self.url = url

    def get_package_id(self) -> str:
        return self.package_id

    def get_size(self) -> int:
        return self.size

    def get_description(self) -> str:
        return self.description

    def get_license(self) -> str:
        return self.license

    def get_url(self) -> str:
        return self.url


class FakeFiles:
    def __init__(self, files: list[str]) -> None:
        self.files = files

    def get_files(self) -> list[str]:
        return self.files


class FakeUpdateDetail:
    def __init__(self, changelog: str) -> None:
        self.changelog = changelog

    def get_changelog(self) -> str:
        return self.changelog


class FakeRepoDetail:
    def __init__(self, repo_id: str, description: str, enabled: bool = True) -> None:
        self.repo_id = repo_id
        self.description = description
        self.enabled = enabled

    def get_id(self) -> str:
        return self.repo_id

    def get_description(self) -> str:
        return self.description

    def get_enabled(self) -> bool:
        return self.enabled


class FakeResults:
    def __init__(
        self,
        packages: list[FakePackage] | None = None,
        details: list[FakeDetails] | None = None,
        files: list[FakeFiles] | None = None,
        update_details: list[FakeUpdateDetail] | None = None,
        repo_details: list[FakeRepoDetail] | None = None,
        exit_code: Any = PackageKitGlib.ExitEnum.SUCCESS,
    ) -> None:
        self.packages = packages or []
        self.details = details or []
        self.files = files or []
        self.update_details = update_details or []
        self.repo_details = repo_details or []
        self.exit_code = exit_code

    def get_package_array(self) -> list[FakePackage]:
        return list(self.packages)

    def get_details_array(self) -> list[FakeDetails]:
        return list(self.details)

    def get_files_array(self) -> list[FakeFiles]:
        return list(self.files)

    def get_update_detail_array(self) -> list[FakeUpdateDetail]:
        return list(self.update_details)

    def get_repo_detail_array(self) -> list[FakeRepoDetail]:
        return list(self.repo_details)

    def get_exit_code(self) -> Any:
        return self.exit_code


class FakePkClient:
    def __init__(
        self,
        packages: list[FakePackage] | None = None,
        updates: list[FakePackage] | None = None,
        details: list[FakeDetails] | None = None,
        files: list[FakeFiles] | None = None,
        update_details: list[FakeUpdateDetail] | None = None,
        repo_details: list[FakeRepoDetail] | None = None,
        exit_code: Any = PackageKitGlib.ExitEnum.SUCCESS,
    ) -> None:
        self.packages = packages or []
        self.updates = updates or []
        self.details = details or []
        self.files = files or []
        self.update_details = update_details or []
        self.repo_details = repo_details or []
        self.exit_code = exit_code
        self.calls: list[tuple[str, ...]] = []

    def get_packages(self, *args: object) -> FakeResults:
        self.calls.append(("get_packages", *args))
        return FakeResults(self.packages)

    def get_updates(self, *args: object) -> FakeResults:
        self.calls.append(("get_updates", *args))
        return FakeResults(self.updates)

    def get_details(self, *args: object) -> FakeResults:
        self.calls.append(("get_details", *args))
        return FakeResults(details=self.details)

    def get_files(self, *args: object) -> FakeResults:
        self.calls.append(("get_files", *args))
        return FakeResults(files=self.files)

    def get_update_detail(self, *args: object) -> FakeResults:
        self.calls.append(("get_update_detail", *args))
        return FakeResults(update_details=self.update_details)

    def install_packages(self, *args: object) -> FakeResults:
        self.calls.append(("install_packages", *args))
        return FakeResults(exit_code=self.exit_code)

    def remove_packages(self, *args: object) -> FakeResults:
        self.calls.append(("remove_packages", *args))
        return FakeResults(exit_code=self.exit_code)

    def update_packages(self, *args: object) -> FakeResults:
        self.calls.append(("update_packages", *args))
        return FakeResults(exit_code=self.exit_code)

    def get_repo_list(self, *args: object) -> FakeResults:
        self.calls.append(("get_repo_list", *args))
        return FakeResults(repo_details=self.repo_details)

    def repo_enable(self, *args: object) -> FakeResults:
        self.calls.append(("repo_enable", *args))
        return FakeResults(exit_code=self.exit_code)

    def repo_remove(self, *args: object) -> FakeResults:
        self.calls.append(("repo_remove", *args))
        return FakeResults(exit_code=self.exit_code)


class FakeRpm:
    def __init__(
        self,
        sizes: dict[str, int] | None = None,
        install_date: datetime | None = datetime(2026, 11, 2, 9, 14),
        files: tuple[str, ...] = ("/usr/bin/thing",),
        required_by: tuple[str, ...] = ("nautilus",),
        changelog: str = "Maintainer - 1.0\n- fixed things",
    ) -> None:
        self.sizes = sizes or {}
        self._install_date = install_date
        self._files = files
        self._required_by = required_by
        self._changelog = changelog

    def installed_sizes(self) -> dict[str, int]:
        return dict(self.sizes)

    def install_date(self, _name: str) -> datetime | None:
        return self._install_date

    def files(self, _name: str) -> tuple[str, ...]:
        return self._files

    def required_by(self, _name: str) -> tuple[str, ...]:
        return self._required_by

    def changelog(self, _name: str) -> str:
        return self._changelog


class FakeHistory:
    def __init__(self, reason: InstallReason | None = InstallReason.USER) -> None:
        self.reason = reason

    def install_reason(self, _name: str) -> InstallReason | None:
        return self.reason


class FakeRepoManager:
    def __init__(self, plan: RepoPlan | None = None) -> None:
        self.plan = plan
        self.prepared: list[RepoRequest] = []
        self.added: list[RepoPlan] = []

    def prepare(self, request: RepoRequest) -> RepoPlan:
        self.prepared.append(request)
        if self.plan is None:
            raise AssertionError("no plan configured")
        return self.plan

    def add(self, plan: RepoPlan) -> None:
        self.added.append(plan)


def make_plan() -> RepoPlan:
    return RepoPlan(
        request=RepoRequest(kind=RepoKind.URL, name="myrepo", baseurl="https://x"),
        repo_id="myrepo",
        name="myrepo",
        baseurl="https://x",
        key_url="https://x/key",
        key_fingerprint="0123456789ABCDEF0123456789ABCDEF01234567",
        key_id="KEYID",
        repo_file_name="parcel-myrepo.repo",
        repo_file="[myrepo]\n",
        key_data=b"KEY",
    )


def installed(name: str, version: str = "1.0-1.fc44") -> FakePackage:
    return FakePackage(
        name,
        version=version,
        repo="installed:updates",
        info=PackageKitGlib.InfoEnum.INSTALLED,
    )


def available(name: str, version: str = "2.0-1.fc44") -> FakePackage:
    return FakePackage(name, version=version, repo="updates")


def make_client(**kwargs: Any) -> tuple[PackageKitClient, FakePkClient]:
    fake = FakePkClient(**kwargs)
    return (
        PackageKitClient(
            fake,
            rpm_db=FakeRpm(sizes={"firefox": 2048}),
            history=FakeHistory(),
        ),
        fake,
    )


# -- listings --------------------------------------------------------------


def test_catalog_splits_installed_and_available_with_sizes() -> None:
    packages = [
        installed("firefox"),
        available("gimp"),
        FakePackage("bash", arch="x86_64", info=PackageKitGlib.InfoEnum.INSTALLED),
        FakePackage("source", arch="src", info=PackageKitGlib.InfoEnum.AVAILABLE),
    ]
    client, _ = make_client(packages=packages)

    installed_packages, available_packages = client.catalog()

    assert [p.name for p in installed_packages] == ["bash", "firefox"]
    assert [p.name for p in available_packages] == ["gimp"]
    assert installed_packages[1].size == 2048
    assert installed_packages[1].repo == "installed:updates"
    assert installed_packages[1].installed
    assert not available_packages[0].installed


def test_catalog_fetches_once_and_invalidate_refetches() -> None:
    client, fake = make_client(packages=[installed("firefox")])

    client.list_installed()
    client.list_available()
    assert len(fake.calls) == 1

    client.invalidate()
    client.list_installed()
    assert len(fake.calls) == 2


def test_catalog_keeps_the_newest_version_per_name_and_arch() -> None:
    client, _ = make_client(
        packages=[
            available("gimp", "2.0-1.fc44"),
            available("gimp", "10.0-1.fc44"),
            available("gimp", "3.0-1.fc44"),
        ]
    )

    assert [p.version for p in client.list_available()] == ["10.0-1.fc44"]


def test_list_updates_marks_security_and_reports_installed_versions() -> None:
    client, _ = make_client(
        updates=[
            FakePackage(
                "firefox",
                version="2.0-1.fc44",
                info=PackageKitGlib.InfoEnum.SECURITY,
            ),
            available("nautilus", "3.0-1.fc44"),
        ]
    )

    updates = client.list_updates({"firefox": "1.0-1.fc44"})

    assert all(isinstance(update, Update) for update in updates)
    assert [(u.name, u.installed_version, u.security) for u in updates] == [
        ("firefox", "1.0-1.fc44", True),
        ("nautilus", None, False),
    ]


def test_list_updates_looks_up_installed_versions_when_not_given() -> None:
    client, _ = make_client(
        packages=[installed("firefox", "1.0-1.fc44")],
        updates=[available("firefox", "2.0-1.fc44")],
    )

    assert client.list_updates()[0].installed_version == "1.0-1.fc44"


def test_list_updates_dedupes_newer_versions() -> None:
    client, _ = make_client(
        updates=[
            available("kernel", "6.1-1"),
            available("kernel", "6.10-1"),
            available("kernel", "6.2-1"),
        ]
    )

    assert [(u.name, u.new_version) for u in client.list_updates({})] == [
        ("kernel", "6.10-1")
    ]


# -- details ---------------------------------------------------------------


def test_detail_for_an_installed_package_merges_packagekit_and_rpm_data() -> None:
    client, _ = make_client(
        details=[
            FakeDetails(
                "bash;5.0;x86_64;installed:fedora",
                size=4096,
                description="The GNU shell",
                license="GPL-3.0-or-later",
                url="https://www.gnu.org/software/bash",
            )
        ],
        files=[FakeFiles(["/usr/bin/bash", "/etc/bashrc"])],
    )
    installed_package = client._to_package(installed("bash"), True, 0)

    detail = client.get_detail(installed_package)

    assert detail.description == "The GNU shell"
    assert detail.license == "GPL-3.0-or-later"
    assert detail.homepage == "https://www.gnu.org/software/bash"
    assert detail.size == 4096
    assert detail.files == ("/usr/bin/bash", "/etc/bashrc")
    assert detail.install_date == datetime(2026, 11, 2, 9, 14)
    assert detail.install_reason is InstallReason.USER
    assert detail.required_by == ("nautilus",)
    assert detail.changelog.startswith("Maintainer - 1.0")


def test_detail_falls_back_to_the_summary_without_a_description() -> None:
    client, _ = make_client(details=[])
    package = client._to_package(available("gimp"), False, 0)

    assert client.get_detail(package).description == "summary"


def test_detail_for_an_available_package_uses_the_update_changelog() -> None:
    client, fake = make_client(
        update_details=[FakeUpdateDetail("- upstream fix")],
    )
    package = client._to_package(available("gimp"), False, 0)

    detail = client.get_detail(package)

    assert detail.changelog == "- upstream fix"
    assert detail.files == ()
    assert detail.install_date is None
    assert detail.install_reason is None
    assert detail.required_by == ()
    assert "get_files" not in [call[0] for call in fake.calls]


def test_detail_tolerates_a_packagekit_error_for_the_changelog() -> None:
    class FailingClient(FakePkClient):
        def get_update_detail(self, *args: object) -> FakeResults:
            raise GLib.Error("no update detail")

    client = PackageKitClient(FailingClient(), rpm_db=FakeRpm(), history=FakeHistory())

    detail = client.get_detail(client._to_package(available("gimp"), False, 0))

    assert detail.changelog == ""


def test_sizes_returns_sizes_keyed_by_package_id() -> None:
    client, fake = make_client(
        details=[
            FakeDetails("gimp;2.0;x86_64;fedora", size=1024),
            FakeDetails("htop;3.0;x86_64;fedora", size=0),
        ]
    )
    packages = [client._to_package(available("gimp"), False, 0)]
    packages.append(client._to_package(available("htop"), False, 0))

    assert client.sizes(packages) == {"gimp;2.0;x86_64;fedora": 1024}
    assert fake.calls[-1][0] == "get_details"


def test_sizes_of_nothing_does_not_query_packagekit() -> None:
    client, fake = make_client()
    assert client.sizes([]) == {}
    assert fake.calls == []


# -- transactions ----------------------------------------------------------


def test_install_runs_a_transaction_and_invalidates_the_catalog() -> None:
    client, fake = make_client(packages=[installed("firefox")])
    client.list_installed()
    package = client._to_package(available("gimp"), False, 0)

    client.install(package)

    method, _flags, ids, *_ = fake.calls[-1]
    assert method == "install_packages"
    assert ids == ["gimp;2.0-1.fc44;x86_64;updates"]

    client.list_installed()
    assert [call[0] for call in fake.calls].count("get_packages") == 2


def test_remove_disables_dependency_cascades() -> None:
    client, fake = make_client()
    package = client._to_package(installed("firefox"), True, 0)

    client.remove(package)

    method, _flags, ids, allow_deps, autoremove, *_ = fake.calls[-1]
    assert method == "remove_packages"
    assert ids == ["firefox;1.0-1.fc44;x86_64;installed:updates"]
    assert allow_deps is False
    assert autoremove is False


def test_update_sends_every_package_in_one_transaction() -> None:
    client, fake = make_client()
    packages = [
        client._to_package(available("firefox", "2.0-1.fc44"), False, 0),
        client._to_package(available("nautilus", "3.0-1.fc44"), False, 0),
    ]

    client.update(packages)

    method, _flags, ids, *_ = fake.calls[-1]
    assert method == "update_packages"
    assert ids == [
        "firefox;2.0-1.fc44;x86_64;updates",
        "nautilus;3.0-1.fc44;x86_64;updates",
    ]


def test_update_rejects_an_empty_package_list() -> None:
    client, fake = make_client()
    with pytest.raises(ValueError):
        client.update([])
    assert fake.calls == []


def test_failed_transaction_raises_and_keeps_the_catalog() -> None:
    client, fake = make_client(
        packages=[installed("firefox")],
        exit_code=PackageKitGlib.ExitEnum.FAILED,
    )
    client.list_installed()
    package = client._to_package(installed("firefox"), True, 0)

    with pytest.raises(BackendError):
        client.remove(package)

    client.list_installed()
    assert [call[0] for call in fake.calls].count("get_packages") == 1


def test_transactions_require_a_packagekit_id() -> None:
    client, _ = make_client()
    package = Package(name="gimp", version="2.0", repo="fedora")

    with pytest.raises(BackendError):
        client.install(package)


# -- repositories ----------------------------------------------------------


def test_list_repos_maps_details_and_puts_system_repos_first() -> None:
    client, fake = make_client(
        repo_details=[
            FakeRepoDetail("rpmfusion-free", "RPM Fusion Free", enabled=False),
            FakeRepoDetail("updates", "Fedora Updates", enabled=True),
            FakeRepoDetail(
                "copr:copr.fedorainfracloud.org:owner:project", "A COPR", enabled=True
            ),
            FakeRepoDetail("fedora", "Fedora", enabled=True),
        ]
    )

    repos = client.list_repos()

    assert [repo.repo_id for repo in repos] == [
        "fedora",
        "updates",
        "copr:copr.fedorainfracloud.org:owner:project",
        "rpmfusion-free",
    ]
    assert [repo.system for repo in repos] == [True, True, False, False]
    assert repos[0].name == "Fedora"
    assert not repos[3].enabled
    assert repos[2].copr == "copr:copr.fedorainfracloud.org:owner:project"
    assert fake.calls[-1][0] == "get_repo_list"


def test_set_repo_enabled_asks_packagekit_and_drops_the_catalog() -> None:
    client, fake = make_client(packages=[installed("firefox")])
    client.list_installed()
    repo = Repo(repo_id="updates", name="Fedora Updates")

    client.set_repo_enabled(repo, False)

    method, repo_id, enabled, *_ = fake.calls[-1]
    assert method == "repo_enable"
    assert repo_id == "updates"
    assert enabled is False

    client.list_installed()
    assert [call[0] for call in fake.calls].count("get_packages") == 2


def test_remove_repo_never_autoremoves_packages() -> None:
    client, fake = make_client()
    repo = Repo(repo_id="rpmfusion-free", name="RPM Fusion Free")

    client.remove_repo(repo)

    method, _flags, repo_id, autoremove, *_ = fake.calls[-1]
    assert method == "repo_remove"
    assert repo_id == "rpmfusion-free"
    assert autoremove is False


def test_remove_repo_refuses_a_system_repo() -> None:
    client, fake = make_client()

    with pytest.raises(BackendError):
        client.remove_repo(Repo(repo_id="fedora", name="Fedora", system=True))

    assert fake.calls == []


def test_failed_repo_change_raises() -> None:
    client, _ = make_client(exit_code=PackageKitGlib.ExitEnum.FAILED)

    with pytest.raises(BackendError):
        client.set_repo_enabled(Repo(repo_id="updates", name="Updates"), False)

    with pytest.raises(BackendError):
        client.remove_repo(Repo(repo_id="rpmfusion-free", name="RPM Fusion"))


def test_repo_preparation_and_adding_go_through_the_manager() -> None:
    manager = FakeRepoManager(plan=make_plan())
    fake = FakePkClient()
    client = PackageKitClient(
        fake, rpm_db=FakeRpm(), history=FakeHistory(), repos=manager
    )
    request = RepoRequest(kind=RepoKind.URL, name="myrepo", baseurl="https://x")

    plan = client.prepare_repo(request)
    client.add_repo(plan)

    assert manager.prepared == [request]
    assert manager.added == [plan]
    assert plan is manager.plan


# -- layering --------------------------------------------------------------


def test_backend_modules_do_not_pull_in_gtk() -> None:
    code = """
import sys
import parcel.backend
import parcel.backend.client

loaded = {"gi.repository.Gtk", "gi.repository.Adw"}
assert not loaded & set(sys.modules), sorted(loaded & set(sys.modules))
"""
    result = run(
        [executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
