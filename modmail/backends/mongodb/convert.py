"""MongoDB model conversion utilities for the modmail system.

This module provides utility functions for converting between
common models and MongoDB document models, handling the persistence
and retrieval of thread and user data in the MongoDB database backend.
"""

from __future__ import annotations

from typing import cast

from beanie import Link, UpdateResponse
from beanie.odm.queries.update import UpdateOne

from ..common import ThreadDMMessageModel, ThreadMessageModel, ThreadModel, ThreadUserModel
from .models import (
    MongoDBThreadDMMessageModel,
    MongoDBThreadDocument,
    MongoDBThreadMessageDocument,
    MongoDBThreadUserDocument,
)

__all__ = [
    "get_or_create_thread_user",
    "thread_dm_message_model_to_document",
    "thread_message_model_to_document",
    "thread_model_to_document",
]


def thread_user_model_to_document(thread_user: ThreadUserModel) -> MongoDBThreadUserDocument:
    """Converts a ThreadUserModel to a MongoDBThreadUserDocument.

    Args:
        thread_user: The ThreadUserModel.

    Returns:
        The converted MongoDBThreadUserDocument.
    """
    return MongoDBThreadUserDocument(
        id=thread_user.user_id,
        user_name=thread_user.user_name,
    )


async def get_or_create_thread_user(thread_user: ThreadUserModel) -> MongoDBThreadUserDocument:
    """Get or create thread user document for a thread user.

    Args:
        thread_user: The thread user model to get or create.

    Returns:
        The MongoDBThreadUserDocument object from the database.
    """
    thread_user_document = thread_user_model_to_document(thread_user)
    return cast(
        MongoDBThreadUserDocument,
        await cast(
            UpdateOne,
            MongoDBThreadUserDocument.find_one(MongoDBThreadUserDocument.id == thread_user.user_id).upsert(
                {"$set": thread_user_document.model_dump(exclude={"id"})},
                on_insert=thread_user_document,
                response_type=UpdateResponse.NEW_DOCUMENT,
            ),
        ),
    )


async def thread_model_to_document(thread: ThreadModel) -> MongoDBThreadDocument:
    """Converts a ThreadModel to a MongoDBThreadDocument.

    This function also creates the thread users if they do not exist in the database.

    Args:
        thread: The ThreadModel to convert.

    Returns:
        The converted MongoDBThreadDocument.
    """
    # Since recipients, created_by, closed_by may be the same user,
    # we can cache them to avoid multiple database calls
    # Need to use Links with cast() to avoid type errors
    thread_users_cache: dict[int, Link[MongoDBThreadUserDocument]] = {}

    recipients: list[Link[MongoDBThreadUserDocument]] = []
    for recipient in thread.recipients:
        if recipient.user_id not in thread_users_cache:
            thread_users_cache[recipient.user_id] = cast(
                Link[MongoDBThreadUserDocument], await get_or_create_thread_user(recipient)
            )
        recipients.append(thread_users_cache[recipient.user_id])

    if thread.created_by.user_id not in thread_users_cache:
        thread_users_cache[thread.created_by.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread.created_by)
        )
    created_by = thread_users_cache[thread.created_by.user_id]

    if thread.closed_by and thread.closed_by.user_id not in thread_users_cache:
        thread_users_cache[thread.closed_by.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread.closed_by)
        )
    closed_by = thread_users_cache[thread.closed_by.user_id] if thread.closed_by else None

    return MongoDBThreadDocument(
        bot_id=thread.bot_id,
        key=thread.key,
        recipients=recipients,
        channel_id=thread.channel_id,
        created_at=thread.created_at,
        created_by=created_by,
        closed_at=thread.closed_at,
        closed_by=closed_by,
        status=thread.status,
        title=thread.title,
        nsfw=thread.nsfw,
    )


async def thread_dm_message_model_to_document(
    thread_dm_message: ThreadDMMessageModel,
    *,
    thread_users_cache: dict[int, Link[MongoDBThreadUserDocument]] | None = None,
) -> MongoDBThreadDMMessageModel:
    """Converts a ThreadDMMessageModel to a MongoDBThreadDMMessageDocument.

    This function also creates the thread user if it does not exist in the database.

    Args:
        thread_dm_message: The ThreadDMMessageModel to convert.
        thread_users_cache: Optional cache for thread users to avoid multiple database calls.

    Returns:
        The converted MongoDBThreadDMMessageDocument.
    """
    if thread_users_cache is None:
        thread_users_cache = {}

    # Ensure the recipient user exists in DB
    if thread_dm_message.recipient.user_id not in thread_users_cache:
        thread_users_cache[thread_dm_message.recipient.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread_dm_message.recipient)
        )

    return MongoDBThreadDMMessageModel(
        message_id=thread_dm_message.message_id,
        recipient_id=thread_dm_message.recipient.user_id,
    )


async def thread_message_model_to_document(thread_message: ThreadMessageModel) -> MongoDBThreadMessageDocument:
    """Converts a ThreadMessageModel to a MongoDBThreadMessageDocument.

    This function also creates the thread users if they do not exist in the database.

    Args:
        thread_message: The ThreadMessageModel to convert.

    Returns:
        The converted MongoDBThreadMessageDocument.
    """
    thread_users_cache: dict[int, Link[MongoDBThreadUserDocument]] = {}

    dm_messages: list[MongoDBThreadDMMessageModel] = []
    for dm_message in thread_message.dm_messages:
        dm_messages.append(
            await thread_dm_message_model_to_document(dm_message, thread_users_cache=thread_users_cache),
        )

    if thread_message.author.user_id not in thread_users_cache:
        thread_users_cache[thread_message.author.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread_message.author)
        )
    author = thread_users_cache[thread_message.author.user_id]

    if thread_message.edited_by and thread_message.edited_by.user_id not in thread_users_cache:
        thread_users_cache[thread_message.edited_by.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread_message.edited_by)
        )
    edited_by = thread_message.edited_by and thread_users_cache[thread_message.edited_by.user_id]

    if thread_message.deleted_by and thread_message.deleted_by.user_id not in thread_users_cache:
        thread_users_cache[thread_message.deleted_by.user_id] = cast(
            Link[MongoDBThreadUserDocument], await get_or_create_thread_user(thread_message.deleted_by)
        )
    deleted_by = thread_message.deleted_by and thread_users_cache[thread_message.deleted_by.user_id]

    return MongoDBThreadMessageDocument(
        bot_id=thread_message.bot_id,
        thread_key=thread_message.thread_key,
        message_id=thread_message.message_id,
        dm_messages=dm_messages,
        author=author,
        content=thread_message.content,
        created_at=thread_message.created_at,
        edited_at=thread_message.edited_at,
        edited_by=edited_by,
        deleted_at=thread_message.deleted_at,
        deleted_by=deleted_by,
        type=thread_message.type,
    )
