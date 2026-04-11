"""SQLAlchemy model for the bot settings table."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common import SettingsModel
from modmail.enum import StatusType

from .activity_model import SQLActivityTable
from .base import Snowflake, SQLBase

__all__ = ["SQLSettingsTable"]


class SQLSettingsTable(SQLBase):
    """SQL model for the bot settings table.

    All fields except [`bot_id`][] are optional, where `None` means the value has never been set.
    The [`activity`][] field is stored in a separate [SQLActivityTable][]{ data-preview } row.

    **Primary key:** [`bot_id`][]
    """

    __tablename__ = "settings"

    bot_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord application ID of the bot these settings belong to."""
    last_ran_version: Mapped[str | None] = mapped_column(String(32))
    """Bot version string from the last startup, e.g. `"v1.2.3"` (`None` on first run)."""
    last_ran_locale: Mapped[str | None] = mapped_column(String(16))
    """BCP-47 locale code active on the previous run, e.g. `"en"` (`None` on first run)."""
    last_slash_synced_version: Mapped[str | None] = mapped_column(String(32))
    """Bot version when slash commands were last synced to Discord (`None` if never synced)."""
    last_slash_minimum_permission_int: Mapped[int | None]
    """Default member permission integer from the last slash-command sync (`None` if never synced)."""
    main_category_or_forum_id: Mapped[Snowflake | None]
    """Discord category or forum channel ID where new ticket channels are created (`None` if unset)."""
    fallback_category_id: Mapped[Snowflake | None]
    """Discord category ID used when the main category is full or unavailable (`None` if unset)."""
    log_channel_id: Mapped[Snowflake | None]
    """Discord channel ID where closed-ticket summaries are posted (`None` if unset)."""
    storage_channel_id: Mapped[Snowflake | None]
    """Discord channel ID used for internal file storage (`None` if unset)."""
    status: Mapped[StatusType | None]
    """Bot presence status shown in Discord as a [StatusType][]{ data-preview } (`None` if unset)."""
    activity: Mapped[SQLActivityTable | None] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, single_parent=True, lazy="joined"
    )
    """Bot activity shown in Discord as an [SQLActivityTable][]{ data-preview } (`None` if unset)."""

    @classmethod
    def from_model(cls, model: SettingsModel) -> SQLSettingsTable:
        """Construct a [SQLSettingsTable][]{ data-preview } from a [SettingsModel][].

        The [`activity`][] relationship is managed separately via [SQLActivityTable][]{ data-preview }.

        Args:
            model: The settings model to convert.

        Returns:
            SQLSettingsTable: An unsaved row ready to merge into a session.
        """
        return cls(**model.model_dump(exclude={"activity"}))

    def to_model(self) -> SettingsModel:
        """Convert this row to a [SettingsModel][]{ data-preview }.

        Returns:
            SettingsModel: The converted common settings model.
        """
        return SettingsModel.model_validate(self)
