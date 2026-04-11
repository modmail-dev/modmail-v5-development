"""Beanie document model for ticket users in MongoDB."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pymongo.errors
from beanie import Document, UpdateResponse
from pymongo import UpdateOne as PyMongoUpdateOne

from modmail.backends.common import TicketUserModel
from modmail.errors import DatabaseOperationError

from .base import BSON_ENCODERS

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne

__all__ = ["MongoDBTicketUserDocument"]


class MongoDBTicketUserDocument(Document):
    """Beanie document for a ticket user.

    Uses the Discord user ID as the document `_id` ([`id`][] field).
    Shared across all tickets, with one document per unique user.
    """

    id: int  # pyright: ignore [reportIncompatibleVariableOverride, reportGeneralTypeIssues]
    """Discord snowflake user ID, stored as the MongoDB `_id`."""
    user_name: str
    """Display name captured at ticket time."""

    class Settings:
        """Settings for MongoDB ticket user collection."""

        name = "TicketUser"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS

    @classmethod
    def from_model(cls, model: TicketUserModel) -> MongoDBTicketUserDocument:
        """Construct a document from a [TicketUserModel][]{ data-preview }.

        Args:
            model: The ticket user model to convert.

        Returns:
            MongoDBTicketUserDocument: An unsaved document constructed from the model.
        """
        return cls(id=model.user_id, user_name=model.user_name)

    def to_model(self) -> TicketUserModel:
        """Convert this document to a common [TicketUserModel][]{ data-preview }.

        Returns:
            TicketUserModel: The converted common user model.
        """
        return TicketUserModel(user_id=self.id, user_name=self.user_name)

    @classmethod
    async def put_model(cls, model: TicketUserModel) -> MongoDBTicketUserDocument:
        """Upsert a ticket user and return the persisted document.

        Args:
            model: The ticket user model to upsert.

        Returns:
            MongoDBTicketUserDocument: The persisted document.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        doc = cls.from_model(model)
        update_dict = doc.model_dump(exclude={"id"})
        try:
            return cast(
                "MongoDBTicketUserDocument",
                await cast(
                    "UpdateOne",
                    cls.find_one(cls.id == model.user_id).upsert(
                        {"$set": update_dict}, on_insert=doc, response_type=UpdateResponse.NEW_DOCUMENT
                    ),
                ),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist ticket user") from exc

    @classmethod
    async def put_many(cls, *models: TicketUserModel) -> list[MongoDBTicketUserDocument]:
        """Bulk-upsert multiple ticket users in a single database call.

        Deduplicates by `user_id` before writing, then issues one
        `bulk_write` with `UpdateOne(upsert=True)` per unique user.

        Args:
            *models: [TicketUserModel][]{ data-preview } records to upsert, possibly with duplicates.

        Returns:
            list[MongoDBTicketUserDocument]: One document per unique user.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        unique_models = list({m.user_id: m for m in models}.values())

        if len(unique_models) == 0:
            return []

        if len(unique_models) == 1:
            return [await cls.put_model(unique_models[0])]

        docs = [cls.from_model(m) for m in unique_models]
        try:
            async with cls.bulk_writer(ordered=False) as bulk:
                for doc in docs:
                    update_dict = doc.model_dump(exclude={"id"})
                    bulk.add_operation(cls, PyMongoUpdateOne({"_id": doc.id}, {"$set": update_dict}, upsert=True))
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist ticket users") from exc
        return docs
