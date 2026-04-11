"""Foundation shared by all MongoDB mixins — the client, database name, and bot config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from modmail.errors import DatabaseConnectionError

if TYPE_CHECKING:
    from typing import Any

    from pymongo import AsyncMongoClient

    from modmail.config.models import Config, MongoDBDatabaseConfig

__all__ = ["MongoDBBackendBase"]

logger = logging.getLogger(__name__)


class MongoDBBackendBase:
    """Base class that provides [`client`][] and [`_mongodb_config`][] to every MongoDB mixin.

    Places this at the base of the MRO so the shared state is
    declared once and available to all domain mixins.
    """

    # These are typed here but initialized in MongoDBBackend.__init__ via super().__init__
    _async_mongo_client: AsyncMongoClient[dict[str, Any]] | None
    db_name: str

    # Inherited from DBBackend via MongoDBBackend's MRO
    _config: Config
    _instance_id: str

    @property
    def client(self) -> AsyncMongoClient[dict[str, Any]]:
        """The [AsyncMongoClient][]{ data-preview } for this backend.

        Raises:
            DatabaseConnectionError: If called before
                [`connect`][....backend.MongoDBBackend._connect]{ data-preview } or after
                [`disconnect`][....backend.MongoDBBackend._disconnect]{ data-preview }.
        """
        if self._async_mongo_client is None:
            raise DatabaseConnectionError("MongoDB client accessed before connect() was called.")
        return self._async_mongo_client

    @property
    def _mongodb_config(self) -> MongoDBDatabaseConfig:
        """The [MongoDBDatabaseConfig][]{ data-preview } for this `bot_id`.

        Raises:
            AttributeError: If the MongoDB config was not provided.
        """
        if self._config.mongodb_config is None:
            raise AttributeError("_mongodb_config accessed but not provided in config.")
        return self._config.mongodb_config
