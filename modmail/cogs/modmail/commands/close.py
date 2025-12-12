"""Command to close a Modmail thread.

This command allows staff members to close a Modmail thread and send a message to the user
indicating that the thread has been closed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail.core import Bot, _, in_modmail_thread, lazy_hybrid_command, staff_only, wrap
from modmail.enum import ThreadMessageType, ThreadStatus
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
@in_modmail_thread()
async def close_command(
    cog: Modmail,
    ctx: commands.Context[Bot],
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Close a thread in Modmail.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the close message. Auto parsed by discord.py.
        message: The message to send as a close message.

    Raises:
        ModmailError: If the command is invoked outside a Modmail thread.
    """
    if ctx.interaction is not None:
        await cog.reply(ctx, _("ftl-cmd-close-message-sending"), delete_after=3, ephemeral=True, auto_embed=False)

    assert isinstance(ctx.channel, discord.abc.GuildChannel)
    thread = await cog.bot.staff_guild.get_thread(ctx.channel)
    if thread is None:
        raise ModmailError("Thread should not be None here.")

    if not message and not attachment:
        message = "Thread closed."  # TODO: config

    try:
        failed_recipients = await thread.process_reply_message(ctx, message, ThreadMessageType.close)

        if failed_recipients:
            # Send a message about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            await cog.send(ctx, _("ftl-cmd-close-message-failed-recipients", recipients=failed_recipients_str))

    except Exception:
        logger.exception("Failed to send close message in %s", ctx.channel)
        await cog.reply(ctx, _("ftl-cmd-close-message-failed"))
    else:
        if ctx.interaction is not None:
            await ctx.interaction.delete_original_response()
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException as e:
                logger.info("Failed to delete the message after closing in %s: %s", ctx.channel, e)
    finally:
        # Close the thread
        await thread.close(ctx.author, ThreadStatus.closed_by_command)
    # TODO: delete channel, create auto delete after close config
