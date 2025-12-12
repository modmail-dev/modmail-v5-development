"""Command to silently close a Modmail thread.

This command allows staff members to close a Modmail thread without sending a message to the user.
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
@in_modmail_thread()
async def sclose_command(
    cog: Modmail,
    ctx: commands.Context[Bot],
    attachment: discord.Attachment | None,
    *,
    message: str = "",
) -> None:
    """Silently close a thread in Modmail.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
        attachment: An optional attachment to include in the close message. Auto parsed by discord.py.
        message: The message to save as a close message (not sent to recipient).

    Raises:
        ModmailError: If the command is invoked outside a Modmail thread.
    """
    if ctx.interaction is not None:
        await cog.reply(ctx, _("ftl-cmd-sclose-message-sending"), delete_after=3, ephemeral=True, auto_embed=False)

    assert isinstance(ctx.channel, discord.abc.GuildChannel)
    thread = await cog.bot.staff_guild.get_thread(ctx.channel)
    if thread is None:
        raise ModmailError("Thread should not be None here.")

    if not message and not attachment:
        message = "Thread closed."  # TODO: config

    try:
        await thread.process_reply_message(ctx, message, ThreadMessageType.sclose)
    except Exception:
        logger.exception("Something went wrong sending sclose message in %s", ctx.channel)
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
