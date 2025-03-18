"""
modmail.config.models.permission_model
======================================
Contains configuration models for the permission system.
Defines the structure and validation for permission-related settings.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from modmail.enum import PermissionRequiredLevel

__all__ = ["PermissionConfig"]


# noinspection PyNestedDecorators
class PermissionConfig(BaseModel):
    """
    Configuration model for the permission system.

    Attributes:
        discord_admin_bypass (bool): Whether users with Discord administrator permission should be given Modmail admin permission.
        overrides (dict[str, PermissionRequiredLevel]): Override a command's permission required permission level.
    """

    discord_admin_bypass: bool = True
    overrides: dict[str, PermissionRequiredLevel] = Field(default_factory=dict, validate_default=True)

    @field_validator("overrides", mode="before")
    @classmethod
    def set_default_overrides_config(
        cls, v: dict[str, PermissionRequiredLevel] | None
    ) -> dict[str, PermissionRequiredLevel]:
        """
        Sets the default overrides if not provided.
        """
        if v is None:
            return {}
        return v

    @field_validator("overrides", mode="before")
    @classmethod
    def sanitize_overrides_values_config(
        cls, v: dict[str, PermissionRequiredLevel | str]
    ) -> dict[str, PermissionRequiredLevel]:
        """
        Sanitizes the overrides command names and parses the permission levels.
        """
        new_v: dict[str, PermissionRequiredLevel] = {}
        for key, value in v.items():
            # Replace spaces and dashes with underscores and convert to lowercase
            key = key.casefold().strip().replace(" ", "_").replace("-", "_")
            if isinstance(value, str):
                try:
                    # noinspection PyTypeChecker
                    new_v[key] = PermissionRequiredLevel[value.casefold()]
                except KeyError:
                    raise ValueError(f"Invalid permission level: {value}")
            else:
                new_v[key] = value
        return new_v
