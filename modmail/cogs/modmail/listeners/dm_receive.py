"""Listen for incoming direct messages and handle them appropriately.

This module defines a listener for incoming direct messages in the Modmail bot.
It processes the messages, checks if the Modmail system is configured,
and creates or retrieves threads for the users.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail import CONFIG
from modmail.core import _
from modmail.errors import ModmailError

if TYPE_CHECKING:
    from .. import Modmail


__all__ = ["dm_receive"]

logger = logging.getLogger(__name__)


@commands.Cog.listener("on_message")
async def dm_receive(cog: Modmail, message: discord.Message) -> None:
    """Handle incoming direct messages.

    Args:
        cog: The DMReceiveListener instance.
        message: The incoming message.
    """
    # Ignore messages from bots
    if message.author.bot:
        return

    # Ignore messages that are not in DMs
    if not isinstance(message.channel, discord.DMChannel):
        return

    staff_guild = cog.bot.staff_guild

    # TODO: config
    success_emoji = "✅"
    error_emoji = "❌"

    if not staff_guild.is_configured():
        prefix = await cog.bot.get_prefix(message)
        if isinstance(prefix, str):
            prefix = [prefix]
        # Check if the message contains a prefix, if not, send a message to the user that Modmail is not configured
        if not any(message.content.startswith(p) for p in prefix):
            logger.warning("Received a DM from %s, but Modmail is not configured.", message.author)
            logger.warning("Message content: %s", message.content)

            msg = await cog.bot.translator.translate(
                _("ftl-dm-received-not-configured", guild_name=staff_guild.guild.name), CONFIG.default_locale
            )
            try:
                await message.reply(msg)
                if error_emoji:
                    await message.add_reaction(error_emoji)
            except (discord.HTTPException, TypeError):
                logger.exception("Failed to send DM or attach emoji to %s", message.author)
        return

    try:
        ctx = await cog.bot.get_context(message)
        try:
            if ctx.command is not None and await ctx.command.can_run(ctx):
                return  # Ignore if the message is a valid command
        except (commands.CommandError, ModmailError):
            pass  # Meaning the command is not valid or not allowed, proceed to process the DM

        thread = await staff_guild.get_thread(message.author)
        if thread is None:
            # If the user is not in a thread, create a new one
            thread = await staff_guild.create_thread(message.author, created_by=message.author)

        failed_recipients = await thread.process_dm_message(message)

        if failed_recipients:
            # Send a message to thread channel about the failed recipients
            failed_recipients_str = ", ".join(user.mention for user in failed_recipients)
            await cog.send(
                thread.channel, _("ftl-dm-received-failed-recipients", recipients=failed_recipients_str)
            )

    except Exception:
        logger.exception("Failed to process DM message from %s", message.author)
        if error_emoji:
            try:
                await message.add_reaction(error_emoji)
            except (discord.HTTPException, TypeError):
                logger.exception("Failed to add error emoji to %s", message.author)
    else:
        if success_emoji:
            try:
                await message.add_reaction(success_emoji)
            except (discord.HTTPException, TypeError):
                logger.exception("Failed to add success emoji to %s", message.author)
