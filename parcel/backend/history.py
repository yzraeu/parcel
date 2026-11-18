"""Why an installed package is on the system.

dnf is the only component that records install reasons, in its history
database. rpm headers do not carry them, and PackageKit does not expose them.
Reading the history is best-effort: on systems without dnf history the reason
is simply unknown.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from parcel.backend.models import InstallReason

_DEFAULT_PATH = Path("/var/lib/dnf/history.sqlite")

# dnf history stores: 1 = pulled in as a dependency, 2 = explicitly installed
# by the user. Anything else (0 = unknown, group installs) stays unknown.
_REASONS = {
    1: InstallReason.DEPENDENCY,
    2: InstallReason.USER,
}

_QUERY = """
SELECT trans_item.reason
FROM trans_item
JOIN rpm ON rpm.item_id = trans_item.item_id
WHERE rpm.name = ? AND trans_item.reason != 0
ORDER BY trans_item.id DESC
LIMIT 1
"""


class HistoryDatabase:
    """Install reasons from the dnf history database."""

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self._path = Path(path)

    def install_reason(self, name: str) -> InstallReason | None:
        if not self._path.is_file():
            return None
        try:
            with sqlite3.connect(f"file:{self._path}?mode=ro", uri=True) as db:
                row = db.execute(_QUERY, (name,)).fetchone()
        except sqlite3.Error:
            return None
        return _REASONS.get(row[0]) if row else None
