"""Modmail Reply Command.

This module defines the `reply_command`, a command for staff members to reply to Modmail threads.
It ensures proper context validation, supports attachments, and handles errors gracefully.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail.core import Bot, _, in_modmail_thread, lazy_hybrid_command, staff_only, wrap
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
@in_modmail_thread()
async def reply_command(
    cog: Modmail,
    ctx: commands.Context[Bot],
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Reply to a thread in Modmail.

    This command allows staff members to reply to a thread in Modmail. It checks if the
    command is invoked in the correct channel and sends the message to the thread.

    The attachment parameter is used to send files along with the message for slash commands.
    It is automatically parsed by discord.py and injected into ctx.message.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the reply. Auto parsed by discord.py.
        message: The message to send as a reply.

    Raises:
        ModmailError: If the command is invoked outside a Modmail thread (exception caught internally).
    """
    # TODO: Support sending stickers
    if not message and not attachment:
        await cog.reply(ctx, _("ftl-cmd-reply-message-empty"), ephemeral=True, auto_embed=False)
        return

    if ctx.interaction is not None:
        await cog.reply(ctx, _("flt-cmd-reply-message-sending"), delete_after=3, ephemeral=True, auto_embed=False)

    assert isinstance(ctx.channel, discord.abc.GuildChannel)
    thread = await cog.bot.staff_guild.get_thread(ctx.channel)
    if thread is None:
        raise ModmailError("Thread should not be None here.")

    try:
        failed_recipients = await thread.process_reply_message(ctx, message)

        if failed_recipients:
            # Send a message about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            await cog.send(ctx, _("ftl-cmd-reply-message-failed-recipients", recipients=failed_recipients_str))

    except Exception:
        logger.exception("Failed to send reply in %s", ctx.channel)
        await cog.reply(ctx, _("ftl-cmd-reply-message-failed"))
    else:
        if ctx.interaction is not None:
            await ctx.interaction.delete_original_response()
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException as e:
                logger.info("Failed to delete the message after replying in %s: %s", ctx.channel, e)
