"""Permission configuration models."""

from __future__ import annotations

from typing import Annotated, cast

from pydantic import BaseModel, Field, field_validator

from modmail.enum import RequiredAccessLevel

__all__ = ["PermissionConfig"]


class PermissionConfig(
    BaseModel,
    frozen=True,
    str_strip_whitespace=True,
    coerce_numbers_to_str=True,
    use_attribute_docstrings=True,
):
    """Configuration model for the permission system."""

    discord_admin_bypass: bool = True
    """Whether users with Discord administrator permission should be given Modmail admin access."""
    default_access_everyone: bool = True
    """Whether everyone has access to commands with the `everyone` access level by default."""
    slash_minimum_permission_int: Annotated[int, Field(ge=0)] = 11264
    """Minimum Discord permissions integer required to see slash commands."""
    overrides: dict[str, RequiredAccessLevel] = Field(default_factory=dict)
    """Mapping of command names to custom required access levels."""

    @field_validator("overrides", mode="before")
    @classmethod
    def sanitize_overrides_values_config(cls, v: object) -> dict[str, RequiredAccessLevel]:
        """Sanitizes command names and parses access levels in the overrides mapping.

        Args:
            v: Dictionary mapping command names to their required access levels,
                which can be either RequiredAccessLevel enum values or strings.

        Returns:
            A dictionary mapping sanitized command names to RequiredAccessLevel enum values.

        Raises:
            ValueError: If an invalid permission access level string is provided.
        """
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError(f"Expected a dict for overrides, got {type(v).__name__}")

        new_v: dict[str, RequiredAccessLevel] = {}
        for key, value in cast("dict[str, object]", v).items():
            key = key.casefold().strip()
            if isinstance(value, RequiredAccessLevel):
                new_v[key] = value
            elif isinstance(value, str):
                try:
                    new_v[key] = RequiredAccessLevel[value.casefold()]
                except KeyError:
                    try:
                        new_v[key] = RequiredAccessLevel(int(value))
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Invalid permission access level: {value}") from e
            elif isinstance(value, int):
                try:
                    new_v[key] = RequiredAccessLevel(value)
                except ValueError as e:
                    raise ValueError(f"Invalid permission access level: {value}") from e
            else:
                raise ValueError(f"Invalid permission access level type: {type(value).__name__}")
        return new_v
