"""
modmail.cogs.utility.commands.status
====================================
This module contains the status command for the Modmail bot.
This command allows you to set the bot's status and activity message.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from modmail.backends import Activity

# noinspection PyProtectedMember
from modmail.core import Bot, _, lazy_hybrid_group, wrap
from modmail.enum import ActivityType, StatusType

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["status_command"]


@wrap(commands.guild_only)
@wrap(app_commands.describe, status=_("ftl-cmd-status-param-status-description"))
@lazy_hybrid_group(
    name=_("ftl-cmd-status-name"),
    fallback=_("ftl-cmd-status-fallback-name"),
    description=_("ftl-cmd-status-description"),
)
async def status_command(self: Utility, ctx: commands.Context[Bot], *, status: str | None = None) -> None:
    """
    Set the bot's status or activity message.

    Possible statuses:
    - online (green)
    - idle (yellow)
    - dnd (red)
    - offline (invisible)

    Possible activities:
    - playing <activity>
    - watching <activity>
    - listening to <activity>
    - competing in <activity>
    - streaming <activity> https://www.twitch.tv/your-channel (Twitch URL at the end)
    - <activity> (custom activity)

    Run `status clear` to clear the bot's status and activity.
    """

    if not status:  # No status provided, show the current status
        current_status = self.bot.database_client.settings_model.status
        current_activity = self.bot.database_client.settings_model.activity

        if current_status is not None and current_activity is not None:
            current_status_message = await self.translate(
                ctx, _("ftl-msg-status-current-status", status=current_status)
            )
            current_activity_message = await self.translate(
                ctx, _("ftl-msg-status-current-activity", activity=current_activity)
            )

            await self.reply(ctx, f"{current_status_message}\n{current_activity_message}", ephemeral=True)
        elif current_status is not None:
            await self.reply(ctx, _("ftl-msg-status-current-status", status=current_status), ephemeral=True)
        elif current_activity is not None:
            await self.reply(ctx, _("ftl-msg-status-current-activity", activity=current_activity), ephemeral=True)
        else:
            await self.reply(ctx, _("ftl-msg-status-no-status"), ephemeral=True)
        return

    status_name_mapping: dict[str, StatusType] = {
        (await self.translate(ctx, _("ftl-model-status-online-name"))).casefold(): StatusType.online,
        (await self.translate(ctx, _("ftl-model-status-idle-name"))).casefold(): StatusType.idle,
        (await self.translate(ctx, _("ftl-model-status-dnd-name"))).casefold(): StatusType.dnd,
        (await self.translate(ctx, _("ftl-model-status-dnd-full-name"))).casefold(): StatusType.dnd,
        (await self.translate(ctx, _("ftl-model-status-offline-name"))).casefold(): StatusType.offline,
        (await self.translate(ctx, _("ftl-model-status-invisible-name"))).casefold(): StatusType.offline,
    }

    if status.casefold() in status_name_mapping.keys():
        # Setting status
        status_type = status_name_mapping[status.casefold()]
        await self.bot.set_bot_presence(status=status_type)
        await self.reply(ctx, _("ftl-msg-status-set-status", status=status_type), ephemeral=True)
        return

    activity_name_mapping: dict[str, ActivityType] = {
        (await self.translate(ctx, _("ftl-model-activity-playing-name"))).casefold() + " ": ActivityType.playing,
        (await self.translate(ctx, _("ftl-model-activity-streaming-name"))).casefold()
        + " ": ActivityType.streaming,
        (await self.translate(ctx, _("ftl-model-activity-listening-name"))).casefold()
        + " ": ActivityType.listening,
        (await self.translate(ctx, _("ftl-model-activity-watching-name"))).casefold() + " ": ActivityType.watching,
        (await self.translate(ctx, _("ftl-model-activity-competing-name"))).casefold()
        + " ": ActivityType.competing,
    }

    for activity_name, activity_type in activity_name_mapping.items():
        if status.casefold().startswith(activity_name) and len(status) > len(activity_name):
            status = status[len(activity_name) :].strip()
            if activity_type != ActivityType.streaming:
                # Setting activity (not streaming)
                activity = Activity(name=status, type=activity_type)
            else:
                # Setting streaming activity
                url: str | None = None

                if (
                    match := re.search(r"(?:https?://)?(?:www\.|m\.)?twitch\.tv/(?P<channel>\S+)\s*$", status)
                ) is not None:
                    # If the status is a Twitch URL, extract the channel name
                    channel = match.group("channel")

                    # Remove the URL from the status, and strip
                    status = re.sub(
                        r"\s*(?:https?://)?(?:www\.|m\.)?twitch\.tv/(?P<channel>\S+)\s*$", "", status
                    ).strip()
                    url = f"https://www.twitch.tv/{channel}"
                    if not status:  # If the status is empty after removing the URL, set it to the URL
                        status = url

                activity = Activity(name=status, type=ActivityType.streaming, url=url)
            await self.bot.set_bot_presence(activity=activity)
            await self.reply(ctx, _("ftl-msg-status-set-activity", activity=activity), ephemeral=True)
            return

    # Setting custom activity
    activity = Activity(name=status, type=ActivityType.custom)
    await self.bot.set_bot_presence(activity=activity)
    await self.reply(ctx, _("ftl-msg-status-set-activity", activity=activity), ephemeral=True)


@wrap(commands.guild_only)
@status_command.command(name=_("ftl-cmd-status-clear-name"), description=_("ftl-cmd-status-clear-description"))
async def status_clear_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Clear the bot's status and activity.
    """
    await self.bot.clear_bot_presence()
    await self.reply(ctx, _("ftl-msg-status-clear-status"), ephemeral=True)
