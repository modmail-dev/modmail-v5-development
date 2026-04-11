"""Enumeration types used throughout Modmail.

Defines access levels, ticket states, activity types, and other shared enums.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from discord import app_commands


class TicketMessageType(enum.Enum):
    """The type of a ticket message.

    Attributes:
        reply: A staff reply sent to the user's DM.
        dm: A message received from the user.
        internal: An internal staff-only note.
        close: A closure message sent when the ticket is closed via command.
        sclose: A silent closure — no message is sent to the user.
    """

    reply = "reply"
    dm = "dm"
    internal = "internal"
    close = "close"
    sclose = "sclose"


class TicketStatus(enum.Enum):
    """Status of a ticket.

    Attributes:
        open: The ticket is currently open.
        closed_by_command: The ticket was closed via a command.
        closed_by_deletion: The ticket was closed because its channel was deleted.
    """

    open = "open"
    closed_by_command = "closed_by_command"
    closed_by_deletion = "closed_by_deletion"

    def is_open(self) -> bool:
        """Check whether this status represents an open ticket.

        Returns:
            True: if the status is `open`.
            False: if the ticket is closed.
        """
        return self == TicketStatus.open


class AccessLevel(enum.IntEnum):
    """Permission access level assignable to a profile.

    Ordered from lowest to highest privilege.

    Attributes:
        everyone: All users; no special permissions required.
        staff: Basic staff access.
        manager: Elevated staff access with management capabilities.
        admin: Full administrative access.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4

    def __locale_str__(self) -> app_commands.locale_str:
        """Get the localized display name for this access level.

        Returns:
            locale_str: the localized name.
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
    """Minimum access level required to run a command.

    Extends [`AccessLevel`][] with an additional `owner` tier that cannot be
    assigned to a profile but can be required by certain commands.

    Attributes:
        everyone: No restriction; any user may run the command.
        staff: Requires staff access or higher.
        manager: Requires manager access or higher.
        admin: Requires admin access or higher.
        owner: Restricted to the bot owner only.
    """

    everyone = 1
    staff = 2
    manager = 3
    admin = 4
    owner = 5

    def __locale_str__(self) -> app_commands.locale_str:
        """Get the localized display name for this required access level.

        Returns:
            locale_str: the localized name.
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

    Attributes:
        user: The profile belongs to an individual Discord user.
        role: The profile belongs to a Discord role.
    """

    user = "user"
    role = "role"


class PermissionOverrideValue(enum.Enum):
    """Value of a permission override.

    Attributes:
        allow: The permission is explicitly granted.
        deny: The permission is explicitly denied.
    """

    allow = "allow"
    deny = "deny"


# Technically, this is not an enum, but storing in this file for consistency.
class ProfileKey(NamedTuple):
    """A composite key identifying a profile.

    Used internally to look up profiles by ID and type.

    Attributes:
        profile_id: The unique identifier of the profile.
        profile_type: Whether the profile belongs to a user or a role.
    """

    profile_id: int
    profile_type: ProfileType


class ActivityType(enum.Enum):
    """Discord presence activity type.

    Attributes:
        playing: Playing a game.
        streaming: Streaming on a platform.
        listening: Listening to something.
        watching: Watching something.
        custom: A custom status message.
        competing: Competing in an event.
    """

    playing = "playing"
    streaming = "streaming"
    listening = "listening"
    watching = "watching"
    custom = "custom"
    competing = "competing"

    def __locale_str__(self) -> app_commands.locale_str:
        """Get the localized Discord activity prefix for this type.

        Returns:
            locale_str: the localized prefix (e.g. "Playing", "Listening to").
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
    """Discord online status.

    Attributes:
        online: Shown as online (green).
        idle: Shown as idle (yellow).
        dnd: Do Not Disturb — shown as red.
        offline: Shown as offline/invisible (grey).
    """

    online = "online"
    idle = "idle"
    dnd = "dnd"
    offline = "offline"

    def __str__(self) -> str:
        """Get the human-readable name of this status.

        Returns:
            str: the display name (e.g. `"Do Not Disturb (dnd)"`).
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
        """Get the localized display name for this status.

        Returns:
            locale_str: the localized status name.
        """
        # noinspection PyProtectedMember
        from .core import _

        return _("ftl-model-status-text", status=self.name)
