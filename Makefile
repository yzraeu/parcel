PYTHON ?= python3

# User install by default. Override for a system install, e.g.:
#   make install PREFIX=/usr/local
#   make install DESTDIR=/tmp/stage PREFIX=/usr
PREFIX ?= $(HOME)/.local
DESTDIR ?=

PKG_SRC := parcel
LAUNCHER_SRC := data/parcel
DESKTOP_SRC := data/dev.izzy.parcel.desktop
METAINFO_SRC := data/dev.izzy.parcel.metainfo.xml

PKG_DST := $(DESTDIR)$(PREFIX)/share/parcel/parcel
LAUNCHER_DST := $(DESTDIR)$(PREFIX)/bin/parcel
DESKTOP_DST := $(DESTDIR)$(PREFIX)/share/applications/dev.izzy.parcel.desktop
METAINFO_DST := $(DESTDIR)$(PREFIX)/share/metainfo/dev.izzy.parcel.metainfo.xml

.PHONY: run test lint format install uninstall

run:
	$(PYTHON) -m parcel

test:
	$(PYTHON) -m pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/parcel
	cp -r $(PKG_SRC) $(DESTDIR)$(PREFIX)/share/parcel/
	find $(DESTDIR)$(PREFIX)/share/parcel -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
	install -Dm755 $(LAUNCHER_SRC) $(LAUNCHER_DST)
	install -Dm644 $(DESKTOP_SRC) $(DESKTOP_DST)
	install -Dm644 $(METAINFO_SRC) $(METAINFO_DST)

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/share/parcel
	rm -f $(LAUNCHER_DST) $(DESKTOP_DST) $(METAINFO_DST)
