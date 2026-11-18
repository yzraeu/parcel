"""Tests for turning user input into dnf repository files."""

from __future__ import annotations

import pytest

from parcel.backend.repo_files import (
    SYSTEM_REPO_IDS,
    is_system_repo,
    parse_copr,
    url_file_name,
    url_key_url,
    url_repo_file,
    validate_baseurl,
    validate_repo_name,
)


def test_parse_copr_accepts_owner_project() -> None:
    project = parse_copr("yzraeu/starship")

    assert project.owner == "yzraeu"
    assert project.project == "starship"
    assert project.repo_id == "copr:copr.fedorainfracloud.org:yzraeu:starship"
    assert project.name == "Copr repo for starship owned by yzraeu"
    assert project.key_url == (
        "https://download.copr.fedorainfracloud.org/results/yzraeu/starship/pubkey.gpg"
    )
    assert project.baseurl.startswith(
        "https://copr-be.cloud.fedoraproject.org/results/yzraeu/starship/"
    )
    assert project.file_name == ("_copr:copr.fedorainfracloud.org:yzraeu:starship.repo")
    assert project.command == (
        "pkexec",
        "dnf",
        "copr",
        "enable",
        "-y",
        "yzraeu/starship",
    )


def test_parse_copr_accepts_a_copr_url() -> None:
    project = parse_copr("https://copr.fedorainfracloud.org/coprs/owner/project/")

    assert (project.owner, project.project) == ("owner", "project")


@pytest.mark.parametrize(
    "value",
    ["", "owner", "owner/project/extra", "owner project", "https://example.com/x"],
)
def test_parse_copr_rejects_anything_else(value: str) -> None:
    with pytest.raises(ValueError, match="owner/project"):
        parse_copr(value)


def test_copr_repo_file_enables_the_repo_and_checks_gpg() -> None:
    project = parse_copr("owner/project")

    content = project.repo_file()

    assert content.startswith("[copr:copr.fedorainfracloud.org:owner:project]\n")
    assert f"baseurl={project.baseurl}\n" in content
    assert "enabled=1\n" in content
    assert "gpgcheck=1\n" in content
    assert f"gpgkey={project.key_url}\n" in content
    assert content.endswith("\n")


def test_validate_repo_name_accepts_dnf_style_ids() -> None:
    assert validate_repo_name(" myrepo ") == "myrepo"
    assert validate_repo_name("copr:owner:project") == "copr:owner:project"


@pytest.mark.parametrize("name", ["", "   ", "with space", "brackets[", "a\nb"])
def test_validate_repo_name_rejects_unsafe_ids(name: str) -> None:
    with pytest.raises(ValueError):
        validate_repo_name(name)


def test_validate_baseurl_strips_the_trailing_slash() -> None:
    assert validate_baseurl(" https://example.com/repo/ ") == (
        "https://example.com/repo"
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "/srv/repo",
        "ftp://example.com/repo",
        "https://",
        "https://example.com/repo?x=1",
        "https://example.com/repo#frag",
        "https://example.com/a b",
    ],
)
def test_validate_baseurl_rejects_unusable_values(url: str) -> None:
    with pytest.raises(ValueError):
        validate_baseurl(url)


def test_url_key_url_points_at_the_repodata_key() -> None:
    assert url_key_url("https://example.com/repo/") == (
        "https://example.com/repo/repodata/repomd.xml.key"
    )


def test_url_repo_file_uses_the_name_and_key() -> None:
    content = url_repo_file(
        "myrepo",
        "https://example.com/repo",
        "https://example.com/repo/repodata/repomd.xml.key",
    )

    assert content.startswith("[myrepo]\n")
    assert "name=myrepo\n" in content
    assert "baseurl=https://example.com/repo\n" in content
    assert "enabled=1\n" in content
    assert "gpgcheck=1\n" in content
    assert "gpgkey=https://example.com/repo/repodata/repomd.xml.key\n" in content


def test_url_file_name_is_owned_by_parcel() -> None:
    assert url_file_name("myrepo") == "parcel-myrepo.repo"
    assert url_file_name("vendor:repo") == "parcel-vendor_repo.repo"


def test_only_the_distribution_repos_are_system() -> None:
    assert set(SYSTEM_REPO_IDS) == {"fedora", "updates"}
    assert is_system_repo("fedora")
    assert is_system_repo("updates")
    assert not is_system_repo("rpmfusion-free")
    assert not is_system_repo("updates-testing")
