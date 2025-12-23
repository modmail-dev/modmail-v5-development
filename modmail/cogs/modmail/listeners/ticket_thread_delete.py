"""Listeners for ticket thread deletion.

This module handles the deletion of ticket threads in the Discord server.
It automatically closes the corresponding ticket in the database when a thread is deleted,
and attempts to identify who deleted the thread through audit logs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail.enum import TicketStatus

if TYPE_CHECKING:
    from .. import Modmail


__all__ = ["ticket_thread_delete"]

logger = logging.getLogger(__name__)


@commands.Cog.listener("on_raw_thread_delete")
async def ticket_thread_delete(cog: Modmail, payload: discord.RawThreadDeleteEvent) -> None:
    """Handle ticket thread deletion.

    Args:
        cog: The Modmail cog instance (self).
        payload: The raw thread delete event payload.
    """
    if payload.guild_id != cog.bot.staff_guild.guild_id:
        return

    ticket_model = await cog.bot.database_client.get_ticket_by_channel(payload.thread_id, only_open=True)
    if not ticket_model:
        return

    if cog.bot.staff_guild.guild.me.guild_permissions.view_audit_log:
        # Find the closing entry in the audit log
        audit_logs = cog.bot.staff_guild.guild.audit_logs(limit=10, action=discord.AuditLogAction.thread_delete)
        async for entry in audit_logs:
            if not entry.target:  # if there is no target (should not happen but just in case)
                continue

            if entry.target.id == payload.thread_id:
                logger.info(
                    "Ticket channel (ID: %s) deleted by %s, closing ticket %s",
                    payload.thread_id,
                    entry.user,
                    ticket_model.key,
                )

                audit_user = None
                if entry.user:
                    audit_user = entry.user

                await cog.bot.staff_guild.close_ticket(
                    ticket_model, closer=audit_user, close_status=TicketStatus.closed_by_deletion
                )
                return
    else:
        logger.warning(
            "[red]View audit log permission not granted, unable to find the user who deleted the thread.",
            extra={"markup": True},
        )

    logger.info(
        "Ticket thread (ID: %s) manually deleted by unknown user, closing ticket %s",
        payload.thread_id,
        ticket_model.key,
    )

    await cog.bot.staff_guild.close_ticket(ticket_model, closer=None, close_status=TicketStatus.closed_by_deletion)
