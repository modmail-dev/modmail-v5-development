"""Alembic environment for SQL backend migrations.

Supports two use-cases:

- **CLI autogenerate** — ``uv run alembic revision --autogenerate -m "name"``:
  ``ALEMBIC_URL`` must be set (directly or via a ``.env`` file).
  Basic logging is configured automatically.

- **Programmatic upgrade** — called via ``migration.do_migration``: the URL is
  already injected into the Alembic config before this file runs, and logging
  is left to the application.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Literal

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from modmail.backends.sql.models.base import SQLBase, UTCTimestamp

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext
    from sqlalchemy.engine import Connection

target_metadata = SQLBase.metadata


def render_item(type_: str, obj: object, autogen_context: AutogenContext) -> str | Literal[False]:
    """Teach Alembic how to render custom types so it emits correct imports.

    Returns:
        A string representation of the type if handled, ``False`` to fall back to default rendering.
    """
    if type_ == "type" and isinstance(obj, UTCTimestamp):
        autogen_context.imports.add("import modmail.backends.sql.models.base")
        return "modmail.backends.sql.models.base.UTCTimestamp()"
    return False


config = context.config

if config.get_alembic_option("sqlalchemy.url") is None:
    # CLI mode — URL not injected by migration.py; load from env and set it now.
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
    _log = logging.getLogger(__name__)

    from dotenv import load_dotenv

    load_dotenv()

    _url = os.environ.get("ALEMBIC_URL")
    if _url is None:
        raise RuntimeError(
            "ALEMBIC_URL environment variable is not set. "
            "Set it directly or add it to a .env file:\n"
            "  ALEMBIC_URL=sqlite+aiosqlite:///./dev.db"
        )
    _log.info("Loaded database URL from ALEMBIC_URL environment variable.")
    config.set_main_option("sqlalchemy.url", _url)


def do_run_migrations(connection: Connection) -> None:
    """Execute pending migrations on a synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Wrap ALTER TABLE operations in a batch (create-copy-drop) so that
        # migrations work on SQLite, which has very limited ALTER TABLE support.
        # PostgreSQL and MySQL ignore the wrapping and use native ALTER TABLE.
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a disposable async engine and run all pending migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline mode is not supported; connect to the database directly.")

asyncio.run(run_async_migrations())
