"""Listen for incoming direct messages and handle them appropriately.

This module defines a listener for incoming direct messages in the Modmail bot.
It processes the messages, checks if the Modmail system is configured,
and creates or retrieves tickets for the users.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

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
        cog: The Modmail cog instance (self).
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

    if not staff_guild.is_setup():
        prefix = await cog.bot.get_prefix(message)
        if isinstance(prefix, str):
            prefix = [prefix]
        # Check if the message contains a prefix, if not, send a message to the user
        # that Modmail is not configured
        if not any(message.content.startswith(p) for p in prefix):
            logger.warning("Received a DM from %s, but Modmail is not configured.", message.author)
            logger.warning("Message content: %s", message.content)

            msg = cog.bot.translate(_("ftl-msg-dm-received-not-configured", guild_name=staff_guild.guild.name))
            try:
                await message.reply(msg)
            except discord.HTTPException, TypeError:
                logger.exception("Failed to send DM to %s", message.author)
            else:
                if error_emoji:
                    cog.bot.spawn_task(
                        message.add_reaction(error_emoji),
                        name=f"add_reaction:{message.id}",
                        suppress_errors=True,
                    )
        return

    try:
        ctx = await cog.bot.get_context(message)
        try:
            if ctx.command is not None and await ctx.command.can_run(ctx):
                return  # Ignore if the message is a valid command
        except commands.CommandError, ModmailError:
            pass  # Meaning the command is not valid or not allowed, proceed to process the DM

        ticket = await staff_guild.get_ticket(message.author)
        if ticket is None:
            # If the user is not in a ticket, create a new one
            ticket = await staff_guild.create_ticket(
                message.author, created_by=message.author, starter_message=message
            )

        await ticket.process_dm_message(message)

    except Exception:
        logger.exception("Failed to process DM message from %s", message.author)
        if error_emoji:
            cog.bot.spawn_task(
                message.add_reaction(error_emoji),
                name=f"add_reaction:{message.id}",
                suppress_errors=True,
            )
    else:
        if success_emoji:
            cog.bot.spawn_task(
                message.add_reaction(success_emoji),
                name=f"add_reaction:{message.id}",
                suppress_errors=True,
            )
