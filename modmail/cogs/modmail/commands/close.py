"""Command to close a Modmail ticket.

This command allows staff members to close a Modmail ticket and send a message to the user
indicating that the ticket has been closed.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, ParamInfo, bot_command, in_modmail_ticket, staff_only
from modmail.enum import TicketMessageType, TicketStatus
from modmail.errors import ModmailError
from modmail.i18n import _

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["close_command"]

logger = logging.getLogger(__name__)


@staff_only
@bot_command(
    name=_("cmd.close.name"),
    description=_("cmd.close.description"),
    help=_("cmd.close.help"),
    param_info={
        "attachment": ParamInfo(
            name=_("cmd.close.param.attachment.name"),
            description=_("cmd.close.param.attachment.description"),
        ),
        "message_text": ParamInfo(
            name=_("cmd.close.param.message.name"),
            description=_("cmd.close.param.message.description"),
        ),
    },
)
@in_modmail_ticket()
async def close_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message_text: str = "",
) -> None:
    """Close the current ticket and send a close message to the recipient(s).

    Args:
        cog: The Modmail cog instance.
        ctx: The command context.
        attachment: Attachment to include in the close message.
        message_text: Close message sent to the recipient(s).

    Raises:
        RuntimeError: When invoked outside a recognized ticket channel.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    if ctx.interaction is not None:
        await ctx.reply(_("msg.close.sending"), delete_after=2, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise RuntimeError("Ticket should not be None here.")

    if not message_text and not attachment:
        # @param closer: Discord user ID of the user closing the ticket
        message_text = ctx.t(_("msg.close.default_message", closer=str(ctx.author.id)))

    ctx.message.content = message_text

    try:
        await ticket.process_reply_message(ctx.message, TicketMessageType.close)
    except ModmailError, discord.HTTPException:
        logger.exception("Failed to send close message in %s", ctx.channel)
        await ctx.reply(_("msg.close.message_failed"), ephemeral=True)

    if ctx.interaction is not None:
        with contextlib.suppress(discord.HTTPException):
            await ctx.interaction.delete_original_response()

    closed = await ticket.close(closer=ctx.author, close_status=TicketStatus.closed_by_command)
    if not closed:
        await ctx.reply(_("msg.close.failed"), ephemeral=True)
        # TODO: delete the close message that was sent, since the ticket is still open
