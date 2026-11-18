"""Tests for dnf history install-reason lookups."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from parcel.backend.history import HistoryDatabase
from parcel.backend.models import InstallReason


def build_history(path: Path, rows: list[tuple[str, int, int]]) -> None:
    """Create a minimal dnf history database.

    ``rows`` are ``(package name, reason, trans_item id)``.
    """
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE item (id INTEGER PRIMARY KEY, item_type INTEGER NOT NULL);
            CREATE TABLE rpm (
                item_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                version TEXT NOT NULL,
                release TEXT NOT NULL,
                arch TEXT NOT NULL
            );
            CREATE TABLE trans_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trans_id INTEGER,
                item_id INTEGER,
                repo_id INTEGER,
                action INTEGER NOT NULL,
                reason INTEGER NOT NULL,
                state INTEGER NOT NULL
            );
            """
        )
        for index, (name, reason, item_id) in enumerate(rows, start=1):
            db.execute("INSERT INTO item (id, item_type) VALUES (?, 1)", (item_id,))
            db.execute(
                "INSERT INTO rpm (item_id, name, epoch, version, release, arch) "
                "VALUES (?, ?, 0, '1', '1', 'x86_64')",
                (item_id, name),
            )
            db.execute(
                "INSERT INTO trans_item (id, trans_id, item_id, action, reason, state) "
                "VALUES (?, ?, ?, 1, ?, 1)",
                (index, 1, item_id, reason),
            )


def test_reason_one_means_dependency(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    build_history(path, [("alsa-lib", 1, 1)])
    assert HistoryDatabase(path).install_reason("alsa-lib") is InstallReason.DEPENDENCY


def test_reason_two_means_user_installed(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    build_history(path, [("filezilla", 2, 1)])
    assert HistoryDatabase(path).install_reason("filezilla") is InstallReason.USER


def test_unknown_reason_and_unknown_package_are_none(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    build_history(path, [("mystery", 0, 1), ("group-installed", 3, 2)])
    history = HistoryDatabase(path)
    assert history.install_reason("mystery") is None
    assert history.install_reason("group-installed") is None
    assert history.install_reason("absent") is None


def test_the_latest_nonzero_reason_wins(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    # Unrelated rows and an upgrade row with reason 0 sit between the entries.
    build_history(
        path,
        [("firefox", 2, 1), ("other", 1, 2), ("firefox", 0, 3)],
    )
    assert HistoryDatabase(path).install_reason("firefox") is InstallReason.USER


def test_missing_database_is_not_an_error(tmp_path: Path) -> None:
    assert HistoryDatabase(tmp_path / "absent.sqlite").install_reason("bash") is None


def test_unreadable_database_is_not_an_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.sqlite"
    path.write_text("not a database")
    assert HistoryDatabase(path).install_reason("bash") is None
