"""Where to send a user who wants to read more about a package.

Pure URL construction: no I/O, no GTK. Only links that can be derived from
data Parcel actually has are offered; there is no point guessing.
"""

from __future__ import annotations

from urllib.parse import quote

from parcel.backend.models import Package

_FEDORA_PACKAGES = "https://packages.fedoraproject.org/pkgs/{name}/"
_FEDORA_SOURCE = "https://src.fedoraproject.org/rpms/{name}"
_COPR_BUILDS = "https://copr.fedorainfracloud.org/coprs/{owner}/{project}/builds/"

# Repos whose packages are the ones published on packages.fedoraproject.org.
_FEDORA_REPOS = frozenset({"fedora", "updates", "updates-testing"})


def copr_project(repo: str) -> tuple[str, str] | None:
    """``(owner, project)`` for a COPR repo id, else None.

    PackageKit ids look like ``copr:copr.fedorainfracloud.org:owner:project``;
    older repositories omit the host and use ``copr:owner:project``.
    """
    parts = repo.removeprefix("installed:").split(":")
    if parts[0] != "copr" or len(parts) < 3:
        return None
    return parts[-2], parts[-1]


def build_links(package: Package) -> tuple[tuple[str, str], ...]:
    """Ordered ``(label, url)`` pairs for the package detail view."""
    links: list[tuple[str, str]] = []
    if package.homepage:
        links.append(("Homepage", package.homepage))

    name = quote(package.name)
    project = copr_project(package.repo)
    if project is not None:
        owner, project_name = project
        links.append(
            (
                "Build page",
                _COPR_BUILDS.format(owner=quote(owner), project=quote(project_name)),
            )
        )
    elif package.repo.removeprefix("installed:") in _FEDORA_REPOS:
        links.append(("Source", _FEDORA_SOURCE.format(name=name)))
        links.append(("Fedora Packages", _FEDORA_PACKAGES.format(name=name)))

    return tuple(links)
