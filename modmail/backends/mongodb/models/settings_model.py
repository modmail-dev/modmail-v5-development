"""
modmail.backends.mongodb.models.settings_model
==============================================
This module defines the MongoDB model for the settings collection.
"""

from __future__ import annotations

from typing import Annotated

from beanie import Indexed  # type: ignore[reportUnknownVariableType]  # beanie is not fully typed
from beanie import Document

__all__ = [
    "Settings",
]


class Settings(Document):
    bot_id: Annotated[int, Indexed(unique=True)]  # the bot ID
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    main_category_id: int | None = None
    fallback_category_id: int | None = None

    class Settings:
        validate_on_save = True
