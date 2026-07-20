from __future__ import annotations

import math
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlparse

PACKAGE_NAME = "lacuna-research-mcp"
DEFAULT_SITE_URL = "https://lacuna.tiptreesystems.com"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_AUTHOR_LIST_LIMIT = 50
SEARCH_MAX_LIMIT = 50
DIRECTION_PAPERS_MAX_LIMIT = 100
LOCAL_LIST_MAX_LIMIT = 200
DEFAULT_MAX_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 0.5
RETRY_AFTER_MAX_SECONDS = 30.0
RETRY_STATUS_CODES = frozenset({429, 502, 503, 504})
SLOW_RESPONSE_SECONDS = 10.0
MAX_NORMALIZE_DEPTH = 64
# Default WARNING so normal operation does not emit httpx's INFO request logs,
# which include full request URLs with the user's query string to stderr that
# MCP hosts may retain. Raise via LACUNA_MCP_LOG_LEVEL for debugging.
DEFAULT_LOG_LEVEL = "WARNING"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


PACKAGE_VERSION = _package_version()
DEFAULT_USER_AGENT = f"{PACKAGE_NAME}/{PACKAGE_VERSION}"


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime settings captured once from environment on first use or create_mcp()."""

    site_url: str = DEFAULT_SITE_URL
    http_timeout: float = DEFAULT_HTTP_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    user_agent: str = DEFAULT_USER_AGENT
    bearer_token: str | None = None


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()


def _parse_timeout(value: str | None) -> float:
    if value is None:
        return DEFAULT_HTTP_TIMEOUT
    try:
        timeout = float(value)
    except ValueError:
        raise ValueError("Invalid LACUNA_MCP_TIMEOUT: must be a number of seconds") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Invalid LACUNA_MCP_TIMEOUT: must be a finite number greater than 0")
    return timeout


def _parse_max_retries(value: str | None) -> int:
    if value is None:
        return DEFAULT_MAX_RETRIES
    try:
        retries = int(value)
    except ValueError:
        raise ValueError("Invalid LACUNA_MCP_MAX_RETRIES: must be a non-negative integer") from None
    if retries < 0:
        raise ValueError("Invalid LACUNA_MCP_MAX_RETRIES: must be a non-negative integer")
    return retries


def _parse_site_url(value: str | None) -> str:
    raw = (value or DEFAULT_SITE_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid LACUNA_SITE_URL: must be an http(s) URL, got {value!r}")
    if parsed.query or parsed.fragment:
        raise ValueError(
            f"Invalid LACUNA_SITE_URL: must not contain a query string or fragment, got {value!r}"
        )
    return raw


def _parse_log_level(value: str | None) -> str:
    if value is None:
        return DEFAULT_LOG_LEVEL
    level = value.strip().upper()
    if level not in LOG_LEVELS:
        raise ValueError(f"Invalid LACUNA_MCP_LOG_LEVEL: must be one of {', '.join(LOG_LEVELS)}")
    return level


def log_level_from_env() -> str:
    return _parse_log_level(os.environ.get("LACUNA_MCP_LOG_LEVEL"))


def runtime_config_from_env() -> RuntimeConfig:
    bearer_token = os.environ.get("LACUNA_MCP_BEARER_TOKEN")
    return RuntimeConfig(
        site_url=_parse_site_url(os.environ.get("LACUNA_SITE_URL")),
        http_timeout=_parse_timeout(os.environ.get("LACUNA_MCP_TIMEOUT")),
        max_retries=_parse_max_retries(os.environ.get("LACUNA_MCP_MAX_RETRIES")),
        user_agent=os.environ.get("LACUNA_MCP_USER_AGENT") or DEFAULT_USER_AGENT,
        bearer_token=bearer_token.strip() if bearer_token else None,
    )
