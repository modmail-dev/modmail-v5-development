"""Contains enumeration classes used throughout the application.

This module defines various enumeration types that are used across the Modmail
application, including access levels, activity types, status types, and more.
"""

from __future__ import annotations

import enum
from typing import NamedTuple

from discord import app_commands


class TicketMessageType(enum.Enum):
    """The type of the ticket message.

    Represents the different types of messages that can be sent in a ticket,
    including reply messages, DM messages, and internal messages.
    """

    reply = "reply"
    dm = "dm"
    internal = "internal"
    close = "close"
    sclose = "sclose"


class TicketStatus(enum.Enum):
    """Status of a ticket.

    Represents the different states a ticket can be in, such as open, closed,
    archived, or deleted.
    """

    open = "open"
    closed_by_command = "closed_by_command"
    closed_by_deletion = "closed_by_deletion"

    def is_open(self) -> bool:
        """Check if the ticket status represents an open ticket.

        Returns:
            True if the ticket is open, False otherwise.
        """
        return self == TicketStatus.open


class AccessLevel(enum.IntEnum):
    """Permission access levels assignable to a profile.

    These levels represent the hierarchy of permissions that can be assigned
    to user profiles within the system, from lowest (everyone) to highest (admin).
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4

    def __locale_str__(self) -> app_commands.locale_str:
        """Get the localized string representation of the access level.

        Returns:
            The localized string for this access level.
        """
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
    """Required access level to run a command.

    Differs from AccessLevel since owner cannot be assigned to a profile but
    is used as a requirement level for certain commands.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4
    owner = 5

    def __locale_str__(self) -> app_commands.locale_str:
        """Get the localized string representation of the required access level.

        Returns:
            The localized string for this required access level.
        """
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
    """Type of profile owner.

    Indicates whether a profile belongs to an individual user or a role.
    """

    user = "user"
    role = "role"


class PermissionOverrideValue(enum.Enum):
    """Value of a permission override.

    Represents whether a permission is explicitly allowed or denied.
    """

    allow = "allow"
    deny = "deny"


# Technically, this is not an enum, but storing in this file for consistency.
class ProfileKey(NamedTuple):
    """A key for identifying a profile in a dictionary.

    Used internally to reference profiles by their ID and type.

    Attributes:
        profile_id: The unique identifier of the profile.
        profile_type: The type of profile (user or role).
    """

    profile_id: int
    profile_type: ProfileType


class ActivityType(enum.Enum):
    """Types of activities a user or bot can display on Discord.

    Corresponds to the different status activities that can be shown
    in a Discord presence (Playing, Streaming, Listening to, etc.).
    """

    playing = "playing"
    streaming = "streaming"
    listening = "listening"
    watching = "watching"
    custom = "custom"
    competing = "competing"

    def __locale_str__(self) -> app_commands.locale_str:
        """Get a localized string representation of the activity prefix.

        Returns a locale_str representing the Discord prefix for the activity type
        (e.g., "playing", "listening to", etc.)

        Returns:
            The localized activity prefix.
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
    """Types of online status on Discord.

    Represents the different visibility states a user can have on Discord.
    """

    online = "online"
    idle = "idle"
    dnd = "dnd"
    offline = "offline"

    def __str__(self) -> str:
        """Get a string representation of the status.

        Returns:
            The human-readable status name.
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
        """Get a localized string representation of the status.

        Returns:
            The localized name of the status.
        """
        # noinspection PyProtectedMember
        from .core import _

        return _("ftl-model-status-text", status=self.name)
