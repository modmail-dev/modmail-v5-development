"""MongoDB model conversion utilities for the modmail system.

This module provides utility functions for converting between
common models and MongoDB document models, handling the persistence
and retrieval of ticket and user data in the MongoDB database backend.
"""

from __future__ import annotations

from typing import cast

from beanie import Link, UpdateResponse
from beanie.odm.queries.update import UpdateOne

from ..common import TicketDMMessageModel, TicketMessageModel, TicketModel, TicketUserModel
from .models import (
    MongoDBTicketDMMessageModel,
    MongoDBTicketDocument,
    MongoDBTicketMessageDocument,
    MongoDBTicketUserDocument,
)

__all__ = [
    "get_or_create_ticket_user",
    "ticket_dm_message_model_to_document",
    "ticket_message_model_to_document",
    "ticket_model_to_document",
]


def ticket_user_model_to_document(ticket_user: TicketUserModel) -> MongoDBTicketUserDocument:
    """Converts a TicketUserModel to a MongoDBTicketUserDocument.

    Args:
        ticket_user: The TicketUserModel.

    Returns:
        The converted MongoDBTicketUserDocument.
    """
    return MongoDBTicketUserDocument(
        id=ticket_user.user_id,
        user_name=ticket_user.user_name,
    )


async def get_or_create_ticket_user(ticket_user: TicketUserModel) -> MongoDBTicketUserDocument:
    """Get or create ticket user document for a ticket user.

    Args:
        ticket_user: The ticket user model to get or create.

    Returns:
        The MongoDBTicketUserDocument object from the database.
    """
    ticket_user_document = ticket_user_model_to_document(ticket_user)
    return cast(
        MongoDBTicketUserDocument,
        await cast(
            UpdateOne,
            MongoDBTicketUserDocument.find_one(MongoDBTicketUserDocument.id == ticket_user.user_id).upsert(
                {"$set": ticket_user_document.model_dump(exclude={"id"})},
                on_insert=ticket_user_document,
                response_type=UpdateResponse.NEW_DOCUMENT,
            ),
        ),
    )


async def ticket_model_to_document(ticket: TicketModel) -> MongoDBTicketDocument:
    """Converts a TicketModel to a MongoDBTicketDocument.

    This function also creates the ticket users if they do not exist in the database.

    Args:
        ticket: The TicketModel to convert.

    Returns:
        The converted MongoDBTicketDocument.
    """
    # Since recipients, created_by, closed_by may be the same user,
    # we can cache them to avoid multiple database calls
    # Need to use Links with cast() to avoid type errors
    ticket_users_cache: dict[int, Link[MongoDBTicketUserDocument]] = {}

    recipients: list[Link[MongoDBTicketUserDocument]] = []
    for recipient in ticket.recipients:
        if recipient.user_id not in ticket_users_cache:
            ticket_users_cache[recipient.user_id] = cast(
                Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(recipient)
            )
        recipients.append(ticket_users_cache[recipient.user_id])

    if ticket.created_by.user_id not in ticket_users_cache:
        ticket_users_cache[ticket.created_by.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket.created_by)
        )
    created_by = ticket_users_cache[ticket.created_by.user_id]

    if ticket.closed_by and ticket.closed_by.user_id not in ticket_users_cache:
        ticket_users_cache[ticket.closed_by.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket.closed_by)
        )
    closed_by = ticket_users_cache[ticket.closed_by.user_id] if ticket.closed_by else None

    return MongoDBTicketDocument(
        bot_id=ticket.bot_id,
        key=ticket.key,
        recipients=recipients,
        channel_id=ticket.channel_id,
        created_at=ticket.created_at,
        created_by=created_by,
        closed_at=ticket.closed_at,
        closed_by=closed_by,
        status=ticket.status,
        title=ticket.title,
        nsfw=ticket.nsfw,
    )


async def ticket_dm_message_model_to_document(
    ticket_dm_message: TicketDMMessageModel,
    *,
    ticket_users_cache: dict[int, Link[MongoDBTicketUserDocument]] | None = None,
) -> MongoDBTicketDMMessageModel:
    """Converts a TicketDMMessageModel to a MongoDBTicketDMMessageDocument.

    This function also creates the ticket user if it does not exist in the database.

    Args:
        ticket_dm_message: The TicketDMMessageModel to convert.
        ticket_users_cache: Optional cache for ticket users to avoid multiple database calls.

    Returns:
        The converted MongoDBTicketDMMessageDocument.
    """
    if ticket_users_cache is None:
        ticket_users_cache = {}

    # Ensure the recipient user exists in DB
    if ticket_dm_message.recipient.user_id not in ticket_users_cache:
        ticket_users_cache[ticket_dm_message.recipient.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket_dm_message.recipient)
        )

    return MongoDBTicketDMMessageModel(
        message_id=ticket_dm_message.message_id,
        recipient_id=ticket_dm_message.recipient.user_id,
    )


async def ticket_message_model_to_document(ticket_message: TicketMessageModel) -> MongoDBTicketMessageDocument:
    """Converts a TicketMessageModel to a MongoDBTicketMessageDocument.

    This function also creates the ticket users if they do not exist in the database.

    Args:
        ticket_message: The TicketMessageModel to convert.

    Returns:
        The converted MongoDBTicketMessageDocument.
    """
    ticket_users_cache: dict[int, Link[MongoDBTicketUserDocument]] = {}

    dm_messages: list[MongoDBTicketDMMessageModel] = []
    for dm_message in ticket_message.dm_messages:
        dm_messages.append(
            await ticket_dm_message_model_to_document(dm_message, ticket_users_cache=ticket_users_cache),
        )

    if ticket_message.author.user_id not in ticket_users_cache:
        ticket_users_cache[ticket_message.author.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket_message.author)
        )
    author = ticket_users_cache[ticket_message.author.user_id]

    if ticket_message.edited_by and ticket_message.edited_by.user_id not in ticket_users_cache:
        ticket_users_cache[ticket_message.edited_by.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket_message.edited_by)
        )
    edited_by = ticket_message.edited_by and ticket_users_cache[ticket_message.edited_by.user_id]

    if ticket_message.deleted_by and ticket_message.deleted_by.user_id not in ticket_users_cache:
        ticket_users_cache[ticket_message.deleted_by.user_id] = cast(
            Link[MongoDBTicketUserDocument], await get_or_create_ticket_user(ticket_message.deleted_by)
        )
    deleted_by = ticket_message.deleted_by and ticket_users_cache[ticket_message.deleted_by.user_id]

    return MongoDBTicketMessageDocument(
        bot_id=ticket_message.bot_id,
        ticket_key=ticket_message.ticket_key,
        message_id=ticket_message.message_id,
        dm_messages=dm_messages,
        author=author,
        content=ticket_message.content,
        created_at=ticket_message.created_at,
        edited_at=ticket_message.edited_at,
        edited_by=edited_by,
        deleted_at=ticket_message.deleted_at,
        deleted_by=deleted_by,
        type=ticket_message.type,
    )
