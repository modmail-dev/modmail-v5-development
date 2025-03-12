"""
modmail.config.models.json_database_model
=========================================
This module defines the configuration model for the JSON database used by the Modmail bot.
It includes validation logic to ensure the storage path is valid and exists, creating it if necessary.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "JsonDatabaseConfig",
]


# noinspection PyNestedDecorators
class JsonDatabaseConfig(BaseModel):
    """
    Configuration model for the JSON database.

    Attributes:
        storage_path (str): The path to the storage directory. Defaults to "data".
    """

    storage_path: str = Field("data", validate_default=True)

    @field_validator("storage_path")
    @classmethod
    def check_storage_path_is_valid(cls, v: str) -> str:
        """
        Validates that the storage path is valid.
        Make sure the storage path exists, make it if it doesn't.
        """

        if not os.path.exists(v):
            os.makedirs(v)
        elif not os.path.isdir(v):
            raise ValueError(f"Storage path {v} is not a directory.")
        return v
