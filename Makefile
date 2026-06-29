.PHONY: install test init ingest queue export

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

init:
	$(PYTHON) -m pokermda.cli init

ingest:
	$(PYTHON) -m pokermda.cli ingest

queue:
	$(PYTHON) -m pokermda.cli queue build

export:
	$(PYTHON) -m pokermda.cli gtowizard export

