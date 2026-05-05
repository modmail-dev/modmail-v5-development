"""Main [`Bot`][] subclass with event handlers, permission checks, and message-sending utilities."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NoReturn, cast, overload

import discord
from discord.ext import commands
from packaging.version import Version

from .. import CONFIG, __version__
from ..backends import create_db_client
from ..enum import ActivityType, PermissionOverrideValue, ProfileType, RequiredAccessLevel, StatusType
from ..errors import (
    BadPermissionsError,
    DatabaseError,
    InstanceAlreadyRunningError,
    LocalizedBadArgumentError,
    NoStaffGuildError,
    UserAccessError,
)
from .context import Context
from .embed import EmbedProxy
from .permission import PermissionCommandIndex
from .staff_guild import StaffGuild
from .translator import Translator, _

if TYPE_CHECKING:
    from ..backends.common import ActivityModel, DBClient, ProfileModel

logger = logging.getLogger(__name__)

__all__ = ["Bot"]


class Bot(commands.Bot):
    """[`commands.Bot`][] subclass wiring together Modmail's database, permissions, and staff guild."""

    asyncio_pending_tasks: ClassVar[set[asyncio.Task[Any]]] = set()
    """Fire-and-forget tasks kept alive until they complete."""

    permission_command_index: PermissionCommandIndex
    """Locale-aware index of commands for permission override management, built at startup."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Configure intents, command prefix, presence defaults, and internal services."""
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
        discord.VoiceClient.warn_dave = False

        super().__init__(*args, **kwargs)

        self.translator: Translator = Translator()
        """Handles FTL-based localization."""
        self.staff_guild: StaffGuild = StaffGuild(self)
        """Manages the configured staff Discord server and ticket lifecycle."""

        self.version: str = __version__
        """Semver string for this Modmail instance."""
        logger.debug("[bold green]Bot version: %s", self.version, extra={"markup": True, "highlighter": None})

        self.database_client: DBClient = create_db_client(CONFIG)
        """Primary interface to the configured backend database."""

        self.add_check(self._bot_can_run_check)
        self.add_check(self._user_access_check)
        self.before_invoke(self.on_before_invoke)

    @staticmethod
    def get_log_url(key: str) -> str:
        """Build a log URL for the given ticket `key` using the configured `log_url` base.

        Args:
            key: Ticket key to append to the base log URL.

        Returns:
            Full URL string for the ticket log.
        """
        return f"{CONFIG.log_url}/{key}"

    async def setup_hook(self) -> None:
        """Run post-login initialization: public-bot check, slash sync, and override key index setup."""
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
                if self.database_client.settings.last_slash_synced_version != self.version:
                    slash_synced = True
                    await self._sync_slash_commands()
            else:
                # Un-sync slash commands if last synced is not None (it's un-synced when None).
                if self.database_client.settings.last_slash_synced_version is not None:
                    slash_synced = True
                    await self._unsync_slash_commands()

        # Update the last ran locale in the database.
        last_ran_locale = self.database_client.settings.last_ran_locale
        if last_ran_locale != CONFIG.default_locale:
            if last_ran_locale is not None:  # The locale was changed, need to resync the commands.
                logger.info("Locale changed from %s to %s", last_ran_locale, CONFIG.default_locale)
                if CONFIG.bot.use_slash_commands and not slash_synced:
                    slash_synced = True
                    await self._sync_slash_commands()

            await self.database_client.update_settings(last_ran_locale=CONFIG.default_locale)

        last_slash_minimum_permission_int = self.database_client.settings.last_slash_minimum_permission_int
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
        last_ran_version = self.database_client.settings.last_ran_version
        if last_ran_version != self.version:
            await self.database_client.update_settings(last_ran_version=self.version)
            logger.debug("Updated last ran version to %s", self.version)

        self.permission_command_index = PermissionCommandIndex.from_bot(self)
        self._resolve_config_permission_overrides()
        await self._apply_renamed_command_keys()

    async def _sync_slash_commands(self) -> None:
        """Sync the command tree with Discord and record the current version in the database."""
        logger.debug("Syncing slash commands (this may take a while).")
        await self.tree.sync()
        logger.debug("Slash commands synced.")
        await self.database_client.update_settings(last_slash_synced_version=self.version)

    async def _unsync_slash_commands(self) -> None:
        """Clear all registered slash commands from Discord and mark as un-synced in the database."""
        logger.debug("Un-syncing slash commands (this may take a while).")
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        logger.debug("Slash commands un-synced.")
        await self.database_client.update_settings(last_slash_synced_version=None)

    def _resolve_config_permission_overrides(self) -> None:
        """Resolve config override keys through the command index using the default locale.

        Runs after [`permission_command_index`][] is built. Each key in
        `CONFIG.permission.overrides` is resolved against the index so that both
        canonical names and the default-locale localized names are accepted in the YAML.
        Unrecognized keys are left in place with a warning logged.
        """
        index = self.permission_command_index(CONFIG.default_locale)
        overrides = CONFIG.permission.overrides
        new_overrides: dict[str, RequiredAccessLevel] = {}
        for key, value in overrides.items():
            resolved = index.resolve(key, allow_raw_key=True)
            if resolved is None:
                logger.warning("CONFIG permission override: ignoring unrecognized command %r", key)
                new_overrides[key] = value
            else:
                new_overrides[resolved] = value
        overrides.clear()
        overrides.update(new_overrides)

    async def _apply_renamed_command_keys(self) -> None:
        """Update stored permission overrides when command callback names have changed.

        Reads rename tables declared on each cog (via `renamed_command_keys`),
        then rewrites any matching keys in every profile's `permission_overrides` dict
        and persists the updated profiles to the database.
        """
        # TODO: Also rename the CONFIG.permission.overrides keys
        renames = {
            k: v
            for cog in self.cogs.values()
            for (k, v) in cast("list[tuple[str, str]]", getattr(type(cog), "renamed_command_keys", []))
        }

        if not renames:
            return

        for profile in self.database_client.profiles:
            new_overrides: dict[str, PermissionOverrideValue] = {}
            changed = False

            for key, value in profile.permission_overrides.items():
                base, suffix = (key.rstrip("+"), "+") if key.endswith("+") else (key, "")
                if new_base := renames.get(base):
                    logger.info(
                        "Profile %d: migrating override key %r → %r",
                        profile.profile_id,
                        key,
                        new_base + suffix,
                    )
                    new_overrides[new_base + suffix] = value
                    changed = True
                else:
                    new_overrides[key] = value

            if changed:
                await self.database_client.update_profile(
                    profile.model_copy(update={"permission_overrides": new_overrides})
                )

    def run(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Always raises; use [`run_bot`][] to start the bot.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("Use `run_bot` instead.")

    def run_bot(self) -> NoReturn:
        """Connect to the database, load extensions, start the bot, and exit with a status code.

        Raises:
            SystemExit: Exit code `0` on clean shutdown, `1` on any startup or runtime error.
        """
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
        except InstanceAlreadyRunningError as e:
            if e.hostname and e.pid:
                logger.critical(
                    "[bold red]Another instance of this bot is already running "
                    "(host: %s, PID: %d, started: %s). "
                    "Stop the other instance before starting a new one. "
                    "If it crashed, wait 30 seconds for the lock to expire automatically.",
                    e.hostname,
                    e.pid,
                    e.acquired_at,
                    extra={"markup": True},
                )
            else:
                logger.critical(
                    "[bold red]Another instance of this bot is already running. "
                    "Stop it before starting a new one.",
                    extra={"markup": True},
                )
            self._exit_status = 1
        except DatabaseError:
            logger.critical("[bold red]Failed to connect to the database.", extra={"markup": True}, exc_info=True)
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
        """Log a critical alert and close the bot when it is no longer in the staff guild."""
        logger.critical(
            "[bold red]The bot was removed from the staff server. "
            "Please invite the bot back to the server and then restart the bot.",
            extra={"markup": True},
        )
        self._exit_status = 1
        await self.close()

    async def on_ready(self) -> None:
        """Validate staff guild membership and log startup info once Discord reports ready."""
        await self.wait_until_ready()

        other_server_names = [
            f"{guild} ({guild.id})" for guild in self.guilds if guild.id != CONFIG.bot.staff_server_id
        ]

        # Check if the bot is in the staff server.
        if not self.staff_guild.guild_exists:
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
        """Verify the staff guild is still reachable and restore presence after each reconnect."""
        logger.debug("Connected to Discord.")
        await self.wait_until_ready()

        # Check if the staff guild still exists,
        # in case the bot was removed from the server between connects.
        if not self.staff_guild.guild_exists:
            await self._not_in_guild_close()
            return

        await self.set_bot_presence()

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Close the bot if removed from the configured staff guild."""
        logger.info("Removed from guild %s", guild.name)
        if guild.id == CONFIG.bot.staff_server_id:
            await self._not_in_guild_close()
            return

    async def get_context(self, message: discord.Message | discord.Interaction, *, cls: Any = Context) -> Context:
        """Return a [`Context`][] for the given message or interaction.

        Args:
            message: The Discord message or interaction to build context from.
            cls: The context class to use.

        Returns:
            A [`Context`][] instance.
        """
        if cls is not Context:
            logger.warning("Custom context classes are not supported and may cause issues.")
        return await super().get_context(message, cls=cls)

    def _get_discord_presence_from_settings(self) -> tuple[discord.BaseActivity | None, discord.Status | None]:
        """Build `(activity, status)` Discord objects from the current database settings.

        Returns:
            Tuple of ([`discord.BaseActivity`][] or `None`, [`discord.Status`][] or `None`)
            reflecting the saved settings.
        """
        dc_activity: discord.BaseActivity | None = None
        dc_status: discord.Status | None = None

        # db_activity and db_status should be the same as activity and status if provided
        db_activity = self.database_client.settings.activity
        db_status = self.database_client.settings.status

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
        """Update Discord presence, persisting any changes to the database first.

        Args:
            activity: New activity to display (`None` leaves the current setting unchanged).
            status: New status to display (`None` leaves the current setting unchanged).
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
        """Clear both activity and status from the database and Discord display."""
        logger.debug("Clearing bot presence.")
        await self.database_client.update_settings(activity=None, status=None)
        await self.set_bot_presence()

    async def on_command_error(self, context: commands.Context[Any], exception: commands.CommandError) -> None:
        """Route command errors to appropriate handlers.

        Unwraps `HybridCommandError`, silences `CommandNotFound`, sends a localized message
        for bad-argument and permission errors, and re-raises unexpected errors.

        Args:
            context: The invocation context.
            exception: The error raised during command execution.
        """
        # Slash/hybrid non-CommandErrors arrive wrapped in HybridCommandError; unwrap once.
        exc: commands.CommandError | discord.app_commands.AppCommandError = exception
        if isinstance(exc, commands.HybridCommandError):
            exc = exc.original

        if isinstance(exc, commands.CommandNotFound | discord.app_commands.CommandNotFound):
            return

        if isinstance(exc, LocalizedBadArgumentError):
            await self.send_message(
                exc.locale_key, channel=context, ephemeral=True, reference=context.message, fail_silently=True
            )
            return

        if isinstance(exc, commands.CheckFailure | discord.app_commands.CheckFailure):
            if isinstance(exc, BadPermissionsError):
                missing_names = (
                    [name.upper() for name, val in exc.missing if val] if exc.missing is not None else []
                )
                logger.warning(
                    "Missing permissions in %r: %s",
                    exc.channel,
                    ", ".join(missing_names) if missing_names else "unknown",
                )
                if missing_names:
                    await self.send_message(
                        _("ftl-msg-bad-permissions", permissions=", ".join(missing_names)),
                        channel=context,
                        ephemeral=True,
                        reference=context.message,
                        fail_silently=True,
                    )
                return

            if isinstance(exc, UserAccessError):
                logger.debug(
                    "[bold]%s[/bold] denied `%s` — [red]%s[/red]",
                    context.author,
                    context.command,
                    exc.result,
                    extra={"markup": True, "highlighter": None},
                )
                if context.interaction is not None and not context.interaction.is_expired():
                    await self.send_message(
                        _("ftl-msg-permission-denied"), channel=context, ephemeral=True, reference=context.message
                    )
            return

        # commands.CommandInvokeError — prefix command body raised an exception.
        # discord.app_commands.CommandInvokeError — slash/hybrid body raised a non-CommandError.
        # Both carry .original with the underlying exception.
        if isinstance(exc, commands.CommandInvokeError | discord.app_commands.CommandInvokeError):
            if isinstance(exc.original, NoStaffGuildError):
                await self._not_in_guild_close()
                return

            if isinstance(exc.original, commands.CheckFailure):
                await self.on_command_error(context, exc.original)
                return

            logger.info(
                "[red]Command %s failed with an uncaught error: %s",
                context.command,
                exc.original,
                exc_info=exc,
                extra={"markup": True},
            )

            await self.send_message(
                _("ftl-msg-command-invoke-error"),
                channel=context,
                ephemeral=True,
                reference=context.message,
                fail_silently=True,
            )
            return

        await super().on_command_error(context, exception)

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        """Close the bot on [`NoStaffGuildError`][]; delegate all other errors to the default handler.

        Args:
            event_method: Name of the event that raised the error.
            *args: Positional arguments passed to the event.
            **kwargs: Keyword arguments passed to the event.
        """
        exc_info = sys.exc_info()
        exc = exc_info[1]

        if isinstance(exc, NoStaffGuildError):
            await self._not_in_guild_close()
            return

        if isinstance(exc, BadPermissionsError):
            missing_names = [name.upper() for name, val in exc.missing if val] if exc.missing is not None else []
            logger.warning(
                "Missing permissions in %r: %s",
                exc.channel,
                ", ".join(missing_names) if missing_names else "unknown",
            )
            return

        await super().on_error(event_method, *args, **kwargs)

    @staticmethod
    async def on_before_invoke(ctx: Context) -> None:
        """Log each command invocation, including the access-check result when available.

        Args:
            ctx: The invocation context.
        """
        access = f" — [green]{ctx.user_access}[/green]" if ctx.user_access is not None else ""
        logger.debug(
            "[bold]%s[/bold] invoked `%s`%s",
            ctx.author,
            ctx.command,
            access,
            extra={"markup": True, "highlighter": None},
        )

    def add_command(self, command: commands.Command[Any, Any, Any]) -> None:
        """Register `command` and warn if its callback name doesn't follow the `_command` convention.

        Also walks any subcommands when `command` is a group, since only top-level
        commands pass through here during cog injection.

        Args:
            command: The command to register.
        """

        def _check_name(name: str, qualname: str) -> None:
            if qualname == "jishaku" or qualname.startswith("jishaku "):
                return  # jishaku commands don't follow the naming convention, so skip the check for them
            if not name.casefold().endswith("_command"):
                logger.debug("Command name does not end with _command: %s (%s)", qualname, name)

        _check_name(command.callback.__name__, command.qualified_name)
        if isinstance(command, commands.Group):
            for sub in command.walk_commands():
                _check_name(sub.callback.__name__, sub.qualified_name)
        super().add_command(command)

    @staticmethod
    def get_canonical_command_name(command: commands.Command[Any, Any, Any]) -> str:
        """Derive the display name from a [`discord.ext.commands.Command`][].

        Strips the `_command` suffix from the callback name and replaces underscores with
        spaces. Falls back to [`discord.ext.commands.Command.qualified_name`][] if the suffix
        is absent.

        Args:
            command: The command to extract the name from.

        Returns:
            The canonical name of the command for permission overrides.
        """
        # Check if the command has an override set in the config.
        command_name = command.callback.__name__.casefold()
        if command_name.endswith("_command"):
            command_name = command_name[:-8]
            command_name = command_name.replace("_", " ").strip()
        else:
            command_name = command.qualified_name  # Use the full qualified name as the command name
        return command_name

    @classmethod
    def get_command_access_level(cls, base_command: commands.Command[Any, Any, Any]) -> RequiredAccessLevel:
        """Return the effective [`RequiredAccessLevel`][] for `base_command`.

        Checks config overrides first (exact name, then wildcard `+` on parents), then
        the `__permission__` attribute set by access-level decorators. Returns
        [`RequiredAccessLevel.everyone`][] when nothing restricts the command.

        Args:
            base_command: The command to check.

        Returns:
            The resolved access level.
        """
        default_access_level: RequiredAccessLevel | None = None

        # If the command is a subcommand, if so, add the parents of the command (in reverse order)
        # and check for most significant access level.
        commands_to_check = [base_command, *base_command.parents]

        # Check if the command has an override set in the config.
        for i, command in enumerate(commands_to_check):
            command_name = cls.get_canonical_command_name(command)

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
        """Return all profiles applicable to `user`, ordered from most to least significant.

        Includes the user's personal profile and, when invoked in a guild, role profiles from
        highest role down to `@everyone`. User profile is prepended last, giving it highest priority.

        Args:
            user: The Discord user or member.

        Returns:
            Profiles in priority order (index 0 = highest priority).
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

    @staticmethod
    async def _user_access_check(ctx: Context) -> bool:
        """Delegate to [`Context.check_user_access`][]; raise [`UserAccessError`][] on denial.

        Args:
            ctx: The invocation context.

        Returns:
            Always `True`; denial is signaled by raising [`UserAccessError`][].

        Raises:
            UserAccessError: If the user lacks the required access level.
            RuntimeError: If `ctx.user_access` is `None`, which should not happen.
        """
        if not await ctx.check_user_access():
            if ctx.user_access is None:
                raise RuntimeError("ctx.user_access should be set by check_user_access, but is None")
            raise UserAccessError(ctx.user_access)
        return True

    async def _bot_can_run_check(self, ctx: Context) -> bool:
        """Always return `True`; channel-permission validation is not yet implemented.

        Args:
            ctx: The invocation context.

        Returns:
            `True`.
        """
        return True  # TODO: Implement this check

    # TODO: implement caching
    def translate(
        self,
        string: discord.app_commands.locale_str,
        *,
        ctx_or_locale: commands.Context[Any] | discord.Locale | str | None = None,
    ) -> str:
        """Translate `string` into the locale implied by `ctx_or_locale`.

        Falls back to the default locale when `ctx_or_locale` is `None` or the context
        has no interaction. Returns `string.message` when translation fails.

        Args:
            string: The locale string to translate.
            ctx_or_locale: A [`Context`][] (locale taken from its interaction), a
                [`discord.Locale`][] or BCP-47 string, or `None` for the default locale.

        Returns:
            The translated string.
        """
        locale: discord.Locale | str = CONFIG.default_locale

        if isinstance(ctx_or_locale, commands.Context):
            if ctx_or_locale.interaction is not None:
                locale = ctx_or_locale.interaction.locale
        elif isinstance(ctx_or_locale, discord.Locale | str):
            locale = ctx_or_locale

        message = self.translator.translate_sync(string, locale)
        if message is None:
            logger.warning("Failed to translate message: %s", string)
            return string.message
        return message

    @overload
    async def send_message(
        self,
        content: str | discord.app_commands.locale_str | None = ...,
        *,
        channel: discord.abc.Messageable,
        ephemeral: bool = ...,
        containerize: bool | None = ...,
        container_color: discord.Color | int | None = ...,
        original_message: discord.Message | None = ...,
        fail_silently: Literal[False] = ...,
        **kwargs: Any,
    ) -> discord.Message: ...

    @overload
    async def send_message(
        self,
        content: str | discord.app_commands.locale_str | None = ...,
        *,
        channel: discord.abc.Messageable,
        ephemeral: bool = ...,
        containerize: bool | None = ...,
        container_color: discord.Color | int | None = ...,
        original_message: discord.Message | None = ...,
        fail_silently: Literal[True],
        **kwargs: Any,
    ) -> discord.Message | None: ...

    async def send_message(
        self,
        content: str | discord.app_commands.locale_str | None = None,
        *,
        channel: discord.abc.Messageable,
        ephemeral: bool = False,
        containerize: bool | None = None,
        container_color: discord.Color | int | None = None,
        original_message: discord.Message | None = None,
        fail_silently: bool = False,
        **kwargs: Any,
    ) -> discord.Message | None:
        """Send (or edit) a message, translating locale strings.

        When `containerize` is `None` (the default), public messages are wrapped in a Component V2
        [`discord.ui.Container`][] and ephemeral ones are sent as plain text. Pass `True` or `False`
        to override. Wrapping is suppressed when a `view`, `embed`, or `embeds` kwarg is present, or
        when `content` is `None`. When `original_message` is given, edits it instead of sending a new
        message. Locale is derived from the interaction when `channel` is a [`Context`][].

        Args:
            content: Text or locale string to send.
            channel: Destination channel or [`Context`][].
            ephemeral: Whether the message should be ephemeral or not.
            containerize: Wrap plain `content` in a Component V2 container. `None` wraps public
                messages and skips ephemeral ones automatically.
            container_color: Accent color for the container's left bar (`None` uses Discord's default).
            original_message: Edit this message instead of sending a new one.
            fail_silently: When `True`, return `None` instead of raising [`BadPermissionsError`][]
                if the bot lacks required permissions. Defaults to `False`.
            **kwargs: Forwarded to `send` or `edit` (e.g. `embed`, `embeds`, `ephemeral`).

        Returns:
            The sent or edited [`discord.Message`][], or `None` if `fail_silently` is `True` and
            the bot lacks the required permissions.

        Raises:
            BadPermissionsError: If the bot lacks the required permissions and `fail_silently` is
                `False`.
            discord.HTTPException: If the send or edit request fails and `fail_silently` is `False`.
        """
        locale: discord.Locale | str = CONFIG.default_locale
        require_perm_check = True

        if isinstance(channel, commands.Context):
            channel = cast("commands.Context[Any]", channel)
            kwargs["ephemeral"] = ephemeral
            if channel.interaction is not None and not channel.interaction.is_expired():
                require_perm_check = False
                if ephemeral:
                    locale = channel.interaction.locale

        if require_perm_check:
            required_perms = discord.Permissions.none()
            required_perms.read_messages = True

            if isinstance(channel, discord.Thread):
                required_perms.send_messages_in_threads = True
            elif isinstance(channel, commands.Context) and isinstance(channel.channel, discord.Thread):
                channel = cast("commands.Context[Any]", channel)
                required_perms.send_messages_in_threads = True
            else:
                required_perms.send_messages = True
            if kwargs.get("tts"):
                required_perms.send_tts_messages = True
            if "embed" in kwargs or "embeds" in kwargs:
                required_perms.embed_links = True
            if "file" in kwargs or "files" in kwargs:
                required_perms.attach_files = True
            if "poll" in kwargs:
                required_perms.send_polls = True

            perms = None
            if isinstance(channel, discord.Thread | discord.abc.GuildChannel):
                perms = channel.permissions_for(channel.guild.me)
            elif isinstance(channel, discord.DMChannel | discord.GroupChannel):
                perms = channel.permissions_for(channel.me)
            elif isinstance(channel, commands.Context):
                channel = cast("commands.Context[Any]", channel)
                perms = channel.channel.permissions_for(channel.me)  # pyright: ignore [reportArgumentType]

            if perms is not None:
                missing = ~perms & required_perms
                if missing.value:
                    if fail_silently:
                        logger.debug("Skipping send to %r — missing permissions: %s", channel, missing)
                        return None
                    raise BadPermissionsError(channel=cast("discord.abc.Messageable", channel), missing=missing)

        if isinstance(content, discord.app_commands.locale_str):
            content = self.translate(content, ctx_or_locale=locale)

        if containerize is None:
            containerize = not ephemeral

        if "view" in kwargs or "embed" in kwargs or "embeds" in kwargs:
            containerize = False

        if containerize and content:
            container_view = discord.ui.LayoutView(timeout=None)
            container_view.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_color=container_color,
                )
            )
            kwargs["view"] = container_view
            content = None

        if "embed" in kwargs:
            embed = kwargs["embed"]
            if isinstance(embed, EmbedProxy):
                kwargs["embed"] = embed.to_embed(self.translator, locale)

        if "embeds" in kwargs:
            embeds: list[discord.Embed] = []
            for embed in kwargs["embeds"]:
                if isinstance(embed, EmbedProxy):
                    embeds.append(embed.to_embed(self.translator, locale))
                else:
                    embeds.append(embed)
            kwargs["embeds"] = embeds

        try:
            if original_message is not None:
                kwargs.pop("reference", None)
                kwargs.pop("ephemeral", None)
                return await original_message.edit(content=content, **kwargs)

            if isinstance(channel, Context):
                return await super(Context, channel).send(content, **kwargs)
            return await channel.send(content, **kwargs)

        except discord.HTTPException as exc:
            if fail_silently:
                logger.debug("Skipping send to %r — HTTP error: %r", channel, exc)
                return None
            raise
