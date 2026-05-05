"""Command to close a Modmail ticket.

This command allows staff members to close a Modmail ticket and send a message to the user
indicating that the ticket has been closed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, _, in_modmail_ticket, lazy_hybrid_command, staff_only, wrap
from modmail.enum import TicketMessageType, TicketStatus
from modmail.errors import ModmailError

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["close_command"]

logger = logging.getLogger(__name__)


@staff_only
@wrap(
    discord.app_commands.rename,
    attachment=_("ftl-cmd-close-param-attachment-name"),
    message=_("ftl-cmd-close-param-message-name"),
)
@wrap(
    discord.app_commands.describe,
    attachment=_("ftl-cmd-close-param-attachment-description"),
    message=_("ftl-cmd-close-param-message-description"),
)
@lazy_hybrid_command(
    name=_("ftl-cmd-close-name"),
    description=_("ftl-cmd-close-description"),
)
@in_modmail_ticket()
async def close_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Close a ticket in Modmail.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the close message. Auto parsed by discord.py.
        message: The message to send as a close message.

    Raises:
        ModmailError: If the command is invoked outside a Modmail ticket.
        RuntimeError: If the command is invoked in a non-text channel, which should be impossible due
            to the in_modmail_ticket check.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    if ctx.interaction is not None:
        await ctx.reply(_("ftl-cmd-close-message-sending"), delete_after=3, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise ModmailError("Ticket should not be None here.")

    if not message and not attachment:
        message = "Ticket closed."  # TODO: config

    try:
        failed_recipients = await ticket.process_reply_message(ctx, message, TicketMessageType.close)

        if failed_recipients:
            # Send a message about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            await ctx.send(_("ftl-cmd-close-message-failed-recipients", recipients=failed_recipients_str))

    except Exception:
        logger.exception("Failed to send close message in %s", ctx.channel)
        await ctx.reply(_("ftl-cmd-close-message-failed"), ephemeral=True)
    else:
        if ctx.interaction is not None:
            await ctx.interaction.delete_original_response()
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException as e:
                logger.info("Failed to delete the message after closing in %s: %s", ctx.channel, e)
    finally:
        # Close the ticket
        await cog.bot.staff_guild.close_ticket(
            ticket.model, closer=ctx.author, close_status=TicketStatus.closed_by_command
        )
