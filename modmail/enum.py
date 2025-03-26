"""
modmail.enum
============
Contains enumeration classes used throughout the application.
Defines access levels, activity types, status types, etc. used by the bot.
"""

from __future__ import annotations

import enum
from typing import NamedTuple

from discord import app_commands


class AccessLevel(enum.IntEnum):
    """
    Enum representing the permission access levels assignable to a profile.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4

    def __locale_str__(self) -> app_commands.locale_str:
        # noinspection PyProtectedMember
        from .core import _

        match self:
            case AccessLevel.everyone:
                return _("ftl-access-level-everyone")
            case AccessLevel.staff:
                return _("ftl-access-level-staff")
            case AccessLevel.manager:
                return _("ftl-access-level-manager")
            case AccessLevel.admin:
                return _("ftl-access-level-admin")


class RequiredAccessLevel(enum.IntEnum):
    """
    Enum representing the required access level to run a command.
    Differs from AccessLevel since owner cannot be assigned to a profile.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4
    owner = 5

    def __locale_str__(self) -> app_commands.locale_str:
        # noinspection PyProtectedMember
        from .core import _

        match self:
            case RequiredAccessLevel.everyone:
                return _("ftl-access-level-everyone")
            case RequiredAccessLevel.staff:
                return _("ftl-access-level-staff")
            case RequiredAccessLevel.manager:
                return _("ftl-access-level-manager")
            case RequiredAccessLevel.admin:
                return _("ftl-access-level-admin")
            case RequiredAccessLevel.owner:
                return _("ftl-access-level-owner")


class ProfileType(enum.Enum):
    """
    Enum representing the type of profile's owner.
    """

    user = 1
    role = 2


class PermissionOverrideValue(enum.Enum):
    """
    Enum representing the value (allow/deny) of a permission override.
    """

    allow = 1
    deny = 2


# Technically, this is not an enum, but storing in this file for consistency.
class ProfileKey(NamedTuple):
    """
    A key for a profile, used to identify the profile in a dictionary.
    Internal use only.
    """

    profile_id: int
    profile_type: ProfileType


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
