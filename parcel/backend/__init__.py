"""PackageKit access for Parcel.

Nothing in this package may import GTK or libadwaita: it is the data layer the
UI is allowed to talk to, and it must stay usable without a display.

Import the model types from :mod:`parcel.backend.models` and the client from
:mod:`parcel.backend.client`; this package deliberately imports neither, so
importing a model never drags in PackageKit or D-Bus.
"""
