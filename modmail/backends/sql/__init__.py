"""SQL database backend package.

Exposes SQLBackend, the SQLAlchemy + aiosqlite implementation of DBBackend.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from .backend import SQLBackend

__all__ = ["SQLBackend"]
