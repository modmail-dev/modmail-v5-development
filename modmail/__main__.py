"""Modmail bot entrypoint script."""

from __future__ import annotations

from . import run_bot

# __name__ is "__main__" when python -m modmail is used
# __name__ is "modmail.__main__" when invoked from start.py
if __name__ in {"__main__", "modmail.__main__"}:
    run_bot("config.toml")
