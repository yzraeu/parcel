PYTHON ?= python3

.PHONY: run test lint format

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
