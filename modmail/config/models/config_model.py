"""
modmail.config.models.config_model
==================================
This module defines the primary configuration model for the Modmail bot.
It uses Pydantic for data validation and settings management, ensuring
that the configuration is correctly loaded and validated from various sources.
"""

from __future__ import annotations

import sys
from typing import Literal, TypeAlias, TypeVar

from packaging.version import Version
from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .bot_model import BotConfig
from .logging_model import LoggingConfig
from .mongodb_database_model import MongoDBDatabaseConfig
from .permission_model import PermissionConfig
from .sql_database_model import SQLDatabaseConfig

__all__ = ["Config"]

SupportedLocales: TypeAlias = Literal["en", "de"]
SupportedDatabases: TypeAlias = Literal["sql", "mongodb"]


# noinspection PyNestedDecorators
class Config(BaseSettings):
    """
    Primary configuration model for the Modmail bot.

    Attributes:
        version (str): The config version.
        bot (BotConfig): The bot configuration.
        allowed_locales (list[str]): A list of allowed locales for use when converting messages.
        default_locale (str): The default locale for the bot.
        database_type (str): The type of database used.
        sql_config (SQLDatabaseConfig | None): The SQL database configuration.
        mongodb_config (MongoDBDatabaseConfig | None): The MongoDB configuration.
        logging (LoggingConfig): The logging configuration.
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
    if "pytest" not in sys.modules:
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
        """
        Prioritize environment variables over config.yaml.
        """
        return env_settings, dotenv_settings, init_settings, file_secret_settings

    @field_validator("version")
    @classmethod
    def check_version_valid(cls, v: str) -> str:
        """
        Checks if the version is valid.
        """
        valid_versions = ("1.0",)  # a tuple of valid versions

        version = str(Version(v))
        if version not in valid_versions:
            raise ValueError(f"Invalid config version. Valid versions are: {', '.join(valid_versions)}")

        # Do version migrations here?

        return version

    @field_validator("default_locale")
    @classmethod
    def check_default_locale_in_allowed(cls, v: str, info: ValidationInfo) -> str:
        """
        Checks if the default locale is valid.
        """
        if v not in info.data["allowed_locales"]:
            raise ValueError(f"The default locale must be in allowed_locales.")
        return v

    _T = TypeVar("_T")

    @field_validator("sql_config", mode="before")
    @classmethod
    def check_using_sql_database_config(cls, v: _T, info: ValidationInfo) -> _T | None:
        """
        This parses SQL configs when the database type is sql.
        """
        if info.data["database_type"] == "sql":
            if not v:
                # This may error since it could be missing required fields.
                v = SQLDatabaseConfig()  # type: ignore[reportCallIssue, reportAssignmentType]
            return v
        return None

    @field_validator("mongodb_config", mode="before")
    @classmethod
    def check_using_mongodb_database_config(cls, v: _T, info: ValidationInfo) -> _T | None:
        """
        This parses MongoDB configs when the database type is mongodb.
        """
        if info.data["database_type"] == "mongodb":
            if not v:
                # This may error since it could be missing required fields.
                v = MongoDBDatabaseConfig()  # type: ignore[reportCallIssue, reportAssignmentType]
            return v
        return None

    @field_validator("logging", mode="before")
    @classmethod
    def set_default_logging_config(cls, v: LoggingConfig | None) -> LoggingConfig:
        """
        Sets the default logging config if not provided.
        """
        if v is None:
            return LoggingConfig()
        return v

    @field_validator("permission", mode="before")
    @classmethod
    def set_default_permission_config(cls, v: PermissionConfig | None) -> PermissionConfig:
        """
        Sets the default permission config if not provided.
        """
        if v is None:
            return PermissionConfig()
        return v

    # TODO: Add a validator to check if the dependencies for the database type is installed
