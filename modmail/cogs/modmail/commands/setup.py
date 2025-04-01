"""Server setup command.

This module implements the setup command and its related functionality, allowing server
administrators to configure their Discord server for use with Modmail. The setup process
creates necessary categories and channels with appropriate permissions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from modmail.core import Bot, _, lazy_hybrid_command, owner_only
from modmail.enum import AccessLevel, ProfileType

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["setup_command"]

logger = logging.getLogger(__name__)

setup_lock = asyncio.Lock()  # Lock to prevent multiple setup commands from running at the same time


@owner_only
@lazy_hybrid_command(
    name=_("ftl-cmd-setup-name"),
    description=_("ftl-cmd-setup-description"),
)
async def setup_command(self: Modmail, ctx: commands.Context[Bot]) -> None:
    """Configure the server for Modmail.

    This command initiates the setup process for Modmail in a guild. It checks if
    the command is run in the correct guild and ensures only one setup can run at a time.

    Args:
        self: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
    """
    if ctx.guild is None or ctx.guild.id != self.bot.staff_guild.guild_id:
        await self.reply(ctx, _("ftl-cmd-setup-wrong-guild", guild_name=self.bot.staff_guild.guild.name))
        return

    if setup_lock.locked():
        await self.reply(ctx, _("ftl-cmd-setup-already-running"))
        return

    async with setup_lock:
        await do_setup(self, ctx)


async def do_setup(self: Modmail, ctx: commands.Context[Bot]) -> None:
    """Perform the full setup process for the Modmail bot in a guild.

    This function handles the interactive setup process including:
    - Checking if the guild is already configured
    - Creating or selecting a category for Modmail channels
    - Setting appropriate permissions for staff members
    - Creating and configuring log and storage channels
    - Finalizing the setup and informing the user

    Args:
        self: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
    """
    assert ctx.guild is not None, "This function should only be ran in a guild context"

    prompt_message: discord.Message | None = None  # The latest prompt message
    response_message: discord.Message | None = None  # The latest response message

    if self.bot.staff_guild.is_configured():
        prompt_message, response = await self.prompt_choices(
            ctx,
            _("ftl-cmd-setup-guild-already-configured-prompt"),
            choices=[
                _("ftl-cmd-setup-guild-already-configured-prompt-continue-anyway"),
            ],
        )
        if response is None:
            logger.debug("User didn't respond to the prompt or cancelled, cancelling setup")
            return

    logger.info("%s is setting up the bot in %s", ctx.author, ctx.guild.name)

    prompt_message, response = await self.prompt_choices(
        ctx,
        _("ftl-cmd-setup-use-new-category-prompt"),
        choices=[
            _("ftl-cmd-setup-use-new-category-prompt-new"),
            _("ftl-cmd-setup-use-new-category-prompt-existing"),
        ],
        original_message=prompt_message,
    )
    if response is None:
        logger.debug("User didn't respond to the prompt or cancelled, cancelling setup")
        return

    # me_user_or_role is the bot's integration role or the bot Member, when setting permission overwrites
    try:
        me_user_or_role = discord.utils.get(ctx.guild.roles, tags__bot_id=ctx.me.id)
        if me_user_or_role is None:
            me_user_or_role = ctx.guild.me
    except AttributeError:  # role.tags could be None, so we need to catch the exception
        me_user_or_role = ctx.guild.me

    if response == 0:  # Using a new category
        if (
            ctx.guild.me.guild_permissions & self.bot.staff_guild.MIN_PERMISSIONS
            != self.bot.staff_guild.MIN_PERMISSIONS
        ):
            await self.reply(ctx, _("ftl-cmd-setup-not-enough-guild-permissions"))
            logger.debug("Bot doesn't have enough permissions to create a new category")
            return

        logger.info("Creating a new category for Modmail")

        # Gives the bot the minimum permissions required to function properly, and hide from everyone else.
        overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            me_user_or_role: self.bot.staff_guild.MIN_PERMISSIONS_OVERWRITE,
        }

        # Allow staff members to see the category and channels
        for profile in self.bot.database_client.profiles:
            if profile.access_level is not None and profile.access_level >= AccessLevel.staff:
                if profile.profile_type == ProfileType.user:
                    try:
                        user = await ctx.guild.fetch_member(profile.profile_id)
                    except discord.NotFound:
                        continue
                    logger.info("Granting %s access to the Modmail category", user)
                    overwrites[user] = discord.PermissionOverwrite(read_messages=True)
                elif profile.profile_type == ProfileType.role:
                    role = ctx.guild.get_role(profile.profile_id)
                    if role is None:
                        continue
                    logger.info("Granting %s access to the Modmail category", role)
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)

        category = await ctx.guild.create_category(
            name=await self.translate(ctx, _("ftl-cmd-setup-category-name")),
            reason=await self.translate(ctx, _("ftl-cmd-setup-category-create-reason")),
            overwrites=overwrites,
            position=0,
        )
        await category.edit(position=0)  # Force the category to the top of the channel list

    else:  # Using an existing category
        prompt_message, response_message = await self.prompt(
            ctx, _("ftl-cmd-setup-use-new-category-prompt-existing-category"), original_message=prompt_message
        )
        if response_message is None:
            logger.debug("User didn't respond to the prompt or cancelled, cancelling setup")
            return

        # Find the category by name or ID
        new_category_name_or_id = response_message.content.strip().casefold()
        for guild_category in ctx.guild.categories:
            if guild_category.name.strip().casefold() == new_category_name_or_id or (
                new_category_name_or_id.isdigit() and guild_category.id == int(new_category_name_or_id)
            ):
                category = guild_category
                break
        else:
            await self.reply(
                ctx,
                _("ftl-cmd-setup-use-new-category-prompt-existing-category-not-found"),
                reference=response_message,
            )
            logger.debug("Category %s not found and cannot be used as Modmail category", new_category_name_or_id)
            return

        if (
            category.permissions_for(ctx.guild.me) & self.bot.staff_guild.MIN_PERMISSIONS
            != self.bot.staff_guild.MIN_PERMISSIONS
        ):
            await self.reply(
                ctx,
                _("ftl-cmd-setup-use-new-category-prompt-existing-category-no-permissions"),
                reference=response_message,
            )
            logger.debug("Bot doesn't have enough permissions to use the category %s", category)
            return

        logger.info("Using existing category %s for Modmail", category)
        await category.set_permissions(
            me_user_or_role,
            overwrite=self.bot.staff_guild.MIN_PERMISSIONS_OVERWRITE,
            reason=await self.translate(ctx, _("ftl-cmd-setup-category-permissions-reason")),
        )

    # Create the channels
    log_channel, storage_channel = await asyncio.gather(
        category.create_text_channel(
            name=await self.translate(ctx, _("ftl-cmd-setup-log-channel-name")),
            topic=await self.translate(ctx, _("ftl-cmd-setup-log-channel-topic")),
            reason=await self.translate(ctx, _("ftl-cmd-setup-log-channel-create-reason")),
            position=0,  # This will be updated later (position here is useless)
        ),
        category.create_text_channel(
            name=await self.translate(ctx, _("ftl-cmd-setup-storage-channel-name")),
            topic=await self.translate(ctx, _("ftl-cmd-setup-storage-channel-topic")),
            reason=await self.translate(ctx, _("ftl-cmd-setup-storage-channel-create-reason")),
            position=0,  # This will be updated later (position here is useless)
        ),
    )

    await asyncio.gather(
        # Disallow everyone but the bot to send messages in the storage channel
        # Previously allowed staffs should still be able to see the channel
        storage_channel.set_permissions(ctx.guild.default_role, read_messages=False, send_messages=False),
        self.bot.staff_guild.setup(category, log_channel, storage_channel),
    )

    logger.info("Modmail setup complete in %s", ctx.guild.name)
    await self.reply(
        ctx,
        _(
            "ftl-cmd-setup-complete",
            category=category.name,
            log_channel=log_channel.mention,
            storage_channel=storage_channel.mention,
        ),
        reference=response_message,
    )

    await log_channel.edit(position=0)  # Force the log channel to the top of the category
    await storage_channel.edit(position=1)  # Force the storage channel to be below the log channel
