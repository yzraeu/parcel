"""Prepare and install new repositories.

The add flow has two halves on purpose. :meth:`RepoManager.prepare` downloads
the signing key and reads its fingerprint; nothing is trusted yet. The UI shows
that fingerprint and only calls :meth:`RepoManager.add` after the user
confirms. COPR prefers ``dnf copr enable``; when that path is unavailable the
backend writes the ``.repo`` file and imports the exact key that was shown.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from parcel.backend.commands import CommandError, CommandRunner, SubprocessRunner
from parcel.backend.keys import (
    KeyInspector,
    SigningKeyError,
    fetch_key,
)
from parcel.backend.models import RepoKind, RepoPlan, RepoRequest
from parcel.backend.repo_files import (
    parse_copr,
    url_file_name,
    url_key_url,
    url_repo_file,
    validate_baseurl,
    validate_repo_name,
)

REPO_DIR = Path("/etc/yum.repos.d")
# pkexec returns 126 when the user dismisses the authentication dialog. Another
# privileged attempt would only prompt again, so that is not a fallback case.
_AUTH_DISMISSED = 126


class RepoManager:
    """Turn a :class:`RepoRequest` into a plan, then install the plan."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        fetch: Callable[[str], bytes] | None = None,
        inspector: KeyInspector | None = None,
        repo_dir: Path = REPO_DIR,
    ) -> None:
        self._runner = runner if runner is not None else SubprocessRunner()
        self._fetch = fetch if fetch is not None else fetch_key
        self._inspector = inspector if inspector is not None else KeyInspector()
        self._repo_dir = Path(repo_dir)

    # -- preparation -------------------------------------------------------

    def prepare(self, request: RepoRequest) -> RepoPlan:
        """Download and inspect the key; the repo is not written yet."""
        if request.kind is RepoKind.COPR:
            return self._prepare_copr(request)
        if request.kind is RepoKind.URL:
            return self._prepare_url(request)
        raise ValueError(f"unknown repository kind: {request.kind}")

    def _prepare_copr(self, request: RepoRequest) -> RepoPlan:
        project = parse_copr(request.copr)
        key_data = self._fetch(project.key_url)
        key = self._inspector.inspect(key_data)
        return RepoPlan(
            request=request,
            repo_id=project.repo_id,
            name=project.name,
            baseurl=project.baseurl,
            key_url=project.key_url,
            key_fingerprint=key.fingerprint,
            key_id=key.key_id,
            repo_file_name=project.file_name,
            repo_file=project.repo_file(),
            key_data=key_data,
            command=project.command,
        )

    def _prepare_url(self, request: RepoRequest) -> RepoPlan:
        name = validate_repo_name(request.name)
        baseurl = validate_baseurl(request.baseurl)
        key_url = url_key_url(baseurl)
        key_data = self._fetch(key_url)
        key = self._inspector.inspect(key_data)
        return RepoPlan(
            request=request,
            repo_id=name,
            name=name,
            baseurl=baseurl,
            key_url=key_url,
            key_fingerprint=key.fingerprint,
            key_id=key.key_id,
            repo_file_name=url_file_name(name),
            repo_file=url_repo_file(name, baseurl, key_url),
            key_data=key_data,
        )

    # -- installation ------------------------------------------------------

    def add(self, plan: RepoPlan) -> None:
        """Install a plan whose fingerprint the user has confirmed."""
        if plan.command:
            try:
                self._runner.run(plan.command)
            except CommandError as error:
                if error.exit_code == _AUTH_DISMISSED:
                    raise
            else:
                return
        self._install_files(plan)

    def _install_files(self, plan: RepoPlan) -> None:
        if not plan.key_data:
            raise SigningKeyError("the repository key is missing from the plan")
        destination = self._repo_dir / plan.repo_file_name
        with tempfile.TemporaryDirectory(prefix="parcel-repo-") as directory:
            root = Path(directory)
            key_path = root / "signing-key.gpg"
            repo_path = root / "repository.repo"
            key_path.write_bytes(plan.key_data)
            repo_path.write_text(plan.repo_file, encoding="utf-8")
            # Import first: a repo file that points at an untrusted key would
            # only make dnf fail. A leftover key is harmless on its own.
            self._runner.run(["pkexec", "rpmkeys", "--import", str(key_path)])
            self._runner.run(
                [
                    "pkexec",
                    "install",
                    "-m",
                    "0644",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    str(repo_path),
                    str(destination),
                ]
            )
