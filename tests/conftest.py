from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from dotenv import load_dotenv
from pytest_mock import MockFixture

import modmail

# A list of regex patterns for filenames that should be protected from being opened in tests.
protected_names = [
    re.compile(r"config\.yaml$", re.I),
    re.compile(r"modmail\.log$", re.I),
    re.compile(r"modmail\.log\.\d+$", re.I),
    re.compile(r"modmail\.db$", re.I),
    re.compile(r"\.env$", re.I),
]


def pytest_configure(config: pytest.Config) -> None:
    # Initializes modmail with the example config file and load .env.test.
    modmail.init("config.yaml.example", configure_logging=False)  # do not configure logging here
    load_dotenv(".env.test")


@pytest.fixture(autouse=True)
def patch_open(mocker: MockFixture, tmp_path: Path) -> Any:
    """Patches open() and Path.open() to use a temporary path for certain files.

    The Path.open() method will be redirected to use open() instead.

    Args:
        mocker: The pytest-mock fixture.
        tmp_path: The temporary directory path provided by pytest.

    Returns:
        The original Path.open() unbound method.
    """
    original_open = open

    def open_func(name: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(name, str | Path):  # Only check if name is a string or Path
            if isinstance(name, str):
                name = Path(name)
            file_name = name.name.casefold()
            if any(protected_name.search(file_name) for protected_name in protected_names):
                return original_open(tmp_path / file_name, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]
        return original_open(name, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mocker.patch("builtins.open", side_effect=open_func, autospec=True)

    def path_open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        return open_func(self, *args, **kwargs)

    original_path_open = Path.open
    mocker.patch("pathlib.Path.open", side_effect=path_open_func, autospec=True)
    return original_path_open


@pytest.fixture(autouse=True)
def initialize_modmail(patch_open: Any) -> None:
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
