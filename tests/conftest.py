from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from dotenv import load_dotenv
from pytest_mock import MockFixture

import modmail


def pytest_configure(config: pytest.Config) -> None:
    # Initializes modmail with the example config file and load .env.test.
    modmail.init("config.yaml.example")
    load_dotenv(".env.test")


@pytest.fixture(autouse=True)
def patch_open(mocker: MockFixture, tmp_path: Path) -> Any:
    """Patches the open function to use a temporary path for certain files.

    Args:
        mocker: The pytest-mock fixture.
        tmp_path: The temporary directory path provided by pytest.

    Returns:
        The original open function.
    """
    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        # A list of protected files that shouldn't be accessed or created
        protected_names = ["config.yaml", "modmail.log", "modmail.db", ".env"]

        if any(protected_name in self.name for protected_name in protected_names):
            return original_func(Path(tmp_path / self.name), *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=True)
    return original_func


@pytest.fixture(autouse=True)
def initialize_modmail() -> None:
    # Re-initializes modmail with the example config file.
    modmail.init("config.yaml.example")


if not TYPE_CHECKING:
    try:
        import uvloop

        @pytest.fixture(scope="session")
        def event_loop_policy() -> uvloop.EventLoopPolicy:
            return uvloop.EventLoopPolicy()

    except ImportError:
        # Fallback to the default event loop policy if uvloop is not available
        pass
