"""Modmail Reply Command.

This module defines the `reply_command`, a command for staff members to reply to Modmail tickets.
It ensures proper context validation, supports attachments, and handles errors gracefully.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, ParamInfo, bot_command, in_modmail_ticket, staff_only
from modmail.i18n import _

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["reply_command"]

logger = logging.getLogger(__name__)


@staff_only
@bot_command(
    name=_("cmd.reply.name"),
    description=_("cmd.reply.description"),
    help=_("cmd.reply.help"),
    param_info={
        "attachment": ParamInfo(
            name=_("cmd.reply.param.attachment.name"),
            description=_("cmd.reply.param.attachment.description"),
        ),
        "message_text": ParamInfo(
            name=_("cmd.reply.param.message.name"),
            description=_("cmd.reply.param.message.description"),
        ),
    },
)
@in_modmail_ticket()
async def reply_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message_text: str = "",
) -> None:
    """Send a reply to the ticket's recipient(s).

    At least one of `message_text` or `attachment` must be provided.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context.
        attachment: File to include in the reply.
        message_text: Reply text sent to the recipient(s).

    Raises:
        RuntimeError: When invoked outside a recognized ticket channel.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    # TODO: Support sending stickers
    if not message_text and not attachment:
        await ctx.reply(_("msg.reply.message_empty"), ephemeral=True)
        return

    if ctx.interaction is not None:
        await ctx.reply(_("msg.reply.sending"), delete_after=2, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise RuntimeError("Ticket should not be None here.")

    ctx.message.content = message_text

    try:
        await ticket.process_reply_message(ctx.message)
    except Exception:
        logger.exception("Failed to send reply in %s", ctx.channel)
        await ctx.reply(_("msg.reply.message_failed"), ephemeral=True)
        return
    finally:
        if ctx.interaction is not None:
            cog.bot.spawn_task(
                ctx.interaction.delete_original_response(),
                name=f"delete_original_response:{ctx.interaction.id}",
                suppress_errors=True,
            )

    if ctx.interaction is None:
        cog.bot.spawn_task(
            ctx.message.delete(),
            name=f"delete_message:{ctx.message.id}",
            suppress_errors=True,
        )
