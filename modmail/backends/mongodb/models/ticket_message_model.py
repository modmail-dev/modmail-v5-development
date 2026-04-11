"""Beanie document models for ticket messages in MongoDB."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pymongo.errors
from beanie import Document, Link
from pydantic import BaseModel
from pymongo import ASCENDING, IndexModel

from modmail.enum import TicketMessageType
from modmail.errors import DatabaseOperationError

from .base import BSON_ENCODERS, UTCTimestamp
from .ticket_user_model import MongoDBTicketUserDocument

if TYPE_CHECKING:
    from modmail.backends.common import TicketDMMessageModel, TicketMessageModel

__all__ = ["MongoDBTicketDMMessageModel", "MongoDBTicketMessageDocument"]


class MongoDBTicketDMMessageModel(BaseModel):
    """Pydantic sub-model for a DM delivery record embedded in a ticket message."""

    message_id: int
    """Discord message ID in the recipient's DM channel."""
    recipient_id: int  # beanie does not support Link[MongoDBTicketUserDocument] in nested models
    """Discord snowflake ID of the DM recipient."""

    @classmethod
    def from_model(cls, model: TicketDMMessageModel) -> MongoDBTicketDMMessageModel:
        """Construct a [MongoDBTicketDMMessageModel][]{ data-preview } from a [TicketDMMessageModel][].

        Args:
            model: The DM delivery record to convert.

        Returns:
            MongoDBTicketDMMessageModel: The converted DM delivery record.
        """
        return cls(message_id=model.message_id, recipient_id=model.recipient.user_id)


class MongoDBTicketMessageDocument(Document):
    """Beanie document for a ticket message.

    DM delivery records are stored as embedded [MongoDBTicketDMMessageModel][]{ data-preview }
    sub-documents, one per recipient.
    """

    bot_id: int
    """Discord application ID of the bot that owns this message."""
    ticket_key: str
    """Key of the parent ticket."""
    message_id: int
    """Discord message ID in the staff-side ticket channel."""
    dm_messages: list[MongoDBTicketDMMessageModel]
    """[MongoDBTicketDMMessageModel][]{ data-preview } delivery records, one per recipient."""
    author: Link[MongoDBTicketUserDocument]
    """[MongoDBTicketUserDocument][]{ data-preview } who sent the message."""
    content: str
    """Raw text content of the message."""
    created_at: UTCTimestamp
    """UTC-aware timestamp when the message was sent."""
    edited_at: UTCTimestamp | None = None
    """UTC-aware timestamp of the most recent edit (`None` if [`edited_by`][] is unset)."""
    edited_by: Link[MongoDBTicketUserDocument] | None = None
    """[MongoDBTicketUserDocument][]{ data-preview } who made the edit
    (`None` if [`edited_at`][] is unset).
    """
    deleted_at: UTCTimestamp | None = None
    """UTC-aware timestamp when the message was deleted (`None` if [`deleted_by`][] is unset)."""
    deleted_by: Link[MongoDBTicketUserDocument] | None = None
    """[MongoDBTicketUserDocument][]{ data-preview } who deleted the message (`None` if not deleted)."""
    type: TicketMessageType
    """Message type as a [TicketMessageType][]{ data-preview }."""

    class Settings:
        """Settings for MongoDB ticket message collection."""

        name = "TicketMessage"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("message_id", ASCENDING)],
                unique=True,
                name="ticket_message_unique",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("type", ASCENDING)],
                name="ticket_message_type_lookup",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("author", ASCENDING)],
                name="ticket_message_author_lookup",
            ),
        ]

    @classmethod
    async def put_model(cls, model: TicketMessageModel) -> MongoDBTicketMessageDocument:
        """Convert a [TicketMessageModel][]{ data-preview } to a document and insert it into MongoDB.

        Args:
            model: The ticket message model to persist.

        Returns:
            MongoDBTicketMessageDocument: The inserted document.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        user_docs = await MongoDBTicketUserDocument.put_many(
            model.author,
            *[dm.recipient for dm in model.dm_messages],
            *([model.edited_by] if model.edited_by else []),
            *([model.deleted_by] if model.deleted_by else []),
        )
        resolved: dict[int, Link[MongoDBTicketUserDocument]] = {
            doc.id: cast("Link[MongoDBTicketUserDocument]", cast("object", doc)) for doc in user_docs
        }

        doc = cls(
            bot_id=model.bot_id,
            ticket_key=model.ticket_key,
            message_id=model.message_id,
            dm_messages=[MongoDBTicketDMMessageModel.from_model(dm) for dm in model.dm_messages],
            author=resolved[model.author.user_id],
            content=model.content,
            created_at=model.created_at,
            edited_at=model.edited_at,
            edited_by=resolved[model.edited_by.user_id] if model.edited_by else None,
            deleted_at=model.deleted_at,
            deleted_by=resolved[model.deleted_by.user_id] if model.deleted_by else None,
            type=model.type,
        )
        try:
            await doc.insert()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist ticket message") from exc
        return doc
