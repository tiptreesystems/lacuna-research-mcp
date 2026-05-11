from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from lacuna_research_mcp.client import close_http_client, configure_runtime_from_env
from lacuna_research_mcp.tools import TOOL_FUNCTIONS


def _load_fast_mcp() -> Any:
    # Deferred so main() can turn a missing optional MCP dependency into a clear CLI error.
    from mcp.server.fastmcp import FastMCP

    return FastMCP


@asynccontextmanager
async def _lifespan(_server: Any) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_http_client()


def create_mcp() -> Any:
    configure_runtime_from_env()
    fast_mcp = _load_fast_mcp()
    app = fast_mcp("lacuna-research-search", lifespan=_lifespan)
    for tool_func in TOOL_FUNCTIONS:
        app.tool()(tool_func)
    return app


def main() -> None:
    try:
        app = create_mcp()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except ModuleNotFoundError as exc:
        if exc.name == "mcp" or (exc.name is not None and exc.name.startswith("mcp.")):
            raise SystemExit(
                "Missing dependency: install this project first, e.g. "
                "`python -m pip install -e .` from the repository root"
            ) from exc
        raise
    app.run()


if __name__ == "__main__":
    main()
