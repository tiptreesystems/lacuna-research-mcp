from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any

import httpx
import pytest

from lacuna_research_mcp import client, config, errors


def set_runtime_config(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: Any,
) -> config.RuntimeConfig:
    runtime_config = replace(config.DEFAULT_RUNTIME_CONFIG, **overrides)
    monkeypatch.setattr(
        client,
        "RUNTIME",
        client.LacunaRuntime(runtime_config, configured_from_env=True),
    )
    return runtime_config


@pytest.fixture(autouse=True)
def default_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    set_runtime_config(monkeypatch)


def patch_client(monkeypatch: pytest.MonkeyPatch, fake_client: Any) -> None:
    async def get_client() -> Any:
        return fake_client

    monkeypatch.setattr(client, "get_http_client", get_client)


class FakeResponse:
    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        text: str = "",
        url: str = "https://lacuna.example/api",
        json_error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = text
        self.url = url
        self.reason_phrase = "reason"
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "http error",
                request=httpx.Request("GET", self.url),
                response=self,  # type: ignore[arg-type]
            )

    def json(self) -> Any:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeAsyncClient:
    def __init__(
        self,
        response: FakeResponse | None = None,
        exc: Exception | None = None,
        *,
        sequence: list[FakeResponse | Exception] | None = None,
    ) -> None:
        self.response = response or FakeResponse({})
        self.exc = exc
        self._sequence = list(sequence) if sequence is not None else None
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.calls.append((args, kwargs))
        if self._sequence is not None:
            item = self._sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self.exc is not None:
            raise self.exc
        return self.response


def test_lazy_runtime_config_uses_environment_without_failing_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client, "RUNTIME", client.LacunaRuntime())
    monkeypatch.setenv("LACUNA_SITE_URL", "https://lacuna.example/")

    assert client.runtime_config().site_url == "https://lacuna.example"


def test_client_is_recreated_when_event_loop_changes() -> None:
    async def get_client() -> httpx.AsyncClient:
        return await client.get_http_client()

    first_client = asyncio.run(get_client())
    second_client = asyncio.run(get_client())

    assert first_client is not second_client
    assert first_client.is_closed
    assert not second_client.is_closed
    asyncio.run(client.close_http_client())


async def test_client_includes_bearer_token_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeHTTPClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    set_runtime_config(monkeypatch, bearer_token="secret-token")  # noqa: S106
    monkeypatch.setattr(client.httpx, "AsyncClient", FakeHTTPClient)

    http_client = await client.get_http_client()

    assert isinstance(http_client, FakeHTTPClient)
    assert captured["headers"] == {
        "User-Agent": config.DEFAULT_USER_AGENT,
        "Authorization": "Bearer secret-token",
    }


async def test_stale_client_close_does_not_overwrite_concurrent_new_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeHTTPClient:
        instances: list[FakeHTTPClient] = []

        def __init__(self, **_kwargs: Any) -> None:
            self.closed = False
            FakeHTTPClient.instances.append(self)

        async def aclose(self) -> None:
            await asyncio.sleep(0)
            self.closed = True

    stale_client = FakeHTTPClient()
    client.RUNTIME._client = stale_client
    client.RUNTIME._client_loop = object()
    monkeypatch.setattr(client.httpx, "AsyncClient", FakeHTTPClient)

    first_client, second_client = await asyncio.gather(
        client.get_http_client(), client.get_http_client()
    )

    assert first_client is second_client
    assert first_client is client.RUNTIME._client
    assert stale_client.closed
    assert len(FakeHTTPClient.instances) == 2


async def test_api_errors_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    set_runtime_config(monkeypatch, max_retries=0)
    fake_client = FakeAsyncClient(
        FakeResponse({}, status_code=404, text="missing", url="https://x.test/nope")
    )
    patch_client(monkeypatch, fake_client)
    caplog.set_level(logging.ERROR, logger=client.__name__)

    with pytest.raises(errors.LacunaMCPError, match="404.*missing"):
        await client.api_get("/nope")
    assert "Lacuna API request failed with 404" in caplog.text


async def test_api_timeout_and_json_errors_are_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    set_runtime_config(monkeypatch, max_retries=0)
    patch_client(monkeypatch, FakeAsyncClient(exc=httpx.TimeoutException("slow")))
    with pytest.raises(errors.LacunaMCPError, match="timed out"):
        await client.api_get("/slow")

    fake_client = FakeAsyncClient(FakeResponse(json_error=ValueError("bad json")))
    patch_client(monkeypatch, fake_client)
    with pytest.raises(errors.LacunaMCPError, match="invalid JSON"):
        await client.api_get("/bad-json")


async def test_api_payload_requires_object(monkeypatch: pytest.MonkeyPatch) -> None:
    set_runtime_config(monkeypatch, max_retries=0)
    patch_client(monkeypatch, FakeAsyncClient(FakeResponse([])))

    assert await client.api_get("/list") == []
    with pytest.raises(errors.LacunaMCPError, match="expected JSON object"):
        await client.api_payload("/list")


async def test_api_payload_adds_mcp_meta_without_overwriting_upstream_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_runtime_config(monkeypatch, max_retries=0)
    patch_client(
        monkeypatch,
        FakeAsyncClient(FakeResponse({"source": "upstream", "_mcp_meta": {"seen": True}})),
    )

    payload = await client.api_payload("/object")

    assert payload["source"] == "upstream"
    assert payload["_mcp_meta"] == {"seen": True, "source": "server_api"}


async def test_api_retries_transient_status_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    set_runtime_config(monkeypatch, max_retries=2)
    monkeypatch.setattr(client, "RETRY_BACKOFF_BASE_SECONDS", 0)
    caplog.set_level(logging.WARNING, logger=client.__name__)
    fake_client = FakeAsyncClient(
        sequence=[
            FakeResponse({}, status_code=503, text="busy"),
            FakeResponse({}, status_code=502, text="bad gateway"),
            FakeResponse({"ok": True}),
        ]
    )
    patch_client(monkeypatch, fake_client)

    assert await client.api_get("/transient") == {"ok": True}
    assert len(fake_client.calls) == 3
    assert "Retrying Lacuna API request" in caplog.text


async def test_api_retries_transport_errors_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_runtime_config(monkeypatch, max_retries=2)
    monkeypatch.setattr(client, "RETRY_BACKOFF_BASE_SECONDS", 0)
    fake_client = FakeAsyncClient(
        sequence=[
            httpx.ConnectError("reset"),
            httpx.TimeoutException("slow"),
            FakeResponse({"ok": True}),
        ]
    )
    patch_client(monkeypatch, fake_client)

    assert await client.api_get("/flaky") == {"ok": True}
    assert len(fake_client.calls) == 3


async def test_api_retries_exhausted_raises_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_runtime_config(monkeypatch, max_retries=1)
    monkeypatch.setattr(client, "RETRY_BACKOFF_BASE_SECONDS", 0)
    fake_client = FakeAsyncClient(
        FakeResponse({}, status_code=503, text="still busy", url="https://x.test/down")
    )
    patch_client(monkeypatch, fake_client)

    with pytest.raises(errors.LacunaMCPError, match="503.*still busy"):
        await client.api_get("/down")
    assert len(fake_client.calls) == 2


async def test_api_does_not_retry_non_transient_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_runtime_config(monkeypatch, max_retries=3)
    monkeypatch.setattr(client, "RETRY_BACKOFF_BASE_SECONDS", 0)
    fake_client = FakeAsyncClient(
        FakeResponse({}, status_code=404, text="missing", url="https://x.test/nope")
    )
    patch_client(monkeypatch, fake_client)

    with pytest.raises(errors.LacunaMCPError, match="404"):
        await client.api_get("/nope")
    assert len(fake_client.calls) == 1
