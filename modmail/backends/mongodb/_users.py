"""MongoDB persistence for ticket user records."""

from __future__ import annotations

from ._base import MongoDBBackendBase


class MongoDBUsersMixin(MongoDBBackendBase):
    """MongoDB mixin for ticket user persistence."""
