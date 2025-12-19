"""Modmail bot external entrypoint script.

This script serves as an entry point for starting the Modmail bot
when executed directly. It uses the runpy module to run the
modmail package as a module (i.e., python -m modmail).
"""

from __future__ import annotations

import multiprocessing
import runpy

if __name__ == "__main__":
    multiprocessing.freeze_support()
    runpy.run_module("modmail")
