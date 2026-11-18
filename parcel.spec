Name:           parcel
Version:        0.2.0
Release:        1%{?dist}
Summary:        A fast, simple, packages-only GUI for dnf on Fedora

License:        GPL-3.0-or-later
URL:            https://github.com/yzraeu/parcel
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
BuildRequires:  make
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-pytest
BuildRequires:  python3-gobject
BuildRequires:  python3-rpm
BuildRequires:  gtk4
BuildRequires:  libadwaita
BuildRequires:  PackageKit-glib
BuildRequires:  xorg-x11-server-Xvfb
BuildRequires:  dbus-daemon

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       PackageKit-glib
Requires:       python3-rpm
Requires:       gnupg2
Requires:       /usr/bin/dnf
Requires:       /usr/bin/pkexec
Requires:       /usr/bin/rpmkeys

Recommends:     dnf-plugins-core

%description
Parcel is a fast, simple, packages-only GUI for dnf on Fedora. It browses,
installs, updates, and removes packages through PackageKit. Four tabs
(Installed, Available, Updates, Repos), a search box, and one button per
action: no screenshots, reviews, or app-store extras.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files parcel
install -Dm644 data/dev.izzy.parcel.desktop %{buildroot}%{_datadir}/applications/dev.izzy.parcel.desktop
install -Dm644 data/dev.izzy.parcel.metainfo.xml %{buildroot}%{_datadir}/metainfo/dev.izzy.parcel.metainfo.xml
desktop-file-validate %{buildroot}%{_datadir}/applications/dev.izzy.parcel.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/dev.izzy.parcel.metainfo.xml

%check
xvfb-run -a dbus-run-session -- make test

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_datadir}/applications/dev.izzy.parcel.desktop
%{_datadir}/metainfo/dev.izzy.parcel.metainfo.xml

%changelog
* Wed Nov 18 2026 yzraeu <yzraeu@gmail.com> - 0.2.0-1
- Initial package
