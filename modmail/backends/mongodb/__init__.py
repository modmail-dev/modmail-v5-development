"""MongoDB database backend package.

Exposes MongoDBBackend, the Beanie ODM implementation of DBBackend.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from .backend import MongoDBBackend

__all__ = ["MongoDBBackend"]
