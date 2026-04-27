"""Common Pydantic model for a permission profile."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

__all__ = ["ProfileModel"]


class ProfileModel(BaseModel):
    """Common immutable model for a user or role permission profile.

    [`permission_overrides`][] maps command names to allow/deny values,
    bypassing the command's access level.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    """Discord application ID of the bot this profile belongs to."""
    profile_id: int
    """Discord snowflake ID of the target user or role."""
    profile_type: ProfileType
    """[ProfileType][]{ data-preview } indicating whether [`profile_id`][] is a user or a role."""
    access_level: AccessLevel | None = None
    """[AccessLevel][]{ data-preview } granted by this profile (`None` if unset)."""

    permission_overrides: dict[str, PermissionOverrideValue] = {}
    """Per-command [PermissionOverrideValue][]{ data-preview } overrides."""

    tag: str | None = None
    """Short display label for this profile (`None` if unset)."""
    color: int | None = None
    """Discord color integer, e.g. `0xFFFFFF` for white (`None` if unset)."""

    @property
    def is_empty(self) -> bool:
        """`True` when the profile has no meaningful configuration and can be safely removed."""
        return all((
            self.access_level is None,
            self.color is None,
            self.tag is None,
            not self.permission_overrides,
        ))

    @property
    def mention(self) -> str:
        """Discord user mention string."""
        if self.profile_type == ProfileType.role:
            return f"<@&{self.profile_id}>"
        return f"<@{self.profile_id}>"
