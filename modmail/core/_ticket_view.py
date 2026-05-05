"""[`TicketView`][] — send/receive bridge between a ticket channel and the recipients' DMs."""

from __future__ import annotations

import asyncio
import datetime
import logging
import operator
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import discord

from .. import CONFIG
from ..backends.common import TicketDMMessageModel, TicketMessageModel, TicketModel, TicketUserModel
from ..enum import TicketMessageType
from ..errors import BadPermissionsError, NoStaffGuildError, NoTicketChannelError
from .embed import EmbedProxy
from .translator import _

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from .context import Context
    from .staff_guild import StaffGuild

logger = logging.getLogger(__name__)


class TicketView:
    """Runtime handle for an open ticket.

    Provides helpers to fetch the ticket channel, format embeds, and relay messages
    between the staff channel and each recipient's DMs.
    """

    def __init__(
        self, staff_guild: StaffGuild, ticket_model: TicketModel, recipients: list[discord.User | discord.Member]
    ) -> None:
        """Attach the staff guild, ticket model, and recipient list.

        Args:
            staff_guild: The staff guild that owns this ticket.
            ticket_model: Database model representing the ticket.
            recipients: Discord users who are part of this ticket.
        """
        self.bot = staff_guild.bot
        """The [`Bot`][] instance."""
        self.staff_guild = staff_guild
        """The staff guild that owns this ticket."""
        self.model = ticket_model
        """Database model for the ticket."""
        self.recipients = recipients
        """Discord users who are part of this ticket."""

    async def get_channel(self) -> discord.TextChannel | discord.Thread:
        """Return the ticket channel or thread.

        Raises:
            NoStaffGuildError: If the staff guild is unavailable.
            NoTicketChannelError: If the channel is missing or the wrong type.
            BadPermissionsError: If the bot lacks the minimum required channel permissions.
        """
        try:
            channel = self.staff_guild.guild.get_channel_or_thread(self.model.channel_id)
        except NoStaffGuildError:
            logger.debug("Staff guild not set, cannot get channel.")
            raise
        if channel is None:
            try:
                channel = await self.staff_guild.guild.fetch_channel(self.model.channel_id)
            except (discord.NotFound, discord.HTTPException) as e:
                # TODO: close ticket on not found
                raise NoTicketChannelError(f"Ticket channel {self.model.channel_id} not found.") from e

        if not isinstance(channel, discord.TextChannel | discord.Thread):
            # TODO: close ticket
            raise NoTicketChannelError("Ticket channel is not a text channel or thread.")

        perms = channel.permissions_for(channel.guild.me)
        missing = ~perms & self.staff_guild.MIN_PERMISSIONS
        if missing.value:
            raise BadPermissionsError(channel=channel, missing=missing)
        return channel

    @property
    def log_url(self) -> str:
        """Log URL for this ticket."""
        return self.bot.get_log_url(self.model.key)

    async def send_initial_staff_message(self) -> None:
        """Send the opening info embed(s) to the ticket channel, one per recipient."""
        channel = await self.get_channel()
        embed_proxies: list[tuple[Any, EmbedProxy]] = []  # list of tuples (sort-key, embed)

        members_mapping: defaultdict[int, list[discord.Member]] = defaultdict(list)

        # TODO: Implement recipients limit (set to 10)
        # Fetch the recipients as guild members, since members are not cached.
        if not self.bot.is_ws_ratelimited():
            for guild in self.bot.guilds:
                for member in await guild.query_members(
                    limit=len(self.recipients),
                    user_ids=[recipient.id for recipient in self.recipients],
                    cache=False,
                ):
                    members_mapping[member.id].append(member)
        else:
            for guild in self.bot.guilds:
                for recipient in self.recipients:
                    try:
                        member = await guild.fetch_member(recipient.id)
                    except discord.NotFound:
                        pass
                    except discord.HTTPException as e:
                        logger.warning(
                            "Something went wrong when querying member %s %s %s", recipient, channel.guild, e
                        )
                    else:
                        members_mapping[recipient.id].append(member)

        for recipient in self.recipients:
            embed = EmbedProxy()
            embed.set_author(name=str(recipient), icon_url=str(recipient.avatar), url=self.log_url)
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

            past_tickets_count = await self.bot.database_client.get_all_tickets_by_recipient(
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
        embeds = [embed.to_embed(self.bot.translator, CONFIG.default_locale) for _x, embed in embed_proxies]

        # Set the timestamp for the first embed
        embeds[0].timestamp = datetime.datetime.now(datetime.UTC)
        await channel.send(embeds=embeds)

    def format_ticket_channel_embed(
        self,
        original_message: discord.Message | tuple[Context, str],
        message_type: TicketMessageType,
    ) -> EmbedProxy:
        """Build an [`EmbedProxy`][] for the staff ticket channel.

        Args:
            original_message: A raw [`discord.Message`][] (for DMs) or a `(ctx, content)` tuple
                (for command-originated replies, where `ctx.message.content` may be empty).
            message_type: Controls embed color and footer.

        Returns:
            An [`EmbedProxy`][] ready to render and send.
        """
        # TODO: format close embed: TicketMessageType = close, sclose

        if isinstance(original_message, tuple):
            ctx, content = original_message
            author = ctx.author
            created_at = ctx.message.created_at  # TODO: Is this correct?
            message_id = ctx.message.id
        else:
            author = original_message.author
            content = original_message.content
            created_at = original_message.created_at
            message_id = original_message.id

        embed = EmbedProxy()
        author_url = f"https://discordapp.com/users/{author.id}"
        embed.set_author(name=str(author), icon_url=str(author.avatar), url=author_url)
        embed.description = content
        embed.timestamp = created_at

        if message_type == TicketMessageType.dm:
            embed.color = discord.Color.blue()
            embed.set_footer(text=_("ftl-msg-ticket-channel-embed-footer", message_id=str(message_id)))
        elif message_type == TicketMessageType.reply:
            embed.color = discord.Color.green()
            # TODO
        return embed

    def format_dm_channel_embed(
        self,
        original_message: discord.Message | tuple[Context, str],
        message_type: TicketMessageType,
    ) -> EmbedProxy:
        """Build an [`EmbedProxy`][] for the recipient's DM channel.

        Args:
            original_message: A raw [`discord.Message`][] or a `(ctx, content)` tuple.
            message_type: Controls embed color.

        Returns:
            An [`EmbedProxy`][] ready to render and send.
        """
        # TODO: format close embed: TicketMessageType = close

        if isinstance(original_message, tuple):
            ctx, content = original_message
            author = ctx.author
            created_at = ctx.message.created_at
        else:
            author = original_message.author
            content = original_message.content
            created_at = original_message.created_at

        embed = EmbedProxy()
        embed.set_author(name=str(author), icon_url=str(author.avatar))
        embed.description = content
        embed.timestamp = created_at

        if message_type == TicketMessageType.dm:
            embed.color = discord.Color.orange()
        elif message_type == TicketMessageType.reply:
            embed.color = discord.Color.green()
            # TODO
        return embed

    async def process_dm_message(self, message: discord.Message) -> list[discord.User | discord.Member]:
        """Relay an incoming DM to the ticket channel and to all other recipients.

        Args:
            message: The DM message received from a recipient.

        Returns:
            Recipients whose DM delivery failed (empty list on full success).
        """
        logger.debug("Processing DM message from %s: %s", message.author, message.content)
        channel = await self.get_channel()
        embed_proxy = self.format_ticket_channel_embed(message, TicketMessageType.dm)
        embed = embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
        coros: list[Awaitable[Any]] = [channel.send(embed=embed)]

        # Send the message to all other recipients in the ticket
        other_recipients = [recipient for recipient in self.recipients if recipient != message.author]
        if other_recipients:
            embed_proxy = self.format_dm_channel_embed(message, TicketMessageType.dm)
            embed = embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
            coros.extend([recipient.send(embed=embed) for recipient in other_recipients])

        sent_messages = await asyncio.gather(*coros, return_exceptions=True)
        ticket_channel_message = sent_messages[0]
        if not isinstance(ticket_channel_message, discord.Message):
            logger.warning("Failed to send message to ticket channel: %s", ticket_channel_message)
            raise ticket_channel_message

        # The received DM message is the first message in the list
        dm_channel_messages: list[TicketDMMessageModel] = [
            TicketDMMessageModel(
                message_id=message.id,
                ticket_message_id=ticket_channel_message.id,
                recipient=TicketUserModel.from_user(message.author),
            )
        ]
        failed_recipients: list[discord.User | discord.Member] = []

        for i, sent_message in enumerate(sent_messages[1:]):
            recipient = other_recipients[i]
            if isinstance(sent_message, discord.Message):
                dm_channel_messages.append(
                    TicketDMMessageModel(
                        message_id=sent_message.id,
                        ticket_message_id=ticket_channel_message.id,
                        recipient=TicketUserModel.from_user(recipient),
                    )
                )
            else:
                logger.error("Failed to send DM message to %s: %s", recipient, sent_message)
                failed_recipients.append(recipient)

        ticket_message_model = TicketMessageModel(
            bot_id=self.model.bot_id,
            ticket_key=self.model.key,
            message_id=ticket_channel_message.id,
            dm_messages=dm_channel_messages,
            author=TicketUserModel.from_user(message.author),
            content=message.content,
            created_at=message.created_at,
            type=TicketMessageType.dm,
        )
        task = asyncio.create_task(self.bot.database_client.save_message(ticket_message_model))
        self.bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(
            lambda t: (
                self.bot.asyncio_pending_tasks.discard(t),
                (
                    logger.warning("Error saving message for ticket %s", self.model.key, exc_info=t.exception())
                    if t.exception()
                    else None
                ),
            )
        )
        return failed_recipients

    async def process_reply_message(
        self, ctx: Context, message: str, message_type: TicketMessageType = TicketMessageType.reply
    ) -> list[discord.User | discord.Member]:
        """Relay a staff reply, close, or note to the ticket channel and recipients' DMs when applicable.

        `message` is the actual content; `ctx.message.content` is not used because it may be empty
        (e.g., when content was passed via a modal). `ctx.author` and `ctx.message.created_at` are
        still valid and used for embed metadata.

        Args:
            ctx: The command context for author and timestamp metadata.
            message: Text to send.
            message_type: Controls which channels receive the message and embed styling.

        Returns:
            Recipients whose DM delivery failed (empty list on full success).
        """
        logger.debug("Processing %s message in ticket %s: %s", message_type, self.model.key, message)
        channel = await self.get_channel()
        embed_proxy = self.format_ticket_channel_embed((ctx, message), message_type)
        embed = embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)

        coros: list[Awaitable[Any]] = [channel.send(embed=embed)]

        # Send the message to all recipients in the ticket
        if message_type in {TicketMessageType.reply, TicketMessageType.close}:
            embed_proxy = self.format_dm_channel_embed((ctx, message), message_type)
            embed = embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
            coros.extend([recipient.send(embed=embed) for recipient in self.recipients])

        sent_messages = await asyncio.gather(*coros, return_exceptions=True)

        ticket_channel_message = sent_messages[0]
        if not isinstance(ticket_channel_message, discord.Message):
            logger.error("Failed to send %s message to ticket channel: %s", message_type, ticket_channel_message)
            raise ticket_channel_message

        dm_channel_messages: list[TicketDMMessageModel] = []
        failed_recipients: list[discord.User | discord.Member] = []

        for i, sent_message in enumerate(sent_messages[1:]):
            recipient = self.recipients[i]
            if isinstance(sent_message, discord.Message):
                dm_channel_messages.append(
                    TicketDMMessageModel(
                        message_id=sent_message.id,
                        ticket_message_id=ticket_channel_message.id,
                        recipient=TicketUserModel.from_user(recipient),
                    )
                )
            else:
                logger.error("Failed to send %s DM message to %s: %s", message_type, recipient, sent_message)
                failed_recipients.append(recipient)

        ticket_message_model = TicketMessageModel(
            bot_id=self.model.bot_id,
            ticket_key=self.model.key,
            message_id=ticket_channel_message.id,
            dm_messages=dm_channel_messages,
            author=TicketUserModel.from_user(ctx.author),
            content=message,
            created_at=ctx.message.created_at,
            type=message_type,
        )
        task = asyncio.create_task(self.bot.database_client.save_message(ticket_message_model))
        self.bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(
            lambda t: (
                self.bot.asyncio_pending_tasks.discard(t),
                (
                    logger.error(
                        "Error saving %s message for ticket %s",
                        message_type,
                        self.model.key,
                        exc_info=t.exception(),
                    )
                    if t.exception()
                    else None
                ),
            )
        )
        return failed_recipients
