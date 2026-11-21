PYTHON ?= python3
VENV_PYTHON := .venv/bin/python

.PHONY: install dev check

.venv/bin/python:
	$(PYTHON) -m venv .venv

install: .venv/bin/python
	$(VENV_PYTHON) -m pip install -r requirements-dev.lock
	$(VENV_PYTHON) -m pip install --no-deps -e .

dev: .venv/bin/python
	$(VENV_PYTHON) -m beforerun --reload

check: .venv/bin/python
	$(VENV_PYTHON) -m compileall -q src
	$(VENV_PYTHON) -m ruff check src
	$(VENV_PYTHON) -m ruff format --check src

