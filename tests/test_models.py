"""Tests for the plain data models."""

from datetime import datetime

import pytest

from parcel.backend.models import (
    InstallReason,
    Package,
    Repo,
    Update,
    format_size,
)


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "size": 2048,
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024**2, "1.0 MiB"),
        (1024**3, "1.0 GiB"),
        (1024**4, "1.0 TiB"),
    ],
)
def test_format_size(size: int, text: str) -> None:
    assert format_size(size) == text


def test_format_size_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        format_size(-1)


def test_size_text_uses_format_size() -> None:
    assert make_package(size=1024**2).size_text == "1.0 MiB"


def test_unknown_size_is_not_shown_as_zero_bytes() -> None:
    assert make_package(size=0).size_text == "unknown"


def test_repo_label_shortens_copr_repositories() -> None:
    assert (
        make_package(repo="copr:copr.fedorainfracloud.org:yzraeu:starship").repo_label
        == "copr:yzraeu/starship"
    )
    assert make_package(repo="copr:owner:project").repo_label == "copr:owner/project"


def test_repo_label_strips_installed_prefix() -> None:
    assert make_package(repo="installed:updates").repo_label == "updates"
    assert make_package(repo="installed:copr:x:y:z").repo_label == "copr:y/z"


def test_repo_label_falls_back_to_unknown() -> None:
    assert make_package(repo="").repo_label == "unknown"
    assert make_package(repo="copr:").repo_label == "copr:"


def test_install_reason_text() -> None:
    assert make_package().install_reason_text == "unknown"
    assert (
        make_package(install_reason=InstallReason.DEPENDENCY).install_reason_text
        == "installed as a dependency"
    )


def test_required_by_text() -> None:
    assert make_package().required_by_text == "Nothing depends on it"
    package = make_package(required_by=("gnome-shell", "nautilus"))
    assert package.required_by_text == "gnome-shell, nautilus"


def test_files_text_preview_counts_hidden_entries() -> None:
    assert make_package().files_text == "No file list available"
    assert make_package(files=("/usr/bin/a",)).files_text == "/usr/bin/a"
    files = tuple(f"/usr/bin/f{index}" for index in range(5))
    assert make_package(files=files).files_text == (
        "/usr/bin/f0, /usr/bin/f1, /usr/bin/f2 (+2 more)"
    )


def test_matches_searches_name_summary_repo_and_description() -> None:
    package = make_package(
        name="firefox",
        summary="Web browser",
        repo="updates",
        description="Built on Gecko.",
    )
    assert package.matches("fire")
    assert package.matches("BROWSER")
    assert package.matches("updates")
    assert package.matches("gecko")
    assert not package.matches("gimp")


def test_empty_query_matches_everything() -> None:
    assert make_package().matches("   ")


def test_package_id_defaults_to_empty() -> None:
    assert make_package().package_id == ""
    assert make_package(package_id="gimp;1;x86_64;fedora").package_id.endswith("fedora")


def test_repo_removability_follows_system_flag() -> None:
    assert not Repo(repo_id="fedora", name="Fedora", system=True).removable
    assert Repo(repo_id="my-repo", name="Mine").removable


def test_update_versions_and_security_matching() -> None:
    update = Update(
        package=make_package(version="142.0-1.fc44"),
        installed_version="141.0.3-1.fc44",
        security=True,
    )
    assert update.name == "firefox"
    assert update.new_version == "142.0-1.fc44"
    assert update.version_text == "141.0.3-1.fc44 \u2192 142.0-1.fc44"
    assert update.matches("security")
    assert update.matches("firefox")


def test_update_without_installed_version_shows_new_version() -> None:
    update = Update(package=make_package(version="142.0-1.fc44"))
    assert update.version_text == "142.0-1.fc44"
    assert not update.matches("security")


def test_install_date_is_kept_verbatim() -> None:
    installed_at = datetime(2026, 11, 2, 9, 14)
    assert make_package(install_date=installed_at).install_date == installed_at
