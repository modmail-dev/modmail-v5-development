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

from modmail.backends import Activity, ActivityType, StatusType
from modmail.core import lazy_hybrid_group, wrap

if TYPE_CHECKING:
    from modmail.core import Bot

    from .. import Utility

__all__ = ["status_command"]


@wrap(commands.guild_only)
@wrap(app_commands.describe, status="The status / activity to set.")
@lazy_hybrid_group(name="status", fallback="set")
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
    - streaming <activity> <https://www.twitch.tv/channel> (Twitch URL at the end)
    - <activity> (custom activity)

    Run `status clear` to clear the bot's status and activity.
    """

    if not status:
        # No status provided, show the current status
        current_status = self.bot.database_client.settings_model.status
        current_activity = self.bot.database_client.settings_model.activity

        if current_status is not None and current_activity is not None:
            await ctx.reply(
                f"Current status: {current_status}\nCurrent activity: {current_activity}", ephemeral=True
            )
        elif current_status is not None:
            await ctx.reply(f"Current status: {current_status}", ephemeral=True)
        elif current_activity is not None:
            await ctx.reply(f"Current activity: {current_activity}", ephemeral=True)
        else:
            await ctx.reply("No status set.", ephemeral=True)
        return

    if status.casefold() == "invisible":
        status = "offline"  # Set invisible as an alias to offline

    if status.casefold() in StatusType.__members__.keys():
        # Setting status
        status = status.casefold()
        # noinspection PyTypeChecker
        status_type: StatusType = StatusType[status]
        await self.bot.set_bot_presence(status=status_type)
        await ctx.reply(f"Status set to {status}.", ephemeral=True)

    elif status.casefold().startswith("playing ") and len(status) > 8:
        # Setting playing activity
        status = status[8:].strip()

        activity = Activity(name=status, type=ActivityType.playing)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)

    elif status.casefold().startswith("streaming ") and len(status) > 10:
        # Setting steaming activity
        status = status[10:].strip()
        url: str | None = None

        if (
            match := re.search(r"(?:https?://)?(?:www\.|m\.)?twitch\.tv/(?P<channel>\S+)\s*$", status)
        ) is not None:
            # If the status is a Twitch URL, extract the channel name
            channel = match.group("channel")
            # Remove the URL from the status, and strip
            status = re.sub(r"\s*(?:https?://)?(?:www\.|m\.)?twitch\.tv/(?P<channel>\S+)\s*$", "", status).strip()
            url = f"https://www.twitch.tv/{channel}"

        activity = Activity(name=status, type=ActivityType.streaming, url=url)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)

    elif status.casefold().startswith("watching ") and len(status) > 9:
        # Setting watching activity
        status = status[9:].strip()

        activity = Activity(name=status, type=ActivityType.watching)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)

    elif status.casefold().startswith("listening to ") and len(status) > 13:
        # Setting listening activity
        status = status[13:].strip()

        activity = Activity(name=status, type=ActivityType.listening)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)

    elif status.casefold().startswith("competing in ") and len(status) > 13:
        # Setting competing activity
        status = status[13:].strip()

        activity = Activity(name=status, type=ActivityType.competing)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)

    else:
        # Setting custom activity
        activity = Activity(name=status, type=ActivityType.custom)
        await self.bot.set_bot_presence(activity=activity)
        await ctx.reply(f"Activity set to {activity}.", ephemeral=True)


@wrap(commands.guild_only)
@status_command.command(name="clear")
async def status_clear_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Clear the bot's status and activity.
    """
    await self.bot.clear_bot_presence()
    await ctx.reply("Status and activity cleared.", ephemeral=True)
