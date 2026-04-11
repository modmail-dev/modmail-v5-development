"""Server setup command.

This module implements the setup command and its related functionality, allowing server
administrators to configure their Discord server for use with Modmail. The setup process
creates necessary categories and channels with appropriate permissions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Literal

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
async def setup_command(cog: Modmail, ctx: commands.Context[Bot]) -> None:
    """Configure the server for Modmail.

    This command initiates the setup process for Modmail in a guild. It checks if
    the command is run in the correct guild and ensures only one setup can run at a time.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
    """
    if ctx.guild is None or ctx.guild.id != cog.bot.staff_guild.guild_id:
        await cog.reply(ctx, _("ftl-cmd-setup-wrong-guild", guild_name=cog.bot.staff_guild.guild.name))
        return

    if setup_lock.locked():
        await cog.reply(ctx, _("ftl-cmd-setup-already-running"))
        return

    async with setup_lock:
        await do_setup(cog, ctx)


async def do_setup(cog: Modmail, ctx: commands.Context[Bot]) -> None:
    """Perform the full setup process for the Modmail bot in a guild.

    This function handles the interactive setup process including:
    - Checking if the guild is already configured
    - Creating or selecting a category for Modmail channels
    - Setting appropriate permissions for staff members
    - Creating and configuring log and storage channels
    - Finalizing the setup and informing the user

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.

    Raises:
        discord.HTTPException: If there is an error creating channels or categories.
    """
    assert ctx.guild is not None, "This function should only be run in a guild context"

    prompt_message: discord.Message | None = None  # The latest prompt message
    response_message: discord.Message | None = None  # The latest response message

    if ctx.guild.me.guild_permissions & cog.bot.staff_guild.MIN_PERMISSIONS != cog.bot.staff_guild.MIN_PERMISSIONS:
        await cog.reply(ctx, _("ftl-cmd-setup-not-enough-guild-permissions"))
        logger.debug("Bot doesn't have enough permissions to create a new category/forum")
        return

    if cog.bot.staff_guild.is_configured():
        prompt_message, response = await cog.prompt_choices(
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

    prompt_message, response = await cog.prompt_choices(
        ctx,
        _("ftl-cmd-setup-use-category-or-forum-prompt"),
        choices=[
            _("ftl-cmd-setup-use-category-or-forum-prompt-category"),
            _("ftl-cmd-setup-use-category-or-forum-prompt-forum"),
        ],
        original_message=prompt_message,
    )
    if response is None:
        logger.debug("User didn't respond to the prompt or cancelled, cancelling setup")
        return

    setup_type: Literal["category", "forum"]
    if response == 0:  # Using a category
        logger.info("Setting up Modmail using categories")
        setup_type = "category"
        prompt_message, response = await cog.prompt_choices(
            ctx,
            _("ftl-cmd-setup-use-new-category-prompt"),
            choices=[
                _("ftl-cmd-setup-use-new-category-prompt-new"),
                _("ftl-cmd-setup-use-new-category-prompt-existing"),
            ],
            original_message=prompt_message,
        )
    else:  # Using a forum
        logger.info("Setting up Modmail using forums")
        setup_type = "forum"
        prompt_message, response = await cog.prompt_choices(
            ctx,
            _("ftl-cmd-setup-use-new-forum-prompt"),
            choices=[
                _("ftl-cmd-setup-use-new-forum-prompt-new"),
                _("ftl-cmd-setup-use-new-forum-prompt-existing"),
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

    if response == 0:  # Using a new category/forum
        logger.info("Creating a new %s for Modmail", setup_type)

        # Gives the bot the minimum permissions required to function properly,
        # and hide from everyone else.
        overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            me_user_or_role: cog.bot.staff_guild.MIN_PERMISSIONS_OVERWRITE,
        }

        # Allow staff members to see the category and channels
        for profile in cog.bot.database_client.profiles:
            if profile.access_level is not None and profile.access_level >= AccessLevel.staff:
                if profile.profile_type == ProfileType.user:
                    try:
                        # Fetch the member since member cache is disabled
                        user = await ctx.guild.fetch_member(profile.profile_id)
                    except discord.NotFound:
                        continue
                    logger.info("Granting %s access to Modmail perms", user)
                    overwrites[user] = discord.PermissionOverwrite(read_messages=True)
                elif profile.profile_type == ProfileType.role:
                    role = ctx.guild.get_role(profile.profile_id)
                    if role is None:
                        continue
                    logger.info("Granting %s access to Modmail perms", role)
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)

        if setup_type == "category":
            category_or_forum = await ctx.guild.create_category(
                name=await cog.translate(ctx, _("ftl-cmd-setup-category-or-forum-name")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-category-or-forum-create-reason")),
                overwrites=overwrites,
                position=0,
            )
        else:
            category_or_forum = await ctx.guild.create_forum(
                name=await cog.translate(ctx, _("ftl-cmd-setup-category-or-forum-name")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-category-or-forum-create-reason")),
                overwrites=overwrites,
                position=0,
                default_auto_archive_duration=10080,  # 7 days
            )
        await category_or_forum.edit(position=0)  # Force to the top of the channels list

    else:  # Using an existing category
        prompt_message, response_message = await cog.prompt(
            ctx,
            _("ftl-cmd-setup-use-new-category-prompt-existing-category")
            if setup_type == "category"
            else _("ftl-cmd-setup-use-new-forum-prompt-existing-forum"),
            original_message=prompt_message,
        )

        if response_message is None:
            logger.debug("User didn't respond to the prompt or cancelled, cancelling setup")
            return

        # Find the category/forum by name or ID
        new_category_or_forum_name_or_id = response_message.content.strip().casefold()
        if setup_type == "category":
            all_categories_or_forums = ctx.guild.categories
        else:
            all_categories_or_forums = ctx.guild.forums

        for guild_category_or_forum in all_categories_or_forums:
            if guild_category_or_forum.name.strip().casefold() == new_category_or_forum_name_or_id or (
                new_category_or_forum_name_or_id.isdigit()
                and guild_category_or_forum.id == int(new_category_or_forum_name_or_id)
            ):
                category_or_forum = guild_category_or_forum
                break
        else:
            await cog.reply(
                ctx,
                _("ftl-cmd-setup-use-new-category-prompt-existing-category-not-found")
                if setup_type == "category"
                else _("ftl-cmd-setup-use-new-forum-prompt-existing-forum-not-found"),
                reference=response_message,
            )
            logger.debug(
                "Category/forum %s not found and cannot be used for Modmail", new_category_or_forum_name_or_id
            )
            return

        if (
            category_or_forum.permissions_for(ctx.guild.me) & cog.bot.staff_guild.MIN_PERMISSIONS
            != cog.bot.staff_guild.MIN_PERMISSIONS
        ):
            await cog.reply(
                ctx,
                _("ftl-cmd-setup-use-new-category-prompt-existing-category-no-permissions")
                if setup_type == "category"
                else _("ftl-cmd-setup-use-new-forum-prompt-existing-forum-no-permissions"),
                reference=response_message,
            )
            logger.debug("Bot doesn't have enough permissions to use the category %s", category_or_forum)
            return

        logger.info("Using existing category/forum %s for Modmail", category_or_forum)
        await category_or_forum.set_permissions(
            me_user_or_role,
            overwrite=cog.bot.staff_guild.MIN_PERMISSIONS_OVERWRITE,
            reason=await cog.translate(ctx, _("ftl-cmd-setup-category-or-forum-permissions-reason")),
        )

    if setup_type == "category":
        assert isinstance(category_or_forum, discord.CategoryChannel), (
            "category_or_forum should be a CategoryChannel"
        )

        # Create the channels
        log_channel, storage_channel = await asyncio.gather(
            category_or_forum.create_text_channel(
                name=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-name")),
                topic=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-topic")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-create-reason")),
                position=0,  # This will be updated later (position here is useless)
            ),
            category_or_forum.create_text_channel(
                name=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-name")),
                topic=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-topic")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-create-reason")),
                position=0,  # This will be updated later (position here is useless)
            ),
        )

        await asyncio.gather(
            # Disallow everyone but the bot to send messages in the storage channel
            # Previously allowed staffs should still be able to see the channel
            storage_channel.set_permissions(ctx.guild.default_role, read_messages=False, send_messages=False),
            cog.bot.staff_guild.setup(category_or_forum, log_channel, storage_channel),
        )

        await cog.reply(
            ctx,
            _(
                "ftl-cmd-setup-category-complete",
                category=category_or_forum.name,
                log_channel=log_channel.mention,
                storage_channel=storage_channel.mention,
            ),
            reference=response_message,
        )

        await log_channel.edit(position=0)  # Force the log channel to the top of the category
        await storage_channel.edit(position=1)  # Force the storage channel to be below the log channel

    else:  # forum
        assert isinstance(category_or_forum, discord.ForumChannel), "category_or_forum should be a ForumChannel"

        # Create the channels as forum threads
        log_channel_with_message, storage_channel_with_message = await asyncio.gather(
            category_or_forum.create_thread(
                name=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-name")),
                content=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-topic")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-create-reason")),
            ),
            category_or_forum.create_thread(
                name=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-name")),
                content=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-topic")),
                reason=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-create-reason")),
            ),
        )
        log_channel = log_channel_with_message.thread
        storage_channel = storage_channel_with_message.thread

        # Unpin any existing pinned threads in the forum
        for thread in category_or_forum.threads:
            if thread.flags.pinned:
                await thread.edit(
                    pinned=False,
                    reason=await cog.translate(ctx, _("ftl-cmd-setup-forum-thread-unpin-reason")),
                )
                break  # only one thread can be pinned, so we can stop after unpinning one

        try:
            await log_channel.edit(
                pinned=True,
                locked=True,
                reason=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-create-reason")),
            )
        except discord.HTTPException as e:
            # something went wrong, there should be no exception here,
            # but catching just in case of cache issues
            if e.code == 30047:  # Maximum number pinned threads in this channel reached (1).  # noqa: PLR2004
                logger.error(
                    "Could not pin the log channel thread in forum %s "
                    "because the maximum pinned threads is reached",
                    category_or_forum,
                )
                await log_channel.edit(
                    locked=True,
                    reason=await cog.translate(ctx, _("ftl-cmd-setup-log-channel-create-reason")),
                )
            else:
                raise

        await asyncio.gather(
            storage_channel.edit(
                locked=True,
                reason=await cog.translate(ctx, _("ftl-cmd-setup-storage-channel-create-reason")),
            ),
            cog.bot.staff_guild.setup(category_or_forum, log_channel, storage_channel),
        )

        await cog.reply(
            ctx,
            _(
                "ftl-cmd-setup-forum-complete",
                forum=category_or_forum.name,
                log_channel=log_channel.mention,
                storage_channel=storage_channel.mention,
            ),
            reference=response_message,
        )

    logger.info("Modmail setup complete in %s", ctx.guild.name)
