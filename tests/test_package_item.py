"""Tests for the GObject list item wrapper."""

from parcel.backend.models import Package
from parcel.ui.package_item import PackageItem


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "size": 2048,
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


def test_subtitle_combines_version_repo_and_size() -> None:
    item = PackageItem(make_package())
    assert item.subtitle == "141.0.3-1.fc44 \u00b7 updates \u00b7 2.0 KiB"


def test_version_text_override_is_used_for_updates() -> None:
    item = PackageItem(
        make_package(), version_text="141.0.3-1.fc44 \u2192 142.0-1.fc44"
    )
    assert item.subtitle.startswith("141.0.3-1.fc44 \u2192 142.0-1.fc44")


def test_unknown_size_is_left_out_of_the_subtitle() -> None:
    item = PackageItem(make_package(size=0))
    assert item.subtitle == "141.0.3-1.fc44 \u00b7 updates"


def test_setting_the_size_updates_and_notifies_the_subtitle() -> None:
    item = PackageItem(make_package(size=0))
    changes: list[str] = []
    item.connect("notify::subtitle", lambda *_: changes.append(item.subtitle))

    item.set_size(1024**2)

    assert item.size == 1024**2
    assert changes == ["141.0.3-1.fc44 \u00b7 updates \u00b7 1.0 MiB"]


def test_setting_the_same_size_does_not_notify() -> None:
    item = PackageItem(make_package(size=2048))
    changes: list[str] = []
    item.connect("notify::subtitle", lambda *_: changes.append(item.subtitle))

    item.set_size(2048)

    assert changes == []


def test_security_flag_is_exposed() -> None:
    assert PackageItem(make_package(), security=True).security
    assert not PackageItem(make_package()).security
