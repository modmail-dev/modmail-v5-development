"""Modmail Reply Command.

This module defines the `reply_command`, a command for staff members to reply to Modmail tickets.
It ensures proper context validation, supports attachments, and handles errors gracefully.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from modmail.core import Context, ParamInfo, _, bot_command, in_modmail_ticket, staff_only

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["reply_command"]

logger = logging.getLogger(__name__)


@staff_only
@bot_command(
    name=_("ftl-cmd-reply-name"),
    description=_("ftl-cmd-reply-description"),
    help=_("ftl-cmd-reply-help"),
    param_info={
        "attachment": ParamInfo(
            name=_("ftl-cmd-reply-param-attachment-name"),
            description=_("ftl-cmd-reply-param-attachment-description"),
        ),
        "message": ParamInfo(
            name=_("ftl-cmd-reply-param-message-name"),
            description=_("ftl-cmd-reply-param-message-description"),
        ),
    },
)
@in_modmail_ticket()
async def reply_command(
    cog: Modmail,
    ctx: Context,
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Send a reply to the ticket's recipient(s).

    At least one of `message` or `attachment` must be provided.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context.
        attachment: File to include in the reply.
        message: Reply text sent to the recipient(s).

    Raises:
        RuntimeError: When invoked outside a recognized ticket channel.
    """
    if not isinstance(ctx.channel, discord.TextChannel | discord.Thread):
        raise RuntimeError("Command invoked in a non-text channel, which should be impossible.")

    # TODO: Support sending stickers
    if not message and not attachment:
        await ctx.reply(_("ftl-cmd-reply-message-empty"), ephemeral=True)
        return

    if ctx.interaction is not None:
        await ctx.reply(_("ftl-cmd-reply-message-sending"), delete_after=2, ephemeral=True)

    ticket = await cog.bot.staff_guild.get_ticket(ctx.channel)
    if ticket is None:
        raise RuntimeError("Ticket should not be None here.")

    try:
        failed_recipients = await ticket.process_reply_message(ctx, message)
        if failed_recipients:
            # Send a message about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            cog.bot.spawn_task(
                ctx.send(_("ftl-cmd-reply-message-failed-recipients", recipients=failed_recipients_str)),
                name=f"send_failed_recipients:{failed_recipients_str}",
                suppress_errors=True,
            )

    except Exception:
        logger.exception("Failed to send reply in %s", ctx.channel)
        await ctx.reply(_("ftl-cmd-reply-message-failed"), ephemeral=True)
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
