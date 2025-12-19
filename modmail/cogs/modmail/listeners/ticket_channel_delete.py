"""Listeners for ticket channel deletion.

This module handles the deletion of ticket channels in the Discord server.
It automatically closes the corresponding ticket in the database when a channel is deleted,
and attempts to identify who deleted the channel through audit logs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import discord
from discord.ext import commands

from modmail.backends.common import TicketUserModel
from modmail.enum import TicketStatus

if TYPE_CHECKING:
    from .. import Modmail


__all__ = ["ticket_channel_delete"]

logger = logging.getLogger(__name__)


@commands.Cog.listener("on_guild_channel_delete")
async def ticket_channel_delete(cog: Modmail, channel: discord.abc.GuildChannel) -> None:
    """Handle ticket channel deletion.

    Args:
        cog: The DMReceiveListener instance.
        channel: The deleted channel.
    """
    if channel.guild.id != cog.bot.staff_guild.guild_id:
        return

    ticket_model = await cog.bot.database_client.get_ticket_by_channel(channel.id, only_open=True)
    if ticket_model:
        if channel.guild.me.guild_permissions.view_audit_log:
            # Find the closing entry in the audit log
            audit_logs = channel.guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete)
            async for entry in audit_logs:
                if not entry.target:  # if there is no target (should not happen but just in case)
                    continue

                if entry.target.id == channel.id:
                    logger.info(
                        "Ticket channel %s deleted by %s, closing ticket %s",
                        channel,
                        entry.user,
                        ticket_model.key,
                    )

                    if not entry.user:  # if there is no user (should not happen but just in case)
                        audit_user = cast(discord.ClientUser, cog.bot.user)
                    else:
                        audit_user = entry.user

                    await cog.bot.database_client.close_ticket(
                        ticket_model.key,
                        TicketUserModel.from_user(audit_user),
                        ticket_status=TicketStatus.closed_by_deletion,
                    )
                    return
        else:
            logger.warning("Ticket channel %s manually deleted, closing ticket %s", channel, ticket_model.key)
            logger.warning(
                "[red]View audit log permission not granted, unable to find the user who deleted the channel.",
                extra={"markup": True},
            )

        # If the audit log entry is not found, close the ticket with the bot as the user
        await cog.bot.database_client.close_ticket(
            ticket_model.key,
            TicketUserModel.from_user(cast(discord.ClientUser, cog.bot.user)),
            ticket_status=TicketStatus.closed_by_deletion,
        )
