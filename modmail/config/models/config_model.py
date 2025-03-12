"""
modmail.config.models.config_model
==================================
This module defines the primary configuration model for the Modmail bot.
It uses Pydantic for data validation and settings management, ensuring
that the configuration is correctly loaded and validated from various sources.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Literal, TypeVar

from packaging.version import Version
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .bot_model import BotConfig
from .json_database_model import JsonDatabaseConfig
from .logging_model import LoggingConfig
from .mongodb_database_model import MongoDBDatabaseConfig

if TYPE_CHECKING:
    from pydantic import ValidationInfo
    from pydantic_settings import PydanticBaseSettingsSource

__all__ = ["Config"]


# noinspection PyNestedDecorators
class Config(BaseSettings):
    """
    Primary configuration model for the Modmail bot.

    Attributes:
        version (str): The config version.
        bot (BotConfig): The bot configuration.
        database_type (Literal["mongodb", "json"]): The type of database used.
        mongodb_config (MongoDBDatabaseConfig | None): The MongoDB configuration.
        json_config (JsonDatabaseConfig | None): The JSON database configuration.
        logging (LoggingConfig): The logging configuration.
    """

    version: str = "1.0"  # the config version
    bot: BotConfig
    database_type: Literal["mongodb", "json"]
    mongodb_config: MongoDBDatabaseConfig | None = Field(None, validate_default=True)
    json_config: JsonDatabaseConfig | None = Field(None, validate_default=True)
    logging: LoggingConfig = Field(LoggingConfig(), validate_default=True)

    # Don't load .env when testing.
    if "pytest" not in sys.modules:
        model_config = SettingsConfigDict(
            env_prefix="modmail_",
            env_file=".env",
            env_file_encoding="utf-8",
            env_nested_delimiter="__",
            case_sensitive=False,
        )
    else:
        model_config = SettingsConfigDict(case_sensitive=False)

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

    _T = TypeVar("_T")

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

    @field_validator("json_config", mode="before")
    @classmethod
    def check_using_json_database_config(cls, v: _T, info: ValidationInfo) -> _T | None:
        """
        This parses json configs when the database type is json.
        """
        if info.data["database_type"] == "json":
            if not v:
                # This may error since it could be missing required fields.
                v = JsonDatabaseConfig()  # type: ignore[reportCallIssue, reportAssignmentType]
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
