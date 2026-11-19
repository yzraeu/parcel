"""GObject wrapper so Gio list models can hold :class:`Package` values."""

from __future__ import annotations

from gi.repository import GObject

from parcel.backend.models import Package, format_size


class PackageItem(GObject.Object):
    """One list entry: a package plus how a row should present it.

    ``size`` starts from the package and can be filled in later when
    PackageKit reports it; changing it refreshes the row subtitle.
    """

    def __init__(
        self,
        package: Package,
        version_text: str = "",
        security: bool = False,
    ) -> None:
        super().__init__()
        self.package = package
        self.version_text = version_text or package.version
        self.security = security
        self.size = package.size
        self._busy = False

    @GObject.Property(type=bool, default=False)
    def busy(self) -> bool:
        """True while a transaction for this package is running."""
        return self._busy

    @busy.setter
    def busy(self, value: bool) -> None:
        self._busy = bool(value)

    @GObject.Property(type=str)
    def subtitle(self) -> str:
        parts = [self.version_text, self.package.repo_label]
        if self.size:
            parts.append(format_size(self.size))
        return " \u00b7 ".join(parts)

    def set_size(self, value: int) -> None:
        """Record a size reported later by PackageKit and refresh the subtitle."""
        if value == self.size:
            return
        self.size = value
        self.notify("subtitle")
