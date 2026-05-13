"""Status command for setting the Modmail bot presence.

This module contains commands that allow administrators to set the bot's
status and activity message on Discord.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from modmail.backends.common import ActivityModel
from modmail.core import Context, ParamInfo, Str, _, admin_only, bot_group, ephemeral_scope, locale_for
from modmail.enum import ActivityType, StatusType

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["status_command"]


@admin_only
@bot_group(
    name=_("ftl-cmd-status-name"),
    fallback=_("ftl-cmd-status-fallback-name"),
    description=_("ftl-cmd-status-description"),
    help=_("ftl-cmd-status-help"),
    param_info={
        "status": ParamInfo(
            name=_("ftl-cmd-status-param-status-name"),
            description=_("ftl-cmd-status-param-status-description"),
        )
    },
)
async def status_command(cog: Utility, ctx: Context, *, status: Str | None = None) -> None:
    """Show or set the bot's Discord presence.

    With no argument, replies ephemerally with the current status and activity.

    Status names: `online`, `idle`, `dnd` / `do not disturb`, `offline` / `invisible`.
    Activity prefixes: `playing`, `watching`, `listening to`, `competing in`,
    `streaming <title> https://www.twitch.tv/<channel>`. Any other value sets a custom activity.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        status: Status name or activity string. Omit to view the current presence.
    """
    if not status:
        with ephemeral_scope(ctx.interaction):
            current_status = cog.bot.database_client.settings.status
            current_activity = cog.bot.database_client.settings.activity
            if current_status is not None and current_activity is not None:
                status_part = ctx.t("ftl-msg-status-current-status", status=current_status)
                activity_part = ctx.t("ftl-msg-status-current-activity", activity=current_activity)
                await ctx.reply(f"{status_part}\n{activity_part}")
            elif current_status is not None:
                await ctx.reply(_("ftl-msg-status-current-status", status=current_status))
            elif current_activity is not None:
                await ctx.reply(_("ftl-msg-status-current-activity", activity=current_activity))
            else:
                await ctx.reply(_("ftl-msg-status-no-status"))
            return

    locales = list(dict.fromkeys([locale_for(ctx.interaction), locale_for(None)]))

    status_name_mapping: dict[str, StatusType] = {
        cog.bot.translate(_(key), locale=loc).casefold(): value
        for loc in locales
        for key, value in [
            ("ftl-model-status-online-name", StatusType.online),
            ("ftl-model-status-idle-name", StatusType.idle),
            ("ftl-model-status-dnd-name", StatusType.dnd),
            ("ftl-model-status-dnd-full-name", StatusType.dnd),
            ("ftl-model-status-offline-name", StatusType.offline),
            ("ftl-model-status-invisible-name", StatusType.offline),
        ]
    }

    if status.casefold() in status_name_mapping:
        status_type = status_name_mapping[status.casefold()]
        await cog.bot.set_bot_presence(status=status_type)
        await ctx.reply(_("ftl-msg-status-set-status", status=status_type))
        return

    activity_name_mapping: dict[str, ActivityType] = {
        cog.bot.translate(_(key), locale=loc).casefold() + " ": value
        for loc in locales
        for key, value in [
            ("ftl-model-activity-playing-name", ActivityType.playing),
            ("ftl-model-activity-streaming-name", ActivityType.streaming),
            ("ftl-model-activity-listening-name", ActivityType.listening),
            ("ftl-model-activity-watching-name", ActivityType.watching),
            ("ftl-model-activity-competing-name", ActivityType.competing),
        ]
    }

    for activity_name, activity_type in activity_name_mapping.items():
        if status.casefold().startswith(activity_name) and len(status) > len(activity_name):
            status = status[len(activity_name) :].strip()
            if activity_type != ActivityType.streaming:
                # Setting activity (not streaming)
                activity = ActivityModel(name=status, type=activity_type)
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

                activity = ActivityModel(name=status, type=ActivityType.streaming, url=url)
            await cog.bot.set_bot_presence(activity=activity)
            await ctx.reply(_("ftl-msg-status-set-activity", activity=activity))
            return

    # Setting custom activity
    activity = ActivityModel(name=status, type=ActivityType.custom)
    await cog.bot.set_bot_presence(activity=activity)
    await ctx.reply(_("ftl-msg-status-set-activity", activity=activity))


@status_command.command(
    name=_("ftl-cmd-status-clear-name"),
    description=_("ftl-cmd-status-clear-description"),
    help=_("ftl-cmd-status-clear-help"),
)
async def status_clear_command(cog: Utility, ctx: Context) -> None:
    """Clear the bot's status and activity.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    await cog.bot.clear_bot_presence()
    await ctx.reply(_("ftl-msg-status-clear-status"))
