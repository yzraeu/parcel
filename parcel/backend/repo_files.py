"""Build and validate dnf ``.repo`` files without touching the filesystem.

Everything here is pure: turn what the user typed into a repo id, a file name,
and the file body. Privileges, downloads, and key inspection live elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# The two repositories Fedora itself owns. They may be switched off, but
# removing them would leave the system without its distribution repos.
SYSTEM_REPO_IDS = frozenset({"fedora", "updates"})

_COPR_HOST = "copr.fedorainfracloud.org"
_COPR_KEY_URL = (
    "https://download.copr.fedorainfracloud.org/results/{owner}/{project}/pubkey.gpg"
)
_COPR_BASEURL = (
    "https://copr-be.cloud.fedoraproject.org/results/{owner}/{project}/"
    "fedora-$releasever-$basearch/"
)
_COPR_URL_PREFIX = "https://copr.fedorainfracloud.org/coprs/"

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_COPR_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
_SAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass(frozen=True, slots=True)
class CoprProject:
    """A validated ``owner/project`` pair."""

    owner: str
    project: str

    @property
    def repo_id(self) -> str:
        return f"copr:{_COPR_HOST}:{self.owner}:{self.project}"

    @property
    def name(self) -> str:
        return f"Copr repo for {self.project} owned by {self.owner}"

    @property
    def baseurl(self) -> str:
        return _COPR_BASEURL.format(owner=self.owner, project=self.project)

    @property
    def key_url(self) -> str:
        return _COPR_KEY_URL.format(owner=self.owner, project=self.project)

    @property
    def file_name(self) -> str:
        # dnf copr uses this exact spelling, colons included.
        return f"_copr:{_COPR_HOST}:{self.owner}:{self.project}.repo"

    @property
    def command(self) -> tuple[str, ...]:
        """The preferred COPR path: let dnf write the file and import the key."""
        return (
            "pkexec",
            "dnf",
            "copr",
            "enable",
            "-y",
            f"{self.owner}/{self.project}",
        )

    def repo_file(self) -> str:
        return _repo_file(
            repo_id=self.repo_id,
            name=self.name,
            baseurl=self.baseurl,
            key_url=self.key_url,
            extra=(
                "type=rpm-md",
                "skip_if_unavailable=True",
                "enabled_metadata=1",
            ),
        )


def is_system_repo(repo_id: str) -> bool:
    return repo_id in SYSTEM_REPO_IDS


def parse_copr(value: str) -> CoprProject:
    """Accept ``owner/project`` and COPR's own copr URL."""
    text = value.strip()
    if text.startswith(_COPR_URL_PREFIX):
        trailing = text[len(_COPR_URL_PREFIX) :]
        parts = [part for part in trailing.split("/") if part]
        if len(parts) == 2:
            text = f"{parts[0]}/{parts[1]}"
    match = _COPR_PATTERN.match(text)
    if match is None:
        raise ValueError("type a COPR project as owner/project")
    return CoprProject(owner=match.group(1), project=match.group(2))


def validate_repo_name(name: str) -> str:
    """Repo ids end up in dnf configuration and in a file name."""
    text = name.strip()
    if not text:
        raise ValueError("the repository needs a name")
    if not _NAME_PATTERN.match(text):
        raise ValueError(
            "the repository name may only contain letters, digits, '.', '_', ':' "
            "and '-'"
        )
    return text


def validate_baseurl(baseurl: str) -> str:
    text = baseurl.strip().rstrip("/")
    if not text:
        raise ValueError("the repository needs a base URL")
    if any(character.isspace() for character in text):
        raise ValueError("the base URL cannot contain spaces or newlines")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("the base URL must start with http:// or https://")
    if parsed.query or parsed.fragment:
        raise ValueError("the base URL cannot contain a query or a fragment")
    return text


def url_key_url(baseurl: str) -> str:
    """Where a plain repository publishes the key that signs its metadata."""
    return f"{validate_baseurl(baseurl)}/repodata/repomd.xml.key"


def url_repo_file(name: str, baseurl: str, key_url: str) -> str:
    repo_id = validate_repo_name(name)
    return _repo_file(
        repo_id=repo_id,
        name=repo_id,
        baseurl=validate_baseurl(baseurl),
        key_url=key_url,
        extra=("type=rpm-md", "skip_if_unavailable=True"),
    )


def url_file_name(name: str) -> str:
    """A Parcel-owned file name so adding a repo cannot overwrite dnf's files."""
    repo_id = validate_repo_name(name)
    safe = _SAFE_FILE_CHARS.sub("_", repo_id)
    return f"parcel-{safe}.repo"


def _repo_file(
    repo_id: str,
    name: str,
    baseurl: str,
    key_url: str,
    extra: tuple[str, ...],
) -> str:
    lines = [
        f"[{repo_id}]",
        f"name={name}",
        f"baseurl={baseurl}",
        "enabled=1",
        "gpgcheck=1",
        "repo_gpgcheck=0",
        f"gpgkey={key_url}",
        *extra,
    ]
    return "\n".join(lines) + "\n"
