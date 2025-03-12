"""
modmail.core.bot
================
This module contains the main Bot class for the Modmail bot, responsible for handling commands and events.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, TYPE_CHECKING, NoReturn

import discord
from discord.ext import commands

from .. import __version__, CONFIG
from ..errors import DatabaseError

if TYPE_CHECKING:
    from ..backends.abc import DBClientBase

# from .help import HelpCmd

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    """
    The main class for the bot.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:

        if CONFIG.bot.prefix is not None:  # Prefix is enabled
            intents = discord.Intents(
                guilds=True, messages=True, reactions=True, typing=True, message_content=True, expressions=True
            )
            command_prefix: list[str] | None = [CONFIG.bot.prefix]
            if CONFIG.bot.respond_bot_mention:
                command_prefix += [f"<@!{CONFIG.bot.bot_id}> ", f"<@{CONFIG.bot.bot_id}> "]
        else:
            intents = discord.Intents(guilds=True, dm_messages=True, reactions=True, typing=True, expressions=True)
            command_prefix = None

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

        super().__init__(*args, **kwargs)

        self.version: str = __version__
        logger.info("[bold green]Bot version:[/] %s", self.version, extra={"markup": True})

        if CONFIG.database_type == "mongodb":
            from ..backends.mongodb import MongoDBClient

            self._database_client: DBClientBase = MongoDBClient(CONFIG)

    async def setup_hook(self) -> None:
        """
        This is called on bot start.
        """
        ...

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
            await self._database_client.connect()
            async with self:
                logger.info("[green]Starting Modmail![/]", extra={"markup": True})
                try:
                    await self.start(CONFIG.bot.token, reconnect=True)
                finally:
                    await self._database_client.disconnect()

        try:
            try:
                # noinspection PyUnresolvedReferences
                import uvloop  # type: ignore[reportMissingImports]

                # Start the bot with uvloop if available.
                with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
                    runner.run(bot_runner())
            except ImportError:
                # uvloop is not available on Windows
                if sys.platform != "win32":
                    logger.warning("uvloop not installed, consider installing with the -G speed option.")
                # Start the bot with the default asyncio loop.
                asyncio.run(bot_runner())
        except KeyboardInterrupt:
            logger.debug("Keyboard interrupt.")
            logger.info("[yellow]Shutting down Modmail.[/]", extra={"markup": True})
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
