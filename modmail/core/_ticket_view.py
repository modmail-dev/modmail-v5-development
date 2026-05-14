"""[`TicketView`][] — send/receive bridge between a ticket channel and the recipients' DMs."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import itertools
import logging
import operator
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

import discord

from .. import CONFIG
from ..backends.common import TicketDMMessageModel, TicketMessageModel, TicketModel, TicketUserModel
from ..enum import TicketMessageType, TicketStatus
from ..errors import BadPermissionsError, NoStaffGuildError, NoTicketChannelError, TicketNotFoundError
from ._partial_recipient import PartialRecipient
from .embed import EmbedProxy
from .translator import _

if TYPE_CHECKING:
    from .staff_guild import StaffGuild

logger = logging.getLogger(__name__)


class TicketView:
    """Runtime handle for an open ticket.

    Provides helpers to fetch the ticket channel, format embeds, and relay messages
    between the staff channel and each recipient's DMs.
    """

    _LOG_SUMMARY_MAX_LENGTH: int = 75
    """Maximum character length for the message preview in the log channel embed."""

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

        Posts the log channel entry as a fire-and-forget task (log issues never block
        ticket creation), then awaits the initial staff message in the ticket channel.

        Args:
            starter_message: The message that triggered ticket creation (`None` if unavailable).

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            DatabaseOperationError: If the past-ticket count query fails.
        """
        self._bot.spawn_task(
            self._post_log_entry(starter_message=starter_message),
            name=f"post_log_entry:{self._model.key}",
        )
        try:
            await self._post_staff_message()
        except discord.HTTPException as esc:
            logger.error("Failed to send initial staff message for ticket %s: %s", self._model.key, esc)
        # TODO: send initial recipient message (welcome/starter message)

    async def close(
        self,
        *,
        closer: discord.User | discord.Member | None,
        close_status: TicketStatus,
    ) -> None:
        """Mark this ticket as closed and perform all cleanup.

        Closes the ticket in the database, updates the in-memory model, then spawns
        channel cleanup and log update as fire-and-forget tasks.

        Args:
            closer: The user closing the ticket, or `None` if the closer is unknown
                (e.g. the channel was deleted manually).
            close_status: The terminal [`TicketStatus`][] to record.

        Raises:
            DatabaseOperationError: If the database write fails.
        """
        if not self._model.status.is_open():
            logger.info("Ticket %s is already closed, not closing again.", self._model.key)
            return

        if close_status.is_open():
            logger.warning("Close status cannot be set to TicketStatus.open? Defaulting to closed_by_command.")
            close_status = TicketStatus.closed_by_command

        closer_model = (
            TicketUserModel.from_user(closer)
            if closer is not None
            else TicketUserModel.from_user(cast("discord.ClientUser", self._bot.user))
        )

        try:
            await self._bot.database_client.close_ticket(self._model.key, closer_model, ticket_status=close_status)
        except TicketNotFoundError as exc:
            logger.error("Failed to close ticket %s: %s", self._model.key, exc)

        self._model = self._model.model_copy(
            update={
                "status": close_status,
                "closed_by": closer_model,
                "closed_at": datetime.datetime.now(datetime.UTC),
            }
        )
        logger.info("Closed ticket %s.", self._model.key)

        self._bot.spawn_task(self._delete_channel(), name=f"delete_channel:{self._model.key}")
        self._bot.spawn_task(self._update_log(), name=f"update_log:{self._model.key}")

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

    async def process_dm_message(self, message: discord.Message) -> None:
        """Relay an incoming DM to the ticket channel and to all other recipients.

        Skips recipients already marked as [`unreachable`][PartialRecipient.unreachable].
        Newly failed deliveries are marked unreachable and reflected in the ticket channel
        embed that is sent after DM delivery completes.

        Args:
            message: The DM message received from a recipient.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            discord.HTTPException: If a transient Discord API error occurs while accessing the
                channel or sending the staff channel embed.
        """
        logger.debug("Processing DM message from %s: %s", message.author, message.content)
        channel = await self.get_channel()

        # Send to other recipients first
        dm_embed = self._format_user_embed(message, TicketMessageType.dm).to_embed(
            self._bot.translator, CONFIG.default_locale
        )
        other_recipients = [r for r in self._recipients if r.id != message.author.id and r.is_reachable()]

        # (dm_message_id, user_model_at_send_time)
        successful_dm_sends: list[tuple[int, TicketUserModel]] = []
        failed_recipients: list[PartialRecipient] = [
            r for r in self._recipients if r.id != message.author.id and r not in other_recipients
        ]
        if failed_recipients:
            logger.debug(
                "Not sending to %s recipients because they are marked unreachable: %s",
                len(failed_recipients),
                failed_recipients,
            )

        if other_recipients:
            dm_results = await asyncio.gather(
                *[r.send(embed=dm_embed) for r in other_recipients],
                return_exceptions=True,
            )
            for recipient, result in zip(other_recipients, dm_results, strict=True):
                if isinstance(result, discord.Message):
                    user_model = recipient.user_model
                    if isinstance(result.channel, discord.DMChannel):
                        for user in result.channel.recipients:
                            if user.id == recipient.id:
                                user_model = TicketUserModel.from_user(user)
                                break
                    successful_dm_sends.append((result.id, user_model))
                elif isinstance(result, discord.Forbidden | discord.NotFound):
                    logger.warning("Failed to DM %s, marking unreachable.", recipient)
                    # TODO: Handle NotFound by removing the recipient
                    recipient.mark_unreachable()
                    failed_recipients.append(recipient)
                else:
                    logger.error("Failed to DM %s: %s", recipient, result)
                    failed_recipients.append(recipient)

        # Build the ticket channel embed now that bad_recipients is fully up to date.
        channel_embed = self._format_staff_embed(
            message,
            TicketMessageType.dm,
            unreachable=failed_recipients,
        ).to_embed(self._bot.translator, CONFIG.default_locale)

        channel_message = await channel.send(embed=channel_embed)

        # Record all DM deliveries keyed by the ticket channel message ID.
        sender_model = TicketUserModel.from_user(message.author)
        dm_models: list[TicketDMMessageModel] = [
            TicketDMMessageModel(
                message_id=message.id,
                ticket_message_id=channel_message.id,
                recipient=sender_model,
            ),
            *[
                TicketDMMessageModel(
                    message_id=dm_id,
                    ticket_message_id=channel_message.id,
                    recipient=user_model,
                )
                for dm_id, user_model in successful_dm_sends
            ],
        ]
        ticket_message_model = TicketMessageModel(
            bot_id=self._model.bot_id,
            ticket_key=self._model.key,
            message_id=channel_message.id,
            dm_messages=dm_models,
            author=sender_model,
            content=message.content,
            created_at=message.created_at,
            type=TicketMessageType.dm,
        )
        self._bot.spawn_task(
            self._bot.database_client.save_message(ticket_message_model),
            name=f"save_message:{self._model.key}",
        )

    async def process_reply_message(
        self, message: discord.Message, message_type: TicketMessageType = TicketMessageType.reply
    ) -> None:
        """Relay a staff reply, close, or note to the ticket channel and recipients' DMs when applicable.

        Skips recipients already marked as [`unreachable`][PartialRecipient.unreachable].
        Newly failed deliveries are marked unreachable and reflected in the ticket channel embed.

        Args:
            message: The message containing the staff reply.
            message_type: Controls which channels receive the message and embed styling.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            discord.HTTPException: If a transient Discord API error occurs while accessing the
                channel or sending the staff channel embed.
        """
        logger.debug("Processing %s message in ticket %s: %s", message_type, self._model.key, message)
        channel = await self.get_channel()

        sends_to_recipients = message_type in {TicketMessageType.reply, TicketMessageType.close}

        # Send DMs to reachable recipients first
        # (dm_message_id, user_model_at_send_time)
        successful_dm_sends: list[tuple[int, TicketUserModel]] = []
        failed_recipients: list[PartialRecipient] = []

        if sends_to_recipients:
            reachable = [r for r in self._recipients if r.is_reachable()]
            failed_recipients.extend(r for r in self._recipients if r not in reachable)
            if failed_recipients:
                logger.debug(
                    "Not sending to %s recipients because they are marked unreachable: %s",
                    len(failed_recipients),
                    failed_recipients,
                )

            if reachable:
                dm_embed = self._format_user_embed(message, message_type).to_embed(
                    self._bot.translator, CONFIG.default_locale
                )
                dm_results = await asyncio.gather(
                    *[r.send(embed=dm_embed) for r in reachable],
                    return_exceptions=True,
                )
                for recipient, result in zip(reachable, dm_results, strict=True):
                    if isinstance(result, discord.Message):
                        user_model = recipient.user_model
                        if isinstance(result.channel, discord.DMChannel) and result.channel.recipients:
                            for user in result.channel.recipients:
                                if user.id == recipient.id:
                                    user_model = TicketUserModel.from_user(user)
                                    break
                        successful_dm_sends.append((result.id, user_model))
                    elif isinstance(result, discord.Forbidden | discord.NotFound):
                        # TODO: Handle NotFound by removing the recipient
                        logger.warning("Failed to DM %s, marking unreachable.", recipient)
                        recipient.mark_unreachable()
                        failed_recipients.append(recipient)
                    else:
                        logger.error("Failed to send %s DM message to %s: %s", message_type, recipient, result)
                        failed_recipients.append(recipient)

        channel_embed = self._format_staff_embed(message, message_type, unreachable=failed_recipients).to_embed(
            self._bot.translator, CONFIG.default_locale
        )

        channel_message = await channel.send(embed=channel_embed)

        dm_models: list[TicketDMMessageModel] = [
            TicketDMMessageModel(
                message_id=dm_id,
                ticket_message_id=channel_message.id,
                recipient=user_model,
            )
            for dm_id, user_model in successful_dm_sends
        ]
        ticket_message_model = TicketMessageModel(
            bot_id=self._model.bot_id,
            ticket_key=self._model.key,
            message_id=channel_message.id,
            dm_messages=dm_models,
            author=TicketUserModel.from_user(message.author),
            content=message.content,
            created_at=message.created_at,
            type=message_type,
        )
        self._bot.spawn_task(
            self._bot.database_client.save_message(ticket_message_model),
            name=f"save_message:{self._model.key}:{message_type}",
        )

    def _format_log_embed(self, *, title: str, description: str) -> discord.Embed:
        """Build the log-channel embed for the current ticket state.

        Args:
            title: Embed title (typically the recipient username list).
            description: Embed description (typically the ticket key and message preview).

        Returns:
            discord.Embed: Ready to send or edit in the log channel.
        """
        embed = EmbedProxy(title=title, description=description)
        # TODO: configurable colors
        if self._model.status.is_open():
            embed.color = discord.Color.green()
            embed.set_footer(text=_("ftl-msg-log-embed-open-footer"))
            embed.timestamp = self._model.created_at
        else:
            embed.color = discord.Color.red()
            if not self._model.closed_by or self._model.closed_by.user_id == CONFIG.bot.bot_id:
                embed.set_footer(text=_("ftl-msg-log-embed-closed-footer-unknown-closer"))
            else:
                embed.set_footer(text=_("ftl-msg-log-embed-closed-footer", user=self._model.closed_by.user_name))
            embed.timestamp = self._model.closed_at or True  # fallback to current time
        return embed.to_embed(self._bot.translator, CONFIG.default_locale)

    def _format_staff_embed(
        self,
        message: discord.Message,
        message_type: TicketMessageType,
        *,
        unreachable: list[PartialRecipient] | None = None,
    ) -> EmbedProxy:
        """Build an [`EmbedProxy`][] for the staff ticket channel.

        Args:
            message: The message to summarize in the embed.
            message_type: Controls embed color and footer.
            unreachable: Recipients who did not receive this message. When provided, a small-text
                warning is appended to the embed description.

        Returns:
            An [`EmbedProxy`][] ready to render and send.
        """
        # TODO: format close embed: TicketMessageType = close, sclose

        embed = EmbedProxy()

        author_url = f"https://discordapp.com/users/{message.author.id}"
        embed.set_author(name=str(message.author), icon_url=str(message.author.display_avatar), url=author_url)
        embed.description = message.content
        embed.timestamp = message.created_at

        if message_type == TicketMessageType.dm:
            embed.color = discord.Color.blue()
            embed.set_footer(text=_("ftl-msg-ticket-channel-embed-footer", message_id=str(message.id)))
        elif message_type == TicketMessageType.reply:
            embed.color = discord.Color.green()
            # TODO

        if unreachable:
            notice = self._bot.translate(
                _(
                    "ftl-msg-ticket-unreachable-recipients",
                    count=len(unreachable),
                    recipients=" ".join(r.mention for r in unreachable),
                )
            )
            # TODO: Small text doesn't work in embeds
            embed.description = (f"{embed.description}\n" if embed.description else "") + f"-# ⚠️ {notice}"

        return embed

    @staticmethod
    def _format_user_embed(message: discord.Message, message_type: TicketMessageType) -> EmbedProxy:
        """Build an [`EmbedProxy`][] for the recipient's DM channel.

        Args:
            message: The message to summarize in the embed.
            message_type: Controls embed color.

        Returns:
            An [`EmbedProxy`][] ready to render and send.
        """
        # TODO: format close embed: TicketMessageType = close

        embed = EmbedProxy()
        embed.set_author(name=str(message.author), icon_url=str(message.author.display_avatar))
        embed.description = message.content
        embed.timestamp = message.created_at

        if message_type == TicketMessageType.dm:
            embed.color = discord.Color.orange()
        elif message_type == TicketMessageType.reply:
            embed.color = discord.Color.green()
            # TODO
        return embed

    async def _post_log_entry(self, *, starter_message: discord.Message | None = None) -> None:
        """Post the opening entry for this ticket in the log channel.

        Builds a summary from `starter_message`, sends the embed, and persists the
        resulting message ID to the database so [`close`][] can edit it later.
        A missing or misconfigured log channel is silently skipped.

        Args:
            starter_message: The message that triggered ticket creation (`None` if unavailable).

        Raises:
            discord.HTTPException: If the log channel send fails.
        """
        log_channel = await self._staff_guild.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log entry for %s.", self._model.key)
            return

        if starter_message is not None and starter_message.content.strip():
            summary = re.sub(r"\s+", " ", starter_message.content.strip())
            if len(summary) > self._LOG_SUMMARY_MAX_LENGTH:
                summary = summary[: self._LOG_SUMMARY_MAX_LENGTH - 3] + "..."
            summary = discord.utils.escape_markdown(summary)
        else:
            summary = self._bot.translate(_("ftl-msg-log-embed-no-content-description"))

        title = " ".join(f"@{r.name}" for r in self._recipients)
        description = f"[`{self._model.key}`]({self.log_url}): {summary}"
        embed = self._format_log_embed(title=title, description=description)

        log_message = await log_channel.send(embed=embed)
        self._model = self._model.model_copy(update={"log_channel_message_id": log_message.id})
        self._bot.spawn_task(
            self._bot.database_client.set_ticket_log_channel_message_id(self._model.key, log_message.id),
            name=f"set_log_message_id:{self._model.key}",
        )

    async def _post_staff_message(self) -> None:
        """Send the opening info embed(s) to the ticket channel, one per recipient.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the ticket channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the required channel permissions.
            DatabaseOperationError: If the past-ticket count query fails.
            discord.HTTPException: If a Discord API error occurs while querying members or
                sending the embed to the channel.
        """
        channel = await self.get_channel()
        embed_proxies: list[tuple[Any, EmbedProxy]] = []  # list of tuples (sort-key, embed)

        members_mapping: defaultdict[int, list[discord.Member]] = defaultdict(list)

        # TODO: Implement recipients limit (set to 10)
        # Fetch the recipients as guild members, since members are not cached.
        recipient_ids = {r.id for r in self._recipients}
        recipient_id_list = list(recipient_ids)

        async def _fetch_members(guild: discord.Guild, target_ids: set[int]) -> None:
            try:
                async for member in guild.fetch_members(limit=None):
                    if member.id in target_ids:
                        members_mapping[member.id].append(member)
            except discord.HTTPException as exc:
                logger.warning("Failed to fetch members in %s: %s", guild, exc)

        for guild in self._bot.guilds:
            if self._bot.is_ws_ratelimited():
                await _fetch_members(guild, recipient_ids)
                continue

            found_ids: set[int] = set()
            need_fallback = False
            try:
                for chunk in itertools.batched(recipient_id_list, 100, strict=False):
                    if self._bot.is_ws_ratelimited():
                        need_fallback = True
                        break
                    chunk_members = await asyncio.wait_for(
                        guild.query_members(limit=len(chunk), user_ids=list(chunk), cache=False),
                        timeout=2.0,
                    )
                    for member in chunk_members:
                        members_mapping[member.id].append(member)
                        found_ids.add(member.id)
            except TimeoutError:
                logger.warning("query_members timed out in %s, falling back to fetch_members", guild)
                need_fallback = True
            except discord.HTTPException as exc:
                logger.warning("query_members failed in %s: %s, falling back to fetch_members", guild, exc)
                need_fallback = True

            if need_fallback:
                await _fetch_members(guild, recipient_ids - found_ids)

        for recipient in self._recipients:
            embed = EmbedProxy()
            embed.set_author(name=str(recipient), icon_url=recipient.display_avatar, url=self.log_url)
            embed.description = _(
                "ftl-msg-new-ticket-initial-embed-description",
                created=discord.utils.format_dt(recipient.created_at, "R"),
            )
            embed.set_footer(text=_("ftl-msg-new-ticket-initial-embed-footer", user_id=str(recipient.id)))

            members = members_mapping.get(recipient.id, [])
            members.sort(key=lambda m: m.guild.name)  # Sort by guild name
            # TODO: check fields limit
            for member in members:
                roles = [role.mention for role in member.roles if not role.is_default()]
                roles_str = ", ".join(roles) if roles else ""
                if member.joined_at:
                    joined_time = discord.utils.format_dt(member.joined_at, "R")
                else:
                    joined_time = _("ftl-msg-new-ticket-initial-embed-guild-field-value-no-join-date")
                embed.add_field(
                    name=member.guild.name,
                    value=_(
                        "ftl-msg-new-ticket-initial-embed-guild-field-value",
                        joined=joined_time,
                        roles=roles_str,
                        has_role=str(bool(roles)).lower(),
                    ),
                    inline=False,
                )

            past_tickets_count = await self._bot.database_client.get_all_tickets_by_recipient(
                recipient.id,
                count=True,
                only_closed=True,
            )
            embed.add_field(
                name=_("ftl-msg-new-ticket-initial-embed-past-tickets-field-name"),
                value=_("ftl-msg-new-ticket-initial-embed-past-tickets-field-value", count=past_tickets_count),
                inline=False,
            )
            embed_proxies.append((recipient.name, embed))

        embed_proxies.sort(key=operator.itemgetter(0))  # Sort by recipient name
        embeds = [embed.to_embed(self._bot.translator, CONFIG.default_locale) for _x, embed in embed_proxies]

        # Set the timestamp for the first embed
        embeds[0].timestamp = datetime.datetime.now(datetime.UTC)
        await channel.send(embeds=embeds)

    async def _delete_channel(self) -> None:
        """Delete or archive the ticket channel after closure.

        Raises:
            NoStaffGuildError: If the staff guild becomes unavailable before the task runs.
        """
        channel = self._staff_guild.guild.get_channel_or_thread(self._model.channel_id)
        if channel is None:
            with contextlib.suppress(discord.HTTPException):
                channel = await self._staff_guild.guild.fetch_channel(self._model.channel_id)

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
            logger.info("%s is closed, skipping channel cleanup due to missing permissions.", self._model.key)
            return

        if self._model.closed_by is None:
            reason = self._bot.translate(_("ftl-msg-ticket-closed-reason-unknown-closer"))
        else:
            reason = self._bot.translate(_("ftl-msg-ticket-closed-reason", user=self._model.closed_by.user_name))

        try:
            # TODO: make archive vs delete configurable
            if isinstance(channel, discord.Thread):
                await channel.edit(archived=True, locked=True, reason=reason)
            else:
                await channel.delete(reason=reason)
        except discord.HTTPException:
            logger.exception("Failed to clean up ticket channel %s.", channel)

    async def _update_log(self) -> None:
        """Edit the log-channel entry to reflect the ticket's closed state.

        Fetches the original message to preserve its title and description, then edits the
        embed with updated color, footer, and timestamp.  No-ops if no log channel or message
        is configured.

        Raises:
            discord.HTTPException: If the final embed edit fails.
        """
        if self._model.log_channel_message_id is None:
            logger.info("No log message ID set, skipping log update for %s.", self._model.key)
            return

        log_channel = await self._staff_guild.get_log_channel()
        if log_channel is None:
            logger.info("No log channel set, skipping log update for %s.", self._model.key)
            return

        try:
            log_message = await log_channel.fetch_message(self._model.log_channel_message_id)
        except discord.NotFound:
            logger.info("Log message %d not found, skipping update.", self._model.log_channel_message_id)
            return
        except discord.HTTPException:
            logger.exception("Failed to fetch log message %d.", self._model.log_channel_message_id)
            return

        if not log_message.embeds:
            logger.error("Log message %d has no embeds, skipping update.", self._model.log_channel_message_id)
            return

        embed = self._format_log_embed(
            title=log_message.embeds[0].title or "?",
            description=log_message.embeds[0].description or "?",
        )
        await log_message.edit(embed=embed)
        logger.debug("Updated log message %d for ticket %s.", self._model.log_channel_message_id, self._model.key)
