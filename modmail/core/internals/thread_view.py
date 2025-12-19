"""ThreadView class for managing thread interactions.

This class handles the creation and management of threads, including sending
messages to the thread channel and processing incoming messages.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections import defaultdict
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from modmail.backends.common import ThreadDMMessageModel, ThreadMessageModel, ThreadModel, ThreadUserModel

from ... import CONFIG
from ...enum import ThreadMessageType, ThreadStatus
from ...errors import BadPermissionsError, NoStaffGuildError, NoThreadChannelError
from ..translator import _
from .embed import EmbedProxy

if TYPE_CHECKING:
    from ..bot import Bot
    from .staff_guild import StaffGuild

__all__ = ["ThreadView"]

logger = logging.getLogger(__name__)


class ThreadView:
    """ThreadView class for managing thread interactions.

    This class handles the creation and management of threads, including sending
    messages to the thread channel and processing incoming messages.

    Attributes:
        staff_guild: The StaffGuild instance associated with the thread.
        model: The ThreadModel instance representing the thread.
        recipients: A list of recipients associated with the thread.
    """

    def __init__(
        self, staff_guild: StaffGuild, thread_model: ThreadModel, recipients: list[discord.User | discord.Member]
    ) -> None:
        """Initialize the ThreadView.

        Args:
            staff_guild: The StaffGuild instance associated with the thread.
            thread_model: The ThreadModel instance representing the thread.
            recipients: A list of recipients associated with the thread.
        """
        self.bot = staff_guild.bot
        self.staff_guild = staff_guild
        self.model = thread_model
        self.recipients = recipients

    @property
    def channel(self) -> discord.TextChannel:
        """Get the channel associated with the thread.

        Returns:
            The channel associated with the thread, or None if the channel does not exist.

        Raises:
            NoStaffGuildError: If the staff guild is not set.
            NoThreadChannelError: If the channel is not found in the staff guild.
            BadPermissionsError: If the bot does not have the required permissions to access the channel.
        """
        try:
            channel = discord.utils.get(self.staff_guild.guild.text_channels, id=self.model.channel_id)
        except NoStaffGuildError:
            logger.debug("Staff guild not set, cannot get channel.")
            raise
        if channel is None:
            raise NoThreadChannelError("Thread channel not found.")

        perms = channel.permissions_for(channel.guild.me)
        if perms & self.staff_guild.MIN_PERMISSIONS != self.staff_guild.MIN_PERMISSIONS:
            raise BadPermissionsError("Bot does not have the required permissions to access the channel.")
        return channel

    # def dm_channel(self) -> discord.DMChannel | None:
    #     """Get the DM channel associated with the thread.
    #
    #     Returns:
    #         The DM channel associated with the thread, or None if the DM channel does not exist.
    #     """
    #     try:
    #         return self.staff_guild.bot(self.model.created_by.user_id).dm_channel
    #     except NoStaffGuildError:
    #         logger.debug("Staff guild not set, cannot get DM channel.")
    #         raise

    @staticmethod
    def _get_log_url(key: str) -> str:
        """Get a formatted log URL for the thread.

        Args:
            key: The key of the thread.

        Returns:
            The formatted log URL.
        """
        return f"{CONFIG.log_url}/{key}"

    async def send_initial_staff_message(self) -> None:
        """Send the initial message to the thread chanel."""
        channel = self.channel  # This checks for permissions and validity
        log_url = self._get_log_url(self.model.key)
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
            embed.set_author(name=str(recipient), icon_url=str(recipient.avatar), url=log_url)
            embed.description = _(
                "ftl-msg-new-thread-initial-embed-description",
                created=discord.utils.format_dt(recipient.created_at, "R"),
            )
            embed.set_footer(text=_("ftl-msg-new-thread-initial-embed-footer", user_id=str(recipient.id)))

            members = members_mapping.get(recipient.id, [])
            members.sort(key=lambda m: m.guild.name)  # Sort by guild name
            # TODO: check fields limit
            for member in members:
                roles = [role.mention for role in member.roles if not role.is_default()]
                roles_str = ", ".join(roles) if roles else ""
                if member.joined_at:
                    joined_time = discord.utils.format_dt(member.joined_at, "R")
                else:
                    joined_time = _("ftl-msg-new-thread-initial-embed-guild-field-value-no-join-date")
                embed.add_field(
                    name=member.guild.name,
                    value=_(
                        "ftl-msg-new-thread-initial-embed-guild-field-value",
                        joined=joined_time,
                        roles=roles_str,
                        has_role=str(bool(roles)).lower(),
                    ),
                    inline=False,
                )

            past_threads_count = await self.bot.database_client.get_all_threads_by_recipient(
                recipient.id,
                count=True,
                only_closed=True,
            )
            embed.add_field(
                name=_("ftl-msg-new-thread-initial-embed-past-threads-field-name"),
                value=_("ftl-msg-new-thread-initial-embed-past-threads-field-value", count=past_threads_count),
                inline=False,
            )
            embed_proxies.append((recipient.name, embed))

        embed_proxies.sort(key=lambda x: x[0])  # Sort by recipient name
        embeds = await asyncio.gather(*[
            embed.to_embed(self.bot.translator, CONFIG.default_locale) for _x, embed in embed_proxies
        ])

        # Set the timestamp for the first embed
        embeds[0].timestamp = datetime.datetime.now(datetime.UTC)
        await channel.send(embeds=embeds)

    def format_thread_channel_embed(
        self,
        original_message: discord.Message | tuple[commands.Context[Bot], str],
        message_type: ThreadMessageType,
    ) -> EmbedProxy:
        """Format the embed for the given message that is sent to the thread channel.

        If the message is invoked within a command, the context and the message are passed as a tuple.

        Args:
            original_message: The original message to format.
            message_type: The type of the message (e.g., ThreadMessageType.dm).

        Returns:
            The formatted embed proxy.
        """
        # TODO: format close embed: ThreadMessageType = close, sclose

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

        if message_type == ThreadMessageType.dm:
            embed.colour = discord.Color.blue()
            embed.set_footer(text=_("ftl-msg-thread-channel-embed-footer", message_id=str(message_id)))
        elif message_type == ThreadMessageType.reply:
            embed.colour = discord.Color.green()
            # TODO
        return embed

    def format_dm_channel_embed(
        self,
        original_message: discord.Message | tuple[commands.Context[Bot], str],
        message_type: ThreadMessageType,
    ) -> EmbedProxy:
        """Format the thread embed for the given message that is sent to the DM channel.

        If the message is invoked within a command, the context and the message are passed as a tuple.

        Args:
            original_message: The original message to format.
            message_type: The type of the message (e.g., ThreadMessageType.dm).

        Returns:
            The formatted embed proxy.
        """
        # TODO: format close embed: ThreadMessageType = close

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

        if message_type == ThreadMessageType.dm:
            embed.colour = discord.Color.orange()
        elif message_type == ThreadMessageType.reply:
            embed.colour = discord.Color.green()
            # TODO
        return embed

    async def process_dm_message(self, message: discord.Message) -> list[discord.User | discord.Member]:
        """Process a DM message and send it to the thread channel.

        Args:
            message: The DM message to process.

        Returns:
            A list of recipients to whom the DM message failed to send.
        """
        logger.debug("Processing DM message from %s: %s", message.author, message.content)
        channel = self.channel  # This checks for permissions and validity
        embed_proxy = self.format_thread_channel_embed(message, ThreadMessageType.dm)
        embed = await embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
        coros: list[Awaitable[Any]] = [channel.send(embed=embed)]

        # Send the message to all other recipients in the thread
        other_recipients = [recipient for recipient in self.recipients if recipient != message.author]
        if other_recipients:
            embed_proxy = self.format_dm_channel_embed(message, ThreadMessageType.dm)
            embed = await embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
            coros.extend([recipient.send(embed=embed) for recipient in other_recipients])

        sent_messages = await asyncio.gather(*coros, return_exceptions=True)
        thread_channel_message = sent_messages[0]
        if not isinstance(thread_channel_message, discord.Message):
            logger.warning("Failed to send message to thread channel: %s", thread_channel_message)
            raise thread_channel_message

        # The received DM message is the first message in the list
        dm_channel_messages: list[ThreadDMMessageModel] = [
            ThreadDMMessageModel(
                message_id=message.id,
                thread_message_id=thread_channel_message.id,
                recipient=ThreadUserModel.from_user(message.author),
            )
        ]
        failed_recipients: list[discord.User | discord.Member] = []

        for i, sent_message in enumerate(sent_messages[1:]):
            recipient = other_recipients[i]
            if isinstance(sent_message, discord.Message):
                dm_channel_messages.append(
                    ThreadDMMessageModel(
                        message_id=sent_message.id,
                        thread_message_id=thread_channel_message.id,
                        recipient=ThreadUserModel.from_user(recipient),
                    )
                )
            else:
                logger.error("Failed to send DM message to %s: %s", recipient, sent_message)
                failed_recipients.append(recipient)

        thread_message_model = ThreadMessageModel(
            bot_id=self.model.bot_id,
            thread_key=self.model.key,
            message_id=thread_channel_message.id,
            dm_messages=dm_channel_messages,
            author=ThreadUserModel.from_user(message.author),
            content=message.content,
            created_at=message.created_at,
            type=ThreadMessageType.dm,
        )
        task = asyncio.create_task(self.bot.database_client.save_message(thread_message_model))
        task.add_done_callback(
            lambda t: (
                logger.warning("Error saving message for thread %s", self.model.key, exc_info=t.exception())
                if t.exception()
                else None
            )
        )
        return failed_recipients

    async def process_reply_message(
        self, ctx: commands.Context[Bot], message: str, message_type: ThreadMessageType = ThreadMessageType.reply
    ) -> list[discord.User | discord.Member]:
        """Process a reply, close, or note message and send it to the DM channel if applicable.

        This method uses message as the content of the reply message.
        Although ctx.message.content may be empty, ctx.message is still used to get the author and
        created_at attributes, which should always be valid.

        Args:
            ctx: The command context containing information about the invocation.
            message: The message to send as a reply.
            message_type: The type of the message (e.g., reply, close, etc.).

        Returns:
            A list of recipients to whom the reply message failed to send.
        """
        logger.debug("Processing %s message in thread %s: %s", message_type, self.model.key, message)
        channel = self.channel  # This checks for permissions and validity
        embed_proxy = self.format_thread_channel_embed((ctx, message), message_type)
        embed = await embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)

        coros: list[Awaitable[Any]] = [channel.send(embed=embed)]

        # Send the message to all recipients in the thread
        if message_type in {ThreadMessageType.reply, ThreadMessageType.close}:
            embed_proxy = self.format_dm_channel_embed((ctx, message), message_type)
            embed = await embed_proxy.to_embed(self.bot.translator, CONFIG.default_locale)
            coros.extend([recipient.send(embed=embed) for recipient in self.recipients])

        sent_messages = await asyncio.gather(*coros, return_exceptions=True)

        thread_channel_message = sent_messages[0]
        if not isinstance(thread_channel_message, discord.Message):
            logger.error("Failed to send %s message to thread channel: %s", message_type, thread_channel_message)
            raise thread_channel_message

        dm_channel_messages: list[ThreadDMMessageModel] = []
        failed_recipients: list[discord.User | discord.Member] = []

        for i, sent_message in enumerate(sent_messages[1:]):
            recipient = self.recipients[i]
            if isinstance(sent_message, discord.Message):
                dm_channel_messages.append(
                    ThreadDMMessageModel(
                        message_id=sent_message.id,
                        thread_message_id=thread_channel_message.id,
                        recipient=ThreadUserModel.from_user(recipient),
                    )
                )
            else:
                logger.error("Failed to send %s DM message to %s: %s", message_type, recipient, sent_message)
                failed_recipients.append(recipient)

        thread_message_model = ThreadMessageModel(
            bot_id=self.model.bot_id,
            thread_key=self.model.key,
            message_id=thread_channel_message.id,
            dm_messages=dm_channel_messages,
            author=ThreadUserModel.from_user(ctx.author),
            content=message,
            created_at=ctx.message.created_at,
            type=message_type,
        )
        task = asyncio.create_task(self.bot.database_client.save_message(thread_message_model))
        task.add_done_callback(
            lambda t: (
                logger.error(
                    "Error saving %s message for thread %s", message_type, self.model.key, exc_info=t.exception()
                )
                if t.exception()
                else None
            )
        )
        return failed_recipients

    async def close(self, closer: discord.User | discord.Member, thread_status: ThreadStatus) -> None:
        """Close the thread and perform any necessary cleanup.

        Args:
            closer: The user who is closing the thread.
            thread_status: The status of the thread after closing (by command, by deletion).

        Raises:
            ValueError: If an invalid thread status is provided for closing.
        """
        logger.debug("Closing thread %s: %s", self.model.key, thread_status)

        if thread_status not in {
            ThreadStatus.closed_by_command,
            ThreadStatus.closed_by_deletion,
        }:
            raise ValueError("Invalid thread status for closing.")

        closer_model = ThreadUserModel.from_user(closer)
        await self.staff_guild.bot.database_client.close_thread(
            self.model.key, closer_model, thread_status=thread_status
        )

        # TODO: config
        # await self.channel.delete(reason=_("ftl-msg-thread-closed-reason", user=closer.name))
        logger.info("Closed thread %s for %s.", self.model.key, self.model.recipients)
