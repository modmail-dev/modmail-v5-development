"""Primary configuration model for the Modmail bot."""

from __future__ import annotations

import os
from pathlib import Path

from babel.core import negotiate_locale
from packaging.version import Version
from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .bot_model import BotConfig
from .database_model import DatabaseConfig
from .logging_model import LoggingConfig
from .permission_model import PermissionConfig

__all__ = ["Config"]

LOCALES_ROOT = Path(__file__).resolve().parent.parent.parent / "locales"


def _discover_locale_dirs() -> tuple[str, ...]:
    """Return locale directory names found under `modmail/locales/`.

    Directories ending with `-custom` are excluded — they are handled
    separately by the [`Translator`][modmail.i18n.Translator] at startup.
    """
    found: set[str] = set()
    if not LOCALES_ROOT.is_dir():
        return ()
    for child in LOCALES_ROOT.iterdir():
        if child.is_dir() and (child / "LC_MESSAGES").is_dir() and not child.name.endswith("-custom"):
            found.add(child.name)
    return tuple(sorted(found, key=str.casefold))


class Config(
    BaseSettings,
    frozen=True,  # pyright: ignore [reportGeneralTypeIssues]
    str_strip_whitespace=True,
    coerce_numbers_to_str=True,
    use_attribute_docstrings=True,
):
    """Primary configuration model for the Modmail bot."""

    version: str = "1.0"  # the config version
    """The config schema version."""
    bot: BotConfig
    """The bot configuration settings."""
    allowed_locales: tuple[str, ...] = Field((), validate_default=True)
    """Tuple of allowed locales for message translations. Auto-discovered from available locale
    directories if left empty."""
    default_locale: str = Field("", validate_default=True)
    """The default locale for the bot. If empty, the first allowed locale is used."""
    log_url: str
    """URL where log entries are posted."""
    database: DatabaseConfig
    """The database connection configuration."""
    permission: PermissionConfig = Field(default_factory=PermissionConfig)
    """The permission configuration settings."""
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    """The logging configuration settings."""

    # Don't load .env when testing.
    if os.environ.get("PYTEST_VERSION") is None:
        model_config = SettingsConfigDict(
            env_prefix="modmail_",
            env_file=".env",
            env_file_encoding="utf-8",
            env_nested_delimiter="__",
            case_sensitive=False,
            extra="ignore",
        )
    else:
        model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customizes the settings source priority order.

        Prioritizes environment variables over configuration files.

        Args:
            settings_cls: The settings class.
            init_settings: Settings from initialization.
            env_settings: Settings from environment variables.
            dotenv_settings: Settings from .env file.
            file_secret_settings: Settings from file secrets.

        Returns:
            A tuple of PydanticBaseSettingsSource ordered by priority.
        """
        return env_settings, dotenv_settings, init_settings, file_secret_settings

    @field_validator("version")
    @classmethod
    def check_version_valid(cls, v: str) -> str:
        """Validates that the configuration version is supported.

        Args:
            v: The version string to validate.

        Returns:
            The validated version string.

        Raises:
            ValueError: If the version is not supported.
        """
        valid_versions = ("1.0",)  # a tuple of valid versions

        try:
            version = str(Version(v))
            if version not in valid_versions:
                raise ValueError(f"Invalid config version. Valid versions are: {', '.join(valid_versions)}")
        except Exception as e:
            raise ValueError(f"Invalid config version. Valid versions are: {', '.join(valid_versions)}") from e

        # Do version migrations here?

        return version

    @field_validator("allowed_locales")
    @classmethod
    def _validate_allowed_locales(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate and resolve allowed locale codes.

        When `value` is non-empty, each entry is deduplicated and matched against
        the available locale directories via `babel.core.negotiate_locale`.

        When `value` is empty the available directories are auto-discovered.

        `.mo` files are compiled and loaded into the `Translator`.

        Returns:
            A sorted tuple of resolved BCP-47 locale codes.

        Raises:
            ValueError: If a locale does not match any available directory
                or bundle loading fails.
        """
        from modmail.i18n import Translator

        available_locales = _discover_locale_dirs()

        if value:
            resolved_set: set[str] = set()
            for entry in value:
                # Deduplicate entries and check if they're valid
                if entry in resolved_set:
                    continue
                entry_str = str(entry)
                match = negotiate_locale([entry_str.replace("_", "-")], available_locales, sep="-")
                if match is None:
                    raise ValueError(
                        f"Locale {entry_str!r} does not match any available locale directory ({available_locales})"
                    )
                resolved_set.add(match)
            resolved = tuple(sorted(resolved_set, key=str.casefold))
        else:
            resolved = available_locales

        if not resolved:
            raise ValueError(
                "No allowed locales resolved. Ensure locale directories are present under "
                "'modmail/locales/' or specify allowed locales in the config."
            )

        try:
            Translator.load_bundles(resolved)
        except Exception as e:
            raise ValueError(f"Failed to load translation bundles for {resolved}: {e}") from e
        return resolved

    @field_validator("default_locale")
    @classmethod
    def _validate_default_locale(cls, value: str, info: ValidationInfo) -> str:
        """Validate and resolve the default locale code.

        Args:
            value: The locale code to validate.
            info: Validation context with access to `allowed_locales` in
                `info.data`.

        Returns:
            The resolved BCP-47 locale code.

        Raises:
            ValueError: If the locale does not match any allowed locale.
        """
        allowed_locales = info.data["allowed_locales"]
        if not value:
            if "en-US" in allowed_locales:
                return "en-US"
            return allowed_locales[0]

        match = negotiate_locale([value.replace("_", "-")], allowed_locales, sep="-")
        if match is None:
            raise ValueError(f"Default locale {value!r} does not match any allowed locale ({allowed_locales})")
        return match

    @field_validator("log_url")
    @classmethod
    def check_log_url(cls, v: str) -> str:
        """Validates the log URL format.

        Args:
            v: The log URL to validate.

        Returns:
            The validated log URL.

        Raises:
            ValueError: If the log URL is not valid.
        """
        if not v.startswith("https://") and not v.startswith("http://"):
            # Allow http, but don't suggest it since it's not secure.
            raise ValueError("Log URL must start with 'https://'")
        return v.strip("/ ")  # Remove trailing slash if present
