"""Modmail Reply Command.

This module defines the `reply_command`, a command for staff members to reply to Modmail tickets.
It ensures proper context validation, supports attachments, and handles errors gracefully.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, _, in_modmail_ticket, lazy_hybrid_command, staff_only, wrap
from modmail.errors import ModmailError

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["reply_command"]

logger = logging.getLogger(__name__)


@staff_only
@wrap(
    discord.app_commands.rename,
    attachment=_("ftl-cmd-reply-param-attachment-name"),
    message=_("ftl-cmd-reply-param-message-name"),
)
@wrap(
    discord.app_commands.describe,
    attachment=_("ftl-cmd-reply-param-attachment-description"),
    message=_("ftl-cmd-reply-param-message-description"),
)
@lazy_hybrid_command(
    name=_("ftl-cmd-reply-name"),
    description=_("ftl-cmd-reply-description"),
)
@in_modmail_ticket()
async def reply_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Reply to a ticket in Modmail.

    This command allows staff members to reply to a ticket in Modmail. It checks if the
    command is invoked in the correct channel and sends the message to the ticket.

    The attachment parameter is used to send files along with the message for slash commands.
    It is automatically parsed by discord.py and injected into ctx.message.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the reply. Auto parsed by discord.py.
        message: The message to send as a reply.

    Raises:
        ModmailError: If the command is invoked outside a Modmail ticket (exception caught internally).
        RuntimeError: If the command is invoked in a non-text channel, which should be impossible due
            to the in_modmail_ticket check.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    # TODO: Support sending stickers
    if not message and not attachment:
        await ctx.reply(_("ftl-cmd-reply-message-empty"), ephemeral=True)
        return

    if ctx.interaction is not None:
        await ctx.reply(_("ftl-cmd-reply-message-sending"), delete_after=3, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise ModmailError("Ticket should not be None here.")

    try:
        failed_recipients = await ticket.process_reply_message(ctx, message)

        if failed_recipients:
            # Send a message about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            await ctx.send(_("ftl-cmd-reply-message-failed-recipients", recipients=failed_recipients_str))

    except Exception:
        logger.exception("Failed to send reply in %s", ctx.channel)
        await ctx.reply(_("ftl-cmd-reply-message-failed"), ephemeral=True)
    else:
        if ctx.interaction is not None:
            await ctx.interaction.delete_original_response()
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException as e:
                logger.info("Failed to delete the message after replying in %s: %s", ctx.channel, e)
