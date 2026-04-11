"""Common database backend abstractions and shared models.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from .db_backend import *
from .db_client import *
from .models import *
