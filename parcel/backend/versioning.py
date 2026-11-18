"""Version comparison and newest-version selection.

PackageKit's listing filters cannot be trusted (some builds ignore them), so
the client lists everything and reduces duplicates here. Comparing rpm
versions by string is wrong (``10`` sorts before ``9``), hence rpm's own
algorithm.
"""

from __future__ import annotations

from collections.abc import Iterable

import rpm

from parcel.backend.models import Package


def parse_evr(version: str) -> tuple[str, str, str]:
    """Split ``[epoch:]version[-release]`` into its three parts."""
    epoch, separator, rest = version.partition(":")
    if not separator:
        epoch, rest = "0", version
    version_part, separator, release = rest.rpartition("-")
    if not separator:
        return epoch, rest, ""
    return epoch, version_part, release


def compare(left: str, right: str) -> int:
    """Negative, zero, or positive, as ``left`` sorts before/with/after right."""
    return rpm.labelCompare(parse_evr(left), parse_evr(right))


def dedupe_latest(packages: Iterable[Package]) -> list[Package]:
    """Keep the newest version of each ``(name, arch)`` pair.

    Ties keep the first package seen.
    """
    newest: dict[tuple[str, str], Package] = {}
    for package in packages:
        key = (package.name, package.arch)
        current = newest.get(key)
        if current is None or compare(package.version, current.version) > 0:
            newest[key] = package
    return list(newest.values())


def sort_packages(packages: Iterable[Package]) -> list[Package]:
    """Alphabetical by name, then architecture, for stable listings."""
    return sorted(packages, key=lambda package: (package.name.casefold(), package.arch))
