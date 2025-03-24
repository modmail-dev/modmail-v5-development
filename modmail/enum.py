"""
modmail.enum
============
Contains enumeration classes used throughout the application.
Defines permission levels, activity types, and status types used by the bot.
"""

from __future__ import annotations

import enum
from typing import NamedTuple

from discord import app_commands


class PermissionLevel(enum.IntEnum):
    """
    Enum representing the permission levels for a user/role permission group.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4

    def __locale_str__(self) -> app_commands.locale_str:
        from .core import _

        match self:
            case PermissionLevel.everyone:
                return _("ftl-perm-level-everyone")
            case PermissionLevel.staff:
                return _("ftl-perm-level-staff")
            case PermissionLevel.manager:
                return _("ftl-perm-level-manager")
            case PermissionLevel.admin:
                return _("ftl-perm-level-admin")


class PermissionRequiredLevel(enum.IntEnum):
    """
    Enum representing the required permission levels to run a command.
    Adds owner since it cannot be assigned to a permission group.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4
    owner = 5

    def __locale_str__(self) -> app_commands.locale_str:
        from .core import _

        match self:
            case PermissionRequiredLevel.everyone:
                return _("ftl-perm-level-everyone")
            case PermissionRequiredLevel.staff:
                return _("ftl-perm-level-staff")
            case PermissionRequiredLevel.manager:
                return _("ftl-perm-level-manager")
            case PermissionRequiredLevel.admin:
                return _("ftl-perm-level-admin")
            case PermissionRequiredLevel.owner:
                return _("ftl-perm-level-owner")


class PermissionGroupType(enum.Enum):
    """
    Enum representing the type of permission group.
    """

    user = 1
    role = 2


class PermissionOverrideType(enum.Enum):
    """
    Enum representing the type of permission override.
    """

    allow = 1
    deny = 2


# Technically, this is not an enum
class PermissionGroupKey(NamedTuple):
    group_id: int
    group_type: PermissionGroupType


class ActivityType(enum.Enum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5

    def __locale_str__(self) -> app_commands.locale_str:
        """
        Returns a locale_str representation of the Discord prefix for the activity type.

        e.g. "playing" -> "playing", "listening" -> "listening to", etc.
        """
        # noinspection PyProtectedMember
        from .core import _

        match self:
            case ActivityType.playing:
                return _("ftl-model-activity-playing-name")
            case ActivityType.streaming:
                return _("ftl-model-activity-streaming-name")
            case ActivityType.listening:
                return _("ftl-model-activity-listening-name")
            case ActivityType.watching:
                return _("ftl-model-activity-watching-name")
            case ActivityType.competing:
                return _("ftl-model-activity-competing-name")
            case ActivityType.custom:
                return _("ftl-blank")


class StatusType(enum.Enum):
    online = 0
    idle = 1
    dnd = 2
    offline = 3

    def __str__(self) -> str:
        """
        Returns a string representation of the status.
        """
        match self:
            case StatusType.online:
                return "Online"
            case StatusType.idle:
                return "Idle"
            case StatusType.dnd:
                return "Do Not Disturb (dnd)"
            case StatusType.offline:
                return "Offline"

    def __locale_str__(self) -> app_commands.locale_str:
        """
        Returns a locale_str of the localized name of the status.
        """
        # noinspection PyProtectedMember
        from .core import _

        return _("ftl-model-status-text", status=self.name)
