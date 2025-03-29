from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def valid_config_dict() -> dict[str, Any]:
    """Provide a valid configuration dictionary for testing.

    Returns:
        A dictionary containing valid configuration data with bot token,
        server ID, database configuration, and other required fields.
    """
    return {
        "version": "1.0",
        "bot": {
            "token": "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz1234567890",
            "staff_server_id": 123456789012345,
        },
        "database_type": "sql",
        "sql_config": {"uri": "sqlite:///modmail-test.db"},
    }
