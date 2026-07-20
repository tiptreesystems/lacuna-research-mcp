from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from lacuna_research_mcp import client, config, server, tools


@pytest.fixture(autouse=True)
def default_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_config = replace(config.DEFAULT_RUNTIME_CONFIG)
    monkeypatch.setattr(
        client,
        "RUNTIME",
        client.LacunaRuntime(runtime_config, configured_from_env=True),
    )


def test_bad_timeout_fails_main_with_clear_message() -> None:
    env = os.environ.copy()
    env["LACUNA_MCP_TIMEOUT"] = "not-a-number"

    completed = subprocess.run(
        [sys.executable, "-c", "from lacuna_research_mcp.server import main; main()"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "Invalid LACUNA_MCP_TIMEOUT: must be a number of seconds" in completed.stderr


def test_create_mcp_resolves_runtime_config_and_registers_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMCP:
        def __init__(
            self,
            name: str,
            *,
            instructions: str | None = None,
            lifespan: Any = None,
            log_level: str | None = None,
        ) -> None:
            self.name = name
            self.instructions = instructions
            self.lifespan = lifespan
            self.log_level = log_level
            self.tools: list[Any] = []
            self.tool_annotations: list[Any] = []

        def tool(self, *, annotations: Any = None) -> Any:
            def register(func: Any) -> Any:
                self.tools.append(func)
                self.tool_annotations.append(annotations)
                return func

            return register

    sentinel_client = object()
    sentinel_loop = object()
    client.RUNTIME._client = sentinel_client
    client.RUNTIME._client_loop = sentinel_loop
    monkeypatch.setattr(server, "_load_fast_mcp", lambda: FakeMCP)
    monkeypatch.delenv("LACUNA_MCP_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LACUNA_SITE_URL", "https://lacuna.example/")
    monkeypatch.setenv("LACUNA_MCP_TIMEOUT", "3.5")
    monkeypatch.setenv("LACUNA_MCP_MAX_RETRIES", "4")
    monkeypatch.setenv("LACUNA_MCP_USER_AGENT", "lacuna-test/1")
    monkeypatch.setenv("LACUNA_MCP_BEARER_TOKEN", " private-token ")

    fake_mcp = server.create_mcp()

    assert fake_mcp.name == "lacuna-research-search"
    assert fake_mcp.instructions is server.SERVER_INSTRUCTIONS
    assert fake_mcp.lifespan is server._lifespan
    # Default to WARNING so httpx's INFO request-URL logs (with the query
    # string) do not reach stderr during normal operation.
    assert fake_mcp.log_level == "WARNING"
    assert tuple(fake_mcp.tools) == tools.TOOL_FUNCTIONS
    assert len(tools.TOOL_FUNCTIONS) == 14
    # Every read-only GET tool gets the same non-destructive annotation object.
    assert len(fake_mcp.tool_annotations) == len(tools.TOOL_FUNCTIONS)
    assert all(a is fake_mcp.tool_annotations[0] for a in fake_mcp.tool_annotations)
    assert (
        config.RuntimeConfig(
            site_url="https://lacuna.example",
            http_timeout=3.5,
            max_retries=4,
            user_agent="lacuna-test/1",
            bearer_token="private-token",  # noqa: S106
        )
        == client.RUNTIME.config
    )
    # configure() now marks an existing client stale rather than dropping
    # it, so the next http_client() call can close it in an async context.
    assert client.RUNTIME._client is sentinel_client
    assert client.RUNTIME._client_loop is sentinel_loop
    assert client.RUNTIME._client_stale is True


def test_create_mcp_log_level_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeMCP:
        def __init__(
            self,
            name: str,
            *,
            instructions: str | None = None,
            lifespan: Any = None,
            log_level: str | None = None,
        ) -> None:
            self.log_level = log_level

        def tool(self, *, annotations: Any = None) -> Any:
            return lambda func: func

    monkeypatch.setattr(server, "_load_fast_mcp", lambda: FakeMCP)
    monkeypatch.setenv("LACUNA_MCP_LOG_LEVEL", "debug")

    assert server.create_mcp().log_level == "DEBUG"


async def test_create_mcp_exposes_instructions_and_read_only_annotations() -> None:
    # Build the real FastMCP app (no fake) to verify the discovery/safety
    # metadata reaches the wire format MCP clients actually read.
    app = server.create_mcp()

    assert app.instructions == server.SERVER_INSTRUCTIONS
    initialization_options = app._mcp_server.create_initialization_options()
    assert initialization_options.server_version == config.PACKAGE_VERSION

    listed = await app.list_tools()
    assert len(listed) == len(tools.TOOL_FUNCTIONS)
    for tool in listed:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True


async def test_lifespan_closes_http_client() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    fake_client = FakeClient()
    client.RUNTIME._client = fake_client
    client.RUNTIME._client_loop = object()

    async with server._lifespan(object()):
        assert client.RUNTIME._client is fake_client

    assert fake_client.closed
    assert client.RUNTIME._client is None
    assert client.RUNTIME._client_loop is None
