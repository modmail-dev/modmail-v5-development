"""Primary configuration model for the Modmail bot.

This module defines the primary configuration model for the Modmail bot.
It uses Pydantic for data validation and settings management, ensuring
that the configuration is correctly loaded and validated from various sources.
"""

from __future__ import annotations

import os
from typing import Literal, TypeVar

from packaging.version import Version
from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .bot_model import BotConfig
from .logging_model import LoggingConfig
from .mongodb_database_model import MongoDBDatabaseConfig
from .permission_model import PermissionConfig
from .sql_database_model import SQLDatabaseConfig

__all__ = ["Config"]

type SupportedLocales = Literal["en", "de"]
type SupportedDatabases = Literal["sql", "mongodb"]


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
    allowed_locales: set[SupportedLocales] = Field({"en", "de"}, min_length=1)
    default_locale: SupportedLocales = Field("en", validate_default=True)
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

    @field_validator("default_locale")
    @classmethod
    def check_default_locale_in_allowed(cls, v: str, info: ValidationInfo) -> str:
        """Ensures the default locale is in the set of allowed locales.

        Args:
            v: The default locale to validate.
            info: Validation context containing other field values.

        Returns:
            The validated default locale.

        Raises:
            ValueError: If the default locale is not in the allowed_locales set.
        """
        if v not in info.data.get("allowed_locales", set()):
            raise ValueError("The default locale must be in allowed_locales.")
        return v

    _T = TypeVar("_T")

    @field_validator("sql_config", mode="before")
    @classmethod
    def check_using_sql_database_config(cls, v: _T, info: ValidationInfo) -> _T | None:
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
    def check_using_mongodb_database_config(cls, v: _T, info: ValidationInfo) -> _T | None:
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
