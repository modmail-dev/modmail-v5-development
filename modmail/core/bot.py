"""
modmail.core.bot
================
This module contains the main Bot class for the Modmail bot, responsible for handling events and loading cogs.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, NoReturn

import discord
from discord.ext import commands

from .. import CONFIG, __version__
from ..backends import Activity, DBClientBase
from ..enum import (
    ActivityType,
    RequiredAccessLevel,
    StatusType,
)
from ..errors import DatabaseError
from .translator import Translator

logger = logging.getLogger(__name__)

__all__ = ["Bot"]


class Bot(commands.Bot):
    """
    The main class for the bot.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:

        if CONFIG.bot.prefix is not None:  # Prefix is enabled
            intents = discord.Intents(
                guilds=True, messages=True, reactions=True, typing=True, message_content=True, expressions=True
            )
            command_prefix: list[str] = [CONFIG.bot.prefix]
            if CONFIG.bot.respond_bot_mention:
                command_prefix += [f"<@!{CONFIG.bot.bot_id}> ", f"<@{CONFIG.bot.bot_id}> "]
        else:
            intents = discord.Intents(guilds=True, dm_messages=True, reactions=True, typing=True, expressions=True)
            command_prefix = []

        # Set owner IDs, if any, otherwise discord.py will fetch the owner IDs from Discord.
        if CONFIG.bot.owner_ids:
            kwargs.setdefault("owner_ids", CONFIG.bot.owner_ids)

        kwargs.setdefault("command_prefix", command_prefix)
        kwargs.setdefault("intents", intents)
        kwargs.setdefault("case_insensitive", True)
        kwargs.setdefault("strip_after_prefix", True)
        kwargs.setdefault("max_messages", None)  # Disable message cache
        kwargs.setdefault("member_cache_flags", discord.MemberCacheFlags.none())  # Disable member cache
        kwargs.setdefault("chunk_guilds_at_startup", False)  # Don't load guilds at startup

        # Set ratelimit timeout to 60s to prevent stalled commands.
        kwargs.setdefault("max_ratelimit_timeout", 60.0)

        # Disallow all mentions by default.
        allowed_mention = discord.AllowedMentions.none()
        kwargs.setdefault("allowed_mentions", allowed_mention)

        # Disable "voice will NOT be supported" warning.
        discord.VoiceClient.warn_nacl = False

        super().__init__(*args, **kwargs)

        self.translator = Translator()

        self.version: str = __version__
        logger.debug("[bold green]Bot version: %s", self.version, extra={"markup": True, "highlighter": None})

        if CONFIG.database_type == "sql":
            from ..backends.sql import SQLClient

            self.database_client: DBClientBase = SQLClient(CONFIG)

        elif CONFIG.database_type == "mongodb":
            from ..backends.mongodb import MongoDBClient

            self.database_client: DBClientBase = MongoDBClient(CONFIG)

        self.add_check(self._global_check)

    async def setup_hook(self) -> None:
        """
        This is called on bot login.

        Syncs the bot command tree when the bot is updated.
        """
        app_info = self.application
        if app_info is None:
            app_info = await self.application_info()

        # Modmail should not be public, this is a safety check.
        if app_info.bot_public:
            if CONFIG.bot.bypass_public_bot_check:
                logger.warning(
                    "[yellow]You have enabled bypass_public_bot_check. This is highly not recommended. "
                    'Make sure to turn off "Public Bot" in the Discord Developer Portal.',
                    extra={"markup": True},
                )
            else:
                logger.critical(
                    '[bold red]Turn off "Public Bot" in the Discord Developer Portal.', extra={"markup": True}
                )
                await self.close()
                return

        # Set the translator for the command tree. Should be done before syncing.
        await self.tree.set_translator(self.translator)

        if CONFIG.bot.force_sync_commands:
            if CONFIG.bot.use_slash_commands:
                logger.info("Force syncing slash commands.")
                logger.warning(
                    "[red]You should turn off force_sync_commands, or else your bot will be rate-limited.",
                    extra={"markup": True},
                )
                await self._sync_slash_commands()
            else:
                logger.info("Force un-syncing slash commands.")
                logger.warning(
                    "[red]You should turn off force_sync_commands, or else your bot will be rate-limited.",
                    extra={"markup": True},
                )
                await self._unsync_slash_commands()

        else:
            if CONFIG.bot.use_slash_commands:
                # Sync slash commands if last synced in a different version.
                if self.database_client.settings_model.slash_last_synced_version != self.version:
                    await self._sync_slash_commands()
            else:
                # Un-sync slash commands if last synced is not None (it's un-synced when None).
                if self.database_client.settings_model.slash_last_synced_version is not None:
                    await self._unsync_slash_commands()

        # Update the last ran version in the database.
        last_ran_version = self.database_client.settings_model.last_ran_version
        if last_ran_version != self.version:
            await self.database_client.update_settings(last_ran_version=self.version)
            logger.debug("Updated last ran version to %s", self.version)

    async def _sync_slash_commands(self) -> None:
        """
        Sync the slash commands.
        """
        logger.debug("Syncing slash commands.")
        await self.tree.sync()
        logger.debug("Slash commands synced.")
        await self.database_client.update_settings(slash_last_synced_version=self.version)

    async def _unsync_slash_commands(self) -> None:
        """
        Unsync the slash commands.
        """
        logger.debug("Un-syncing slash commands.")
        self.tree.clear_commands(guild=None)
        logger.debug("Slash commands un-synced.")
        await self.tree.sync()
        await self.database_client.update_settings(slash_last_synced_version=None)

    def run(self, *args: Any, **kwargs: Any) -> NoReturn:
        """
        Disable the default `run` method.
        You should use `run_bot` instead.
        """
        raise NotImplementedError("Use `run_bot` instead.")

    def run_bot(self) -> NoReturn:
        """
        Runs the bot and terminates the script.
        """

        async def bot_runner() -> None:
            await self.database_client.connect()

            for ext in ["utility"]:
                logger.debug("Loading extension %s", ext)
                await self.load_extension(f".cogs.{ext}", package="modmail")
            if CONFIG.bot.enable_jishaku:
                logger.warning("[red]Loading extension jishaku (this may be unsafe)", extra={"markup": True})
                await self.load_extension("jishaku")

            async with self:
                logger.info("[bold green]Modmail is starting.", extra={"markup": True})
                try:
                    await self.start(CONFIG.bot.token.get_secret_value(), reconnect=True)
                finally:
                    await self.database_client.disconnect()

        try:
            try:
                # noinspection PyUnresolvedReferences
                import uvloop

                # Start the bot with uvloop if available.
                with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
                    runner.run(bot_runner())
            except ImportError as e:
                # uvloop is not available on Windows
                if e.name == "uvloop" and sys.platform != "win32":
                    logger.warning("uvloop not installed, consider installing with the -G speed option.")
                    # Start the bot with the default asyncio loop.
                    asyncio.run(bot_runner())
                else:
                    raise  # re-raise the exception if it's not about uvloop
        except KeyboardInterrupt:
            logger.debug("Keyboard interrupt.")
            logger.info("[yellow]Shutting down Modmail.", extra={"markup": True})
        except DatabaseError:
            logger.critical("[bold red]Failed to connect to the database.", extra={"markup": True})
            sys.exit(1)
        except discord.PrivilegedIntentsRequired:
            logger.debug("Login failure.", exc_info=True)
            logger.critical(
                "Prefixed commands require the message content privileged intent. "
                "Please enable it in the developer portal: https://discord.com/developers/applications/."
            )
            sys.exit(1)
        except discord.errors.LoginFailure:
            logger.debug("Login failure.", exc_info=True)
            logger.critical("Failed to login to Discord. Check your token.")
            sys.exit(1)
        except Exception as e:
            logger.debug("An unknown error occurred.", exc_info=True)
            logger.critical("An unknown error occurred: %s", e)
            sys.exit(1)
        sys.exit(0)

    # noinspection PyMethodMayBeStatic
    async def on_ready(self) -> None:
        """
        This is called when the bot is ready.
        """
        logger.info("[bold green]Bot is ready.", extra={"markup": True})

    async def on_connect(self) -> None:
        """
        This is called when the bot connects to Discord.
        """
        logger.debug("Connected to Discord.")
        await self.set_bot_presence()

    def _get_discord_presence_from_settings(self) -> tuple[discord.BaseActivity | None, discord.Status | None]:
        """
        Get the discord presence from the database settings.
        :return: a tuple of discord.Activity and discord.Status, both may be None.
        """

        dc_activity: discord.BaseActivity | None = None
        dc_status: discord.Status | None = None

        # db_activity and db_status should be the same as activity and status if provided
        db_activity = self.database_client.settings_model.activity
        db_status = self.database_client.settings_model.status

        if db_activity:
            if db_activity.type == ActivityType.custom:
                dc_activity = discord.CustomActivity(name=db_activity.name)
            elif db_activity.type == ActivityType.streaming:
                stream_url = db_activity.url
                if stream_url is None:
                    logger.warning(
                        "Streaming activity requires a URL. Using default URL: https://www.twitch.tv/live."
                    )
                    stream_url = "https://www.twitch.tv/live"
                if not stream_url.startswith("https://www.twitch.tv/"):  # TODO: validate in the model
                    logger.warning("Streaming activity URL must start with https://www.twitch.tv/")
                    stream_url = "https://www.twitch.tv/live"
                dc_activity = discord.Streaming(name=db_activity.name, url=stream_url)
            else:
                dc_activity = discord.Activity(
                    name=db_activity.name, type=discord.ActivityType[db_activity.type.name]
                )

        if db_status:
            dc_status = discord.Status[db_status.name]

        return dc_activity, dc_status

    async def set_bot_presence(
        self, *, activity: Activity | None = None, status: StatusType | None = None
    ) -> None:
        """
        Set the bot's presence.

        If activity and/or status is provided, it will update the database settings.
        """
        await self.wait_until_ready()  # Wait until the bot is ready

        # Update the database settings
        if activity is not None:
            await self.database_client.update_settings(activity=activity)
        if status is not None:
            await self.database_client.update_settings(status=status)

        dc_activity, dc_status = self._get_discord_presence_from_settings()

        logger.debug("Setting bot presence to %r (%r)", dc_activity, dc_status)
        await self.change_presence(activity=dc_activity, status=dc_status)

    async def clear_bot_presence(self) -> None:
        """
        Clear the bot's presence.
        """
        logger.debug("Clearing bot presence.")
        await self.database_client.update_settings(activity=None, status=None)
        await self.set_bot_presence()

    @staticmethod
    def get_command_access_level(ctx: commands.Context[Bot]) -> RequiredAccessLevel:
        """
        Get the access level of the command.
        Returns "everyone" if no access level is set.

        :param ctx: The context of the command.
        :return: The access level of the command.
        """
        if ctx.command is None:  # When would this happen?
            logger.debug("The context command is None? %s", ctx)
            return RequiredAccessLevel.everyone

        default_access_level: RequiredAccessLevel | None = None

        # If the command is a subcommand, if so, add the parents of the command (in reverse order).
        commands_to_check = [ctx.command] + ctx.command.parents

        for command in commands_to_check:
            if default_access_level is None:
                # Check if the command has an access level set.
                if hasattr(ctx.command.callback, "__permission__"):
                    # See: modmail/core/permission.py
                    default_access_level = ctx.command.callback.__permission__  # type: ignore[reportFunctionMemberAccess]

            command_name: str = command.callback.__name__.casefold()
            if command_name.endswith("_command"):
                command_name = command_name[:-8]
            else:
                logger.debug("Command name does not end with _command: %s", command.qualified_name)

            # Check if the command has an override set in the config.
            for key, value in CONFIG.permission.overrides.items():
                if key.casefold() == command_name:
                    return value

        # If no access level is set, then everyone can use the command.
        return default_access_level if default_access_level is not None else RequiredAccessLevel.everyone

    def _global_check(self, ctx: commands.Context[Bot]) -> bool:
        """
        A global check that runs before every command.
        This can be used to enforce certain conditions globally.
        """
        #     Check if the bot can run the command.
        #     Verify the bot has the following permissions:
        #     - Send Messages
        #     - Embed Links
        #     - Attach Files
        #     - TODO: Add more permissions
        #     """
        #     return True
        return True
