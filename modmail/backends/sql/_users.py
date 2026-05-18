"""SQL persistence for ticket user records."""

from __future__ import annotations

from ._base import SQLBackendBase


class SQLUsersMixin(SQLBackendBase):
    """SQL mixin for ticket user persistence."""
