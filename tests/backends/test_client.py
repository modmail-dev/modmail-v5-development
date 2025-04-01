from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from concurrent.futures import ProcessPoolExecutor
from typing import cast

import motor.motor_asyncio
import pymongo.errors
import pytest
from pydantic import SecretStr
from pytest_mock import MockFixture
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from modmail.backends.common import DBClientBase, Profile
from modmail.backends.mongodb import MongoDBClient
from modmail.backends.mongodb.models import MongoDBActivityModel, MongoDBProfileDocument, MongoDBSettingsDocument
from modmail.backends.sql import SQLClient
from modmail.backends.sql.migration import rollback_migration
from modmail.backends.sql.models import (
    SQLActivityTable,
    SQLPermissionOverrideTable,
    SQLProfileTable,
    SQLSettingsTable,
)
from modmail.config import load_config
from modmail.config.models import Config, MongoDBDatabaseConfig, SQLDatabaseConfig
from modmail.enum import AccessLevel, ActivityType, PermissionOverrideValue, ProfileType, StatusType
from modmail.errors import DatabaseConnectionError


@pytest.fixture(scope="module", params=["sqlite"], ids=["sqlite"])
def sql_config(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Config:
    """Load configuration for SQL database tests.

    Creates a module-scoped fixture that configures and returns a Config object
    with SQLite database settings for testing.

    Args:
        request: The pytest request object containing test parameters.
        tmp_path_factory: Factory for creating temporary directories.

    Returns:
        A Config object configured for SQLite testing.
    """
    config = load_config("config.yaml.example")  # Use the sample config file for testing
    assert config is not None, "Failed to load config"
    config.database_type = "sql"

    if request.param == "sqlite":
        # Create a single temporary SQLite database file for the entire test session
        db_path = tmp_path_factory.mktemp("modmail-sqlite-test") / "modmail-test.db"
        config.sql_config = SQLDatabaseConfig(uri=cast(SecretStr, f"sqlite+aiosqlite:////{db_path}"))

    return config


@pytest.fixture(scope="module")
def mongodb_config() -> Config:
    """Load configuration for MongoDB database tests.

    Creates a module-scoped fixture that configures and returns a Config object
    with MongoDB database settings for testing.

    Returns:
        A Config object configured for MongoDB testing.
    """
    config = load_config("config.yaml.example")
    assert config is not None, "Failed to load config"
    config.database_type = "mongodb"
    config.mongodb_config = MongoDBDatabaseConfig(
        uri=cast(SecretStr, os.environ["TEST_MONGODB_URI"]),
        database="_modmail-test",
    )
    return config


@pytest.fixture(scope="module", params=["sqlite"], ids=["sqlite"])
async def sql_client_session(
    request: pytest.FixtureRequest, sql_config: Config
) -> AsyncGenerator[SQLClient, None]:
    """Create a module-scoped SQL client for testing.

    Establishes a connection to the test database, cleans it before testing,
    and performs cleanup after all tests are complete.

    Args:
        request: The pytest request object containing test parameters.
        sql_config: The SQL database configuration.

    Yields:
        A connected SQLClient instance for test usage.
    """
    assert sql_config.sql_config is not None, "SQL config is None"

    # Drop the test database to ensure a clean state
    with ProcessPoolExecutor() as pool:
        await asyncio.get_running_loop().run_in_executor(
            pool, rollback_migration, sql_config.sql_config.uri.get_secret_value()
        )

    client = SQLClient(sql_config)
    await client.connect()

    yield client
    await client.disconnect()

    # Ensure the database is cleaned up after all tests
    with ProcessPoolExecutor() as pool:
        await asyncio.get_running_loop().run_in_executor(
            pool, rollback_migration, sql_config.sql_config.uri.get_secret_value()
        )


@pytest.fixture(scope="module")
async def mongodb_client_session(mongodb_config: Config) -> AsyncGenerator[MongoDBClient, None]:
    """Create a module-scoped MongoDB client for testing.

    Establishes a connection to the test MongoDB database, drops the database
    for a clean testing environment, and cleans up after testing.

    Args:
        mongodb_config: The MongoDB database configuration.

    Yields:
        A connected MongoDBClient instance for test usage.
    """
    assert mongodb_config.mongodb_config is not None, "MongoDB config is None"

    # Drop the test database to ensure a clean state
    motor_db = motor.motor_asyncio.AsyncIOMotorClient(mongodb_config.mongodb_config.uri.get_secret_value())  # pyright: ignore [reportUnknownVariableType]
    await motor_db.drop_database(mongodb_config.mongodb_config.database)
    motor_db.close()

    client = MongoDBClient(mongodb_config)
    await client.connect()

    yield client
    await client.disconnect()

    # Ensure the database is cleaned up after all tests
    motor_db = motor.motor_asyncio.AsyncIOMotorClient(mongodb_config.mongodb_config.uri.get_secret_value())  # pyright: ignore [reportUnknownVariableType]
    await motor_db.drop_database(mongodb_config.mongodb_config.database)
    motor_db.close()


@pytest.fixture
async def sql_client(sql_client_session: SQLClient) -> AsyncGenerator[SQLClient, None]:
    """Provide a function-scoped SQL client fixture for individual tests.

    Creates a clean testing environment by clearing data before each test
    and restoring the initial state afterward. This ensures test isolation.

    Args:
        sql_client_session: The session-scoped SQL client.

    Yields:
        The SQLClient instance with a clean database state for testing.
    """
    assert sql_client_session._async_session is not None

    async with sql_client_session._async_session() as session:
        # Clear any test data from previous tests
        await session.execute(delete(SQLSettingsTable))
        await session.execute(delete(SQLProfileTable))
        await session.execute(delete(SQLPermissionOverrideTable))
        await session.execute(delete(SQLActivityTable))
        await session.commit()

    # Initialize settings
    await sql_client_session.sync_settings()
    await sql_client_session.sync_profiles()

    yield sql_client_session

    async with sql_client_session._async_session() as session:
        # Clear any test data from previous tests
        await session.execute(delete(SQLSettingsTable))
        await session.execute(delete(SQLProfileTable))
        await session.execute(delete(SQLPermissionOverrideTable))
        await session.execute(delete(SQLActivityTable))
        await session.commit()

    # Re-sync the client to reset the in-memory state
    await sql_client_session.sync_settings()
    await sql_client_session.sync_profiles()


@pytest.fixture
async def mongodb_client(mongodb_client_session: MongoDBClient) -> AsyncGenerator[MongoDBClient, None]:
    """Provide a function-scoped MongoDB client fixture for individual tests.

    Creates a clean testing environment by clearing collections before each test
    and restoring the initial state afterward. This ensures test isolation.

    Args:
        mongodb_client_session: The session-scoped MongoDB client.

    Yields:
        The MongoDBClient instance with a clean database state for testing.
    """
    # Clear data before test
    motor_client = mongodb_client_session._client
    assert motor_client is not None, "Failed to connect to MongoDB"
    assert mongodb_client_session._config.mongodb_config is not None, "MongoDB config is None"
    db = motor_client.get_database(mongodb_client_session._config.mongodb_config.database)

    await db[MongoDBProfileDocument.Settings.name].delete_many({})
    await db[MongoDBSettingsDocument.Settings.name].delete_many({})

    # Initialize settings
    await mongodb_client_session.sync_settings()
    await mongodb_client_session.sync_profiles()

    yield mongodb_client_session

    # Clean up after test - delete data but keep collections
    await db[MongoDBProfileDocument.Settings.name].delete_many({})
    await db[MongoDBSettingsDocument.Settings.name].profiles.delete_many({})

    # Reset in-memory state
    await mongodb_client_session.sync_settings()
    await mongodb_client_session.sync_profiles()


@pytest.fixture(params=["sqlite", "mongodb"], ids=["sqlite", "mongodb"])
def client(request: pytest.FixtureRequest, sql_client: SQLClient, mongodb_client: MongoDBClient) -> DBClientBase:
    """Provide a database client for testing across different database backends.

    This parameterized fixture allows running the same tests against multiple
    database implementations to ensure consistent behavior.

    Args:
        request: The pytest request object containing the database parameter.
        sql_client: The configured SQL client.
        mongodb_client: The configured MongoDB client.

    Returns:
        A database client implementation (either SQL or MongoDB).
    """
    if request.param == "sqlite":
        return sql_client
    return mongodb_client


def test_settings_initialization(client: DBClientBase) -> None:
    """Test that settings are properly initialized upon connection."""
    # The fixture already creates and connects the client
    assert client.settings_model is not None
    assert client.settings_model.bot_id == client._config.bot.bot_id


@pytest.mark.asyncio
async def test_update_settings(client: DBClientBase) -> None:
    """Test updating various settings."""
    # Update basic settings
    new_status = StatusType.dnd
    new_category_id = 123456789012345

    await client.update_settings(status=new_status, main_category_id=new_category_id)

    # Verify settings were updated
    assert client.settings_model.status == new_status
    assert client.settings_model.main_category_id == new_category_id

    await client.sync_settings()

    # Verify settings persist after sync
    assert client.settings_model.status == new_status
    assert client.settings_model.main_category_id == new_category_id

    # Reset settings to default
    await client.update_settings(status=None, main_category_id=None)

    assert client.settings_model.status is None
    assert client.settings_model.main_category_id is None

    # Update activity
    activity_data = {"type": ActivityType.streaming, "name": "Test Activity", "url": "https://example.com"}

    await client.update_settings(activity=activity_data)

    # Verify activity was updated
    assert client.settings_model.activity is not None
    assert client.settings_model.activity.type == ActivityType.streaming
    assert client.settings_model.activity.name == "Test Activity"
    assert client.settings_model.activity.url == "https://example.com"

    await client.sync_settings()

    # Verify activity persists after sync
    assert client.settings_model.activity is not None
    assert client.settings_model.activity.type == ActivityType.streaming
    assert client.settings_model.activity.name == "Test Activity"
    assert client.settings_model.activity.url == "https://example.com"

    # Test removing activity
    await client.update_settings(activity=None)
    assert client.settings_model.activity is None


@pytest.mark.asyncio
async def test_sync_settings_sql(sql_client: SQLClient) -> None:
    """Test syncing settings from the database."""
    # Update settings directly in the database
    assert sql_client._async_session is not None

    new_status = StatusType.offline

    async with sql_client._async_session() as session:
        query = select(SQLSettingsTable).where(SQLSettingsTable.bot_id == sql_client._config.bot.bot_id)
        result = await session.execute(query)
        settings_table = result.scalar_one()
        settings_table.status = new_status
        await session.commit()

    # Sync settings and verify
    await sql_client.sync_settings()
    assert sql_client.settings_model.status == new_status


@pytest.mark.asyncio
async def test_sync_settings_mongodb(mongodb_client: MongoDBClient) -> None:
    """Test syncing settings from the MongoDB database."""
    # Update settings directly in the database
    new_status = StatusType.offline

    # Get the current settings document
    settings_document = await MongoDBSettingsDocument.find_one(
        MongoDBSettingsDocument.bot_id == mongodb_client._config.bot.bot_id
    )
    assert settings_document is not None

    # Update the status and save
    settings_document.status = new_status
    await settings_document.replace()

    # Sync settings and verify
    await mongodb_client.sync_settings()
    assert mongodb_client.settings_model.status == new_status


@pytest.mark.asyncio
async def test_profile_operations(client: DBClientBase) -> None:
    """Test profile CRUD operations."""
    # Test profile creation
    profile_id = 12345678901234567
    profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=AccessLevel.everyone,
        permission_overrides={"test_command": PermissionOverrideValue.allow},
        tag="Test User",
    )

    await client.update_profile(profile)

    # Test getting profile
    retrieved_profile = client.get_profile(profile_id, ProfileType.user)
    assert retrieved_profile is not None
    assert retrieved_profile.profile_id == profile_id
    assert retrieved_profile.profile_type == ProfileType.user
    assert retrieved_profile.access_level == AccessLevel.everyone

    # Retrieve the profile again to ensure it still exists after sync
    await client.sync_profiles()
    retrieved_profile = client.get_profile(profile_id, ProfileType.user)
    assert retrieved_profile is not None
    assert retrieved_profile.tag == "Test User"
    assert retrieved_profile.colour is None
    assert retrieved_profile.permission_overrides["test_command"] == PermissionOverrideValue.allow

    # Test updating profile
    updated_profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=None,
        permission_overrides={},
        tag="Updated User",
        colour=0x00FF00,
    )

    await client.update_profile(updated_profile)

    # Verify the update
    retrieved_updated_profile = client.get_profile(profile_id, ProfileType.user)
    assert retrieved_updated_profile is not None
    assert retrieved_updated_profile.access_level is None
    assert retrieved_updated_profile.tag == "Updated User"

    # Retrieve the profile again to ensure it still exists after sync
    await client.sync_profiles()
    retrieved_updated_profile = client.get_profile(profile_id, ProfileType.user)
    assert retrieved_updated_profile is not None
    assert retrieved_updated_profile.colour == 0x00FF00
    assert retrieved_updated_profile.permission_overrides == {}

    # Test deleting profile
    await client.delete_profile(profile_id)
    assert client.get_profile(profile_id, ProfileType.user) is None
    await client.sync_profiles()  # Sync again to ensure deletion is reflected
    assert client.get_profile(profile_id, ProfileType.user) is None


@pytest.mark.asyncio
async def test_multiple_profile_types(client: DBClientBase) -> None:
    """Test that user and role profiles can coexist with the same ID."""
    profile_id1 = 12345678901234568
    profile_id2 = 12345678901234569

    # Create user profile
    user_profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id1,
        profile_type=ProfileType.user,
        access_level=AccessLevel.staff,
        permission_overrides={},
        tag="Test User",
        colour=None,
    )

    # Create role profile with same ID
    role_profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id2,
        profile_type=ProfileType.role,
        access_level=AccessLevel.admin,
        permission_overrides={"cmd1": PermissionOverrideValue.allow},
        tag="Test Role",
        colour=0xFFFF00,
    )

    # Save both profiles
    await client.update_profile(user_profile)
    await client.update_profile(role_profile)
    await client.sync_profiles()  # Sync to ensure both profiles are saved

    # Retrieve and verify both still exist and are different
    retrieved_user = client.get_profile(profile_id1, ProfileType.user)
    retrieved_role = client.get_profile(profile_id2, ProfileType.role)

    assert retrieved_user is not None
    assert retrieved_role is not None
    assert retrieved_user.tag == "Test User"
    assert retrieved_role.tag == "Test Role"
    assert len(client.profiles) == 2
    assert retrieved_user in client.profiles
    assert retrieved_role in client.profiles
    await client.delete_profile(profile_id1)
    await client.delete_profile(profile_id2)


@pytest.mark.asyncio
async def test_permission_override_cascades_sql(sql_client: SQLClient) -> None:
    """Test that permission overrides are deleted when a profile is deleted."""
    profile_id = 12345678901234570

    # Create profile with overrides
    profile = Profile(
        bot_id=sql_client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=AccessLevel.everyone,
        permission_overrides={"cmd1": PermissionOverrideValue.allow, "cmd2": PermissionOverrideValue.deny},
    )

    await sql_client.update_profile(profile)

    # Check overrides were created
    assert sql_client._async_session is not None
    async with sql_client._async_session() as session:
        query = select(SQLPermissionOverrideTable).where(
            and_(
                (SQLPermissionOverrideTable.bot_id == sql_client._config.bot.bot_id),
                (SQLPermissionOverrideTable.profile_id == profile_id),
            )
        )
        result = await session.execute(query)
        overrides = result.scalars().all()
        assert len(overrides) == 2

    # Delete the profile
    await sql_client.delete_profile(profile_id)

    # Verify overrides were deleted
    async with sql_client._async_session() as session:
        query = select(SQLPermissionOverrideTable).where(
            and_(
                (SQLPermissionOverrideTable.bot_id == sql_client._config.bot.bot_id),
                (SQLPermissionOverrideTable.profile_id == profile_id),
            )
        )
        result = await session.execute(query)
        overrides = result.scalars().all()
        assert len(overrides) == 0


@pytest.mark.asyncio
async def test_permission_override_cascades_mongodb(mongodb_client: MongoDBClient) -> None:
    """Test that permission overrides are properly updated when a profile is deleted in MongoDB."""
    profile_id = 12345678901234570

    # Create profile with overrides
    profile = Profile(
        bot_id=mongodb_client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=AccessLevel.everyone,
        permission_overrides={"cmd1": PermissionOverrideValue.allow, "cmd2": PermissionOverrideValue.deny},
    )

    await mongodb_client.update_profile(profile)

    # Check that profile exists with overrides
    retrieved_profile = mongodb_client.get_profile(profile_id, ProfileType.user)
    assert retrieved_profile is not None
    assert len(retrieved_profile.permission_overrides) == 2

    # Find the profile document directly in the database
    profile_document = await MongoDBProfileDocument.find_one(
        MongoDBProfileDocument.bot_id == mongodb_client._config.bot.bot_id,
        MongoDBProfileDocument.profile_id == profile_id,
        MongoDBProfileDocument.profile_type == ProfileType.user,
    )
    assert profile_document is not None
    assert len(profile_document.permission_overrides) == 2

    # Delete the profile
    await mongodb_client.delete_profile(profile_id)

    # Verify profile is gone including permission overrides
    assert mongodb_client.get_profile(profile_id, ProfileType.user) is None
    await mongodb_client.sync_profiles()  # Force sync from database
    assert mongodb_client.get_profile(profile_id, ProfileType.user) is None


@pytest.mark.asyncio
async def test_activity_cascades_sql(sql_client: SQLClient) -> None:
    """Test that activity is deleted when settings are updated with activity=None."""
    # First, set activity
    activity_data = {"type": ActivityType.streaming, "name": "Test Stream", "url": "https://twitch.tv/example"}

    await sql_client.update_settings(activity=activity_data)

    # Verify activity exists in database
    assert sql_client._async_session is not None
    async with sql_client._async_session() as session:
        query = select(SQLActivityTable).where(SQLActivityTable.bot_id == sql_client._config.bot.bot_id)
        result = await session.execute(query)
        activity = result.scalar_one_or_none()
        assert activity is not None

    # Set activity to None
    await sql_client.update_settings(activity=None)

    # Verify activity was removed from database
    async with sql_client._async_session() as session:
        query = select(SQLActivityTable).where(SQLActivityTable.bot_id == sql_client._config.bot.bot_id)
        result = await session.execute(query)
        activity = result.scalar_one_or_none()
        assert activity is None


@pytest.mark.asyncio
async def test_activity_cascades_mongodb(mongodb_client: MongoDBClient) -> None:
    """Test that activity is properly removed when settings are updated with activity=None in MongoDB."""
    # First, set activity
    activity_data = {"type": ActivityType.streaming, "name": "Test Stream", "url": "https://twitch.tv/example"}

    await mongodb_client.update_settings(activity=activity_data)

    # Verify activity exists in model
    assert mongodb_client.settings_model.activity is not None
    assert mongodb_client.settings_model.activity.type == ActivityType.streaming

    # Verify activity exists in database
    settings_document = await MongoDBSettingsDocument.find_one(
        MongoDBSettingsDocument.bot_id == mongodb_client._config.bot.bot_id
    )
    assert settings_document is not None
    assert settings_document.activity is not None
    assert isinstance(settings_document.activity, MongoDBActivityModel)
    assert settings_document.activity.name == "Test Stream"

    # Set activity to None
    await mongodb_client.update_settings(activity=None)

    # Verify activity was removed from model
    assert mongodb_client.settings_model.activity is None

    # Verify activity was removed from database
    settings_document = await MongoDBSettingsDocument.find_one(
        MongoDBSettingsDocument.bot_id == mongodb_client._config.bot.bot_id
    )
    assert settings_document is not None
    assert settings_document.activity is None


@pytest.mark.asyncio
async def test_sql_connection_error_handling(
    sql_config: Config, monkeypatch: pytest.MonkeyPatch, mocker: MockFixture
) -> None:
    """Test that database connection errors are properly handled."""
    # Mock create_async_engine to raise an error
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.AsyncEngine.begin",
        mocker.MagicMock(side_effect=Exception("Connection error")),
    )

    client = SQLClient(sql_config)

    # Verify that connect() raises DatabaseConnectionError
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.AsyncEngine.begin",
        mocker.MagicMock(side_effect=SQLAlchemyError("Connection error")),
    )

    client = SQLClient(sql_config)

    # Verify that connect() raises DatabaseConnectionError
    with pytest.raises(DatabaseConnectionError):
        await client.connect()


@pytest.mark.asyncio
async def test_mongodb_connection_error_handling(
    mongodb_config: Config, monkeypatch: pytest.MonkeyPatch, mocker: MockFixture
) -> None:
    """Test that MongoDB connection errors are properly handled."""

    # Mock AsyncIOMotorClient.server_info to raise an error
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=Exception("Connection error"),
    )

    client = MongoDBClient(mongodb_config)

    # Verify that connect() raises DatabaseConnectionError
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Try with a specific MongoDB error
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.OperationFailure("authentication failed"),
    )

    client = MongoDBClient(mongodb_config)

    # Verify that connect() raises DatabaseConnectionError
    with pytest.raises(DatabaseConnectionError):
        await client.connect()


@pytest.mark.asyncio
async def test_update_settings_error_handling_sql(sql_client: SQLClient, mocker: MockFixture) -> None:
    """Test that errors during settings updates are properly handled."""

    mock_commit = mocker.patch.object(AsyncSession, "commit", side_effect=SQLAlchemyError("Update failed"))

    # Verify update_settings raises DatabaseConnectionError and calls sync_settings
    sync_settings_spy = mocker.spy(sql_client, "sync_settings")

    with pytest.raises(DatabaseConnectionError):
        await sql_client.update_settings(status=StatusType.online)

    # Verify sync_settings was called to restore state
    assert sync_settings_spy.call_count == 1

    mocker.stop(mock_commit)


@pytest.mark.asyncio
async def test_update_settings_error_handling_mongodb(mongodb_client: MongoDBClient, mocker: MockFixture) -> None:
    """Test that errors during settings updates in MongoDB are properly handled."""

    mocker.patch.object(MongoDBSettingsDocument, "replace", side_effect=Exception("Update failed"))

    # Verify update_settings raises DatabaseConnectionError
    with pytest.raises(DatabaseConnectionError):
        await mongodb_client.update_settings(status=StatusType.online)


@pytest.mark.asyncio
async def test_update_permission_overrides(client: DBClientBase) -> None:
    """Test updating permission overrides for a profile, both changing existing and adding new ones."""
    profile_id = 98765432109876543

    # Create a profile with initial permission overrides
    initial_profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=AccessLevel.admin,
        permission_overrides={
            "existing_cmd": PermissionOverrideValue.allow,
            "to_be_removed": PermissionOverrideValue.deny,
        },
        tag="Override Test",
    )

    # Save the initial profile
    await client.update_profile(initial_profile)

    # Verify the profile was created with correct overrides
    retrieved_profile = client.get_profile(profile_id, ProfileType.user)
    assert retrieved_profile is not None
    assert retrieved_profile.permission_overrides["existing_cmd"] == PermissionOverrideValue.allow
    assert retrieved_profile.permission_overrides["to_be_removed"] == PermissionOverrideValue.deny
    assert len(retrieved_profile.permission_overrides) == 2

    # Update the profile with modified overrides:
    # - Change "existing_cmd" from ALLOW to DENY
    # - Add a new override for "new_cmd"
    # - Remove "to_be_removed" override
    updated_profile = Profile(
        bot_id=client._config.bot.bot_id,
        profile_id=profile_id,
        profile_type=ProfileType.user,
        access_level=AccessLevel.admin,
        permission_overrides={
            "existing_cmd": PermissionOverrideValue.deny,  # Changed from ALLOW to DENY
            "new_cmd": PermissionOverrideValue.allow,  # Newly added
        },
        tag="Override Test",
    )

    # Update the profile
    await client.update_profile(updated_profile)

    # Fetch the profile to verify the updates
    updated_retrieved_profile = client.get_profile(profile_id, ProfileType.user)
    assert updated_retrieved_profile is not None
    assert len(updated_retrieved_profile.permission_overrides) == 2
    assert updated_retrieved_profile.permission_overrides["existing_cmd"] == PermissionOverrideValue.deny
    assert updated_retrieved_profile.permission_overrides["new_cmd"] == PermissionOverrideValue.allow
    assert "to_be_removed" not in updated_retrieved_profile.permission_overrides

    await client.sync_settings()
    # Double check after sync
    updated_retrieved_profile = client.get_profile(profile_id, ProfileType.user)
    assert updated_retrieved_profile is not None
    assert len(updated_retrieved_profile.permission_overrides) == 2
    assert updated_retrieved_profile.permission_overrides["existing_cmd"] == PermissionOverrideValue.deny
    assert updated_retrieved_profile.permission_overrides["new_cmd"] == PermissionOverrideValue.allow
    assert "to_be_removed" not in updated_retrieved_profile.permission_overrides

    # Clean up
    await client.delete_profile(profile_id)


@pytest.mark.asyncio
async def test_mongodb_connection_error_handling_detailed(
    mongodb_config: Config, mocker: MockFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Test all error branches in MongoDB connection error handling.

    This test verifies that each specific error condition in the MongoDB client's connect method
    is caught and produces the appropriate error logs.
    """
    # Test case 1: Connection refused error
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.ServerSelectionTimeoutError("Connection refused"),
    )

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the correct error message was logged
    assert any("Failed to connect to MongoDB. Is it running?" in message for message in caplog.messages)

    # Test case 2: IP not whitelisted (connection closed)
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.ServerSelectionTimeoutError("connection closed"),
    )

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the correct error message was logged
    assert any("Your IP may not be whitelisted" in message for message in caplog.messages)

    # Test case 3: Certificate verification failed (MacOS)
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.ServerSelectionTimeoutError("CERTIFICATE_VERIFY_FAILED"),
    )
    original_os_name = os.name
    mocker.patch.object(os, "name", "darwin")  # Simulate running on MacOS

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the MacOS-specific error message was logged
    assert any("Install Certificates.command" in message for message in caplog.messages)

    # Test case 4: Certificate verification failed (non-MacOS)
    caplog.clear()
    mocker.patch.object(os, "name", "not_darwin")  # Simulate running on other OS

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the general certificate error message was logged
    assert any("SSL cert verification" in message for message in caplog.messages)
    assert all("Install Certificates.command" not in message for message in caplog.messages)

    # Restore original os.name
    mocker.patch.object(os, "name", original_os_name)

    # Test case 5: Unknown ServerSelectionTimeoutError
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.ServerSelectionTimeoutError("Some other error"),
    )

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the unknown error message was logged
    assert any("An unknown error occurred" in message for message in caplog.messages)

    # Test case 6: Authentication failure
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.OperationFailure("authentication failed"),
    )

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the authentication error message was logged
    assert any("Invalid credentials" in message for message in caplog.messages)

    # Test case 7: Unknown OperationFailure
    caplog.clear()
    mocker.patch(
        "motor.motor_asyncio.AsyncIOMotorClient.server_info",
        side_effect=pymongo.errors.OperationFailure("Some other operation failure"),
    )

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the unknown error message was logged
    assert any("An unknown error occurred" in message for message in caplog.messages)

    # Test case 8: Generic exception
    caplog.clear()
    mocker.patch("motor.motor_asyncio.AsyncIOMotorClient.server_info", side_effect=Exception("Some generic error"))

    client = MongoDBClient(mongodb_config)
    with pytest.raises(DatabaseConnectionError):
        await client.connect()

    # Check that the generic error message was logged
    assert any("An unknown error occurred" in message for message in caplog.messages)
    assert any("Please report this error" in message for message in caplog.messages)
