"""
modmail.config.models
=====================
This module defines the data models used for configuration files in the project.
These models represent various configuration sections and are used to load,
validate, and manage configuration settings for the bot.
"""

from __future__ import annotations

from .bot_model import BotConfig
from .config_model import Config
from .json_database_model import JsonDatabaseConfig
from .logging_model import LoggingConfig
from .mongodb_database_model import MongoDBDatabaseConfig

__all__ = [
    "BotConfig",
    "Config",
    "JsonDatabaseConfig",
    "LoggingConfig",
    "MongoDBDatabaseConfig",
]
