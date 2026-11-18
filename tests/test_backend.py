"""Tests for the PackageKit client, using fakes only — never live D-Bus."""

from __future__ import annotations

from pathlib import Path
from subprocess import run
from sys import executable

import gi

gi.require_version("PackageKitGlib", "1.0")

from gi.repository import PackageKitGlib  # noqa: E402

from parcel.backend import client as client_module  # noqa: E402
from parcel.backend.client import PackageKitClient  # noqa: E402
from parcel.backend.models import Update  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakePackage:
    def __init__(
        self,
        name: str,
        version: str = "1.0-1.fc44",
        arch: str = "x86_64",
        repo: str = "updates",
        info: int = PackageKitGlib.InfoEnum.AVAILABLE,
        summary: str = "summary",
        package_id: str | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.arch = arch
        self.repo = repo
        self.info = info
        self.summary = summary
        self.package_id = package_id

    def get_id(self) -> str:
        return self.package_id or (
            f"{self.name};{self.version};{self.arch};{self.repo}"
        )

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return self.version

    def get_arch(self) -> str:
        return self.arch

    def get_summary(self) -> str:
        return self.summary

    def get_info(self) -> int:
        return self.info


class FakeResults:
    def __init__(self, packages: list[FakePackage]) -> None:
        self.packages = packages

    def get_package_array(self) -> list[FakePackage]:
        return list(self.packages)


class FakePkClient:
    def __init__(self, packages: list[FakePackage] | None = None) -> None:
        self.packages = packages or []
        self.calls: list[tuple[str, ...]] = []

    def get_packages(self, *args: object) -> FakeResults:
        self.calls.append(("get_packages", *args))
        return FakeResults(self.packages)

    def search_names(self, *args: object) -> FakeResults:
        self.calls.append(("search_names", *args))
        return FakeResults(self.packages)

    def get_updates(self, *args: object) -> FakeResults:
        self.calls.append(("get_updates", *args))
        return FakeResults(self.packages)


def test_list_installed_maps_packages_and_asks_for_installed_only() -> None:
    fake = FakePkClient(
        [
            FakePackage(
                "firefox",
                version="141.0.3-1.fc44",
                info=PackageKitGlib.InfoEnum.INSTALLED,
            )
        ]
    )
    packages = PackageKitClient(fake).list_installed()

    assert len(packages) == 1
    package = packages[0]
    assert package.name == "firefox"
    assert package.version == "141.0.3-1.fc44"
    assert package.repo == "updates"
    assert package.arch == "x86_64"
    assert package.summary == "summary"
    assert package.installed is True

    method, filters, *_ = fake.calls[0]
    assert method == "get_packages"
    assert filters & PackageKitGlib.FilterEnum.INSTALLED
    assert filters & PackageKitGlib.FilterEnum.NEWEST


def test_search_passes_the_query_and_maps_available_packages() -> None:
    fake = FakePkClient([FakePackage("gimp", repo="fedora")])
    packages = PackageKitClient(fake).search("  gimp  ")

    assert [(p.name, p.repo, p.installed) for p in packages] == [
        ("gimp", "fedora", False)
    ]
    method, filters, values, *_ = fake.calls[0]
    assert method == "search_names"
    assert values == ["gimp"]
    assert filters & PackageKitGlib.FilterEnum.NEWEST
    assert filters & PackageKitGlib.FilterEnum.NOT_SOURCE


def test_blank_search_does_not_query_packagekit() -> None:
    fake = FakePkClient([FakePackage("gimp")])
    assert PackageKitClient(fake).search("   ") == []
    assert fake.calls == []


def test_list_updates_flags_security_updates() -> None:
    fake = FakePkClient(
        [
            FakePackage(
                "firefox",
                version="142.0-1.fc44",
                info=PackageKitGlib.InfoEnum.SECURITY,
            ),
            FakePackage("nautilus", version="48.3-1.fc44"),
        ]
    )
    updates = PackageKitClient(fake).list_updates()

    assert [update.name for update in updates] == ["firefox", "nautilus"]
    assert all(isinstance(update, Update) for update in updates)
    assert updates[0].security is True
    assert updates[0].new_version == "142.0-1.fc44"
    assert updates[1].security is False
    assert fake.calls[0][0] == "get_updates"


def test_malformed_package_id_yields_empty_repo_instead_of_crashing() -> None:
    fake = FakePkClient([FakePackage("gimp", package_id="gimp")])
    assert PackageKitClient(fake).search("gimp")[0].repo == ""


def test_default_constructor_uses_the_lazy_packagekit_client(
    monkeypatch,
) -> None:
    fake = FakePkClient([FakePackage("gimp")])
    monkeypatch.setattr(client_module, "_new_pk_client", lambda: fake)

    assert [package.name for package in PackageKitClient().search("gimp")] == ["gimp"]
    assert fake.calls


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
