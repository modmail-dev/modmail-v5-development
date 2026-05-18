"""Send/receive bridge between a ticket channel and the recipients' DMs."""

from __future__ import annotations

import asyncio
import datetime
import itertools
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, cast

import discord

from .. import CONFIG
from ..backends.common import TicketDMMessageModel, TicketMessageModel, TicketModel, TicketUserModel
from ..enum import TicketMessageType, TicketStatus
from ..errors import (
    BadPermissionsError,
    DatabaseOperationError,
    NoStaffGuildError,
    NoTicketChannelError,
    TicketNotFoundError,
)
from ._partial_recipient import PartialRecipient
from .translator import _

if TYPE_CHECKING:
    from .staff_guild import StaffGuild

logger = logging.getLogger(__name__)


class TicketView:
    """Runtime handle for an open ticket."""

    __slots__ = ("_bot", "_model", "_recipients", "_staff_guild")

    def __init__(self, staff_guild: StaffGuild, ticket_model: TicketModel) -> None:
        """Attach the staff guild and ticket model; build recipients from stored data.

        Args:
            staff_guild: The staff guild that owns this ticket.
            ticket_model: Database model representing the ticket.
        """
        self._bot = staff_guild.bot
        self._staff_guild = staff_guild
        self._model = ticket_model
        self._recipients = [PartialRecipient(staff_guild.bot, r) for r in ticket_model.recipients]

    @property
    def log_url(self) -> str:
        """Log viewer URL for this ticket."""
        return f"{CONFIG.log_url}/{self._model.key}"

    async def open(self, *, starter_message: discord.Message | None = None) -> None:
        """Perform the ticket opening sequence.

        This method:
            1. Posts the initial log entry.
            2. Posts the opening info to the ticket channel.
            3. Sends the welcome DM to each recipient.

        Args:
            starter_message: The message that triggered ticket creation (`None` if unavailable).
        """
        self._bot.spawn_task(
            self._post_log_message(starter_message=starter_message),
            name=f"post_log_entry:{self._model.key}",
        )

        staff_sent = await self._post_staff_welcome_message()
        if not staff_sent:
            logger.error("Failed to send initial staff message for ticket %s.", self._model.key)

        await self._post_welcome_dm_messages()

    async def close(
        self,
        *,
        closer: discord.User | discord.Member | None,
        close_status: TicketStatus,
    ) -> bool:
        """Mark this ticket as closed and perform all cleanup.

        Args:
            closer: The user closing the ticket, or `None` if the closer is unknown
                (e.g. the channel was deleted manually).
            close_status: The terminal [`TicketStatus`][] to record.

        Returns:
            `True` if the ticket is closed or `False` if it is still open after this operation.
        """
        if not self._model.status.is_open():
            logger.warning("Ticket %s is already closed, not closing again.", self._model.key)
            return True

        if close_status.is_open():
            logger.warning("Close status cannot be set to %s? Defaulting to closed_by_command.", close_status)
            close_status = TicketStatus.closed_by_command

        closer_model = (
            TicketUserModel.from_user(closer)
            if closer is not None
            else TicketUserModel.from_user(cast("discord.ClientUser", self._bot.user))
        )

        try:
            await self._bot.database_client.close_ticket(self._model.key, closer_model, ticket_status=close_status)
        except (TicketNotFoundError, DatabaseOperationError) as exc:
            logger.error("Failed to close ticket %s: %s", self._model.key, exc)
            # Refresh the ticket model from the database
            model = await self._bot.database_client.get_ticket_by_key(self._model.key, only_open=False)
            if model is None:
                logger.warning("Ticket %s disappeared during close operation!", self._model.key)
                return True
            self._model = model
        else:
            self._model = self._model.model_copy(
                update={
                    "status": close_status,
                    "closed_by": closer_model,
                    "closed_at": datetime.datetime.now(datetime.UTC),
                }
            )

        if self._model.status.is_open():
            logger.warning("Ticket %s is still open after close operation!", self._model.key)
            return False

        logger.info("Closed ticket %s.", self._model.key)

        self._bot.spawn_task(self._update_log_message(), name=f"update_log:{self._model.key}")
        # TODO: make archive and delete configurable
        self._bot.spawn_task(self._delete_channel(), name=f"delete_channel:{self._model.key}")
        return True

    async def get_channel(self, *, check_permissions: bool = True) -> discord.TextChannel | discord.Thread:
        """Return the ticket channel or thread.

        Args:
            check_permissions: When `True` (default), raises [`BadPermissionsError`][] if the bot
                lacks the required channel permissions.  Pass `False` to skip this check when only
                verifying the channel exists (e.g. during ticket lookup).

        Returns:
            The resolved ticket channel.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the channel is missing or the wrong type.
            BadPermissionsError: If `check_permissions` is `True` and the bot lacks permissions.
            discord.HTTPException: If a transient Discord API error occurs while fetching the channel.
        """
        try:
            channel = self._staff_guild.guild.get_channel_or_thread(self._model.channel_id)
        except NoStaffGuildError:
            logger.debug("Staff guild not set, cannot get channel.")
            raise
        if channel is None:
            try:
                channel = await self._staff_guild.guild.fetch_channel(self._model.channel_id)
            except discord.NotFound as e:
                raise NoTicketChannelError(f"Ticket channel {self._model.channel_id} not found.") from e
            # Other discord.HTTPException is a transient network error — let it propagate.

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            raise NoTicketChannelError("Ticket channel is not a text channel or thread.")

        if check_permissions:
            perms = channel.permissions_for(channel.guild.me)
            missing = ~perms & self._staff_guild.MIN_PERMISSIONS
            if missing.value:
                raise BadPermissionsError(channel=channel, missing=missing)
        return channel

    async def process_dm_message(self, message: discord.Message) -> int:
        """Relay an incoming DM to the ticket channel and to all other recipients.

        Skips recipients already tracked as unreachable by [`ReachabilityRegistry`][].
        The sender's unreachable record is cleared (they proved reachable).  Newly failed
        deliveries are marked unreachable and reflected in the ticket channel layout that
        is sent after DM delivery completes.

        Args:
            message: The DM message received from a recipient.

        Returns:
            The ID of the message sent to the ticket channel.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            discord.HTTPException: If a transient Discord API error.
        """
        logger.debug("Processing DM message from %s: %s", message.author, message.content)
        channel = await self.get_channel()

        reachable: list[PartialRecipient] = []
        failed_recipients: list[PartialRecipient] = []
        for recipient in self._recipients:
            if recipient.id == message.author.id:
                recipient.mark_reachable()
                continue
            if recipient.is_reachable():
                reachable.append(recipient)
            else:
                failed_recipients.append(recipient)

        if failed_recipients:
            logger.debug("Skipping already-unreachable recipient(s): %s", failed_recipients)

        sent_dm: list[tuple[PartialRecipient, discord.Message]] = []
        if reachable:
            dm_view = self._build_dm_message_view(message, TicketMessageType.dm)
            sent_dm, new_failed = await self._send_to_recipients(reachable, dm_view)
            failed_recipients += new_failed

        staff_view = self._build_staff_message_view(message, TicketMessageType.dm, unreachable=failed_recipients)
        channel_message = await self._bot.send_message(channel=channel, view=staff_view)

        sender_model = TicketUserModel.from_user(message.author)
        dm_models: list[TicketDMMessageModel] = [
            TicketDMMessageModel(
                message_id=message.id, ticket_message_id=channel_message.id, recipient=sender_model
            )
        ]

        for recipient, sent_message in sent_dm:
            user_model: TicketUserModel | None = None
            if isinstance(sent_message.channel, discord.abc.PrivateChannel):
                for channel_recipient in sent_message.channel.recipients:
                    if channel_recipient.id == recipient.id:
                        user_model = TicketUserModel.from_user(channel_recipient)

            if user_model is None:
                user_model = recipient.user_model

            dm_models.append(
                TicketDMMessageModel(
                    message_id=sent_message.id, ticket_message_id=channel_message.id, recipient=user_model
                )
            )

        self._bot.spawn_task(
            self._bot.database_client.save_message(
                TicketMessageModel(
                    bot_id=self._model.bot_id,
                    ticket_key=self._model.key,
                    message_id=channel_message.id,
                    dm_messages=dm_models,
                    author=sender_model,
                    content=message.content,
                    created_at=message.created_at,
                    type=TicketMessageType.dm,
                )
            ),
            name=f"save_message:{self._model.key}",
        )
        return channel_message.id

    async def process_reply_message(
        self, message: discord.Message, message_type: TicketMessageType = TicketMessageType.reply
    ) -> int:
        """Relay a staff reply, close, or note to the ticket channel and recipients' DMs.

        Args:
            message: The message containing the staff reply.
            message_type: The type of the message.

        Returns:
            The ID of the message sent to the ticket channel.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            discord.HTTPException: If a transient Discord API error occurs.
        """
        logger.debug("Processing %s message in ticket %s: %s", message_type, self._model.key, message)
        channel = await self.get_channel()

        sent_dm: list[tuple[PartialRecipient, discord.Message]] = []
        failed_recipients: list[PartialRecipient] = []

        if message_type in {TicketMessageType.reply, TicketMessageType.close}:
            reachable: list[PartialRecipient] = []
            for recipient in self._recipients:
                if recipient.is_reachable():
                    reachable.append(recipient)
                else:
                    failed_recipients.append(recipient)
            if failed_recipients:
                logger.debug("Skipping already-unreachable recipient(s): %s", failed_recipients)

            dm_view = self._build_dm_message_view(message, message_type)
            sent_dm, new_failed = await self._send_to_recipients(reachable, dm_view)
            failed_recipients += new_failed

        staff_view = self._build_staff_message_view(message, message_type, unreachable=failed_recipients)
        channel_message = await self._bot.send_message(channel=channel, view=staff_view)

        dm_models: list[TicketDMMessageModel] = []
        for recipient, sent_message in sent_dm:
            user_model: TicketUserModel | None = None
            if isinstance(sent_message.channel, discord.abc.PrivateChannel):
                for channel_recipient in sent_message.channel.recipients:
                    if channel_recipient.id == recipient.id:
                        user_model = TicketUserModel.from_user(channel_recipient)

            if user_model is None:
                user_model = recipient.user_model

            dm_models.append(
                TicketDMMessageModel(
                    message_id=sent_message.id, ticket_message_id=channel_message.id, recipient=user_model
                )
            )

        self._bot.spawn_task(
            self._bot.database_client.save_message(
                TicketMessageModel(
                    bot_id=self._model.bot_id,
                    ticket_key=self._model.key,
                    message_id=channel_message.id,
                    dm_messages=dm_models,
                    author=TicketUserModel.from_user(message.author),
                    content=message.content,
                    created_at=message.created_at,
                    type=message_type,
                )
            ),
            name=f"save_message:{self._model.key}:{message_type}",
        )
        return channel_message.id

    async def _send_to_recipients(
        self,
        recipients: list[PartialRecipient],
        views: discord.ui.LayoutView | list[discord.ui.LayoutView],
    ) -> tuple[list[tuple[PartialRecipient, discord.Message]], list[PartialRecipient]]:
        """Send views concurrently to recipients and handle delivery failures.

        When `views` is a single [`discord.ui.LayoutView`][], it is sent to every
        recipient.  When a list is passed, each item pairs with the
        recipient at the same index.

        Args:
            recipients: Reachable recipients to send to.
            views: One view, or one view per recipient in the same order.

        Returns:
            A 2-tuple of `(sent, failed)` where `sent` contains `(recipient, message)`
            pairs for every successful delivery, and `failed` contains every recipient
            whose delivery failed.
        """
        if isinstance(views, discord.ui.LayoutView):
            views = [views] * len(recipients)

        sent: list[tuple[PartialRecipient, discord.Message]] = []
        failed: list[PartialRecipient] = []

        async def _send_one(recipient: PartialRecipient, view: discord.ui.LayoutView) -> None:
            try:
                msg = await recipient.send(view=view)
                sent.append((recipient, msg))
            except (discord.Forbidden, discord.NotFound) as exc:
                # TODO: NotFound should remove the recipient, not just mark unreachable.
                logger.warning("Failed to DM %s, marking unreachable (%s).", recipient, exc)
                recipient.mark_unreachable()
                failed.append(recipient)
            except Exception:
                logger.exception("Failed to DM %s due to unknown reason.", recipient)
                recipient.mark_unreachable()
                failed.append(recipient)

        async with asyncio.TaskGroup() as tg:
            for recipient, view in zip(recipients, views, strict=True):
                tg.create_task(_send_one(recipient, view))

        return sent, failed

    def _build_log_message_view(self) -> discord.ui.LayoutView:
        """Build the log-channel view for the current ticket state.

        Layout is title, body in a [`Section`][] with the first recipient's avatar
        as thumbnail, then footer. At least one of the three parts must be provided.
        Accent colour tracks open/closed status.

        Returns:
            A [`discord.ui.LayoutView`][] ready to send or edit in the log channel.
        """
        if not self._recipients:
            logger.error("Ticket %s has no recipients, cannot build log view.", self._model.key)
            layout = discord.ui.LayoutView(timeout=None)
            layout.add_item(discord.ui.Container(discord.ui.TextDisplay(self._bot.translate(_("ftl-error")))))
            return layout

        is_open = self._model.status.is_open()
        closer = self._model.closed_by
        has_real_closer = (not is_open) and closer is not None and closer.user_id != CONFIG.bot.bot_id
        status = "open" if is_open else ("closed_by" if has_real_closer else "closed")

        first_recipient = self._recipients[0]

        params: dict[str, str] = {
            "users": "  ".join(f"<@{r.user_id}>" for r in self._model.recipients),
            "key": self._model.key,
            "log_url": self.log_url,
            "created_ts": str(int(self._model.created_at.timestamp())),
            "created_by": str(self._model.created_by.user_id),
            "closed_ts": str(int(self._model.closed_at.timestamp())) if self._model.closed_at else "0",
            "closed_by": str(closer.user_id) if closer else "",
            "channel_id": str(self._model.channel_id),
            "status": status,
        }
        title = self._bot.translate(_("ftl-msg-ticket-log-title", escape=True, **params)).strip()
        body = self._bot.translate(_("ftl-msg-ticket-log-body", escape=True, **params)).strip()
        footer = self._bot.translate(_("ftl-msg-ticket-log-footer", escape=True, **params)).strip()

        items: list[discord.ui.Item[discord.ui.LayoutView]] = []

        if title:
            items.append(discord.ui.TextDisplay(title))

        if body:
            if items:
                items.append(discord.ui.Separator[discord.ui.LayoutView](visible=False))
            items.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(body),
                    accessory=discord.ui.Thumbnail[discord.ui.LayoutView](media=first_recipient.display_avatar),
                )
            )

        if footer:
            if items:
                items.append(discord.ui.Separator[discord.ui.LayoutView](visible=True))
            items.append(discord.ui.TextDisplay(footer))

        if not items:
            items = [discord.ui.TextDisplay(self._bot.translate(_("ftl-error")))]

        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(
            discord.ui.Container(
                *items,
                accent_color=discord.Color.brand_green() if is_open else discord.Color.red(),
            )
        )
        return layout

    async def _build_staff_starter_recipient_container(
        self,
        recipient: PartialRecipient,
        guild_members: list[discord.Member],
    ) -> discord.ui.Container[discord.ui.LayoutView]:
        """Build the opening-info [`discord.ui.Container`][] for one ticket recipient.

        Args:
            recipient: The recipient to display.
            guild_members: All guild memberships found for this recipient, sorted by guild name.

        Returns:
            A [`discord.ui.Container`][] with account info, mutual-server entries, and ticket meta.
        """
        try:
            past_ticket_count = await self._bot.database_client.get_all_tickets_by_recipient(
                recipient.id, count=True, only_closed=True
            )
        except DatabaseOperationError:
            logger.exception("Failed to fetch past ticket count for %s, using fallback.", recipient)
            past_ticket_count = 0

        params: dict[str, str | int] = {
            "user_name": recipient.display_name,
            "user_id": str(recipient.id),
            "account_created_ts": str(int(recipient.created_at.timestamp())),
            "log_url": self.log_url,
            "key": self._model.key,
            "created_ts": str(int(self._model.created_at.timestamp())),
            "past_ticket_count": past_ticket_count,
        }

        section = discord.ui.Section(
            discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-ticket-info-title", escape=True, **params))),
            discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-ticket-info-body", escape=True, **params))),
            accessory=discord.ui.Thumbnail[discord.ui.LayoutView](media=recipient.display_avatar),
        )

        guild_items: list[discord.ui.Item[discord.ui.LayoutView]] = []
        for i, member in enumerate(guild_members):
            if i > 0:
                guild_items.append(
                    discord.ui.Separator[discord.ui.LayoutView](spacing=discord.SeparatorSpacing.small)
                )
            role_mentions = [r.mention for r in member.roles if not r.is_default()]
            guild_name = self._bot.translate(
                _(
                    "ftl-msg-ticket-info-guild-name",
                    escape=True,
                    guild_name=member.guild.name,
                    guild_id=str(member.guild.id),
                )
            )
            guild_items.extend([
                discord.ui.TextDisplay(guild_name),
                discord.ui.Separator[discord.ui.LayoutView](visible=False),
            ])
            guild_details = self._bot.translate(
                _(
                    "ftl-msg-ticket-info-guild-entry",
                    escape=True,
                    joined_ts=str(int(member.joined_at.timestamp())) if member.joined_at else "0",
                    roles=", ".join(role_mentions) if role_mentions else "none",
                )
            )
            guild_items.append(discord.ui.TextDisplay(guild_details))

        if not guild_items:
            guild_items.append(
                discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-ticket-info-no-shared-servers")))
            )

        return discord.ui.Container(
            section,
            discord.ui.Separator[discord.ui.LayoutView](visible=True),
            *guild_items,
            discord.ui.Separator[discord.ui.LayoutView](visible=True),
            discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-ticket-info-footer", escape=True, **params))),
            accent_color=discord.Color.blurple(),
        )

    def _build_staff_message_view(
        self,
        message: discord.Message,
        message_type: TicketMessageType,
        *,
        unreachable: list[PartialRecipient] | None = None,
    ) -> discord.ui.LayoutView:
        """Build the staff-channel view for a ticket message.

        All formatting is driven from FTL keys so locale files fully control
        the title, footer, and unreachable warning.  The Section pairs the
        author's avatar with a FTL title and the message body.

        The close and sclose commands provide their own default body text
        via FTL keys in the command files before calling this method.

        Args:
            message: The message to render.
            message_type: Controls accent colour and which FTL keys are looked up.
            unreachable: Recipients who did not receive this message.

        Returns:
            A [`discord.ui.LayoutView`][] ready to send to the ticket channel.
        """
        author = message.author

        params: dict[str, str] = {
            "author_id": str(author.id),
            "author_name": author.display_name,
            "message_id": str(message.id),
            "created_ts": str(int(message.created_at.timestamp())),
            "key": self._model.key,
            "log_url": self.log_url,
        }

        match message_type:
            case TicketMessageType.dm:
                accent_color = discord.Color.blurple()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-dm", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-dm", escape=True, **params))
            case TicketMessageType.reply:
                accent_color = discord.Color.brand_green()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-reply", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-reply", escape=True, **params))
            case TicketMessageType.internal:
                accent_color = discord.Color.yellow()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-internal", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-internal", escape=True, **params))
            case TicketMessageType.close:
                accent_color = discord.Color.red()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-close", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-close", escape=True, **params))
            case TicketMessageType.sclose:
                accent_color = discord.Color.red()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-sclose", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-sclose", escape=True, **params))
            case _:  # pyright: ignore [reportUnnecessaryComparison]
                logger.warning("Unexpected message type %s in staff view, using fallback.", message_type)
                accent_color = discord.Color.greyple()
                title = self._bot.translate(_("ftl-msg-ticket-staff-title-dm", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-staff-footer-dm", escape=True, **params))

        display_thumbnail = message_type not in {TicketMessageType.close, TicketMessageType.sclose}
        section_children: list[discord.ui.TextDisplay[discord.ui.LayoutView]] = [discord.ui.TextDisplay(title)]

        if message_text := (message.content or "").strip():
            section_children.append(discord.ui.TextDisplay(message_text))

        container_items: list[discord.ui.Item[discord.ui.LayoutView]]

        if display_thumbnail:
            container_items = [
                discord.ui.Section(
                    *section_children,
                    accessory=discord.ui.Thumbnail[discord.ui.LayoutView](media=str(author.display_avatar)),
                ),
                discord.ui.Separator[discord.ui.LayoutView](visible=True),
                discord.ui.TextDisplay(footer),
            ]
        else:
            container_items = [
                *section_children,
                discord.ui.Separator[discord.ui.LayoutView](visible=True),
                discord.ui.TextDisplay(footer),
            ]

        if unreachable:
            container_items.append(
                discord.ui.TextDisplay(
                    self._bot.translate(
                        _(
                            "ftl-msg-ticket-staff-unreachable",
                            count=len(unreachable),
                            recipients=", ".join(r.mention for r in unreachable),
                        )
                    )
                )
            )

        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(discord.ui.Container(*container_items, accent_color=accent_color))
        return layout

    def _build_dm_message_view(
        self, message: discord.Message, message_type: TicketMessageType
    ) -> discord.ui.LayoutView:
        """Build the recipient-DM Components v2 layout for a ticket message.

        All formatting is driven from FTL keys so locale files fully control the
        title and footer for every message type.  For dm and reply the author's
        avatar is shown as a thumbnail in a Section; for close the layout uses
        flat TextDisplays without a thumbnail.

        The close command provides its own default body text via FTL keys in the
        command files before calling this method.

        Args:
            message: The message to render.
            message_type: Controls accent colour and which FTL keys are looked up.

        Returns:
            A [`discord.ui.LayoutView`][] ready to send to a recipient's DM channel.
        """
        author = message.author

        params: dict[str, str] = {
            "author_id": str(author.id),
            "author_name": author.display_name,
            "message_id": str(message.id),
            "created_ts": str(int(message.created_at.timestamp())),
            "key": self._model.key,
            "log_url": self.log_url,
        }

        match message_type:
            case TicketMessageType.dm:
                accent_color = discord.Color.orange()
                title = self._bot.translate(_("ftl-msg-ticket-user-title-dm", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-user-footer-dm", escape=True, **params))
            case TicketMessageType.reply:
                accent_color = discord.Color.brand_green()
                title = self._bot.translate(_("ftl-msg-ticket-user-title-reply", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-user-footer-reply", escape=True, **params))
            case TicketMessageType.close:
                accent_color = discord.Color.red()
                title = self._bot.translate(_("ftl-msg-ticket-user-title-close", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-user-footer-close", escape=True, **params))
            case _:  # internal and sclose messages are not sent to recipients, use dm as fallback
                accent_color = discord.Color.greyple()
                title = self._bot.translate(_("ftl-msg-ticket-user-title-dm", escape=True, **params))
                footer = self._bot.translate(_("ftl-msg-ticket-user-footer-dm", escape=True, **params))

        display_thumbnail = message_type not in {TicketMessageType.close, TicketMessageType.sclose}
        section_children: list[discord.ui.TextDisplay[discord.ui.LayoutView]] = [discord.ui.TextDisplay(title)]

        if message_text := (message.content or "").strip():
            section_children.append(discord.ui.TextDisplay(message_text))

        container: discord.ui.Container[discord.ui.LayoutView]

        if display_thumbnail:
            container = discord.ui.Container(
                discord.ui.Section(
                    *section_children,
                    accessory=discord.ui.Thumbnail[discord.ui.LayoutView](media=str(author.display_avatar)),
                ),
                discord.ui.Separator[discord.ui.LayoutView](visible=True),
                discord.ui.TextDisplay(footer),
                accent_color=accent_color,
            )
        else:
            container = discord.ui.Container(
                *section_children,
                discord.ui.Separator[discord.ui.LayoutView](visible=True),
                discord.ui.TextDisplay(footer),
                accent_color=accent_color,
            )

        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(container)
        return layout

    def _build_dm_welcome_view(self, recipient: PartialRecipient) -> discord.ui.LayoutView:
        """Build a personalised welcome view sent to a recipient when a ticket is opened.

        Args:
            recipient: The recipient to send this view to.

        Returns:
            A [`discord.ui.LayoutView`][] ready to send to the recipient's DM channel.
        """
        params: dict[str, str] = {
            "user_id": str(recipient.id),
            "user_name": recipient.display_name,
        }
        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-dm-welcome-title", escape=True, **params))),
                discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-dm-welcome-body", escape=True, **params))),
                discord.ui.Separator[discord.ui.LayoutView](visible=True),
                discord.ui.TextDisplay(self._bot.translate(_("ftl-msg-dm-welcome-footer", escape=True, **params))),
                accent_color=discord.Color.brand_green(),
            )
        )
        return layout

    async def _post_welcome_dm_messages(self) -> None:
        """Send a personalised welcome view to every reachable recipient."""
        reachable = [r for r in self._recipients if r.is_reachable()]
        if not reachable:
            logger.debug("No reachable recipients to send welcome DM for ticket %s.", self._model.key)
            return

        views = [self._build_dm_welcome_view(r) for r in reachable]
        await self._send_to_recipients(reachable, views)

    async def _post_log_message(self, *, starter_message: discord.Message | None = None) -> bool:
        """Post the log message for this ticket in the log channel.

        Args:
            starter_message: The message that triggered ticket creation (`None` if unavailable).

        Returns:
            `True` if the log message was posted successfully, `False` otherwise.
        """
        log_channel = await self._staff_guild.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log entry for %s.", self._model.key)
            return False

        try:
            log_message = await self._bot.send_message(channel=log_channel, view=self._build_log_message_view())
        except discord.HTTPException as exc:
            logger.error("Failed to send log message for ticket %s: %s", self._model.key, exc)
            return False

        self._model = self._model.model_copy(update={"log_channel_message_id": log_message.id})
        self._bot.spawn_task(
            self._bot.database_client.set_ticket_log_channel_message_id(self._model.key, log_message.id),
            name=f"set_log_message_id:{self._model.key}",
        )
        return True

    async def _post_staff_welcome_message(self) -> bool:
        """Send the opening info to the ticket channel.

        Returns:
            `True` if the staff message was posted successfully, `False` otherwise.
        """
        try:
            channel = await self.get_channel()
        except (NoStaffGuildError, NoTicketChannelError, BadPermissionsError, discord.HTTPException) as exc:
            logger.warning(
                "Failed to get channel for ticket %s during staff message posting: %s", self._model.key, exc
            )
            return False

        members_mapping: defaultdict[int, list[discord.Member]] = defaultdict(list)
        recipient_ids = {r.id for r in self._recipients}

        async def _fetch_guild_members(guild: discord.Guild, target_ids: set[int]) -> list[discord.Member]:
            try:
                result = [m async for m in guild.fetch_members(limit=None) if m.id in target_ids]
            except discord.HTTPException as exc:
                logger.warning("Failed to fetch members in %s: %s", guild, exc)
                result = []
            return result

        for guild in self._bot.guilds:
            if self._bot.is_ws_ratelimited():
                for member in await _fetch_guild_members(guild, recipient_ids):
                    members_mapping[member.id].append(member)
                continue

            found_ids: set[int] = set()
            need_fallback = False
            try:
                for chunk in itertools.batched(list(recipient_ids), 100, strict=False):
                    if self._bot.is_ws_ratelimited():
                        need_fallback = True
                        break
                    for member in await asyncio.wait_for(
                        guild.query_members(limit=len(chunk), user_ids=list(chunk), cache=False),
                        timeout=2.0,
                    ):
                        members_mapping[member.id].append(member)
                        found_ids.add(member.id)
            except TimeoutError:
                logger.warning("query_members timed out in %s, falling back to fetch_members", guild)
                need_fallback = True
            except discord.HTTPException as exc:
                logger.warning("query_members failed in %s: %s, falling back to fetch_members", guild, exc)
                need_fallback = True

            if need_fallback:
                for member in await _fetch_guild_members(guild, recipient_ids - found_ids):
                    members_mapping[member.id].append(member)

        # TODO: send one message per recipient (discord's 40-component limit)
        # probably make a persistent pagination component to flip through recipients
        # when there are multiple, instead of sending a wall of text with all mutual servers
        recipients = sorted(self._recipients, key=lambda r: r.display_name)
        if recipients:
            recipient = recipients[0]
            members = sorted(members_mapping.get(recipient.id, []), key=lambda m: m.guild.name)
            container = await self._build_staff_starter_recipient_container(recipient, members)
            layout = discord.ui.LayoutView(timeout=None)
            layout.add_item(container)
            await self._bot.send_message(channel=channel, view=layout)
        return True

    async def _update_log_message(self) -> bool:
        """Edit the log-channel message to reflect the ticket's closed state.

        Returns:
            `True` if the log message was successfully updated, `False` otherwise.
        """
        if self._model.log_channel_message_id is None:
            logger.info("No log message ID set, skipping log update for %s.", self._model.key)
            return False

        log_channel = await self._staff_guild.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log update for %s.", self._model.key)
            return False

        try:
            log_message = await log_channel.fetch_message(self._model.log_channel_message_id)
            # Discord.py weird behavior, it resets allowed mention to all on message edit:
            # https://github.com/Rapptz/discord.py/pull/10406
            allowed_mentions = discord.AllowedMentions.none()
            if log_message.mention_everyone:
                allowed_mentions.everyone = True
            if log_message.mentions:
                allowed_mentions.users = log_message.mentions
            if log_message.role_mentions:
                allowed_mentions.roles = log_message.role_mentions
            await log_message.edit(view=self._build_log_message_view(), allowed_mentions=allowed_mentions)
        except discord.NotFound:
            logger.info("Log message %d not found, skipping update.", self._model.log_channel_message_id)
            return False
        except discord.HTTPException:
            logger.exception("Failed to fetch or update log message %d.", self._model.log_channel_message_id)
            return False

        logger.debug("Updated log message %d for ticket %s.", self._model.log_channel_message_id, self._model.key)
        return True

    async def _delete_channel(self) -> bool:
        """Delete or archive the ticket channel after closure.

        Returns:
            `True` if the channel was successfully deleted or archived, `False` otherwise.
        """
        try:
            channel = await self.get_channel()
        except (NoStaffGuildError, NoTicketChannelError) as exc:
            logger.warning("Failed to get channel for ticket %s during cleanup: %s", self._model.key, exc)
            return False
        except BadPermissionsError as exc:
            logger.warning(
                "Missing permissions to get channel for ticket %s during cleanup: %s", self._model.key, exc
            )
            return False
        except discord.HTTPException as exc:
            logger.warning(
                "HTTP error while getting channel for ticket %s during cleanup: %s", self._model.key, exc
            )
            return False

        if self._model.closed_by is None:
            reason = self._bot.translate(_("ftl-msg-ticket-closed-reason-unknown-closer"))
        else:
            reason = self._bot.translate(_("ftl-msg-ticket-closed-reason", user=self._model.closed_by.user_name))

        try:
            if isinstance(channel, discord.Thread):
                await channel.edit(archived=True, locked=True, reason=reason)
            else:
                await channel.delete(reason=reason)
        except discord.HTTPException:
            logger.exception("Failed to clean up ticket channel %s.", channel)
            return False
        return True
