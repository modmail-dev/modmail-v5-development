"""Modmail bot entrypoint script.

This script serves as the main entry point for starting the Modmail bot.
It imports and calls the necessary initialization and run functions
from the modmail package.
"""

from __future__ import annotations

from . import init, run_bot

# __name__ is "__main__" when python -m modmail is used
# __name__ is "modmail.__main__" when invoked from start.py
if __name__ in {"__main__", "modmail.__main__"}:
    init()
    run_bot()
