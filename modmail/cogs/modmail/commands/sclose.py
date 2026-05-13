"""Command to silently close a Modmail ticket.

This command allows staff members to close a Modmail ticket without sending a message to the user.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, ParamInfo, _, bot_command, in_modmail_ticket, staff_only
from modmail.enum import TicketMessageType, TicketStatus

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["sclose_command"]

logger = logging.getLogger(__name__)


@staff_only
@bot_command(
    name=_("ftl-cmd-sclose-name"),
    description=_("ftl-cmd-sclose-description"),
    help=_("ftl-cmd-sclose-help"),
    param_info={
        "attachment": ParamInfo(
            name=_("ftl-cmd-sclose-param-attachment-name"),
            description=_("ftl-cmd-sclose-param-attachment-description"),
        ),
        "message": ParamInfo(
            name=_("ftl-cmd-sclose-param-message-name"),
            description=_("ftl-cmd-sclose-param-message-description"),
        ),
    },
)
@in_modmail_ticket()
async def sclose_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Close the current ticket without notifying the recipient(s).

    Any `message` or `attachment` is saved in the ticket log but not delivered.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context.
        attachment: Attachment to log (not sent to recipients).
        message: Note saved to the ticket log, not delivered to recipients.

    Raises:
        RuntimeError: When invoked outside a recognized ticket channel.
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
