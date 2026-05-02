"""[`StaffGuild`][] — ticket lifecycle, channel setup, and access control for the staff guild."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
import re
from typing import TYPE_CHECKING, Literal, cast

import discord

from .. import CONFIG
from ..backends.common import TicketModel, TicketUserModel
from ..enum import AccessLevel, ProfileType, TicketStatus
from ..errors import BadPermissionsError, NoModmailCategoryError, NoStaffGuildError
from ._ticket_view import TicketView
from .embed import EmbedProxy
from .translator import _

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .bot import Bot

__all__ = ["StaffGuild"]

logger = logging.getLogger(__name__)

# Discord API error code for "Maximum number of pinned threads reached (1)".
_MAX_PINNED_THREADS_ERROR_CODE = 30047


class StaffGuild:
    """Manages the staff Discord server where Modmail tickets are handled."""

    def __init__(self, bot: Bot) -> None:
        """Attach the bot and read the staff guild ID from config.

        Args:
            bot: The [`Bot`][] instance that owns this staff guild.
        """
        self.bot = bot
        """The [`Bot`][] instance that owns this staff guild."""

    def __str__(self) -> str:
        """Return the guild's name."""
        return self.guild.name if self.guild_exists else "<Invalid Guild>"

    def __repr__(self) -> str:
        """Return `StaffGuild(guild_id=...)` for debugging."""
        return f"StaffGuild(guild_id={self.guild_id})"

    @property
    def guild_id(self) -> int:
        """The Discord ID of the configured staff server."""
        return CONFIG.bot.staff_server_id

    @property
    def MIN_PERMISSIONS(self) -> discord.Permissions:  # noqa: N802
        """Minimum guild-level permissions required for the bot to function.

        Warning:
            When changing these, also update the `ftl-cmd-setup-not-enough-guild-permissions`
            localization key.

        Note:
            View Audit Log is strongly recommended — it lets Modmail detect the closer when a
            ticket channel is deleted manually — but is not enforced here.
        """
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
        """Channel-level permission overwrite equivalent of [`MIN_PERMISSIONS`][].

        Identical to [`MIN_PERMISSIONS`][] except `manage_roles` is omitted
        (Discord does not allow that flag on channel-level overwrites).
        """
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
    def guild_exists(self) -> bool:
        """`True` if the bot is currently a member of the configured staff guild."""
        try:
            return bool(self.guild)
        except NoStaffGuildError:
            return False

    @property
    def guild(self) -> discord.Guild:
        """The configured staff guild.

        Raises:
            NoStaffGuildError: If the bot is not a member of the configured guild.
        """
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            raise NoStaffGuildError(f"Staff guild with ID {self.guild_id} not found.")
        return guild

    @property
    def category_or_forum(self) -> discord.CategoryChannel | discord.ForumChannel:
        """The configured Modmail ticket category or forum channel.

        Raises:
            NoStaffGuildError: If the bot is not a member of the configured guild.
            NoModmailCategoryError: If no channel ID is saved or the channel no longer exists.
            BadPermissionsError: If the bot lacks [`MIN_PERMISSIONS`][] on the channel.
        """
        if not self.guild_exists:  # Check if the guild exists
            raise NoStaffGuildError(f"Staff guild with ID {self.guild_id} not found.")

        category_or_forum_id = self.bot.database_client.settings.main_category_or_forum_id
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
        """Return the configured log channel, unarchiving it if needed.

        Returns:
            The log channel/thread, or `None` if not configured, missing, or the bot lacks permissions.
        """
        if not self.guild_exists:
            return None

        channel_id = self.bot.database_client.settings.log_channel_id
        if channel_id is None:
            return None

        channel = self.guild.get_channel(channel_id)
        if channel is None:
            # Try to fetch the channel via API (if the thread was auto-archived, it won't be in cache)
            try:
                channel = await self.guild.fetch_channel(channel_id)
            except discord.HTTPException as e:
                if isinstance(e, discord.NotFound):
                    logger.warning("Modmail log channel (ID: %d) was not found.", channel_id)
                    # TODO: unset the channel ID
                else:
                    logger.error(
                        "Modmail log channel (ID: %d) could not be fetched due to an HTTP error: %s", channel_id, e
                    )
                return None

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            logger.warning("Modmail log channel (ID: %d) is not a text channel or thread.", channel_id)
            # TODO: unset the channel ID
            return None

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.warning("Some permissions are missing from the log channel, channel is unusable.")
            return None
        return channel

    async def get_storage_channel(self) -> discord.TextChannel | None:
        """Return the configured storage channel.

        Returns:
            The storage channel, or `None` if not configured, missing, or the bot lacks permissions.
        """
        if not self.guild_exists:
            return None

        channel_id = self.bot.database_client.settings.storage_channel_id
        if channel_id is None:
            return None

        channel = self.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.guild.fetch_channel(channel_id)
            except discord.HTTPException as e:
                if isinstance(e, discord.NotFound):
                    logger.warning("Modmail storage channel (ID: %d) was not found.", channel_id)
                    # TODO: unset the channel ID
                else:
                    logger.error(
                        "Modmail storage channel (ID: %d) could not be fetched due to an HTTP error: %s",
                        channel_id,
                        e,
                    )
                return None

        if not isinstance(channel, discord.TextChannel):
            logger.warning("Modmail storage channel (ID: %d) is not a text channel.", channel_id)
            # TODO: unset the channel ID
            return None

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            logger.critical("Some permissions are missing from the storage channel, channel is unusable.")
            return None
        return channel

    def is_setup(self) -> bool:
        """Return `True` when the guild exists and a Modmail category or forum is reachable."""
        try:
            return self.guild_exists and bool(self.category_or_forum)
        except NoStaffGuildError, NoModmailCategoryError, BadPermissionsError:
            return False

    def _get_bot_role_or_member(self) -> discord.Role | discord.Member:
        """Return the bot's integration role, or its guild [`discord.Member`][] if no role exists."""
        try:
            role = discord.utils.get(self.guild.roles, tags__bot_id=self.guild.me.id)
            if role is not None:
                return role
        except AttributeError:
            pass
        return self.guild.me

    def _build_category_overwrites(
        self,
    ) -> dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]:
        """Build permission overwrites for a new Modmail category or forum.

        Hides the channel from everyone, grants the bot its minimum required permissions,
        and gives read access to each profile with staff-level access or above.

        Returns:
            Permission overwrites mapping for use in channel or forum creation.
        """
        overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            self._get_bot_role_or_member(): self.MIN_PERMISSIONS_OVERWRITE,
        }

        for profile in self.bot.database_client.profiles:
            if profile.access_level is not None and profile.access_level >= AccessLevel.staff:
                if profile.profile_type == ProfileType.role:
                    if (role := self.guild.get_role(profile.profile_id)) is None:
                        logger.info(
                            "Skipping profile %s with missing role %s for Modmail channel permissions",
                            profile.profile_id,
                            profile.profile_id,
                        )
                        continue
                    logger.info("Granting role %s access to Modmail channel", profile.profile_id)
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                else:
                    logger.info("Granting user %s access to Modmail channel", profile.profile_id)
                    overwrites[discord.Object(profile.profile_id)] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                    )
        return overwrites

    async def setup(
        self,
        setup_type: Literal["category", "forum"],
        *,
        existing_channel_id: int | None = None,
    ) -> tuple[
        discord.CategoryChannel | discord.ForumChannel,
        discord.TextChannel | discord.Thread,
        discord.TextChannel,
    ]:
        """Set up the Modmail category or forum along with the log and storage channels.

        When `existing_channel_id` is given the channel is adopted (bot permissions are applied)
        rather than created. Otherwise, a fresh category or forum is created with the correct
        permission overwrites.

        Args:
            setup_type: Whether to use a `"category"` or `"forum"` layout.
            existing_channel_id: Discord ID of an existing channel to adopt (`None` to
                create a new one).

        Returns:
            A three-tuple of `(category_or_forum, log_channel, storage_channel)`.

        Raises:
            BadPermissionsError: If the bot lacks the minimum guild permissions required to run setup.
            NoModmailCategoryError: If `existing_channel_id` is set but the channel is not
                found or is the wrong type.
            discord.HTTPException: If Discord rejects a channel or thread creation request.
        """
        category_or_forum: discord.CategoryChannel | discord.ForumChannel
        log_channel: discord.TextChannel | discord.Thread
        storage_channel: discord.TextChannel

        if self.guild.me.guild_permissions & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            raise BadPermissionsError("Bot lacks the minimum guild permissions required to run setup.")

        if existing_channel_id is not None:
            resolved = self.guild.get_channel(existing_channel_id)
            if not isinstance(resolved, discord.CategoryChannel | discord.ForumChannel):
                raise NoModmailCategoryError(
                    f"Existing channel {existing_channel_id} not found or is the wrong type."
                )
            if resolved.permissions_for(resolved.guild.me) & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
                raise BadPermissionsError("Bot lacks the minimum channel permissions required to run setup.")

            category_or_forum = resolved
            await category_or_forum.set_permissions(
                self._get_bot_role_or_member(),
                overwrite=self.MIN_PERMISSIONS_OVERWRITE,
                reason=self.bot.translate(_("ftl-msg-setup-category-or-forum-permissions-reason")),
            )
            # TODO: alert the user they need to grant staff access manually to the existing channel
        else:
            overwrites = self._build_category_overwrites()
            channel_name = self.bot.translate(_("ftl-msg-setup-category-or-forum-name"))
            create_reason = self.bot.translate(_("ftl-msg-setup-category-or-forum-create-reason"))
            if setup_type == "category":
                category_or_forum = await self.guild.create_category(
                    name=channel_name,
                    reason=create_reason,
                    overwrites=overwrites,
                    position=0,
                )
            else:
                category_or_forum = await self.guild.create_forum(
                    name=channel_name,
                    reason=create_reason,
                    overwrites=overwrites,
                    position=0,
                    default_auto_archive_duration=10080,  # 7 days
                )
            await category_or_forum.edit(position=0)

        log_reason = self.bot.translate(_("ftl-msg-setup-log-channel-create-reason"))
        storage_reason = self.bot.translate(_("ftl-msg-setup-storage-channel-create-reason"))

        storage_overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            self._get_bot_role_or_member(): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        if isinstance(category_or_forum, discord.CategoryChannel):
            log_channel, storage_channel = await asyncio.gather(
                category_or_forum.create_text_channel(
                    name=self.bot.translate(_("ftl-msg-setup-log-channel-name")),
                    topic=self.bot.translate(_("ftl-msg-setup-log-channel-topic")),
                    reason=log_reason,
                ),
                category_or_forum.create_text_channel(
                    name=self.bot.translate(_("ftl-msg-setup-storage-channel-name")),
                    topic=self.bot.translate(_("ftl-msg-setup-storage-channel-topic")),
                    overwrites=storage_overwrites,
                    reason=storage_reason,
                ),
            )

            await cast("discord.TextChannel", log_channel).edit(position=0)
            await storage_channel.edit(position=1)

        else:
            for thread in category_or_forum.threads:
                if thread.flags.pinned:
                    await thread.edit(
                        pinned=False,
                        reason=self.bot.translate(_("ftl-msg-setup-forum-thread-unpin-reason")),
                    )
                    break

            log_thread_msg, storage_channel = await asyncio.gather(
                category_or_forum.create_thread(
                    name=self.bot.translate(_("ftl-msg-setup-log-channel-name")),
                    content=self.bot.translate(_("ftl-msg-setup-log-channel-topic")),
                    reason=log_reason,
                ),
                self.guild.create_text_channel(
                    name=self.bot.translate(_("ftl-msg-setup-storage-channel-name")),
                    topic=self.bot.translate(_("ftl-msg-setup-storage-channel-topic")),
                    reason=storage_reason,
                    overwrites=storage_overwrites,
                ),
            )
            log_channel = log_thread_msg.thread

            try:
                await log_channel.edit(pinned=True, locked=True, reason=log_reason)
            except discord.HTTPException as e:
                if e.code == _MAX_PINNED_THREADS_ERROR_CODE:
                    logger.error(
                        "Could not pin the log thread in forum %s because the maximum pinned threads is reached",
                        category_or_forum,
                    )
                    await log_channel.edit(locked=True, reason=log_reason)
                else:
                    raise
            await storage_channel.edit(position=1)

        await self.bot.database_client.update_settings(
            main_category_or_forum_id=category_or_forum.id,
            log_channel_id=log_channel.id,
            storage_channel_id=storage_channel.id,
        )
        logger.info(
            "Setup complete in %s: %s=%d, log_channel=%d, storage_channel=%d",
            self.guild.name,
            setup_type,
            category_or_forum.id,
            log_channel.id,
            storage_channel.id,
        )

        return category_or_forum, log_channel, storage_channel

    async def grant_access(self, profile_id: int, profile_type: ProfileType) -> None:
        """Grant read access to the Modmail category or forum for a profile.

        Args:
            profile_id: Discord ID of the user or role to grant access to.
            profile_type: Whether `profile_id` refers to a user or a role.

        Raises:
            discord.HTTPException: If the permission overwrite update fails due to an API error.
        """
        if not self.is_setup():
            return

        if profile_id == CONFIG.bot.bot_id:
            logger.debug("Not granting access to the bot itself")
            return

        user_or_role: discord.Member | discord.Role
        if profile_type == ProfileType.user:
            try:
                user_or_role = await self.guild.fetch_member(profile_id)
            except discord.NotFound:
                logger.info("Not granting access to %s, user not in guild", profile_id)
                return  # User not found, do nothing
        else:
            if (role := self.guild.get_role(profile_id)) is None:  # Role not found, do nothing
                logger.info("Not granting access to %s, role not in guild", profile_id)
                return
            user_or_role = role

        logger.info("Granting %s access to the Modmail category", user_or_role)
        overwrite = self.category_or_forum.overwrites_for(user_or_role)
        if overwrite.is_empty():
            # Grant access to the category/forum
            overwrite.read_messages = True
            overwrite.send_messages = True
            reason = self.bot.translate(_("ftl-msg-grant-access-reason", user_or_role=user_or_role.mention))
            await self.category_or_forum.set_permissions(user_or_role, overwrite=overwrite, reason=reason)
        else:
            logger.info("Not granting access to %s, already has an overwrite in the channel", user_or_role)

    async def revoke_access(self, profile_id: int) -> None:
        """Revoke read access to the Modmail category or forum for a profile.

        Args:
            profile_id: Discord ID of the user or role to revoke access from.

        Raises:
            discord.HTTPException: If the permission overwrite update fails due to an API error.
        """
        if not self.is_setup():
            return

        if profile_id == CONFIG.bot.bot_id:
            logger.debug("Not revoking access from the bot itself")
            return

        # Using .edit() instead of .set_permissions() in case the profile_id isn't in the server
        all_overwrites = self.category_or_forum.overwrites
        for user_or_role, overwrite in all_overwrites.items():
            if user_or_role.id == profile_id:
                # Check if default overwrite set by Modmail
                if overwrite == discord.PermissionOverwrite(read_messages=True, send_messages=True):
                    logger.info("Revoking %s access to the Modmail category", user_or_role)
                    all_overwrites.pop(user_or_role)
                    break
                logger.info("Not revoking access to %s for category, overwrites were modified", user_or_role)
                return
        else:
            logger.info("Not revoking access to %s for category, overwrites were not found", profile_id)
            return

        reason = self.bot.translate(_("ftl-msg-revoke-access-reason", user_or_role=str(user_or_role)))
        await self.category_or_forum.edit(overwrites=all_overwrites, reason=reason)

    async def get_ticket(
        self, user_or_channel: discord.User | discord.Member | discord.TextChannel | discord.Thread, /
    ) -> TicketView | None:
        """Return the open ticket associated with a user or ticket channel.

        Args:
            user_or_channel: A Discord user or member to look up by recipient, or the ticket
                channel/thread to look up directly.

        Returns:
            The matching [`TicketView`][] (`None` if no open ticket exists).
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
            except discord.HTTPException as e:
                if isinstance(e, discord.NotFound):
                    # Ticket channel does not exist, close the ticket
                    logger.warning(
                        "Ticket channel %s does not exist, closing ticket %s",
                        ticket_model.channel_id,
                        ticket_model.key,
                    )
                    await self.close_ticket(
                        ticket_model, closer=None, close_status=TicketStatus.closed_by_deletion
                    )
                else:
                    logger.exception(
                        "Something went wrong fetching ticket channel %s for ticket %s",
                        ticket_model.channel_id,
                        ticket_model.key,
                    )
                return None

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            logger.warning(
                "Ticket channel %s is not a text channel or thread, closing ticket %s",
                ticket_model.channel_id,
                ticket_model.key,
            )
            await self.close_ticket(ticket_model, closer=None, close_status=TicketStatus.closed_by_deletion)
            return None

        if channel.permissions_for(channel.guild.me) & self.MIN_PERMISSIONS != self.MIN_PERMISSIONS:
            # TODO: probably handle this differently, maybe alert staff that the channel is inaccessible
            #  and needs permissions fixed rather than silently closing the ticket
            logger.warning(
                "Insufficient permissions to access ticket channel %s for ticket %s, closing ticket.",
                channel.id,
                ticket_model.key,
            )
            await self.close_ticket(ticket_model, closer=None, close_status=TicketStatus.closed_by_deletion)
            return None

        recipients: list[discord.User | discord.Member] = []
        for recipient in ticket_model.recipients:
            try:
                # Using .fetch_user since members are not cached
                user = await self.bot.fetch_user(recipient.user_id)  # TODO: Implement some caching
            except discord.NotFound:  # TODO: Handle this better (show to user)
                logger.info("User %s account deleted", recipient.user_id)
                continue
            except discord.HTTPException:
                logger.warning("Failed to fetch user %s", recipient.user_id)
                continue
            recipients.append(user)
        # TODO: handle no recipients
        return TicketView(self, ticket_model, recipients)

    async def _format_log_channel_message_embed(
        self, ticket: TicketModel, *, title: str, description: str
    ) -> discord.Embed:
        """Build a colored, timestamped log-channel embed for `ticket`.

        Args:
            ticket: The ticket whose status and timestamps the embed reflects.
            title: Embed title — typically the recipient usernames.
            description: Embed description — typically the ticket key and summary.

        Returns:
            A [`discord.Embed`][] ready to post or edit in the log channel.
        """
        embed = EmbedProxy(title=title, description=description)
        # TODO: configable colors
        if ticket.status.is_open():
            embed.color = discord.Color.green()
            embed.set_footer(text=_("ftl-msg-log-embed-open-footer"))
            embed.timestamp = ticket.created_at
        else:
            embed.color = discord.Color.red()
            if not ticket.closed_by or ticket.closed_by.user_id == self.guild.me.id:
                embed.set_footer(text=_("ftl-msg-log-embed-closed-footer-unknown-closer"))
            else:
                embed.set_footer(text=_("ftl-msg-log-embed-closed-footer", user=ticket.closed_by.user_name))
            embed.timestamp = ticket.closed_at or True  # Fallback to current time if closed_at is None
        return embed.to_embed(self.bot.translator, CONFIG.default_locale)

    async def _send_log_channel_message(
        self,
        ticket: TicketModel,
        recipients: Iterable[discord.User | discord.Member],
        *,
        starter_message: discord.Message | None = None,
    ) -> int | None:
        """Post an opening entry to the log channel for a newly created ticket.

        Args:
            ticket: The ticket to log.
            recipients: The users the ticket was opened for.
            starter_message: The message that triggered ticket creation (`None` if unavailable).

        Returns:
            The message ID of the log entry, or `None` if no log channel is configured.
        """
        log_channel = await self.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log message for %s.", ticket.key)
            return None

        if starter_message is not None and starter_message.content.strip():
            # Remove excessive whitespace and limit to 75 characters for thread starter message preview
            ticket_summary = re.sub(r"\s+", " ", starter_message.content.strip())
            wrap_limit = 75
            if len(ticket_summary) > wrap_limit:
                ticket_summary = ticket_summary[: wrap_limit - 3] + "..."
            ticket_summary = discord.utils.escape_markdown(ticket_summary.strip())
        else:
            ticket_summary = self.bot.translate(_("ftl-msg-log-embed-no-content-description"))

        log_url = self.bot.get_log_url(ticket.key)
        description = f"[`{ticket.key}`]({log_url}): {ticket_summary}"
        title = " ".join([f"@{recipient.name}" for recipient in recipients])

        embed = await self._format_log_channel_message_embed(ticket, title=title, description=description)
        log_channel_message = await log_channel.send(embed=embed)
        task = asyncio.create_task(
            self.bot.database_client.set_ticket_log_channel_message_id(ticket.key, log_channel_message.id)
        )
        self.bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(self.bot.asyncio_pending_tasks.discard)
        return log_channel_message.id

    async def _update_log_channel_message(self, ticket: TicketModel) -> None:
        """Edit the log-channel entry for a ticket to reflect its closed state.

        Args:
            ticket: The [`TicketModel`][] that was just closed.
        """
        if ticket.log_channel_message_id is None:
            logger.info("No log channel message ID set, skipping log message update for %s.", ticket.key)
            return

        log_channel = await self.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log message update for %s.", ticket.key)
            return

        try:
            log_channel_message = await log_channel.fetch_message(ticket.log_channel_message_id)
        except discord.HTTPException as e:
            if isinstance(e, discord.NotFound):
                logger.info(
                    "Log channel message %d not found in log channel, won't update.", ticket.log_channel_message_id
                )
            else:
                logger.error("Failed to fetch log channel message %d: %s", ticket.log_channel_message_id, e)
            return

        if not log_channel_message.embeds:
            logger.error("The log channel message %d has no embeds, won't update.", ticket.log_channel_message_id)
            return

        title = log_channel_message.embeds[0].title or "?"
        description = log_channel_message.embeds[0].description or "?"

        embed = await self._format_log_channel_message_embed(ticket, title=title, description=description)
        await log_channel_message.edit(embed=embed)
        logger.debug("Updated log channel message ID %d.", ticket.log_channel_message_id)

    @staticmethod
    def _make_channel_name(*users: discord.User | discord.Member) -> str:
        """Return a hyphen-joined channel name derived from the recipients' usernames.

        Args:
            *users: The ticket recipients.
        """
        # TODO: Add more options for channel names
        return "-".join([str(user.name) for user in users])

    async def create_ticket(
        self,
        *recipients: discord.User | discord.Member,
        created_by: discord.User | discord.Member,
        starter_message: discord.Message | None = None,
    ) -> TicketView:
        """Open a new Modmail ticket for one or more recipients.

        Args:
            *recipients: The users the ticket is being opened for.
            created_by: The user who initiated the ticket.
            starter_message: The message that triggered ticket creation (`None` if not available).

        Returns:
            A [`TicketView`][] representing the newly created ticket.

        Raises:
            NoStaffGuildError: If the staff guild is not configured.
            ValueError: If no recipients are provided.
        """
        if not self.is_setup():
            raise NoStaffGuildError("Staff guild is not configured")

        if not recipients:
            raise ValueError("At least one user must be provided")

        reason = self.bot.translate(
            _("ftl-msg-new-ticket-reason", users=", ".join(str(user) for user in recipients))
        )
        # TODO: error handle http reqs
        if isinstance(self.category_or_forum, discord.CategoryChannel):
            channel = await self.category_or_forum.create_text_channel(
                name=self._make_channel_name(*recipients), reason=reason
            )
        else:
            # New forum threads require a starter message
            if starter_message is not None and starter_message.content.strip():
                # Remove excessive whitespace and limit to 150 characters
                # for thread starter message preview
                ticket_summary = re.sub(r"\s+", " ", starter_message.content.strip())
                wrap_limit = 150
                if len(ticket_summary) > wrap_limit:
                    ticket_summary = ticket_summary[: wrap_limit - 3] + "..."
                ticket_summary = discord.utils.escape_markdown(ticket_summary)
            else:
                ticket_summary = self.bot.translate(
                    _(
                        "ftl-msg-new-ticket-default-thread-opening-message",
                        users=" ".join(user.mention for user in recipients),
                    )
                )
            channel = (
                await self.category_or_forum.create_thread(
                    name=self._make_channel_name(*recipients), content=ticket_summary, reason=reason
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

            task = asyncio.create_task(
                self._send_log_channel_message(ticket, recipients, starter_message=starter_message)
            )
            self.bot.asyncio_pending_tasks.add(task)
            task.add_done_callback(self.bot.asyncio_pending_tasks.discard)

            await asyncio.gather(
                view.send_initial_staff_message(),
                # TODO: send initial recipient message (welcome/starter message)
            )
        except Exception:
            logger.exception("Failed to create ticket or send initial message.")
            # Send a message to the channel indicating the failure
            try:
                await channel.send(self.bot.translate(_("ftl-msg-create-ticket-failed")))
            except discord.HTTPException:
                logger.exception("Failed to send error message to channel %s", channel.id)
            raise  # TODO: reraise a custom modmail error
        return view

    async def _delete_after_ticket_closed(
        self, ticket: TicketModel, *, closer: discord.User | discord.Member | None
    ) -> None:
        """Delete or lock the ticket channel after the ticket is marked closed.

        Args:
            ticket: The [`TicketModel`][] whose channel should be cleaned up.
            closer: The user who closed the ticket (`None` if the closer is unknown).
        """
        channel = self.guild.get_channel_or_thread(ticket.channel_id)
        if channel is None:
            with contextlib.suppress(discord.HTTPException):
                channel = await self.guild.fetch_channel(ticket.channel_id)

        if channel is None:
            return

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            return

        if isinstance(channel, discord.Thread) and channel.locked:
            return

        perms = channel.permissions_for(channel.guild.me)
        if (isinstance(channel, discord.TextChannel) and not perms.manage_channels) or (
            isinstance(channel, discord.Thread) and not perms.manage_threads
        ):
            logger.info(
                "%s is closed, skipping thread close operation due to lacking Discord permissions.", ticket.key
            )
            return

        if closer is None:
            close_reason = self.bot.translate(_("ftl-msg-ticket-closed-reason-unknown-closer"))
        else:
            close_reason = self.bot.translate(_("ftl-msg-ticket-closed-reason", user=closer.name))

        try:
            # TODO: config archive or delete on close
            if isinstance(channel, discord.Thread):
                await channel.edit(archived=True, locked=True, reason=close_reason)
            else:
                await channel.delete(reason=close_reason)
        except discord.HTTPException:
            logger.exception("Failed to delete/archive ticket channel %s", channel)

    async def close_ticket(
        self, ticket: TicketModel, *, closer: discord.User | discord.Member | None, close_status: TicketStatus
    ) -> None:
        """Mark a ticket as closed and schedule channel cleanup and log updates.

        Args:
            ticket: The [`TicketModel`][] to close.
            closer: The user closing the ticket (`None` if the closer is unknown).
            close_status: The [`TicketStatus`][] value to set on the ticket.
        """
        if not ticket.status.is_open():
            logger.info("Ticket %s is already closed, skipping close operation.", ticket.key)
            return

        logger.debug("Closing ticket %s: %s", ticket.key, close_status)
        if close_status.is_open():
            logger.warning(
                "Close status cannot be open for ticket %s, defaulting to closed_by_command.", ticket.key
            )
            close_status = TicketStatus.closed_by_command

        if closer is None:
            closer_model = TicketUserModel.from_user(cast("discord.ClientUser", self.bot.user))
        else:
            closer_model = TicketUserModel.from_user(closer)

        await self.bot.database_client.close_ticket(ticket.key, closer_model, ticket_status=close_status)
        # Update the ticket model locally
        ticket = ticket.model_copy(
            update={
                "status": close_status,
                "closed_by": closer_model,
                "closed_at": datetime.datetime.now(datetime.UTC),
            }
        )

        logger.info("Closed ticket %s for %s.", ticket.key, ticket.recipients)

        # Deletion/archive the ticket channel
        task = asyncio.create_task(self._delete_after_ticket_closed(ticket, closer=closer))
        self.bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(self.bot.asyncio_pending_tasks.discard)

        # Update the log channel message
        task2 = asyncio.create_task(self._update_log_channel_message(ticket))
        self.bot.asyncio_pending_tasks.add(task2)
        task2.add_done_callback(self.bot.asyncio_pending_tasks.discard)
