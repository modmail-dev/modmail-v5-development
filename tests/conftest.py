from __future__ import annotations

import pytest

import modmail


def pytest_configure(config: pytest.Config) -> None:
    # Initializes modmail with the example config file.
    # TODO: Move the log file to a temporary location
    modmail.init("config.yaml.example")
