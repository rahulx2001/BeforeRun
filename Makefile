PYTHON ?= python3
VENV_PYTHON := .venv/bin/python

.PHONY: install dev check browser-check

.venv/bin/python:
	$(PYTHON) -m venv .venv

install: .venv/bin/python
	$(VENV_PYTHON) -m pip install -r requirements-dev.lock
	$(VENV_PYTHON) -m pip install --no-deps -e .

dev: .venv/bin/python
	$(VENV_PYTHON) -m beforerun --reload

check: .venv/bin/python
	$(VENV_PYTHON) -m compileall -q src
	$(VENV_PYTHON) -m ruff check src tests
	$(VENV_PYTHON) -m ruff format --check src tests
	$(VENV_PYTHON) -m pytest -m 'not live and not browser' -q tests

browser-check: .venv/bin/python
	$(VENV_PYTHON) -m pytest -m 'browser and not live' -q tests

