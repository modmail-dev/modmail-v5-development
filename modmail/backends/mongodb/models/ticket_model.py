"""Beanie document model for tickets in MongoDB."""

from __future__ import annotations

from typing import cast

import pymongo.errors
from beanie import Document, Link
from pymongo import ASCENDING, IndexModel

from modmail.backends.common import TicketModel
from modmail.enum import TicketStatus
from modmail.errors import DatabaseOperationError, TicketCreationError

from .base import BSON_ENCODERS, UTCTimestamp
from .ticket_user_model import MongoDBTicketUserDocument

__all__ = ["MongoDBTicketDocument"]


class MongoDBTicketDocument(Document):
    """Beanie document for a ticket.

    Two unique indexes are maintained: ([`bot_id`][], [`key`][]) for key-based lookup
    and ([`bot_id`][], [`channel_id`][]) to enforce one ticket per Discord channel.
    Recipients and user references are stored as Beanie `Link` fields.
    """

    bot_id: int
    """Discord application ID of the bot that owns this ticket."""
    key: str
    """Random 12-character alphanumeric ticket identifier."""
    recipients: list[Link[MongoDBTicketUserDocument]]
    """Non-staff users who are parties to this ticket."""
    channel_id: int
    """Discord channel or forum-thread ID where staff interact."""
    created_at: UTCTimestamp
    """UTC-aware timestamp when the ticket was opened."""
    created_by: Link[MongoDBTicketUserDocument]
    """[MongoDBTicketUserDocument][]{ data-preview } who initiated the ticket."""
    closed_at: UTCTimestamp | None = None
    """UTC-aware timestamp when closed (`None` if [`closed_by`][] is unset)."""
    closed_by: Link[MongoDBTicketUserDocument] | None = None
    """[MongoDBTicketUserDocument][]{ data-preview } who closed the ticket
    (`None` if [`closed_at`][] is unset).
    """
    log_channel_message_id: int | None = None
    """Summary message ID posted to the log channel on closure (`None` if not yet posted)."""
    status: TicketStatus
    """Current lifecycle state as a [TicketStatus][]{ data-preview }."""
    title: str | None = None
    """Human-readable title for the ticket (`None` if unset)."""
    nsfw: bool = False
    """Whether the ticket channel is marked as age-restricted in Discord."""

    class Settings:
        """Settings for MongoDB ticket collection."""

        name = "Ticket"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("key", ASCENDING)],
                unique=True,
                name="ticket_unique",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("channel_id", ASCENDING)],
                unique=True,
                name="ticket_channel_unique",
            ),
        ]

    def to_model(self) -> TicketModel:
        """Convert this document to a common [TicketModel][]{ data-preview }.

        All `Link` fields must already be resolved (i.e. the document must have
        been fetched with `fetch_links=True`).

        Returns:
            TicketModel: The converted common ticket model.

        Raises:
            RuntimeError: If any linked user field has not been resolved.
        """
        if any(isinstance(cast("object", r), Link) for r in self.recipients):
            raise RuntimeError("recipients links not resolved; fetch with fetch_links=True")
        if isinstance(cast("object", self.created_by), Link):
            raise RuntimeError("created_by link not resolved; fetch with fetch_links=True")
        if isinstance(cast("object", self.closed_by), Link):
            raise RuntimeError("closed_by link not resolved; fetch with fetch_links=True")

        recipients = [cast("MongoDBTicketUserDocument", cast("object", r)).to_model() for r in self.recipients]
        created_by = cast("MongoDBTicketUserDocument", cast("object", self.created_by)).to_model()
        closed_by = (
            cast("MongoDBTicketUserDocument", cast("object", self.closed_by)).to_model()
            if self.closed_by
            else None
        )

        return TicketModel(
            bot_id=self.bot_id,
            key=self.key,
            recipients=recipients,
            channel_id=self.channel_id,
            created_at=self.created_at,
            created_by=created_by,
            status=self.status,
            closed_by=closed_by,
            closed_at=self.closed_at,
            log_channel_message_id=self.log_channel_message_id,
            title=self.title,
            nsfw=self.nsfw,
        )

    @classmethod
    async def put_model(cls, model: TicketModel) -> MongoDBTicketDocument:
        """Convert a [TicketModel][]{ data-preview } to a document and insert it into MongoDB.

        Args:
            model: The ticket model to persist.

        Returns:
            MongoDBTicketDocument: The inserted document.

        Raises:
            TicketCreationError: If a ticket with the same key already exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        user_docs = await MongoDBTicketUserDocument.put_many(
            *model.recipients,
            model.created_by,
            *([model.closed_by] if model.closed_by else []),
        )
        resolved: dict[int, Link[MongoDBTicketUserDocument]] = {
            doc.id: cast("Link[MongoDBTicketUserDocument]", cast("object", doc)) for doc in user_docs
        }

        doc = cls(
            bot_id=model.bot_id,
            key=model.key,
            recipients=[resolved[r.user_id] for r in model.recipients],
            channel_id=model.channel_id,
            created_at=model.created_at,
            created_by=resolved[model.created_by.user_id],
            closed_at=model.closed_at,
            closed_by=resolved[model.closed_by.user_id] if model.closed_by else None,
            log_channel_message_id=model.log_channel_message_id,
            status=model.status,
            title=model.title,
            nsfw=model.nsfw,
        )
        try:
            await doc.insert()
        except pymongo.errors.DuplicateKeyError as exc:
            key_pattern = set((exc.details or {}).get("keyPattern", {}).keys())
            if key_pattern == {"bot_id", "key"}:
                raise TicketCreationError("A ticket with this key already exists") from exc
            raise DatabaseOperationError("Failed to persist ticket") from exc
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist ticket") from exc
        return doc
