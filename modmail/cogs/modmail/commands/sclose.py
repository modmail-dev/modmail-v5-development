"""Command to silently close a Modmail ticket.

This command allows staff members to close a Modmail ticket without sending a message to the user.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, _, in_modmail_ticket, lazy_hybrid_command, staff_only, wrap
from modmail.enum import TicketMessageType, TicketStatus

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["sclose_command"]

logger = logging.getLogger(__name__)


@staff_only
@wrap(
    discord.app_commands.rename,
    attachment=_("ftl-cmd-sclose-param-attachment-name"),
    message=_("ftl-cmd-sclose-param-message-name"),
)
@wrap(
    discord.app_commands.describe,
    attachment=_("ftl-cmd-sclose-param-attachment-description"),
    message=_("ftl-cmd-sclose-param-message-description"),
)
@lazy_hybrid_command(
    name=_("ftl-cmd-sclose-name"),
    description=_("ftl-cmd-sclose-description"),
)
@in_modmail_ticket()
async def sclose_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Silently close a ticket in Modmail.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the close message. Auto parsed by discord.py.
        message: The message to save as a close message (not sent to recipient).

    Raises:
        RuntimeError: If an impossible situation is encountered.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    if ctx.interaction is not None:
        await ctx.reply(_("ftl-cmd-sclose-message-sending"), delete_after=2, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise RuntimeError("Ticket should not be None here.")

    if not message and not attachment:
        message = "Ticket closed."  # TODO: config

    try:
        await ticket.process_reply_message(ctx, message, TicketMessageType.sclose)
    except Exception:
        logger.exception("Failed to save sclose message in %s", ctx.channel)

    if ctx.interaction is not None:
        with contextlib.suppress(discord.HTTPException):
            await ctx.interaction.delete_original_response()

    try:
        await cog.bot.staff_guild.close_ticket(
            ticket.model, closer=ctx.author, close_status=TicketStatus.closed_by_command
        )
    except Exception:
        logger.exception("Failed to close ticket in %s", ctx.channel)
        await ctx.reply(_("ftl-cmd-sclose-failed"), ephemeral=True)
