"""Ticket lifecycle, channel setup, and access control for the staff guild."""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import TYPE_CHECKING, Literal, cast

import discord

from ..backends import TicketModel, TicketUserModel
from ..config import config
from ..enum import AccessLevel, ProfileType, TicketStatus
from ..errors import (
    BadPermissionsError,
    ModmailError,
    NoModmailCategoryError,
    NoStaffGuildError,
    NoTicketChannelError,
    TicketCreationError,
)
from ..i18n import _
from ._ticket_view import TicketView

if TYPE_CHECKING:
    from ._partial_recipient import PartialRecipient
    from .bot import Bot

__all__ = ["StaffGuild"]

logger = logging.getLogger(__name__)


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
        return config.bot.staff_server_id

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
            pin_messages=True,
            bypass_slowmode=True,
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
            pin_messages=True,
            bypass_slowmode=True,
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

        category_or_forum_id = self.bot.db.settings.main_category_or_forum_id
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
        missing = ~perms & self.MIN_PERMISSIONS
        if missing.value:
            raise BadPermissionsError(channel=category_or_forum, missing=missing)
        return category_or_forum

    async def get_log_channel(self) -> discord.TextChannel | discord.Thread | None:
        """Return the configured log channel, unarchiving it if needed.

        Returns:
            The log channel/thread, or `None` if not configured, missing, or the bot lacks permissions.
        """
        if not self.guild_exists:
            return None

        channel_id = self.bot.db.settings.log_channel_id
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
        if (~perms & self.MIN_PERMISSIONS).value:
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

        channel_id = self.bot.db.settings.storage_channel_id
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
        if (~perms & self.MIN_PERMISSIONS).value:
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

        for profile in self.bot.db.profiles:
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

        missing = ~self.guild.me.guild_permissions & self.MIN_PERMISSIONS
        if missing.value:
            raise BadPermissionsError(channel=self.guild, missing=missing)

        if existing_channel_id is not None:
            resolved = self.guild.get_channel(existing_channel_id)
            if not isinstance(resolved, discord.CategoryChannel | discord.ForumChannel):
                raise NoModmailCategoryError(
                    f"Existing channel {existing_channel_id} not found or is the wrong type."
                )
            perms = resolved.permissions_for(resolved.guild.me)
            missing = ~perms & self.MIN_PERMISSIONS
            if missing.value:
                raise BadPermissionsError(channel=resolved, missing=missing)

            category_or_forum = resolved
            await category_or_forum.set_permissions(
                self._get_bot_role_or_member(),
                overwrite=self.MIN_PERMISSIONS_OVERWRITE,
                reason=self.bot.translate(_("msg.setup.category_forum.permissions_reason")),
            )
            # TODO: alert the user they need to grant staff access manually to the existing channel
        else:
            overwrites = self._build_category_overwrites()
            channel_name = self.bot.translate(_("msg.setup.category_forum.name"))
            create_reason = self.bot.translate(_("msg.setup.category_forum.create_reason"))
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

        log_reason = self.bot.translate(_("msg.setup.log_channel.create_reason"))
        storage_reason = self.bot.translate(_("msg.setup.storage_channel.create_reason"))

        storage_overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            self._get_bot_role_or_member(): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        if isinstance(category_or_forum, discord.CategoryChannel):
            log_channel, storage_channel = await asyncio.gather(
                category_or_forum.create_text_channel(
                    name=self.bot.translate(_("msg.setup.log_channel.name")),
                    topic=self.bot.translate(_("msg.setup.log_channel.topic")),
                    reason=log_reason,
                ),
                category_or_forum.create_text_channel(
                    name=self.bot.translate(_("msg.setup.storage_channel.name")),
                    topic=self.bot.translate(_("msg.setup.storage_channel.topic")),
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
                        reason=self.bot.translate(_("msg.setup.forum_thread.unpin_reason")),
                    )
                    break

            log_thread_msg, storage_channel = await asyncio.gather(
                category_or_forum.create_thread(
                    name=self.bot.translate(_("msg.setup.log_channel.name")),
                    content=self.bot.translate(_("msg.setup.log_channel.topic")),
                    reason=log_reason,
                ),
                self.guild.create_text_channel(
                    name=self.bot.translate(_("msg.setup.storage_channel.name")),
                    topic=self.bot.translate(_("msg.setup.storage_channel.topic")),
                    reason=storage_reason,
                    overwrites=storage_overwrites,
                ),
            )
            log_channel = log_thread_msg.thread

            try:
                await log_channel.edit(pinned=True, locked=True, reason=log_reason)
            except discord.HTTPException as e:
                # Discord API error code for "Maximum number of pinned threads reached (1)".
                max_pinned_threads_error_code = 30047
                if e.code == max_pinned_threads_error_code:
                    logger.error(
                        "Could not pin the log thread in forum %s because the maximum pinned threads is reached",
                        category_or_forum,
                    )
                    await log_channel.edit(locked=True, reason=log_reason)
                else:
                    raise
            await storage_channel.edit(position=1)

        await self.bot.db.update_settings(
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

        if profile_id == config.bot.bot_id:
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
            # @param user_or_role: Mention string of the user or role being granted access
            reason = self.bot.translate(_("msg.access.grant", user_or_role=user_or_role.mention))
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

        if profile_id == config.bot.bot_id:
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

        # @param user_or_role: String of the user or role being revoked
        reason = self.bot.translate(_("msg.access.revoke", user_or_role=str(user_or_role)))
        await self.category_or_forum.edit(overwrites=all_overwrites, reason=reason)

    @staticmethod
    def _make_channel_name(*users: discord.User | discord.Member | PartialRecipient) -> str:
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
            TicketCreationError: If the ticket creation fails.
        """
        if not recipients:
            raise ValueError("At least one user must be provided")

        if not self.is_setup():
            raise NoStaffGuildError("Staff guild is not configured")

        # @param users: Comma-separated list of recipient mentions
        reason = self.bot.translate(_("msg.ticket.new_reason", users=", ".join(str(user) for user in recipients)))
        try:
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
                        # @param users: Comma-separated list of recipient mentions
                        _(
                            "msg.ticket.opening_message",
                            users=" ".join(user.mention for user in recipients),
                        )
                    )
                channel = (
                    await self.category_or_forum.create_thread(
                        name=self._make_channel_name(*recipients), content=ticket_summary, reason=reason
                    )
                ).thread
        except discord.HTTPException as exc:
            logger.exception("Failed to create ticket channel for %s", recipients)
            raise TicketCreationError from exc

        ticket = TicketModel(
            bot_id=config.bot.bot_id,
            key=TicketModel.generate_key(),
            recipients=[TicketUserModel.from_user(user) for user in recipients],
            channel_id=channel.id,
            created_at=datetime.datetime.now(datetime.UTC),
            created_by=TicketUserModel.from_user(created_by),
            status=TicketStatus.open,
        )

        async def _handle_ticket_creation_failure(exc_info: BaseException) -> None:
            logger.error("Failed to create ticket channel for %s", recipients, exc_info=exc_info)
            # TODO: handle this better, tell the user if created by dm
            await self.bot.send_message(
                self.bot.translate(_("msg.ticket.create_failed")),
                channel=channel,
                ephemeral=True,
                fail_silently=True,
            )

        try:
            await self.bot.db.create_ticket(ticket)
        except TicketCreationError as exc:
            await _handle_ticket_creation_failure(exc)
            raise
        except ModmailError as exc:
            await _handle_ticket_creation_failure(exc)
            raise TicketCreationError from exc

        view = TicketView(self, ticket)
        try:
            await view.open(starter_message=starter_message)
        except NoStaffGuildError as exc:
            await _handle_ticket_creation_failure(exc)
            raise
        except ModmailError as exc:
            await _handle_ticket_creation_failure(exc)
            raise TicketCreationError from exc

        return view

    async def get_ticket(
        self,
        lookup: discord.User | discord.Member | discord.TextChannel | discord.Thread | TicketModel,
        /,
    ) -> TicketView | None:
        """Return the ticket associated with a user, channel, or existing model.

        When a [`TicketModel`][] is passed the view is returned immediately with no database or
        channel lookup — useful when the caller already has the model (e.g. deletion listeners).
        For a user or channel, the open ticket is looked up in the database and the channel is
        checked for existence (permissions are not verified here; they surface on first use).

        Args:
            lookup: A Discord user/member (looks up by recipient), a ticket channel/thread
                (looks up by channel ID), or a [`TicketModel`][] (wraps directly).

        Returns:
            The matching [`TicketView`][], or `None` if no open ticket exists or the channel
            has been deleted.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
        """
        if isinstance(lookup, TicketModel):
            return TicketView(self, lookup)

        if isinstance(lookup, discord.User | discord.Member):
            ticket_model = await self.bot.db.get_ticket_by_recipient(lookup.id)
        else:
            ticket_model = await self.bot.db.get_ticket_by_channel(lookup.id, only_open=True)

        if ticket_model is None:
            logger.debug("No ticket found for %s", lookup)
            return None

        if not ticket_model.recipients:
            logger.error("Ticket %s has no recipients, auto-closing.", ticket_model.key)
            try:
                await self.bot.db.close_ticket(
                    ticket_model.key,
                    TicketUserModel.from_user(cast("discord.ClientUser", self.bot.user)),
                    ticket_status=TicketStatus.closed_by_deletion,
                )
            except ModmailError as exc:
                logger.error("Failed to close corrupted ticket %s: %s", ticket_model.key, exc)
            return None

        view = TicketView(self, ticket_model)
        try:
            # Skip permission check here — bad permissions surface as an error on first use
            await view.get_channel(check_permissions=False)
        except NoTicketChannelError:
            logger.warning("Ticket channel for %s is missing, closing.", ticket_model.key)
            try:
                await view.close(closer=None, close_status=TicketStatus.closed_by_deletion)
            except ModmailError as exc:
                logger.error("Failed to close ticket %s: %s", ticket_model.key, exc)
            return None
        except discord.HTTPException as exc:
            logger.error(
                "An unexpected discord API error while accessing channel for ticket %s: %s",
                ticket_model.key,
                exc,
            )
        return view
