"""Core bot implementation for the Modmail system.

This module contains the main Bot class responsible for handling Discord events,
loading cogs, and managing the bot's functionality.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any, NoReturn

import discord
from discord.ext import commands
from packaging.version import Version

from .. import CONFIG, __version__, utils
from ..enum import ActivityType, PermissionOverrideValue, ProfileType, RequiredAccessLevel, StatusType
from ..errors import DatabaseError, NoStaffGuildError
from .internals import StaffGuild
from .translator import Translator, _

if TYPE_CHECKING:
    from ..backends.common import ActivityModel, DBClientBase, ProfileModel

logger = logging.getLogger(__name__)

__all__ = ["Bot"]


class Bot(commands.Bot):
    """Main bot class for handling Modmail functionality.

    This class extends discord.py's Bot class to provide Modmail-specific functionality
    including database integration, command permission handling, and presence management.

    Attributes:
        translator: Translator instance for handling translations.
        staff_guild: StaffGuild instance for managing staff server interactions.
        version: The version of the bot.
        database_client: Database client instance for interacting with the database.
    """

    # Set of pending asyncio tasks, used for tracking long-running operations.
    asyncio_pending_tasks: set[asyncio.Task[Any]] = set()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Modmail bot.

        Args:
            *args: Variable length argument list for commands.Bot.
            **kwargs: Arbitrary keyword arguments for commands.Bot.
        """
        self._exit_status = 0  # Used to set the exit code of the bot when it exits.

        intents = discord.Intents(
            guilds=True, messages=True, reactions=True, typing=True, message_content=True, expressions=True
        )

        if CONFIG.bot.prefix is not None:  # Prefix is enabled
            logger.info("Using prefix: %s", CONFIG.bot.prefix)
            command_prefix: list[str] = [CONFIG.bot.prefix]
            if CONFIG.bot.respond_bot_mention:
                command_prefix += [f"<@!{CONFIG.bot.bot_id}> ", f"<@{CONFIG.bot.bot_id}> "]
        else:
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
        # This is currently disabled due to discord.py poor rate limit handler logic.
        # kwargs.setdefault("max_ratelimit_timeout", 60.0)

        # Disallow all mentions by default.
        allowed_mention = discord.AllowedMentions.none()
        kwargs.setdefault("allowed_mentions", allowed_mention)

        # Disable "voice will NOT be supported" warning.
        discord.VoiceClient.warn_nacl = False

        super().__init__(*args, **kwargs)

        self.translator: Translator = Translator()
        self.staff_guild: StaffGuild = StaffGuild(self)

        self._bot_initialized_event = asyncio.Event()

        self.version: str = __version__
        logger.debug("[bold green]Bot version: %s", self.version, extra={"markup": True, "highlighter": None})

        if CONFIG.database_type == "sql":
            from ..backends.sql import SQLClient

            self.database_client: DBClientBase = SQLClient(CONFIG)

        elif CONFIG.database_type == "mongodb":
            from ..backends.mongodb import MongoDBClient

            self.database_client: DBClientBase = MongoDBClient(CONFIG)

        self.add_check(self._bot_can_run_check)
        self.add_check(self._permission_check)
        self.before_invoke(self.on_before_invoke)

    async def wait_until_ready(self) -> None:
        """Wait until the bot is ready and the database is connected."""
        await super().wait_until_ready()
        await self._bot_initialized_event.wait()

    async def setup_hook(self) -> None:
        """Initialize bot configuration and synchronize commands.

        This method is called automatically on bot login and handles:
        - Verification of bot publicity settings.
        - Command tree synchronization.
        - Database settings updates.
        - Locale configuration.
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

        if not CONFIG.bot.use_slash_commands:
            logger.info("Slash commands are disabled.")

        slash_synced = False

        if CONFIG.bot.force_sync_commands:
            slash_synced = True
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
                if self.database_client.settings_model.last_slash_synced_version != self.version:
                    slash_synced = True
                    await self._sync_slash_commands()
            else:
                # Un-sync slash commands if last synced is not None (it's un-synced when None).
                if self.database_client.settings_model.last_slash_synced_version is not None:
                    slash_synced = True
                    await self._unsync_slash_commands()

        # Update the last ran locale in the database.
        last_ran_locale = self.database_client.settings_model.last_ran_locale
        if last_ran_locale != CONFIG.default_locale:
            if last_ran_locale is not None:  # The locale was changed, need to resync the commands.
                logger.info("Locale changed from %s to %s", last_ran_locale, CONFIG.default_locale)
                if CONFIG.bot.use_slash_commands and not slash_synced:
                    slash_synced = True
                    await self._sync_slash_commands()

            await self.database_client.update_settings(last_ran_locale=CONFIG.default_locale)

        last_slash_minimum_permission_int = self.database_client.settings_model.last_slash_minimum_permission_int
        if last_slash_minimum_permission_int != CONFIG.permission.slash_minimum_permission_int:
            if last_slash_minimum_permission_int is not None:
                logger.info(
                    "Slash minimum permission changed from %s to %s",
                    last_slash_minimum_permission_int,
                    CONFIG.permission.slash_minimum_permission_int,
                )
                if CONFIG.bot.use_slash_commands and not slash_synced:
                    slash_synced = True
                    await self._sync_slash_commands()
            await self.database_client.update_settings(
                last_slash_minimum_permission_int=CONFIG.permission.slash_minimum_permission_int
            )

        # Update the last ran version in the database.
        last_ran_version = self.database_client.settings_model.last_ran_version
        if last_ran_version != self.version:
            await self.database_client.update_settings(last_ran_version=self.version)
            logger.debug("Updated last ran version to %s", self.version)

        self._bot_initialized_event.set()

    async def _sync_slash_commands(self) -> None:
        """Synchronize slash commands with Discord.

        Updates the slash command configuration on Discord servers and stores
        the sync version in the database.
        """
        logger.debug("Syncing slash commands (this may take a while).")
        await self.tree.sync()
        logger.debug("Slash commands synced.")
        await self.database_client.update_settings(last_slash_synced_version=self.version)

    async def _unsync_slash_commands(self) -> None:
        """Remove all slash commands from Discord.

        Clears all registered slash commands and updates the database to reflect
        the un-synced state.
        """
        logger.debug("Un-syncing slash commands (this may take a while).")
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        logger.debug("Slash commands un-synced.")
        await self.database_client.update_settings(last_slash_synced_version=None)

    def run(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Disabled method to prevent incorrect bot initialization.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            NotImplementedError: Always raised to direct users to use run_bot() instead.
        """
        raise NotImplementedError("Use `run_bot` instead.")

    def run_bot(self) -> NoReturn:
        """Start the bot and handle the main execution loop.

        Initializes database connection, loads extensions, and handles various
        startup scenarios and potential errors.

        Raises:
            SystemExit: With appropriate exit codes based on execution result.
        """  # noqa: DOC502
        self._exit_status = 0

        async def bot_runner() -> None:
            await self.database_client.connect()

            for ext in ["utility", "modmail"]:
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
            if not TYPE_CHECKING:
                try:
                    import uvloop
                except ImportError as e:
                    # uvloop is not available on Windows
                    if e.name == "uvloop" and sys.platform != "win32":
                        logger.warning("uvloop not installed, consider installing with the -G speed option.")
                    uvloop = asyncio  # Use the default asyncio loop.

                # Start the bot with uvloop.run or asyncio.run
                uvloop.run(bot_runner())
        except KeyboardInterrupt:
            logger.debug("Keyboard interrupt.")
            logger.info("[yellow]Shutting down Modmail.", extra={"markup": True})
        except DatabaseError:
            logger.critical("[bold red]Failed to connect to the database.", extra={"markup": True})
            self._exit_status = 1
        except discord.PrivilegedIntentsRequired:
            logger.debug("Login failure.", exc_info=True)
            logger.critical(
                "Prefixed commands require the message content privileged intent. "
                "Please enable it in the developer portal: https://discord.com/developers/applications/."
            )
            self._exit_status = 1
        except discord.errors.LoginFailure:
            logger.debug("Login failure.", exc_info=True)
            logger.critical("Failed to login to Discord. Check your token.")
            self._exit_status = 1
        except Exception as e:
            logger.debug("An unknown error occurred.", exc_info=True)
            logger.critical("An unknown error occurred: %s", e)
            self._exit_status = 1

        sys.exit(self._exit_status)  # Should be 0 if everything went well, 1 if there was an error.

    async def _not_in_guild_close(self) -> None:
        """Close the bot if it is not in the staff guild.

        This method is called when the bot is removed from the staff guild.
        """
        logger.critical(
            "[bold red]The bot was removed from the staff server. "
            "Please invite the bot back to the server and then restart the bot.",
            extra={"markup": True},
        )
        self._exit_status = 1
        await self.close()

    async def on_ready(self) -> None:
        """Handle bot ready event.

        Called when the bot has successfully connected to Discord and is ready to
        receive events.
        """
        await self.wait_until_ready()

        other_server_names = [
            f"{guild} ({guild.id})" for guild in self.guilds if guild.id != CONFIG.bot.staff_server_id
        ]

        # Check if the bot is in the staff server.
        if not self.staff_guild.exists:
            # TODO: Send the bot's invite link
            logger.critical(
                "[bold red]The bot is not in the staff server (%d). "
                "Please double check the ID, invite the bot to the server, and then restart the bot.",
                CONFIG.bot.staff_server_id,
                extra={"markup": True},
            )
            if other_server_names:  # If the bot is in other servers, show them.
                logger.critical(
                    "[bold red]The bot is currently these servers: %s",
                    ", ".join(other_server_names),
                    extra={"markup": True},
                )
            self._exit_status = 1
            await self.close()
            return

        logger.info("[bold green]Bot is ready.", extra={"markup": True})
        logger.info("Logged in as: %s", self.user)

        if other_server_names:
            logger.info("Staff server: %s", self.staff_guild)
            logger.info("Other servers: %s", ", ".join(other_server_names))
        else:
            logger.info("Server: %s", self.staff_guild)

        if Version(self.version).is_prerelease:
            logger.info(
                "[bold yellow]Running a development version. Please report any issues to the Modmail team.",
                extra={"markup": True},
            )

    async def on_connect(self) -> None:
        """Handle bot connect event.

        Called when the bot establishes a connection to Discord. Sets up initial
        presence configuration.
        """
        logger.debug("Connected to Discord.")
        await self.wait_until_ready()

        # Check if the staff guild still exists, in case the bot was removed from the server between connects.
        if not self.staff_guild.exists:
            await self._not_in_guild_close()
            return

        await self.set_bot_presence()

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handle guild removal event.

        Called when the bot is removed from a guild.
        Exit bot if the guild is the staff server.
        """
        logger.info("Removed from guild %s", guild.name)
        if guild.id == CONFIG.bot.staff_server_id:
            await self._not_in_guild_close()
            return

    def _get_discord_presence_from_settings(self) -> tuple[discord.BaseActivity | None, discord.Status | None]:
        """Generate Discord presence objects from database settings.

        Returns:
            A tuple containing the activity and status to display.
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
            # noinspection PyTypeChecker
            dc_status = discord.Status[db_status.name]

        return dc_activity, dc_status

    async def set_bot_presence(
        self, *, activity: ActivityModel | None = None, status: StatusType | None = None
    ) -> None:
        """Update the bot's Discord presence.

        If either argument is provided, the database settings will be updated before
        applying the new presence.

        Args:
            activity: Optional activity to set for the bot.
            status: Optional status to set for the bot.
        """
        await self.wait_until_ready()  # Wait until the bot is ready

        # Update the database settings
        if activity is not None and status is not None:
            await self.database_client.update_settings(activity=activity, status=status)
        elif activity is not None:
            await self.database_client.update_settings(activity=activity)
        elif status is not None:
            await self.database_client.update_settings(status=status)

        dc_activity, dc_status = self._get_discord_presence_from_settings()

        logger.debug("Setting bot presence to %r (%r)", dc_activity, dc_status)
        await self.change_presence(activity=dc_activity, status=dc_status)

    async def clear_bot_presence(self) -> None:
        """Remove the bot's current presence settings.

        Clears both activity and status from the database and Discord display.
        """
        logger.debug("Clearing bot presence.")
        await self.database_client.update_settings(activity=None, status=None)
        await self.set_bot_presence()

    async def on_command_error(self, context: commands.Context[Any], exception: commands.CommandError, /) -> None:
        """Handle command execution errors.

        Ignores CommandNotFound and CheckFailure errors, passes others to parent handler.

        Args:
            context: The context in which the command was executed.
            exception: The error that occurred during execution.
        """
        # Ignore command not found errors
        if isinstance(exception, commands.CommandNotFound):
            return

        # Ignore command check failure errors
        if isinstance(exception, commands.CheckFailure):
            if getattr(context, "_perm_check_reason", "").startswith("fail:"):  # The permission check failed
                # noinspection PyUnresolvedReferences
                logger.debug(
                    "%s is not allowed to run `%s` (%s)",
                    context.author,
                    context.command,
                    context._perm_check_reason,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                )
                if context.interaction is not None:  # tell the user they don't have permission
                    message = await self.translator.translate(
                        _("ftl-msg-permission-denied"), context.interaction.locale
                    )
                    await context.reply(message, ephemeral=True)
            return

        if isinstance(exception, commands.CommandInvokeError):
            if isinstance(exception.original, NoStaffGuildError):
                await self._not_in_guild_close()
                return

            logger.info(
                "[red]Command %s failed with an uncaught error: %s",
                context.command,
                exception.original,
                exc_info=exception,
                extra={"markup": True},
            )

            # Tell the user there was an error
            if context.interaction is not None:
                message = await self.translator.translate(
                    _("ftl-msg-command-invoke-error"), context.interaction.locale
                )
                await context.reply(message, ephemeral=True)
            else:
                permissions = context.channel.permissions_for(context.me)  # pyright: ignore [reportArgumentType]
                if permissions.read_messages and permissions.send_messages:
                    message = await self.translator.translate(
                        _("ftl-msg-command-invoke-error"), CONFIG.default_locale
                    )
                    await context.reply(message, ephemeral=True)
            return

        await super().on_command_error(context, exception)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        """Handle errors that occur during event processing.

        When NoStaffGuildError is raised, log a critical error and exit the bot.

        Args:
            event_method: The name of the event method where the error occurred.
            *args: Positional arguments passed to the event method.
            **kwargs: Keyword arguments passed to the event method.
        """
        exc_info = sys.exc_info()

        if isinstance(exc_info[1], NoStaffGuildError):
            await self._not_in_guild_close()
            return
        await super().on_error(event_method, *args, **kwargs)

    @staticmethod
    async def on_before_invoke(ctx: commands.Context[Bot]) -> None:
        """Perform pre-command execution logging.

        Logs command execution attempts with permission check results if available.

        Args:
            ctx: The context in which the command is being executed.
        """
        if hasattr(ctx, "_perm_check_reason"):  # This gets injected by the permission check
            # noinspection PyProtectedMember
            logger.debug(
                "%s is running `%s`, allowed reason (%s)",
                ctx.author,
                ctx.command,
                ctx._perm_check_reason,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            )
        else:
            logger.debug("User %s is running the %s command.", ctx.author, ctx.command)

    @staticmethod
    def get_command_access_level(base_command: commands.Command[Any, Any, Any]) -> RequiredAccessLevel:
        """Determine the required access level for a command.

        Args:
            base_command: The command to check.

        Returns:
            The access level required to use the command.
            Defaults to "everyone" if no access level is explicitly set.
        """
        default_access_level: RequiredAccessLevel | None = None

        # If the command is a subcommand, if so, add the parents of the command (in reverse order)
        # and check for most significant access level.
        commands_to_check = [base_command, *base_command.parents]

        # Check if the command has an override set in the config.
        for i, command in enumerate(commands_to_check):
            command_name = utils.get_command_name(command)

            # If the parent command has a wildcard override. e.g. "profile+" will match "profile add"
            override = CONFIG.permission.overrides.get(command_name + "+")

            if i == 0:  # Check for override on the exact command name
                override = CONFIG.permission.overrides.get(command_name, override)

            if override is not None:
                return override

            # Set the default access level if the command has an access level set.
            # Otherwise, propagate the access level lookup to the parent command.
            if default_access_level is None and hasattr(command.callback, "__permission__"):
                # See: modmail/core/permission.py
                default_access_level = command.callback.__permission__  # pyright: ignore [reportFunctionMemberAccess]

        # If no access level is set, then everyone can use the command.
        return default_access_level if default_access_level is not None else RequiredAccessLevel.everyone

    def get_all_user_profiles(self, user: discord.User | discord.Member) -> list[ProfileModel]:
        """Retrieve all applicable profiles for a user.

        Args:
            user: The Discord user or member to get profiles for.

        Returns:
            List of profiles ordered from most to least significant,
            including user profile and role profiles if applicable.
        """
        all_profiles: list[ProfileModel] = []  # All profiles to check for permission overrides

        user_profile = self.database_client.get_profile(user.id, ProfileType.user)
        if isinstance(user, discord.Member):  # Command invoked in a guild
            # Loops all roles from @everyone -> top role
            for role in user.roles:
                role_profile = self.database_client.get_profile(role.id, ProfileType.role)
                if role_profile is not None:
                    all_profiles.insert(0, role_profile)
        if user_profile is not None:
            all_profiles.insert(0, user_profile)
        return all_profiles

    async def _permission_check(self, ctx: commands.Context[Bot]) -> bool:
        """Verify if a user has permission to execute a command.

        Args:
            ctx: The context in which the command is being executed.

        Returns:
            True if the user has permission to execute the command, False otherwise.
        """
        if ctx.author.bot:  # Ignore commands invoked by bots
            ctx._perm_check_reason = "fail: bot"  # pyright: ignore [reportAttributeAccessIssue]
            return False

        if ctx.command is None:  # pragma: nocover ; When would this happen?
            logger.warning("The context command is None? %s", ctx)
            return True

        if await self.is_owner(ctx.author):
            ctx._perm_check_reason = "pass: owner"  # pyright: ignore [reportAttributeAccessIssue]
            return True

        all_profiles = self.get_all_user_profiles(ctx.author)
        command_access_level = self.get_command_access_level(ctx.command)

        # If the command is a subcommand, if so, add the parents of the command (in reverse order).
        commands_to_check = [ctx.command, *ctx.command.parents]

        for i, command in enumerate(commands_to_check):
            command_name = utils.get_command_name(command)

            for profile in all_profiles:
                if i == 0:  # Check for override on the exact command name
                    if profile.permission_overrides.get(command_name) == PermissionOverrideValue.deny:
                        ctx._perm_check_reason = f"fail: {profile.profile_id} deny {command_name}"  # pyright: ignore [reportAttributeAccessIssue]
                        return False
                    if profile.permission_overrides.get(command_name) == PermissionOverrideValue.allow:
                        ctx._perm_check_reason = f"pass: {profile.profile_id} allow {command_name}"  # pyright: ignore [reportAttributeAccessIssue]
                        return True
                elif command_access_level == RequiredAccessLevel.owner:
                    # Owner-only commands cannot be overridden by wildcard overrides on parent.
                    # However, when i=0, the wildcard override is checked on the exact command name.
                    break

                # Check for wildcard override (on parents). e.g. "profile+" will match "profile add"
                if profile.permission_overrides.get(command_name + "+") == PermissionOverrideValue.deny:
                    ctx._perm_check_reason = f"fail: {profile.profile_id} deny {command_name}+"  # pyright: ignore [reportAttributeAccessIssue]
                    return False

                if profile.permission_overrides.get(command_name + "+") == PermissionOverrideValue.allow:
                    ctx._perm_check_reason = f"pass: {profile.profile_id} allow {command_name}+"  # pyright: ignore [reportAttributeAccessIssue]
                    return True

        # Owner check
        if command_access_level == RequiredAccessLevel.owner:
            ctx._perm_check_reason = "fail: owner only"  # pyright: ignore [reportAttributeAccessIssue]
            return False

        if CONFIG.permission.default_access_everyone and command_access_level == RequiredAccessLevel.everyone:
            # If the command is set to everyone, allow it.
            ctx._perm_check_reason = "pass: everyone"  # pyright: ignore [reportAttributeAccessIssue]
            return True

        for profile in all_profiles:
            if profile.access_level is None:
                continue

            # Check if the user has the required access level for the command.
            if profile.access_level >= command_access_level:
                ctx._perm_check_reason = (  # pyright: ignore [reportAttributeAccessIssue]
                    f"pass: {profile.profile_id} level {profile.access_level} >= {command_access_level}"
                )
                return True

        ctx._perm_check_reason = f"fail: no access {command_access_level}"  # pyright: ignore [reportAttributeAccessIssue]
        return False

    async def _bot_can_run_check(self, ctx: commands.Context[Bot]) -> bool:
        """Verify if the bot has necessary permissions to execute a command.

        Args:
            ctx: The context in which the command is being run.

        Returns:
            True if the bot can run the command, False otherwise.
        """
        #     Check if the bot can run the command.
        #     Verify the bot has the following permissions:
        #     - Send Messages
        #     - Embed Links
        #     - Attach Files
        #     - TODO: Add more permissions
        #     """
        #     return True
        return True  # pragma: nocover ; TODO: Implement this check

    @staticmethod
    def get_log_url(key: str) -> str:
        """Get a formatted log URL for the ticket.

        Args:
            key: The key of the ticket.

        Returns:
            The formatted log URL.
        """
        return f"{CONFIG.log_url}/{key}"
