"""Configuration for the bot's logging system."""

from __future__ import annotations

import contextlib
import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

from rich.logging import RichHandler
from rich.text import Text

if TYPE_CHECKING:
    from types import ModuleType

    from .config.models import LoggingConfig

__all__ = ["setup_logging"]

_LOGFILE_DEFAULT_LEVEL = logging.WARNING
_LOGFILE_LEVELS: dict[str, int] = {
    "modmail": logging.DEBUG,
    "discord": logging.INFO,
    "discord.state": logging.DEBUG,
    "discord.http": logging.INFO,
    "discord.gateway": logging.INFO,
    "sqlalchemy.engine": logging.INFO,
    "pymongo": logging.INFO,
}
_LOGFILE_MIN_LEVEL = min(
    [*_LOGFILE_LEVELS.values(), _LOGFILE_DEFAULT_LEVEL],
    key=lambda x: _LOGFILE_DEFAULT_LEVEL if x == logging.NOTSET else x,
)


class FileFormatter(logging.Formatter):
    """Formats log records for file output, stripping rich markup."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03d"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record, stripping Rich markup if present.

        Args:
            record: The log record to format.

        Returns:
            The formatted log string.
        """
        formatted = super().format(record)
        if record.__dict__.get("markup", False):
            formatted = Text.from_markup(formatted).plain
        return formatted


class PerLoggerFilter(logging.Filter):
    """Pass or reject a log record based on per-logger minimum levels.

    Each logger name in *logger_levels* maps to a minimum level.
    The most specific matching name determines the threshold for the
    record.  Loggers that don't match any entry use *default_level*.
    Entries set to `NOTSET` inherit *default_level* rather than applying
    their own threshold.
    """

    def __init__(self, logger_levels: dict[str, int], default_level: int = logging.NOTSET) -> None:
        """Initialize the per-logger filter.

        Args:
            logger_levels: Mapping of logger names to minimum levels.
            default_level: Fallback level for unlisted loggers.
        """
        super().__init__()
        self._default_level = default_level
        self._logger_levels = sorted(logger_levels.items(), key=lambda x: -len(x[0]))

    def filter(self, record: logging.LogRecord) -> bool:
        """Determine if a log record passes the per-logger threshold.

        Args:
            record: The log record to check.

        Returns:
            True if the record's level meets the threshold, False otherwise.
        """
        for name, level in self._logger_levels:
            if record.name == name or record.name.startswith(name + "."):
                if level == logging.NOTSET:  # not set will inherit root level
                    break
                return record.levelno >= level
        return record.levelno >= self._default_level


def _load_suppress_targets() -> list[ModuleType]:
    """Import optional modules for Rich traceback suppression.

    Returns:
        Module objects to suppress in Rich tracebacks.
    """
    targets: list[ModuleType] = []
    for mod_name in (
        "discord",
        "sqlalchemy",
        "pymongo",
        "uvloop",
        "aiohttp",
        "beanie",
        "alembic",
        "asyncio",
    ):
        with contextlib.suppress(ImportError):
            targets.append(__import__(mod_name))
    return targets


def setup_logging(logging_config: LoggingConfig) -> None:
    """Configure logging from *logging_config*.

    In **managed** mode removes all existing handlers from every
    managed logger, resets their levels to `NOTSET`, then attaches a
    console (`RichHandler`) and optional file (`RotatingFileHandler`)
    handler to the root logger.  Per-logger minimum levels are enforced
    by a `PerLoggerFilter` on each handler:

    * Console handler uses the user-configurable `*_level` fields
      (`discord_level`, `sqlalchemy_level`, etc.).
    * File handler uses a fixed scheme defined in `_LOGFILE_LEVELS`
      (modmail=DEBUG, discord.state=DEBUG, others=INFO,
      unconfigured=WARNING).

    In **unmanaged** mode only the file handler is attached (with the
    same fixed scheme).  No logger levels are touched, and the caller
    is responsible for console output.

    Args:
        logging_config: The logging sub-config to apply.
    """
    root = logging.getLogger()

    # Remove old logfile handler if exists
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            root.removeHandler(h)
            h.close()

    def attach_logfile_handler() -> None:
        """Attach a rotating file handler to the root logger."""
        if logging_config.logfile is not None:
            file_handler = RotatingFileHandler(
                logging_config.logfile,
                mode="a",
                maxBytes=logging_config.logfile_max_size,
                backupCount=logging_config.logfile_backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(FileFormatter(logging_config.logfile_format))
            file_handler.setLevel(_LOGFILE_MIN_LEVEL)
            file_handler.addFilter(PerLoggerFilter(_LOGFILE_LEVELS, _LOGFILE_DEFAULT_LEVEL))
            root.addHandler(file_handler)

    if not logging_config.managed:
        attach_logfile_handler()
        return

    managed_loggers: dict[str, int] = {
        "": logging_config.root_level,
        "modmail": logging_config.modmail_level,
        "discord": logging_config.discord_level,
        "discord.state": logging_config.discord_state_level,
        "discord.http": logging_config.discord_http_level,
        "discord.gateway": logging_config.discord_gateway_level,
        "sqlalchemy": logging_config.sqlalchemy_level,
        "sqlalchemy.engine": logging_config.sqlalchemy_engine_level,
        "pymongo": logging_config.pymongo_level,
        "pymongo.topology": logging_config.pymongo_topology_level,
    }

    user_levels: dict[str, int] = {}
    for name, level in managed_loggers.items():
        lg = logging.getLogger(name)
        for h in list(lg.handlers):
            lg.removeHandler(h)
            h.close()

        # Determine the minimum level for this logger based on console and file outputs
        min_level = logging_config.root_level if level == logging.NOTSET else level

        if logging_config.logfile is not None:
            for n, lv in sorted(_LOGFILE_LEVELS.items(), key=lambda x: -len(x[0])):
                if name == n or name.startswith(n + "."):
                    if lv == logging.NOTSET:
                        min_level = min(min_level, _LOGFILE_DEFAULT_LEVEL)
                    else:
                        min_level = min(min_level, lv)
                    break
        lg.setLevel(min_level)
        if name:
            user_levels[name] = level

    # Configure loggers in _LOGFILE_LEVELS not in managed_loggers
    if logging_config.logfile is not None:
        configured = {name for name in managed_loggers if name}
        for n, lv in _LOGFILE_LEVELS.items():
            if n in configured:
                continue
            lg = logging.getLogger(n)
            for h in list(lg.handlers):
                lg.removeHandler(h)
                h.close()
            file_effective = _LOGFILE_DEFAULT_LEVEL if lv == logging.NOTSET else lv
            lg.setLevel(min(logging_config.root_level, file_effective))

    fmt = logging.Formatter(logging_config.stdout_format)
    console = RichHandler(
        show_level=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        log_time_format=lambda dt: Text(dt.strftime("%X,%f")[:-3]),
        tracebacks_suppress=_load_suppress_targets(),
    )
    # TODO: enable markup by default for modmail logs
    console.setFormatter(fmt)
    console_min_level = min(
        [*user_levels.values(), logging_config.root_level],
        key=lambda x: logging_config.root_level if x == logging.NOTSET else x,
    )
    console.setLevel(console_min_level)
    console.addFilter(PerLoggerFilter(user_levels, logging_config.root_level))
    root.addHandler(console)
    attach_logfile_handler()
