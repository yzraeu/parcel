"""Tests for package link construction."""

from parcel.backend.links import build_links, copr_project
from parcel.backend.models import Package


def make_package(**overrides: object) -> Package:
    data: dict[str, object] = {
        "name": "firefox",
        "version": "141.0.3-1.fc44",
        "repo": "updates",
        "homepage": "https://www.mozilla.org/firefox/",
    }
    data.update(overrides)
    return Package(**data)  # type: ignore[arg-type]


def test_copr_project_parses_current_and_legacy_ids() -> None:
    assert copr_project("copr:copr.fedorainfracloud.org:yzraeu:starship") == (
        "yzraeu",
        "starship",
    )
    assert copr_project("installed:copr:owner:project") == ("owner", "project")
    assert copr_project("fedora") is None
    assert copr_project("copr:") is None


def test_fedora_package_links_to_source_and_packages_page() -> None:
    assert build_links(make_package()) == (
        ("Homepage", "https://www.mozilla.org/firefox/"),
        ("Source", "https://src.fedoraproject.org/rpms/firefox"),
        ("Fedora Packages", "https://packages.fedoraproject.org/pkgs/firefox/"),
    )


def test_copr_package_links_to_its_build_page_instead() -> None:
    links = build_links(make_package(repo="copr:copr.fedorainfracloud.org:me:tool"))

    assert links == (
        ("Homepage", "https://www.mozilla.org/firefox/"),
        (
            "Build page",
            "https://copr.fedorainfracloud.org/coprs/me/tool/builds/",
        ),
    )


def test_third_party_repo_gets_no_fedora_package_links() -> None:
    assert build_links(make_package(repo="google-chrome-canary", homepage="")) == ()


def test_names_are_escaped_in_urls() -> None:
    links = build_links(make_package(name="perl(Foo)", homepage=""))

    assert ("Source", "https://src.fedoraproject.org/rpms/perl%28Foo%29") in links
