Name:           parcel
Version:        0.2.0
Release:        1%{?dist}
Summary:        A fast, packages-only GUI for dnf on Fedora

License:        GPL-3.0-or-later
URL:            https://github.com/yzraeu/parcel
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
BuildRequires:  make
BuildRequires:  python3-pytest
BuildRequires:  python3-gobject
BuildRequires:  python3-rpm
BuildRequires:  gtk4
BuildRequires:  libadwaita
BuildRequires:  PackageKit-glib
BuildRequires:  xorg-x11-server-Xvfb
BuildRequires:  dbus-daemon

Requires:       gtk4
Requires:       libadwaita
Requires:       python3
Requires:       python3-gobject
Requires:       python3-rpm
Requires:       PackageKit-glib

%description
Parcel is a fast, simple, packages-only GUI for dnf on Fedora. Four
tabs, a search box, and one button per action: browse installed packages,
install new ones, apply updates, and manage repositories. No screenshots,
reviews, or app-store extras.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing to compile: a Python package, a launcher, a desktop file
# and metainfo.

%install
%make_install PREFIX=%{_prefix}
desktop-file-validate %{buildroot}%{_datadir}/applications/dev.izzy.parcel.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/dev.izzy.parcel.metainfo.xml

%check
xvfb-run -a dbus-run-session -- make test

%files
%license LICENSE
%doc README.md
%{_bindir}/parcel
%{_datadir}/parcel/
%{_datadir}/applications/dev.izzy.parcel.desktop
%{_datadir}/metainfo/dev.izzy.parcel.metainfo.xml

%changelog
* Wed Nov 18 2026 yzraeu <yzraeu@gmail.com> - 0.2.0-1
- Initial package: browse, search, install, remove and update packages
  through PackageKit, plus repository management and an About dialog
