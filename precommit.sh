#!/bin/sh
uv run ruff check
uv run ruff format --check
uv run pyrefly check
uv run pytest
