"""MongoDB database backend for Modmail via the Beanie ODM and PyMongo async driver."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import pymongo.errors
from beanie import init_beanie  # pyright: ignore [reportUnknownVariableType]
from pymongo import AsyncMongoClient

from modmail.errors import DatabaseConnectionError

from ..common.db_backend import DBBackend
from ._base import MongoDBBackendBase
from ._lock import MongoDBLockMixin
from ._profiles import MongoDBProfilesMixin
from ._settings import MongoDBSettingsMixin
from ._tickets import MongoDBTicketsMixin
from .migration import do_migration
from .models import (
    MongoDBInstanceLockDocument,
    MongoDBProfileDocument,
    MongoDBSettingsDocument,
    MongoDBTicketDocument,
    MongoDBTicketMessageDocument,
    MongoDBTicketUserDocument,
)

if TYPE_CHECKING:
    from modmail.config.models import Config

    # Resolve docs import
    from modmail.errors import InstanceAlreadyRunningError  # pyright: ignore [reportUnusedImport]  # noqa: F401


__all__ = ["MongoDBBackend"]

logger = logging.getLogger(__name__)


class MongoDBBackend(
    MongoDBLockMixin,
    MongoDBSettingsMixin,
    MongoDBProfilesMixin,
    MongoDBTicketsMixin,
    MongoDBBackendBase,
    DBBackend,
):
    """Concrete [DBBackend][]{ data-preview } assembled from four domain mixins.

    Wires the lock, settings, profile, and ticket mixins together with the
    [AsyncMongoClient][]{ data-preview }, Beanie ODM initialization, and migration
    runner on [`_connect`][].
    """

    _document_models = [
        MongoDBInstanceLockDocument,
        MongoDBSettingsDocument,
        MongoDBProfileDocument,
        MongoDBTicketDocument,
        MongoDBTicketUserDocument,
        MongoDBTicketMessageDocument,
    ]

    def __init__(self, config: Config) -> None:
        """Initialize the MongoDB backend.

        Args:
            config: The bot [Config][]{ data-preview }.
        """
        super().__init__(config)
        self.db_name = self._mongodb_config.database
        """The name of the MongoDB database to connect to."""

        self._async_mongo_client: AsyncMongoClient[dict[str, Any]] | None = None

    async def _connect(self) -> None:
        """Connect to MongoDB and run startup procedures.

        Creates the [AsyncMongoClient][]{ data-preview }, verifies connectivity with a
        `server_info` call, acquires the instance lock, initializes Beanie with all
        document models, and runs migrations.

        Raises:
            DatabaseConnectionError: If the connection attempt fails for any reason,
                including authentication failures, network errors, or TLS issues.
            InstanceAlreadyRunningError: If the MongoDB instance has already been
                locked by another bot instance.
        """
        try:
            # InvalidURI is raised during AsyncMongoClient initialization if the URI is malformed
            self._async_mongo_client = AsyncMongoClient(
                self._mongodb_config.uri.get_secret_value(),
                connectTimeoutMS=4000,
                serverSelectionTimeoutMS=5000,
                tlsAllowInvalidCertificates=self._mongodb_config.tls_allow_invalid_certificates,
                compressors="zstd,zlib",
                zlibCompressionLevel=1,
            )
            await self._async_mongo_client.server_info()

        except pymongo.errors.InvalidURI as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)

            logger.critical(
                "Your MongoDB connection URI is invalid. Make sure your MongoDB "
                "connection URI is correct and properly formatted."
            )
            raise DatabaseConnectionError from e

        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            error_str = str(e)
            if "Connection refused" in error_str:
                logger.critical(
                    "Failed to connect to MongoDB. Is it running? "
                    "Make sure your MongoDB connection URI is correct."
                )
            elif "connection closed" in error_str:
                logger.critical(
                    "Failed to connect to MongoDB. "
                    "Your IP may not be whitelisted to access the database. "
                    "Make sure to whitelist all IP addresses that will be connecting "
                    "to the database or whitelist '0.0.0.0/0'."
                )
            elif "CERTIFICATE_VERIFY_FAILED" in error_str:
                if os.name == "darwin":
                    logger.critical(
                        "Failed to connect to MongoDB. Check there's no proxies blocking SSL cert "
                        "verification. Try updating your CA certificates by `cd` to your Python "
                        "directory then run `Install Certificates.command` or run "
                        "`pip3 install --upgrade certifi`. If you are using a self-signed certificate, "
                        "set `tls_allow_invalid_certificates` to `true` in your config."
                    )
                else:
                    logger.critical(
                        "Failed to connect to MongoDB. Check there's no proxies blocking SSL cert "
                        "verification. If you are using a self-signed certificate, "
                        "set `tls_allow_invalid_certificates` to `true` in your config."
                    )
            else:
                logger.critical(
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server "
                    "is reachable. Please report this error to the Modmail team."
                )
                logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e

        except pymongo.errors.OperationFailure as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            if "authentication failed" in str(e):
                logger.critical(
                    "Failed to connect to MongoDB. Invalid credentials. "
                    "Make sure you're using the correct username and password for your database, "
                    "and the password must be escaped according to RFC 3986."
                )
            else:
                logger.critical(
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server "
                    "is reachable. Please report this error to the Modmail team."
                )
                logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e

        except Exception as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            logger.critical(
                "An unknown error occurred while connecting to MongoDB. Check your MongoDB server "
                "is reachable. Please report this error to the Modmail team."
            )
            logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e

        await init_beanie(
            database=self._async_mongo_client.get_database(self.db_name),
            document_models=self._document_models,
        )
        logger.debug("Connected to MongoDB.")

        logger.debug("Running database migrations.")
        await do_migration(self._mongodb_config.uri.get_secret_value(), self.db_name)

        # May raise InstanceAlreadyRunningError when another bot is holding the instance lock
        await self._acquire_instance_lock()

    async def _disconnect(self) -> None:
        """Close the MongoDB client connection."""
        if self._async_mongo_client:
            await self._async_mongo_client.close()
            self._async_mongo_client = None
            logger.debug("Disconnected from MongoDB.")
