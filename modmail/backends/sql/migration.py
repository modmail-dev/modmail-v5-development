"""SQL migration runner using Alembic.

Exposes [`do_migration`][] for programmatic `upgrade to head` from the running
bot.  To auto-generate a new version file from the project root:

    uv run alembic revision --autogenerate -m "description"
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

__all__ = ["do_migration"]

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _upgrade_head(uri: str) -> None:
    """Run `alembic upgrade head` synchronously.

    Intended to be called from a worker thread (via [`asyncio.to_thread`][]) that
    has no running event loop, so `env.py`'s [`asyncio.run`][] call can start a
    fresh one.

    Args:
        uri: The SQL database connection URI.
    """
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", uri)
    command.upgrade(cfg, "head")


async def do_migration(uri: str) -> None:
    """Run all pending Alembic migrations against the given database URI.

    Delegates to a worker thread so the event loop is not blocked, and so
    that `env.py`'s internal [`asyncio.run`][] call gets a loop-free thread in
    which to start its own event loop.

    Args:
        uri: The SQL database connection URI.
    """
    await asyncio.to_thread(_upgrade_head, uri)
