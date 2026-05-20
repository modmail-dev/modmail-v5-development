"""Primary configuration model for the Modmail bot.

This module defines the primary configuration model for the Modmail bot.
It uses Pydantic for data validation and settings management, ensuring
that the configuration is correctly loaded and validated from various sources.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from babel.core import negotiate_locale
from packaging.version import Version
from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .bot_model import BotConfig
from .logging_model import LoggingConfig
from .mongodb_database_model import MongoDBDatabaseConfig
from .permission_model import PermissionConfig
from .sql_database_model import SQLDatabaseConfig

__all__ = ["Config"]

type SupportedDatabases = Literal["sql", "mongodb"]

LOCALES_ROOT = Path(__file__).resolve().parent.parent.parent / "locales"


def _discover_locale_dirs() -> set[str]:
    """Return locale directory names found under `modmail/locales/`.

    Directories ending with `-custom` are excluded — they are handled
    separately by the [`Translator`][modmail.i18n.Translator] at startup.
    """
    found: set[str] = set()
    if not LOCALES_ROOT.is_dir():
        return found
    for child in sorted(LOCALES_ROOT.iterdir()):
        if child.is_dir() and (child / "LC_MESSAGES").is_dir() and not child.name.endswith("-custom"):
            found.add(child.name)
    return found


class Config(BaseSettings):
    """Primary configuration model for the Modmail bot.

    This class represents the complete configuration for the Modmail bot,
    including bot settings, database configurations, logging, permissions,
    and localization settings.

    Attributes:
        version: The config schema version.
        bot: The bot configuration settings.
        allowed_locales: A set of allowed locales for message translations.
        default_locale: The default locale for the bot.
        database_type: The type of database being used (sql or mongodb).
        sql_config: The SQL database configuration if using SQL.
        mongodb_config: The MongoDB configuration if using MongoDB.
        permission: The permission configuration settings.
        logging: The logging configuration settings.
    """

    version: str = "1.0"  # the config version
    bot: BotConfig
    allowed_locales: set[str] = Field(default_factory=set)
    default_locale: str = ""
    log_url: str
    database_type: SupportedDatabases
    sql_config: SQLDatabaseConfig | None = Field(None, validate_default=True)
    mongodb_config: MongoDBDatabaseConfig | None = Field(None, validate_default=True)
    permission: PermissionConfig = Field(PermissionConfig(), validate_default=True)
    logging: LoggingConfig = Field(LoggingConfig(), validate_default=True)

    # Don't load .env when testing.
    if os.environ.get("PYTEST_VERSION") is None:
        model_config = SettingsConfigDict(
            env_prefix="modmail_",
            env_file=".env",
            env_file_encoding="utf-8",
            env_nested_delimiter="__",
            case_sensitive=False,
            extra="ignore",
        )
    else:
        model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customizes the settings source priority order.

        Prioritizes environment variables over configuration files.

        Args:
            settings_cls: The settings class.
            init_settings: Settings from initialization.
            env_settings: Settings from environment variables.
            dotenv_settings: Settings from .env file.
            file_secret_settings: Settings from file secrets.

        Returns:
            A tuple of PydanticBaseSettingsSource ordered by priority.
        """
        return env_settings, dotenv_settings, init_settings, file_secret_settings

    @field_validator("version")
    @classmethod
    def check_version_valid(cls, v: str) -> str:
        """Validates that the configuration version is supported.

        Args:
            v: The version string to validate.

        Returns:
            The validated version string.

        Raises:
            ValueError: If the version is not supported.
        """
        valid_versions = ("1.0",)  # a tuple of valid versions

        try:
            version = str(Version(v))
            if version not in valid_versions:
                raise ValueError(f"Invalid config version. Valid versions are: {', '.join(valid_versions)}")
        except Exception as e:
            raise ValueError(f"Invalid config version. Valid versions are: {', '.join(valid_versions)}") from e

        # Do version migrations here?

        return version

    @model_validator(mode="after")
    def _validate_locales(self) -> Config:
        """Validate allowed_locales and default_locale, then compile and load bundles.

        If allowed_locales is empty the available locale directories are
        auto-discovered.  Each entry is matched against the available
        directories via `babel.core.negotiate_locale`.  `.mo` files are
        compiled on demand and then loaded into the `Translator`.

        Returns:
            The validated config instance with resolved locale fields.

        Raises:
            ValueError: If a locale does not match any available directory
                or bundle loading fails.
        """
        from modmail.i18n import Translator
        from modmail.locales import ensure_compiled

        available = _discover_locale_dirs()
        raw = self.allowed_locales

        if raw:
            resolved: set[str] = set()
            for entry in raw:
                entry_str = str(entry)
                match = negotiate_locale([entry_str.replace("_", "-")], list(available), sep="-")
                if match is None:
                    raise ValueError(
                        f"Locale {entry_str!r} does not match any available locale directory ({sorted(available)})"
                    )
                resolved.add(match)
        else:
            resolved = available

        ensure_compiled()
        try:
            Translator.load_bundles(sorted(resolved))
        except Exception as e:
            raise ValueError(f"Failed to load translation bundles for {resolved}: {e}") from e

        self.allowed_locales = resolved

        if not self.default_locale:
            self.default_locale = next(iter(resolved))
        else:
            match = negotiate_locale([self.default_locale.replace("_", "-")], list(resolved), sep="-")
            if match is None:
                raise ValueError(
                    f"Default locale {self.default_locale!r} does not match "
                    f"any allowed locale ({sorted(resolved)})"
                )
            self.default_locale = match

        return self

    @field_validator("sql_config", mode="before")
    @classmethod
    def check_using_sql_database_config[T](cls, v: T, info: ValidationInfo) -> T | None:
        """Sets up SQL database configuration when SQL is selected.

        Args:
            v: The SQL configuration value.
            info: Validation context containing other field values.

        Returns:
            SQL configuration if using SQL database, otherwise None.
        """
        if info.data.get("database_type") == "sql":
            if not v:
                # This may error since it could be missing required fields.
                v = SQLDatabaseConfig()  # pyright: ignore [reportCallIssue, reportAssignmentType]
            return v
        return None

    @field_validator("mongodb_config", mode="before")
    @classmethod
    def check_using_mongodb_database_config[T](cls, v: T, info: ValidationInfo) -> T | None:
        """Sets up MongoDB configuration when MongoDB is selected.

        Args:
            v: The MongoDB configuration value.
            info: Validation context containing other field values.

        Returns:
            MongoDB configuration if using MongoDB, otherwise None.
        """
        if info.data.get("database_type") == "mongodb":
            if not v:
                # This may error since it could be missing required fields.
                v = MongoDBDatabaseConfig()  # pyright: ignore [reportCallIssue, reportAssignmentType]
            return v
        return None

    @field_validator("logging", mode="before")
    @classmethod
    def set_default_logging_config(cls, v: LoggingConfig | None) -> LoggingConfig:
        """Provides default logging configuration if none is specified.

        Args:
            v: The logging configuration or None.

        Returns:
            The provided logging configuration or a default one.
        """
        if v is None:
            return LoggingConfig()
        return v

    @field_validator("permission", mode="before")
    @classmethod
    def set_default_permission_config(cls, v: PermissionConfig | None) -> PermissionConfig:
        """Provides default permission configuration if none is specified.

        Args:
            v: The permission configuration or None.

        Returns:
            The provided permission configuration or a default one.
        """
        if v is None:
            return PermissionConfig()
        return v

    # TODO: Add a validator to check if the dependencies for the database type is installed

    @field_validator("log_url")
    @classmethod
    def check_log_url(cls, v: str) -> str:
        """Validates the log URL format.

        Args:
            v: The log URL to validate.

        Returns:
            The validated log URL.

        Raises:
            ValueError: If the log URL is not valid.
        """
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError("Log URL must start with 'https://'")
        return v.strip("/ ")  # Remove trailing slash if present
