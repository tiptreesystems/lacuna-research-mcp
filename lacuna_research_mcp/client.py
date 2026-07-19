from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, NoReturn

import httpx

from lacuna_research_mcp.config import (
    DEFAULT_RUNTIME_CONFIG,
    RETRY_AFTER_MAX_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
    RETRY_STATUS_CODES,
    SLOW_RESPONSE_SECONDS,
    RuntimeConfig,
    runtime_config_from_env,
)
from lacuna_research_mcp.errors import LacunaMCPError
from lacuna_research_mcp.normalize import normalize_url_fields

logger = logging.getLogger(__name__)


class LacunaRuntime:
    """Owns runtime configuration and the event-loop-bound HTTP client."""

    def __init__(
        self,
        config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
        *,
        configured_from_env: bool = False,
    ) -> None:
        self.config = config
        self.configured_from_env = configured_from_env
        self._client: httpx.AsyncClient | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None
        self._client_stale: bool = False
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None

    def configure(self, config: RuntimeConfig) -> None:
        """Apply a new runtime config.

        Must not run concurrently with in-flight requests: an open client
        will be closed on the next http_client() call, and any coroutine still
        holding a reference to it will fail.
        """
        self.config = config
        self.configured_from_env = True
        if self._client is None:
            self._client_loop = None
            self._lock = None
            self._lock_loop = None
            self._client_stale = False
        else:
            self._client_stale = True

    def runtime_config(self) -> RuntimeConfig:
        if not self.configured_from_env:
            self.configure(runtime_config_from_env())
        return self.config

    async def http_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        async with self._client_lock(loop):
            config = self.runtime_config()
            client_loop_changed = self._client_loop is not loop
            if self._client is not None and (self._client_stale or client_loop_changed):
                await self._close_stale_client(
                    self._client,
                    best_effort=client_loop_changed,
                )
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=config.http_timeout,
                    headers=self._headers(config),
                )
                self._client_loop = loop
            return self._client

    async def close(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._client_lock(loop):
            client = self._client
            client_loop_changed = self._client_loop is not loop
            self._detach_client(client)
            if client is not None:
                await self._close_client(client, best_effort=client_loop_changed)

    def _client_lock(self, loop: asyncio.AbstractEventLoop) -> asyncio.Lock:
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def _detach_client(self, client: httpx.AsyncClient | None) -> None:
        if self._client is client:
            self._client = None
            self._client_loop = None
            self._client_stale = False

    async def _close_stale_client(
        self,
        stale_client: httpx.AsyncClient,
        *,
        best_effort: bool,
    ) -> None:
        self._detach_client(stale_client)
        await self._close_client(stale_client, best_effort=best_effort)

    @staticmethod
    async def _close_client(client: httpx.AsyncClient, *, best_effort: bool) -> None:
        try:
            await client.aclose()
        except Exception:
            if not best_effort:
                raise
            logger.debug("Could not close HTTP client from a previous event loop", exc_info=True)

    @staticmethod
    def _headers(config: RuntimeConfig) -> dict[str, str]:
        headers = {"User-Agent": config.user_agent}
        if config.bearer_token:
            headers["Authorization"] = f"Bearer {config.bearer_token}"
        return headers


RUNTIME = LacunaRuntime()


def set_runtime_config(config: RuntimeConfig) -> None:
    RUNTIME.configure(config)


def configure_runtime_from_env() -> RuntimeConfig:
    config = runtime_config_from_env()
    set_runtime_config(config)
    return config


def runtime_config() -> RuntimeConfig:
    return RUNTIME.runtime_config()


async def get_http_client() -> httpx.AsyncClient:
    return await RUNTIME.http_client()


async def close_http_client() -> None:
    await RUNTIME.close()


def _response_excerpt(response: httpx.Response) -> str:
    text = (getattr(response, "text", "") or "").strip()
    if not text:
        return getattr(response, "reason_phrase", "") or "no response body"
    return text[:300]


@dataclass(frozen=True)
class _RequestAttempt:
    response: httpx.Response | None
    transient_exception: Exception | None
    elapsed_seconds: float


async def _perform_request(url: str, params: dict[str, Any] | None) -> _RequestAttempt:
    started_at = time.monotonic()
    try:
        client = await get_http_client()
        response = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        return _RequestAttempt(None, exc, time.monotonic() - started_at)
    except httpx.TransportError as exc:
        return _RequestAttempt(None, exc, time.monotonic() - started_at)
    except httpx.RequestError as exc:
        _raise_request_error(url, exc)
    return _RequestAttempt(response, None, time.monotonic() - started_at)


def _raise_request_error(url: str, exc: httpx.RequestError) -> NoReturn:
    message = f"Lacuna API request failed for {url}: {exc}"
    logger.error(message)
    raise LacunaMCPError(message) from exc


def _log_slow_response(url: str, attempt: _RequestAttempt) -> None:
    if attempt.response is None or attempt.elapsed_seconds < SLOW_RESPONSE_SECONDS:
        return
    logger.warning(
        "Slow Lacuna API response for %s: %.2fs status=%s",
        url,
        attempt.elapsed_seconds,
        attempt.response.status_code,
    )


def _is_retryable(attempt: _RequestAttempt) -> bool:
    if attempt.transient_exception is not None:
        return True
    return attempt.response is not None and attempt.response.status_code in RETRY_STATUS_CODES


def _should_retry(attempt: _RequestAttempt, attempt_index: int, max_retries: int) -> bool:
    return _is_retryable(attempt) and attempt_index < max_retries


def _retry_reason(attempt: _RequestAttempt) -> str:
    if attempt.transient_exception is not None:
        return repr(attempt.transient_exception)
    if attempt.response is not None:
        return f"HTTP {attempt.response.status_code}"
    return "missing response"


def _log_retry(
    url: str,
    attempt: _RequestAttempt,
    attempt_index: int,
    max_retries: int,
) -> None:
    logger.warning(
        "Retrying Lacuna API request for %s after %s (attempt %s/%s)",
        url,
        _retry_reason(attempt),
        attempt_index + 1,
        max_retries,
    )


def _retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None or response.status_code != 429:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            return None
        seconds = retry_at.timestamp() - time.time()
    if not math.isfinite(seconds):
        return None
    # Cap so a misconfigured server or proxy cannot suspend the call for
    # hours; a still-limiting server surfaces as a terminal 429 after retries.
    return min(max(0.0, seconds), RETRY_AFTER_MAX_SECONDS)


async def _sleep_before_retry(attempt: _RequestAttempt, attempt_index: int) -> None:
    retry_after = _retry_after_seconds(attempt.response)
    delay = (
        retry_after if retry_after is not None else RETRY_BACKOFF_BASE_SECONDS * (2**attempt_index)
    )
    await asyncio.sleep(delay)


def _terminal_response_or_raise(
    url: str,
    attempt: _RequestAttempt,
    config: RuntimeConfig,
) -> httpx.Response:
    if attempt.transient_exception is not None:
        _raise_transient_error(url, attempt.transient_exception, config)
    if attempt.response is None:
        raise RuntimeError("Lacuna API retry loop finished without a response or exception")
    _raise_for_status(attempt.response)
    return attempt.response


def _raise_transient_error(
    url: str,
    exc: Exception,
    config: RuntimeConfig,
) -> NoReturn:
    if isinstance(exc, httpx.TimeoutException):
        message = f"Lacuna API request timed out after {config.http_timeout:g}s for {url}"
    else:
        message = f"Lacuna API request failed for {url}: {exc}"
    logger.error(message)
    raise LacunaMCPError(message) from exc


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        error_response = exc.response
        status = error_response.status_code
        response_url = str(error_response.url)
        excerpt = _response_excerpt(error_response)
        message = f"Lacuna API request failed with {status} for {response_url}: {excerpt}"
        logger.error(message)
        raise LacunaMCPError(message) from exc


def _parse_json_response(response: httpx.Response, config: RuntimeConfig) -> Any:
    try:
        return normalize_url_fields(response.json(), site_url=config.site_url)
    except ValueError as exc:
        message = f"Lacuna API returned invalid JSON for {response.url}"
        logger.error(message)
        raise LacunaMCPError(message) from exc


async def api_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    config = runtime_config()
    url = f"{config.site_url}{path}"
    for attempt_index in range(config.max_retries + 1):
        attempt = await _perform_request(url, params)
        _log_slow_response(url, attempt)
        if _should_retry(attempt, attempt_index, config.max_retries):
            _log_retry(url, attempt, attempt_index, config.max_retries)
            await _sleep_before_retry(attempt, attempt_index)
            continue

        response = _terminal_response_or_raise(url, attempt, config)
        return _parse_json_response(response, config)

    raise RuntimeError("Lacuna API retry loop exited without making a request")  # pragma: no cover


async def api_object(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = await api_get(path, params=params)
    if not isinstance(payload, dict):
        message = f"Lacuna API returned {type(payload).__name__} for {path}; expected JSON object"
        logger.error(message)
        raise LacunaMCPError(message)
    return payload


def ensure_mcp_meta(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("_mcp_meta")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["_mcp_meta"] = metadata
    return metadata


async def api_payload(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = await api_object(path, params=params)
    ensure_mcp_meta(payload)["source"] = "server_api"
    return payload
