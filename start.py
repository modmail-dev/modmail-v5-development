"""Modmail bot entrypoint script.

This script serves as the main entry point for starting the Modmail bot.
It imports and calls the necessary initialization and run functions
from the modmail package.
"""

from __future__ import annotations

import modmail

if __name__ == "__main__":
    modmail.init()
    modmail.run_bot()
