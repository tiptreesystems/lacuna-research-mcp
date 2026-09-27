from __future__ import annotations

import inspect
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

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
            version: str = "",
            lifespan: Any = None,
            log_level: str | None = None,
        ) -> None:
            self.name = name
            self.instructions = instructions
            self.version = version
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
    monkeypatch.setattr(server, "_load_mcp_server", lambda: FakeMCP)
    monkeypatch.delenv("LACUNA_MCP_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LACUNA_SITE_URL", "https://lacuna.example/")
    monkeypatch.setenv("LACUNA_MCP_TIMEOUT", "3.5")
    monkeypatch.setenv("LACUNA_MCP_MAX_RETRIES", "4")
    monkeypatch.setenv("LACUNA_MCP_USER_AGENT", "lacuna-test/1")
    monkeypatch.setenv("LACUNA_MCP_BEARER_TOKEN", " private-token ")

    fake_mcp = server.create_mcp()

    assert fake_mcp.name == "lacuna-research-search"
    assert fake_mcp.instructions is server.SERVER_INSTRUCTIONS
    assert fake_mcp.version == config.PACKAGE_VERSION
    assert "expanded conference names may not be indexed" in fake_mcp.instructions
    assert fake_mcp.lifespan is server._lifespan
    # Default to WARNING so httpx's INFO request-URL logs (with the query
    # string) do not reach stderr during normal operation.
    assert fake_mcp.log_level == "WARNING"
    assert tuple(inspect.unwrap(tool) for tool in fake_mcp.tools) == tools.TOOL_FUNCTIONS
    assert len(tools.TOOL_FUNCTIONS) == 13
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
            version: str = "",
            lifespan: Any = None,
            log_level: str | None = None,
        ) -> None:
            self.log_level = log_level

        def tool(self, *, annotations: Any = None) -> Any:
            return lambda func: func

    monkeypatch.setattr(server, "_load_mcp_server", lambda: FakeMCP)
    monkeypatch.setenv("LACUNA_MCP_LOG_LEVEL", "debug")

    assert server.create_mcp().log_level == "DEBUG"


async def test_create_mcp_exposes_instructions_and_read_only_annotations() -> None:
    # Build the real MCPServer app (no fake) to verify the discovery/safety
    # metadata reaches the wire format MCP clients actually read.
    app = server.create_mcp()

    assert app.instructions == server.SERVER_INSTRUCTIONS
    assert "cite its canonical Lacuna URL" in app.instructions
    assert app.version == config.PACKAGE_VERSION

    async with Client(app) as mcp_client:
        assert mcp_client.protocol_version == "2026-07-28"
        assert mcp_client.server_info is not None
        assert mcp_client.server_info.name == "lacuna-research-search"
        assert mcp_client.server_info.version == config.PACKAGE_VERSION
        assert mcp_client.instructions == server.SERVER_INSTRUCTIONS

    listed = await app.list_tools()
    assert len(listed) == len(tools.TOOL_FUNCTIONS)
    for tool in listed:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True

    tools_by_name = {tool.name: tool for tool in listed}
    assert tools_by_name["search_lacuna"].description.startswith("Search Lacuna's ML/AI corpus")
    assert 'search_type="hypothesis"' in tools_by_name["search_lacuna"].description
    assert "novel ML/AI research ideas" in tools_by_name["search_lacuna"].description
    assert "generated novel ML/AI research proposal" in tools_by_name["get_hypothesis"].description
    assert 'search_lacuna(search_type="hypothesis")' in tools_by_name["get_hypothesis"].description


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


@pytest.mark.parametrize(
    ("version_info", "expected_version"),
    [
        ((3, 14, 0, "alpha", 7), "3.14.0a7"),
        ((3, 14, 0, "beta", 4), "3.14.0b4"),
        ((3, 14, 0, "candidate", 2), "3.14.0rc2"),
    ],
)
def test_unsupported_python_message_flags_early_314_prereleases(
    version_info: tuple[int, int, int, str, int],
    expected_version: str,
) -> None:
    message = server._unsupported_python_message(version_info)
    assert message is not None
    assert f"Python {expected_version} is a prerelease" in message
    assert "uvx --python 3.13 lacuna-research-mcp" in message


@pytest.mark.parametrize(
    "version_info",
    [
        (3, 11, 9, "final", 0),
        (3, 13, 0, "candidate", 1),
        (3, 14, 0, "candidate", 3),
        (3, 14, 0, "final", 0),
        (3, 14, 2, "final", 0),
    ],
)
def test_unsupported_python_message_allows_supported_interpreters(
    version_info: tuple[int, int, int, str, int],
) -> None:
    assert server._unsupported_python_message(version_info) is None


def test_main_exits_cleanly_on_unsupported_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_unsupported_python_message", lambda: "nope")

    def fail_create() -> None:
        raise AssertionError("create_mcp should not run")

    monkeypatch.setattr(server, "create_mcp", fail_create)
    with pytest.raises(SystemExit, match="nope"):
        server.main()


@pytest.mark.parametrize(
    ("tool_name", "arguments", "message"),
    [
        (
            "search_lacuna",
            {"query": "ImageNet", "search_type": "resource", "date_from": "2023"},
            "date_from not supported for resource search",
        ),
        ("get_resource", {"resource_id_or_url": ""}, "Invalid resource id or URL"),
        ("get_paper", {"artifact_id_or_url": ""}, "Path segment must not be empty"),
    ],
)
async def test_tool_validation_errors_reach_mcp_client(
    tool_name: str, arguments: dict[str, Any], message: str
) -> None:
    async with Client(server.create_mcp()) as mcp_client:
        result = await mcp_client.call_tool(tool_name, arguments)
    assert result.is_error
    assert message in " ".join(item.text for item in result.content if item.type == "text")


@pytest.mark.parametrize(
    ("tool_name", "arguments", "status", "message"),
    [
        (
            "search_lacuna",
            {"query": "ImageNet", "search_type": "resource", "resource_kind": "datasets"},
            400,
            "Invalid kind: 'datasets'. Expected one of: codebase, dataset, demo, model.",
        ),
        (
            "search_lacuna",
            {"query": "ImageNet", "search_type": "paper", "provider": "github"},
            400,
            "kind/provider filters require type=resource or type=all.",
        ),
        (
            "get_resource",
            {"resource_id_or_url": "art_missing"},
            404,
            "Resource 'art_missing' was not found.",
        ),
    ],
)
async def test_api_errors_reach_mcp_client(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, Any],
    status: int,
    message: str,
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"detail": message})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:

        async def get_http_client() -> httpx.AsyncClient:
            return http_client

        monkeypatch.setattr(client, "get_http_client", get_http_client)
        async with Client(server.create_mcp()) as mcp_client:
            result = await mcp_client.call_tool(tool_name, arguments)
    assert len(requests) == 1
    assert result.is_error
    assert message in " ".join(item.text for item in result.content if item.type == "text")


async def test_tool_wrapper_leaves_unexpected_errors_to_sdk() -> None:
    error = RuntimeError("internal crash")

    async def broken_tool() -> None:
        raise error

    with pytest.raises(RuntimeError) as exc_info:
        await server._with_tool_errors(broken_tool)()
    assert exc_info.value is error
    assert not isinstance(exc_info.value, ToolError)


async def test_tool_wrapper_preserves_discovery_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapped_tools = await server.create_mcp().list_tools()
    monkeypatch.setattr(server, "_with_tool_errors", lambda tool: tool)
    original_tools = await server.create_mcp().list_tools()
    assert [tool.model_dump() for tool in wrapped_tools] == [
        tool.model_dump() for tool in original_tools
    ]
