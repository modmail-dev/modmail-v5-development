"""Module for managing the staff guild of the bot.

This module provides the StaffGuild class, which represents the staff server
for the bot and handles various operations related to it.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, cast

import discord

from ... import CONFIG
from ...backends.common import TicketModel, TicketUserModel
from ...enum import ProfileType, TicketStatus
from ...errors import BadPermissionsError, NoModmailCategoryError, NoStaffGuildError
from ..translator import _
from .ticket_view import TicketView

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
        It help logs the closer when they manually delete a ticket channel.

        Returns:
            The discord.Permissions of the minimum permissions for Modmail.
        """
        # Using getter here to prevent accidental changes to the permissions.
        return discord.Permissions(
            read_messages=True,
            read_message_history=True,
            send_messages=True,
            send_messages_in_threads=True,
            create_public_threads=True,
            create_private_threads=True,
            embed_links=True,
            add_reactions=True,
            attach_files=True,
            manage_channels=True,
            manage_messages=True,
            manage_roles=True,
            manage_threads=True,
            # TODO: Add pin messages and bypass slowmode perms
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
            create_public_threads=True,
            create_private_threads=True,
            embed_links=True,
            add_reactions=True,
            attach_files=True,
            manage_channels=True,
            manage_messages=True,
            manage_threads=True,
            # TODO: Add pin messages and bypass slowmode perms
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
    def category_or_forum(self) -> discord.CategoryChannel | discord.ForumChannel:
        """Get the modmail category or forum.

        Returns:
            The modmail category or forum if it exists, otherwise None.

        Raises:
            NoModmailCategoryError: If the modmail category or forum is not found.
            NoStaffGuildError: If the staff guild is not found.
            BadPermissionsError: If the bot does not have the required permissions.
        """
        if not self.exists:  # Check if the guild exists
            raise NoStaffGuildError(f"Staff guild with ID {self.guild_id} not found.")

        category_or_forum_id = self.bot.database_client.settings_model.main_category_or_forum_id
        if category_or_forum_id is None:
            raise NoModmailCategoryError("No modmail category or forum found in the database.")

        category_or_forum = self.guild.get_channel(category_or_forum_id)
        if category_or_forum is None:
            raise NoModmailCategoryError("Modmail category or forum not found in the guild.")
        if not isinstance(category_or_forum, discord.CategoryChannel | discord.ForumChannel):
            raise NoModmailCategoryError(
                "Modmail category or forum ID does not correspond to a category or forum."
            )

        perms = category_or_forum.permissions_for(category_or_forum.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.error("One or more essential permissions are missing from the main category or forum.")
            raise BadPermissionsError(
                "One or more essential permissions are missing from the main category or forum."
            )
        return category_or_forum

    async def get_log_channel(self) -> discord.TextChannel | discord.Thread | None:
        """Get the modmail log channel.

        Returns:
            The modmail log channel if it exists, otherwise None.
        """
        if not self.exists:
            return None

        channel_id = self.bot.database_client.settings_model.log_channel_id
        if channel_id is None:
            return None

        channel = self.guild.get_channel(channel_id)
        if channel is None:
            # Try to fetch the channel via API (if the thread was auto-archived, it won't be in cache)
            try:
                channel = await self.guild.fetch_channel(channel_id)
            except discord.NotFound, discord.HTTPException:
                logger.warning("Modmail log channel (ID: %d) was not found.", channel_id)
                return None
            if isinstance(channel, discord.TextChannel) or (
                isinstance(channel, discord.Thread) and not channel.archived
            ):
                logger.warning(
                    "Modmail log channel (ID: %d) was not found in cache, fetched via API. "
                    "(THIS SHOULD NOT HAPPEN)",
                    channel_id,
                )

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            logger.warning("Modmail log channel (ID: %d) is not a text channel or thread.", channel_id)
            return None

        if isinstance(channel, discord.Thread) and channel.archived:
            logger.info("Modmail log channel (ID: %d) was archived, unarchiving it.", channel_id)
            await channel.edit(archived=False)

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.warning("Some permissions are missing from the log channel, channel is unusable.")
            return None
        return channel

    async def get_storage_channel(self) -> discord.TextChannel | discord.Thread | None:
        """Get the modmail storage channel.

        Returns:
            The modmail storage channel if it exists, otherwise None.
        """
        if not self.exists:
            return None

        channel_id = self.bot.database_client.settings_model.storage_channel_id
        if channel_id is None:
            return None

        channel = self.guild.get_channel(channel_id)
        if channel is None:
            # Try to fetch the channel via API (if the thread was auto-archived, it won't be in cache)
            try:
                channel = await self.guild.fetch_channel(channel_id)
            except discord.NotFound, discord.HTTPException:
                logger.warning("Modmail storage channel (ID: %d) was not found.", channel_id)
                return None
            if isinstance(channel, discord.TextChannel) or (
                isinstance(channel, discord.Thread) and not channel.archived
            ):
                logger.warning(
                    "Modmail storage channel (ID: %d) was not found in cache, fetched via API. "
                    "(THIS SHOULD NOT HAPPEN)",
                    channel_id,
                )

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            logger.warning("Modmail storage channel (ID: %d) is not a text channel or thread.", channel_id)
            return None

        if isinstance(channel, discord.Thread) and channel.archived:
            logger.info("Modmail storage channel (ID: %d) was archived, unarchiving it.", channel_id)
            await channel.edit(archived=False)

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.critical("Some permissions are missing from the storage channel, channel is unusable.")
            return None
        return channel

    def is_configured(self) -> bool:
        """Check if the staff guild is configured.

        Returns:
            True if the guild is configured, False otherwise.
        """
        try:
            return self.exists and bool(self.category_or_forum)
        except NoStaffGuildError, NoModmailCategoryError, BadPermissionsError:
            return False

    async def setup(
        self,
        category_or_forum: discord.CategoryChannel | discord.ForumChannel,
        log_channel: discord.TextChannel | discord.Thread,
        storage_channel: discord.TextChannel | discord.Thread,
    ) -> None:
        """Set up the staff guild.

        Args:
            category_or_forum: The category or forum used for modmail.
            log_channel: The log channel or thread to use for modmail logs.
            storage_channel: The storage channel or thread to use for modmail storage.
        """
        # Save the channels in the database.
        await self.bot.database_client.update_settings(
            main_category_or_forum_id=category_or_forum.id,
            log_channel_id=log_channel.id,
            storage_channel_id=storage_channel.id,
        )

    async def grant_access(self, profile_id: int, profile_type: ProfileType) -> None:
        """Grant access to the Modmail category or forum.

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
        overwrite = self.category_or_forum.overwrites_for(user_or_role)
        overwrite.read_messages = True  # Grant access to the category

        reason = await self.bot.translator.translate(
            _("ftl-msg-grant-access-reason", user_or_role=str(user_or_role)),
            CONFIG.default_locale,
        )
        coros: list[Awaitable[Any]] = [
            self.category_or_forum.set_permissions(user_or_role, overwrite=overwrite, reason=reason)
        ]

        storage_channel = await self.get_storage_channel()
        if storage_channel is not None and not isinstance(storage_channel, discord.Thread):
            # Since the storage channel permissions are different, we need to set them separately
            # And threads cannot have overwrites set on them
            overwrite = storage_channel.overwrites_for(user_or_role)
            overwrite.read_messages = True
            coros += [storage_channel.set_permissions(user_or_role, overwrite=overwrite, reason=reason)]

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

        overwrite = self.category_or_forum.overwrites_for(user_or_role)
        if overwrite == discord.PermissionOverwrite(read_messages=True):  # default overwrite
            logger.info("Revoking %s access to the Modmail category", user_or_role)
            coros += [self.category_or_forum.set_permissions(user_or_role, overwrite=None, reason=reason)]
        else:
            logger.info("Not revoking access to %s for category, overwrites were modified", user_or_role)

        storage_channel = await self.get_storage_channel()
        if storage_channel is not None and not isinstance(storage_channel, discord.Thread):
            # threads cannot have overwrites set on them
            overwrite = storage_channel.overwrites_for(user_or_role)
            if overwrite == discord.PermissionOverwrite(read_messages=True):  # default overwrite
                logger.info("Revoking %s access to the Modmail storage channel", user_or_role)
                coros += [storage_channel.set_permissions(user_or_role, overwrite=None, reason=reason)]
            else:
                logger.info(
                    "Not revoking access to %s for storage channel, overwrites were modified", user_or_role
                )
        if coros:
            await asyncio.gather(*coros)

    async def get_ticket(
        self, /, user_or_channel: discord.User | discord.Member | discord.TextChannel | discord.Thread
    ) -> TicketView | None:
        """Get an open ticket for a user or channel.

        Args:
            user_or_channel: The user or channel to get the ticket for.

        Returns:
            The ticket for the user or channel, or None if it doesn't exist.
        """
        if isinstance(user_or_channel, discord.User | discord.Member):
            ticket_model = await self.bot.database_client.get_ticket_by_recipient(user_or_channel.id)
        else:
            ticket_model = await self.bot.database_client.get_ticket_by_channel(user_or_channel.id, only_open=True)

        if ticket_model is None:
            logger.debug("No ticket found for %s", user_or_channel)
            return None

        channel = self.guild.get_channel_or_thread(ticket_model.channel_id)
        if channel is None:
            try:
                channel = await self.guild.fetch_channel(ticket_model.channel_id)
            except discord.NotFound, discord.HTTPException:
                # Ticket channel does not exist, close the ticket
                logger.warning(
                    "Ticket channel %s does not exist, closing ticket %s",
                    ticket_model.channel_id,
                    ticket_model.key,
                )
                await self.bot.database_client.close_ticket(
                    ticket_model.key,
                    TicketUserModel.from_user(cast(discord.ClientUser, self.bot.user)),
                    ticket_status=TicketStatus.closed_by_deletion,
                )
                return None

            if isinstance(channel, discord.TextChannel) or (
                isinstance(channel, discord.Thread) and not channel.archived
            ):
                logger.warning(
                    "Ticket channel or thread %s was not found in cache, fetched via API. "
                    "(THIS SHOULD NOT HAPPEN)",
                    ticket_model.channel_id,
                )

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            logger.warning(
                "Ticket channel %s is not a text channel or thread, closing ticket %s",
                ticket_model.channel_id,
                ticket_model.key,
            )
            await self.bot.database_client.close_ticket(
                ticket_model.key,
                TicketUserModel.from_user(cast(discord.ClientUser, self.bot.user)),
                ticket_status=TicketStatus.closed_by_deletion,
            )
            return None

        if isinstance(channel, discord.Thread) and channel.archived:
            # TODO: if possible: un-archive if archived due to inactivity, otherwise close the ticket if manual
            # There's many places in the code that unarchives the thread, when implementing the TO/DO
            # need to change those as well.
            logger.info("Ticket channel %s is an archived thread, unarchiving it.", ticket_model.channel_id)
            await channel.edit(archived=False)

        recipients: list[discord.User | discord.Member] = []
        for recipient in ticket_model.recipients:
            try:
                # Using .fetch_user since members are not cached
                user = await self.bot.fetch_user(recipient.user_id)  # TODO: Implement some caching
            except discord.NotFound:  # TODO: Handle this better (show to user)
                logger.info("User %s not found in guild", recipient.user_id)
                continue
            except discord.HTTPException:
                logger.warning("Failed to fetch user %s", recipient.user_id)
                continue
            recipients.append(user)

        return TicketView(self, ticket_model, recipients)

    @staticmethod
    def _make_channel_name(*users: discord.User | discord.Member) -> str:
        """Generate a channel name for the ticket.

        Args:
            *users: The users of the ticket.

        Returns:
            The generated channel name.
        """
        # TODO: Add more options for channel names
        return "-".join([str(user.name) for user in users])

    async def create_ticket(
        self,
        *recipients: discord.User | discord.Member,
        created_by: discord.User | discord.Member,
        starter_message: discord.Message | None = None,
    ) -> TicketView:
        """Create a new ticket for the given users.

        Args:
            *recipients: The users to create the ticket for.
            created_by: The user who created the ticket.
            starter_message: An optional message that started the ticket.

        Returns:
            The created ticket view.

        Raises:
            NoStaffGuildError: If the staff guild is not configured.
            ValueError: If no users are provided.
        """
        if not self.is_configured():
            raise NoStaffGuildError("Staff guild is not configured")

        if not recipients:
            raise ValueError("At least one user must be provided")

        reason = await self.bot.translator.translate(
            _("ftl-msg-new-ticket-reason", users=", ".join(str(user) for user in recipients)),
            CONFIG.default_locale,
        )
        if isinstance(self.category_or_forum, discord.CategoryChannel):
            channel = await self.category_or_forum.create_text_channel(
                name=self._make_channel_name(*recipients), reason=reason
            )
        else:
            if starter_message is not None and starter_message.content.strip():
                # Remove excessive whitespace and limit to 150 characters for thread starter message preview
                thread_starter_message = re.sub(r"\s+", " ", starter_message.content.strip())
                wrap_limit = 150
                if len(thread_starter_message) > wrap_limit:
                    thread_starter_message = thread_starter_message[: wrap_limit - 3] + "..."
            else:
                thread_starter_message = await self.bot.translator.translate(
                    _(
                        "ftl-msg-new-ticket-default-thread-opening-message",
                        users=" ".join(user.mention for user in recipients),
                    ),
                    CONFIG.default_locale,
                )
            channel = (
                await self.category_or_forum.create_thread(
                    name=self._make_channel_name(*recipients), content=thread_starter_message, reason=reason
                )
            ).thread

        ticket = TicketModel(
            bot_id=CONFIG.bot.bot_id,
            key=TicketModel.generate_key(),
            recipients=[TicketUserModel.from_user(user) for user in recipients],
            channel_id=channel.id,
            created_at=datetime.datetime.now(datetime.UTC),
            created_by=TicketUserModel.from_user(created_by),
            status=TicketStatus.open,
        )
        try:
            await self.bot.database_client.create_ticket(ticket)
            view = TicketView(self, ticket, list(recipients))
            await view.send_initial_staff_message()
            # TODO: send initial recipient message
        except Exception:
            logger.exception("Failed to create ticket or send initial message.")
            # Send a message to the channel indicating the failure
            try:
                await channel.send(
                    await self.bot.translator.translate(_("ftl-msg-create-ticket-failed"), CONFIG.default_locale)
                )
            except discord.HTTPException:
                logger.exception("Failed to send error message to channel %s", channel.id)
            raise
        return view
