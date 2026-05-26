"""Listeners for ticket channel deletion.

This module handles the deletion of ticket channels in the Discord server.
It automatically closes the corresponding ticket in the database when a channel is deleted,
and attempts to identify who deleted the channel through audit logs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail.enum import TicketStatus

if TYPE_CHECKING:
    from .. import Modmail


__all__ = ["ticket_channel_delete"]

logger = logging.getLogger(__name__)


@commands.Cog.listener("on_guild_channel_delete")
async def ticket_channel_delete(cog: Modmail, channel: discord.abc.GuildChannel) -> None:
    """Handle ticket channel deletion.

    Args:
        cog: The Modmail cog instance (self).
        channel: The deleted channel.
    """
    if channel.guild.id != cog.bot.staff_guild.guild_id:
        return

    ticket_model = await cog.bot.db.get_ticket_by_channel(channel.id, only_open=True)
    if not ticket_model:
        return

    view = await cog.bot.staff_guild.get_ticket(ticket_model)
    if view is None:
        return

    if channel.guild.me.guild_permissions.view_audit_log:
        audit_logs = channel.guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete)
        async for entry in audit_logs:
            if not entry.target:
                continue
            if entry.target.id == channel.id:
                logger.info(
                    "Ticket channel %s deleted by %s, closing ticket %s",
                    channel,
                    entry.user,
                    ticket_model.key,
                )
                await view.close(
                    closer=entry.user or None,
                    close_status=TicketStatus.closed_by_deletion,
                )
                return
    else:
        logger.warning(
            "[red]View audit log permission not granted, unable to find the user who deleted the channel.",
            extra={"markup": True},
        )

    logger.info("Ticket channel %s manually deleted by unknown user, closing ticket %s", channel, ticket_model.key)
    await view.close(closer=None, close_status=TicketStatus.closed_by_deletion)
