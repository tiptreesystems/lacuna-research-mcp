from __future__ import annotations

import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from lacuna_research_mcp import config


def test_user_agent_uses_package_identity() -> None:
    if os.environ.get("LACUNA_MCP_USER_AGENT"):
        pytest.skip("user agent overridden by environment")

    assert f"{config.PACKAGE_NAME}/{version(config.PACKAGE_NAME)}" == config.DEFAULT_USER_AGENT


def test_timeout_env_parsing_is_explicit() -> None:
    assert config._parse_timeout(None) == config.DEFAULT_HTTP_TIMEOUT
    assert config._parse_timeout("3.5") == 3.5

    with pytest.raises(ValueError, match="must be a number"):
        config._parse_timeout("not-a-number")
    with pytest.raises(ValueError, match="finite number greater than 0"):
        config._parse_timeout("0")
    with pytest.raises(ValueError, match="finite number greater than 0"):
        config._parse_timeout("inf")
    with pytest.raises(ValueError, match="finite number greater than 0"):
        config._parse_timeout("nan")


def test_max_retries_env_parsing_is_explicit() -> None:
    assert config._parse_max_retries(None) == config.DEFAULT_MAX_RETRIES
    assert config._parse_max_retries("0") == 0
    assert config._parse_max_retries("5") == 5

    with pytest.raises(ValueError, match="non-negative integer"):
        config._parse_max_retries("not-a-number")
    with pytest.raises(ValueError, match="non-negative integer"):
        config._parse_max_retries("-1")


def test_log_level_env_parsing_is_explicit() -> None:
    assert config._parse_log_level(None) == config.DEFAULT_LOG_LEVEL
    assert config.DEFAULT_LOG_LEVEL == "WARNING"
    assert config._parse_log_level("info") == "INFO"
    assert config._parse_log_level(" debug ") == "DEBUG"

    with pytest.raises(ValueError, match="must be one of"):
        config._parse_log_level("verbose")


def test_bad_timeout_does_not_fail_import() -> None:
    env = os.environ.copy()
    env["LACUNA_MCP_TIMEOUT"] = "not-a-number"

    completed = subprocess.run(
        [sys.executable, "-c", "import lacuna_research_mcp.server; print('ok')"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "ok"
