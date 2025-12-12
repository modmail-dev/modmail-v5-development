"""Listeners for thread channel deletion.

This module handles the deletion of thread channels in the Discord server.
It automatically closes the corresponding thread in the database when a channel is deleted,
and attempts to identify who deleted the channel through audit logs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import discord
from discord.ext import commands

from modmail.backends.common import ThreadUserModel
from modmail.enum import ThreadStatus

if TYPE_CHECKING:
    from .. import Modmail


__all__ = ["thread_channel_delete"]

logger = logging.getLogger(__name__)


@commands.Cog.listener("on_guild_channel_delete")
async def thread_channel_delete(cog: Modmail, channel: discord.abc.GuildChannel) -> None:
    """Handle thread channel deletion.

    Args:
        cog: The DMReceiveListener instance.
        channel: The deleted channel.
    """
    if channel.guild.id != cog.bot.staff_guild.guild_id:
        return

    thread_model = await cog.bot.database_client.get_thread_by_channel(channel.id, only_open=True)
    if thread_model:
        if channel.guild.me.guild_permissions.view_audit_log:
            # Find the closing entry in the audit log
            audit_logs = channel.guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete)
            async for entry in audit_logs:
                if not entry.target:  # if there is no target (should not happen but just in case)
                    continue

                if entry.target.id == channel.id:
                    logger.info(
                        "Thread channel %s deleted by %s, closing thread %s",
                        channel,
                        entry.user,
                        thread_model.key,
                    )

                    if not entry.user:  # if there is no user (should not happen but just in case)
                        audit_user = cast(discord.ClientUser, cog.bot.user)
                    else:
                        audit_user = entry.user

                    await cog.bot.database_client.close_thread(
                        thread_model.key,
                        ThreadUserModel.from_user(audit_user),
                        thread_status=ThreadStatus.closed_by_deletion,
                    )
                    return
        else:
            logger.warning("Thread channel %s manually deleted, closing thread %s", channel, thread_model.key)
            logger.warning(
                "[red]View audit log permission not granted, unable to find the user who deleted the channel.",
                extra={"markup": True},
            )

        # If the audit log entry is not found, close the thread with the bot as the user
        await cog.bot.database_client.close_thread(
            thread_model.key,
            ThreadUserModel.from_user(cast(discord.ClientUser, cog.bot.user)),
            thread_status=ThreadStatus.closed_by_deletion,
        )
