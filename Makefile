.PHONY: setup install test init scan ingest status queue-review export-gtowizard daily queue export

PYTHON ?= python3

setup: install

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

init:
	$(PYTHON) -m pokermda.cli init

scan:
	$(PYTHON) -m pokermda.cli scan-raw

ingest:
	$(PYTHON) -m pokermda.cli ingest --new-only

status:
	$(PYTHON) -m pokermda.cli status imports

queue-review:
	$(PYTHON) -m pokermda.cli queue-review

queue:
	$(PYTHON) -m pokermda.cli queue build

export-gtowizard:
	$(PYTHON) -m pokermda.cli export-gtowizard

export:
	$(PYTHON) -m pokermda.cli gtowizard export

daily:
	$(PYTHON) -m pokermda.cli daily
