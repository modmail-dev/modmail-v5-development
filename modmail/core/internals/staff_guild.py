"""Module for managing the staff guild of the bot.

This module provides the StaffGuild class, which represents the staff server
for the bot and handles various operations related to it.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, cast

import discord

from ... import CONFIG
from ...backends.common import ThreadModel, ThreadUserModel
from ...enum import ProfileType, ThreadStatus
from ...errors import BadPermissionsError, NoModmailCategoryError, NoStaffGuildError
from ..translator import _
from .thread_view import ThreadView

if TYPE_CHECKING:
    from ..bot import Bot


logger = logging.getLogger(__name__)


__all__ = ["StaffGuild"]


class StaffGuild:
    """Represents the staff server for the bot."""

    def __init__(self, bot: Bot) -> None:
        """Initialize the StaffGuild for the modmail bot.

        Args:
            bot: The bot instance.
        """
        self.bot = bot
        self.guild_id = CONFIG.bot.staff_server_id

    def __str__(self) -> str:
        """Return the guild's name."""
        return self.guild.name if self.exists else "<Invalid Guild>"

    def __repr__(self) -> str:
        """Return a string representation of the StaffGuild instance."""
        return f"StaffGuild(guild_id={self.guild_id})"

    @property
    def MIN_PERMISSIONS(self) -> discord.Permissions:  # noqa: N802
        """The minimum permissions required for the bot to function properly.

        When changing this, make sure to also change the localization files.
        (ftl-cmd-setup-not-enough-guild-permissions, etc.)

        The view audit-log permission is highly recommended, but not required.
        It help logs the closer when they manually delete a thread channel.

        Returns:
            The discord.Permissions of the minimum permissions for Modmail.
        """
        # Using getter here to prevent accidental changes to the permissions.
        return discord.Permissions(
            read_messages=True,
            read_message_history=True,
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            add_reactions=True,
            attach_files=True,
            manage_channels=True,
            manage_messages=True,
            manage_roles=True,
        )

    @property
    def MIN_PERMISSIONS_OVERWRITE(self) -> discord.PermissionOverwrite:  # noqa: N802
        """The minimum permissions of the bot for the category's overwrites.

        Similar to MIN_PERMISSIONS, but manage roles cannot be set here due to limitations.

        Returns:
            The discord.PermissionOverwrite of the minimum permissions overwrite for Modmail.
        """
        # Using getter here to prevent accidental changes to the permissions.
        return discord.PermissionOverwrite(
            read_messages=True,
            read_message_history=True,
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            add_reactions=True,
            attach_files=True,
            manage_channels=True,
            manage_messages=True,
        )

    @property
    def exists(self) -> bool:
        """Check if the staff guild exists.

        Returns:
            True if the guild is valid, False otherwise.
        """
        try:
            return bool(self.guild)
        except NoStaffGuildError:
            return False

    @property
    def guild(self) -> discord.Guild:
        """Get the staff guild.

        Returns:
            The staff guild as a discord.Guild object.

        Raises:
            NoStaffGuildError: If the staff guild is not found.
        """
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            raise NoStaffGuildError(f"Staff guild with ID {self.guild_id} not found.")
        return guild

    @property
    def category(self) -> discord.CategoryChannel:
        """Get the modmail category.

        Returns:
            The modmail category if it exists, otherwise None.

        Raises:
            NoModmailCategoryError: If the modmail category is not found.
            NoStaffGuildError: If the staff guild is not found.
            BadPermissionsError: If the bot does not have the required permissions.
        """
        if not self.exists:  # Check if the guild exists
            raise NoStaffGuildError(f"Staff guild with ID {self.guild_id} not found.")

        category_id = self.bot.database_client.settings_model.main_category_id
        if category_id is None:
            raise NoModmailCategoryError("No modmail category found in the database.")

        category = discord.utils.get(self.guild.categories, id=category_id)
        if category is None:
            raise NoModmailCategoryError("Modmail category not found in the guild.")

        perms = category.permissions_for(category.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.critical("Some permissions were missing from the main category, category is unusable.")
            raise BadPermissionsError(
                "Some permissions were missing from the main category, category is unusable."
            )
        return category

    @property
    def log_channel(self) -> discord.TextChannel | None:
        """Get the modmail log channel.

        Returns:
            The modmail log channel if it exists, otherwise None.
        """
        if not self.exists:
            return None

        channel_id = self.bot.database_client.settings_model.log_channel_id
        if channel_id is None:
            return None

        channel = discord.utils.get(self.guild.text_channels, id=channel_id)
        if channel is None:
            return None

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.critical("Some permissions were missing from the log channel, channel is unusable.")
            return None
        return channel

    @property
    def storage_channel(self) -> discord.TextChannel | None:
        """Get the modmail storage channel.

        Returns:
            The modmail storage channel if it exists, otherwise None.
        """
        if not self.exists:
            return None

        channel_id = self.bot.database_client.settings_model.storage_channel_id
        if channel_id is None:
            return None

        channel = discord.utils.get(self.guild.text_channels, id=channel_id)
        if channel is None:
            return None

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.critical("Some permissions were missing from the storage channel, channel is unusable.")
            return None
        return channel

    def is_configured(self) -> bool:
        """Check if the staff guild is configured.

        Returns:
            True if the guild is configured, False otherwise.
        """
        try:
            return self.exists and bool(self.category)
        except (NoStaffGuildError, NoModmailCategoryError, BadPermissionsError):
            return False

    async def setup(
        self,
        category: discord.CategoryChannel,
        log_channel: discord.TextChannel,
        storage_channel: discord.TextChannel,
    ) -> None:
        """Set up the staff guild.

        Args:
            category: The category to use for modmail channels.
            log_channel: The log channel to use for modmail logs.
            storage_channel: The storage channel to use for modmail storage.
        """
        # Save the channels in the database.
        await self.bot.database_client.update_settings(
            main_category_id=category.id, log_channel_id=log_channel.id, storage_channel_id=storage_channel.id
        )

    async def grant_access(self, profile_id: int, profile_type: ProfileType) -> None:
        """Grant access to the Modmail category.

        Args:
            profile_id: The ID of the profile to grant access to.
            profile_type: The type of the profile (user or role).
        """
        if not self.is_configured():
            return

        if profile_id == CONFIG.bot.bot_id:
            logger.debug("Not granting access to the bot itself")
            return

        if profile_type == ProfileType.user:
            try:
                user_or_role = await self.guild.fetch_member(profile_id)
            except discord.NotFound:
                logger.info("Not granting access to %s, user not in guild", profile_id)
                return  # User not found, do nothing
        else:
            user_or_role = self.guild.get_role(profile_id)
            if user_or_role is None:  # Role not found, do nothing
                logger.info("Not granting access to %s, role not in guild", profile_id)
                return

        logger.info("Granting %s access to the Modmail category", user_or_role)
        overwrite = self.category.overwrites_for(user_or_role)
        overwrite.read_messages = True  # Grant access to the category

        reason = await self.bot.translator.translate(
            _("ftl-msg-grant-access-reason", user_or_role=str(user_or_role)),
            CONFIG.default_locale,
        )
        coros: list[Awaitable[Any]] = [
            self.category.set_permissions(user_or_role, overwrite=overwrite, reason=reason)
        ]

        if self.storage_channel is not None:
            # Since the storage channel permissions are different, we need to set them separately
            overwrite = self.storage_channel.overwrites_for(user_or_role)
            overwrite.read_messages = True
            coros += [self.storage_channel.set_permissions(user_or_role, overwrite=overwrite, reason=reason)]

        await asyncio.gather(*coros)

    async def revoke_access(self, profile_id: int, profile_type: ProfileType) -> None:
        """Revoke access to the Modmail category.

        Args:
            profile_id: The ID of the profile to revoke access from.
            profile_type: The type of the profile (user or role).
        """
        if not self.is_configured():
            return

        if profile_id == CONFIG.bot.bot_id:
            logger.debug("Not revoking access from the bot itself")
            return

        if profile_type == ProfileType.user:
            try:
                user_or_role = await self.guild.fetch_member(profile_id)
            except discord.NotFound:
                logger.info("Not revoking access from %s, user not in guild", profile_id)
                return  # User not found, do nothing
        else:
            user_or_role = self.guild.get_role(profile_id)
            if user_or_role is None:  # Role not found, do nothing
                logger.info("Not revoking access from %s, role not in guild", profile_id)
                return

        coros: list[Awaitable[Any]] = []
        reason = await self.bot.translator.translate(
            _("ftl-msg-revoke-access-reason", user_or_role=str(user_or_role)),
            CONFIG.default_locale,
        )

        overwrite = self.category.overwrites_for(user_or_role)
        if overwrite == discord.PermissionOverwrite(read_messages=True):  # default overwrite
            logger.info("Revoking %s access to the Modmail category", user_or_role)
            coros += [self.category.set_permissions(user_or_role, overwrite=None, reason=reason)]
        else:
            logger.info("Not revoking access to %s for category, overwrites were modified", user_or_role)

        if self.storage_channel is not None:
            overwrite = self.storage_channel.overwrites_for(user_or_role)
            if overwrite == discord.PermissionOverwrite(read_messages=True):  # default overwrite
                logger.info("Revoking %s access to the Modmail storage channel", user_or_role)
                coros += [self.storage_channel.set_permissions(user_or_role, overwrite=None, reason=reason)]
            else:
                logger.info(
                    "Not revoking access to %s for storage channel, overwrites were modified", user_or_role
                )
        if coros:
            await asyncio.gather(*coros)

    async def get_thread(
        self, /, user_or_channel: discord.User | discord.Member | discord.abc.GuildChannel
    ) -> ThreadView | None:
        """Get an open thread for a user or channel.

        Args:
            user_or_channel: The user or channel to get the thread for.

        Returns:
            The thread for the user or channel, or None if it doesn't exist.
        """
        if isinstance(user_or_channel, discord.User | discord.Member):
            thread_model = await self.bot.database_client.get_thread_by_recipient(user_or_channel.id)
        else:
            thread_model = await self.bot.database_client.get_thread_by_channel(user_or_channel.id, only_open=True)

        if thread_model is None:
            logger.debug("No thread found for %s", user_or_channel)
            return None

        channel = self.guild.get_channel(thread_model.channel_id)
        if channel is None:
            logger.warning(
                "Thread channel %s does not exist, closing thread %s", thread_model.channel_id, thread_model.key
            )
            await self.bot.database_client.close_thread(
                thread_model.key,
                ThreadUserModel.from_user(cast(discord.ClientUser, self.bot.user)),
                thread_status=ThreadStatus.closed_by_deletion,
            )
            return None

        recipients: list[discord.User | discord.Member] = []
        for recipient in thread_model.recipients:
            try:
                user = await self.bot.fetch_user(recipient.user_id)  # TODO: Implement some caching
            except discord.NotFound:  # TODO: Handle this better (show to user)
                logger.info("User %s not found in guild", recipient.user_id)
                continue
            except discord.HTTPException:
                logger.warning("Failed to fetch user %s", recipient.user_id)
                continue
            recipients.append(user)

        return ThreadView(self, thread_model, recipients)

    @staticmethod
    def _make_channel_name(*users: discord.User | discord.Member) -> str:
        """Generate a channel name for the thread.

        Args:
            *users: The users of the thread.

        Returns:
            The generated channel name.
        """
        # TODO: Add more options for channel names
        return "-".join([str(user.name) for user in users])

    async def create_thread(
        self,
        *recipients: discord.User | discord.Member,
        created_by: discord.User | discord.Member,
    ) -> ThreadView:
        """Create a new thread for the given users.

        Args:
            *recipients: The users to create the thread for.
            created_by: The user who created the thread.

        Returns:
            The created thread view.

        Raises:
            NoStaffGuildError: If the staff guild is not configured.
            ValueError: If no users are provided.
        """
        if not self.is_configured():
            raise NoStaffGuildError("Staff guild is not configured")

        if not recipients:
            raise ValueError("At least one user must be provided")

        reason = await self.bot.translator.translate(
            _("ftl-msg-new-thread-reason", users=", ".join(str(user) for user in recipients)),
            CONFIG.default_locale,
        )
        channel = await self.category.create_text_channel(name=self._make_channel_name(*recipients), reason=reason)

        thread = ThreadModel(
            bot_id=CONFIG.bot.bot_id,
            key=ThreadModel.generate_key(),
            recipients=[ThreadUserModel.from_user(user) for user in recipients],
            channel_id=channel.id,
            created_at=datetime.datetime.now(datetime.UTC),
            created_by=ThreadUserModel.from_user(created_by),
            status=ThreadStatus.open,
        )
        try:
            await self.bot.database_client.create_thread(thread)
            view = ThreadView(self, thread, list(recipients))
            await view.send_initial_staff_message()
            # TODO: send initial recipient message
        except Exception:
            logger.exception("Failed to create thread or send initial message.")
            # Send a message to the channel indicating the failure
            try:
                await channel.send(
                    await self.bot.translator.translate(_("ftl-msg-create-thread-failed"), CONFIG.default_locale)
                )
            except discord.HTTPException:
                logger.exception("Failed to send error message to channel %s", channel.id)
            raise
        return view
