"""
modmail.backends.common.models.permission_override_model
=======================================================-
This module defines the model for permission overrides.
It provides a structure for command-specific permission configurations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import PermissionGroupType, PermissionOverrideType

__all__ = ["PermissionOverride"]


class PermissionOverride(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    group_id: int
    group_type: PermissionGroupType

    override: PermissionOverrideType
