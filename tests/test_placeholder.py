"""Tests for the placeholder datasets."""

from parcel.backend.models import Package, Update
from parcel.ui import placeholder


def test_installed_placeholder_is_installed() -> None:
    packages = placeholder.installed()
    assert packages
    assert all(isinstance(package, Package) for package in packages)
    assert all(package.installed for package in packages)


def test_available_placeholder_is_not_installed() -> None:
    packages = placeholder.available()
    assert packages
    assert all(not package.installed for package in packages)


def test_placeholder_names_are_unique_per_tab() -> None:
    for packages in (placeholder.installed(), placeholder.available()):
        names = [package.name for package in packages]
        assert len(names) == len(set(names))


def test_updates_point_at_installed_packages() -> None:
    installed_names = {package.name for package in placeholder.installed()}
    updates = placeholder.updates()
    assert updates
    assert all(isinstance(update, Update) for update in updates)
    assert {update.name for update in updates} <= installed_names
    assert all(update.installed_version for update in updates)
    assert any(update.security for update in updates)


def test_installed_rows_carry_detail_data() -> None:
    assert all(
        package.description and package.files for package in placeholder.installed()
    )
