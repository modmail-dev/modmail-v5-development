"""init

Revision ID: 3b425c85d526
Revises:
Create Date: 2026-04-09 18:51:18.383297
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import modmail.backends.sql.models.base

# revision identifiers, used by Alembic.
revision: str = "3b425c85d526"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "instance_lock",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("acquired_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=False),
        sa.Column("heartbeat_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bot_id", name=op.f("pk_instance_lock")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "settings",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("last_ran_version", sa.String(length=32), nullable=True),
        sa.Column("last_ran_locale", sa.String(length=16), nullable=True),
        sa.Column("last_slash_synced_version", sa.String(length=32), nullable=True),
        sa.Column("last_slash_minimum_permission_int", sa.Integer(), nullable=True),
        sa.Column("main_category_or_forum_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column("fallback_category_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column("log_channel_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column("storage_channel_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column(
            "status",
            sa.Enum("online", "idle", "dnd", "offline", name="statustype", create_constraint=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("bot_id", name=op.f("pk_settings")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "ticket_user",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("user_name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_ticket_user")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "activity",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "playing",
                "streaming",
                "listening",
                "watching",
                "custom",
                "competing",
                name="activitytype",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["settings.bot_id"],
            name=op.f("fk_activity_bot_id_settings"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bot_id", name=op.f("pk_activity")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "profile",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "profile_type",
            sa.Enum("user", "role", name="profiletype", create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "access_level",
            sa.Enum("everyone", "staff", "manager", "admin", name="accesslevel", create_constraint=True),
            nullable=True,
        ),
        sa.Column("tag", sa.String(length=128), nullable=True),
        sa.Column("color", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["settings.bot_id"],
            name=op.f("fk_profile_bot_id_settings"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bot_id", "profile_id", "profile_type", name=op.f("pk_profile")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "ticket",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("key", sa.String(length=12), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("created_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("closed_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=True),
        sa.Column("closed_by_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column("log_channel_message_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open", "closed_by_command", "closed_by_deletion", name="ticketstatus", create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("nsfw", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["closed_by_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_closed_by_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_created_by_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("bot_id", "key", name=op.f("pk_ticket")),
        sa.UniqueConstraint("bot_id", "channel_id", name="uq_ticket_channel"),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "permission_override",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "profile_type",
            # profiletype was already created with the profile table above; don't create it again.
            sa.Enum("user", "role", name="profiletype", create_constraint=True, create_type=False),
            nullable=False,
        ),
        sa.Column("command_name", sa.String(length=256), nullable=False),
        sa.Column(
            "override_value",
            sa.Enum("allow", "deny", name="permissionoverridevalue", create_constraint=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bot_id", "profile_id", "profile_type"],
            ["profile.bot_id", "profile.profile_id", "profile.profile_type"],
            name="fk_permission_override_profile",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "bot_id", "profile_id", "profile_type", "command_name", name=op.f("pk_permission_override")
        ),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "ticket_message",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("ticket_key", sa.String(length=12), nullable=False),
        sa.Column("message_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("author_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("content", sa.String(length=4096), nullable=False),
        sa.Column("created_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=False),
        sa.Column("edited_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=True),
        sa.Column("edited_by_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column("deleted_at", modmail.backends.sql.models.base.UTCTimestamp(), nullable=True),
        sa.Column("deleted_by_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "reply", "dm", "internal", "close", "sclose", name="ticketmessagetype", create_constraint=True
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_message_author_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bot_id", "ticket_key"],
            ["ticket.bot_id", "ticket.key"],
            name="fk_ticket_message_ticket",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_message_deleted_by_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_message_edited_by_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_message")),
        sa.UniqueConstraint("bot_id", "ticket_key", "message_id", name="uq_ticket_message"),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_index(
        "ix_ticket_message_author", "ticket_message", ["bot_id", "ticket_key", "author_id"], unique=False
    )
    op.create_index("ix_ticket_message_type", "ticket_message", ["bot_id", "ticket_key", "type"], unique=False)
    op.create_table(
        "ticket_recipient",
        sa.Column("bot_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("ticket_key", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_id", "ticket_key"],
            ["ticket.bot_id", "ticket.key"],
            name="fk_ticket_recipient_ticket",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_recipient_user_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("bot_id", "ticket_key", "user_id", name=op.f("pk_ticket_recipient")),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )
    op.create_index("ix_ticket_recipient_user_id", "ticket_recipient", ["user_id"], unique=False)
    op.create_table(
        "ticket_dm_message",
        sa.Column("message_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("ticket_message_ref_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["ticket_user.user_id"],
            name=op.f("fk_ticket_dm_message_recipient_id_ticket_user"),
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_message_ref_id"],
            ["ticket_message.id"],
            name=op.f("fk_ticket_dm_message_ticket_message_ref_id_ticket_message"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name=op.f("pk_ticket_dm_message")),
        sa.UniqueConstraint("ticket_message_ref_id", "recipient_id", name="uq_ticket_dm_message"),
        mariadb_charset="utf8mb4",
        mariadb_collate="utf8mb4_unicode_ci",
        mariadb_engine="InnoDB",
        mariadb_row_format="DYNAMIC",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
        mysql_row_format="DYNAMIC",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("ticket_dm_message")
    op.drop_index("ix_ticket_recipient_user_id", table_name="ticket_recipient")
    op.drop_table("ticket_recipient")
    op.drop_index("ix_ticket_message_type", table_name="ticket_message")
    op.drop_index("ix_ticket_message_author", table_name="ticket_message")
    op.drop_table("ticket_message")
    op.drop_table("permission_override")
    op.drop_table("ticket")
    op.drop_table("profile")
    op.drop_table("activity")
    op.drop_table("ticket_user")
    op.drop_table("settings")
    op.drop_table("instance_lock")
    # Drop PostgreSQL named enum types that were created alongside their tables.
    # On MySQL/MariaDB and SQLite these calls are no-ops (no named types exist).
    sa.Enum(name="ticketmessagetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticketstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="permissionoverridevalue").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="accesslevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="profiletype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="activitytype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="statustype").drop(op.get_bind(), checkfirst=True)
