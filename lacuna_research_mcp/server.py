from __future__ import annotations

import argparse
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

from lacuna_research_mcp.client import close_http_client, configure_runtime_from_env
from lacuna_research_mcp.config import PACKAGE_VERSION, log_level_from_env
from lacuna_research_mcp.errors import LacunaMCPError
from lacuna_research_mcp.tools import TOOL_FUNCTIONS, TOOL_TITLES

# Kept so the self-contained scope/workflow summary lands within the first 512
# characters that some MCP clients (e.g. Codex) surface; the tool enumeration
# follows after that boundary.
SERVER_INSTRUCTIONS = (
    "Lacuna is a read-only knowledge graph of machine learning and AI research: "
    "papers, research directions (clusters), authors, venues, institutions, "
    "generated hypotheses, and paper-linked resources (code, datasets, models). "
    "It does not cover biographies, news, or non-research "
    "web content; answer questions outside that scope from other sources rather "
    "than guessing. Workflow: if you have no ID or URL, call search_lacuna first, "
    "then pass the IDs or URLs it returns to the detail tools to fetch entity "
    "details. When a Lacuna entity materially informs an answer, cite its "
    "canonical Lacuna URL so the user can inspect the source. For conferences "
    "commonly known by an acronym, search using the standard acronym (for "
    "example, NeurIPS, ICML, ICLR, CVPR, or ACL); expanded conference names may "
    "not be indexed. All tools are read-only and never mutate state."
    "\n\nDetail tools: get_paper, get_direction and get_direction_papers, "
    "get_author_context, get_author_papers, get_author_directions, "
    "get_author_neighbors, "
    "get_venue_context, get_institution_context and get_institution_authors, "
    "get_hypothesis, and get_resource."
)


def _load_mcp_server() -> Any:
    # Deferred so main() can turn a missing optional MCP dependency into a clear CLI error.
    from mcp.server.mcpserver import MCPServer

    return MCPServer


def _read_only_tool_annotations() -> Any:
    # Deferred import mirrors _load_mcp_server so a missing mcp dependency still
    # surfaces as a clear CLI error rather than an import failure at module load.
    from mcp.types import ToolAnnotations

    # All tools issue GET requests against the Lacuna API: read-only,
    # non-destructive, idempotent, and querying an external corpus (open world).
    # These are advisory hints for MCP clients, not security enforcement.
    return ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )


@asynccontextmanager
async def _lifespan(_server: Any) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_http_client()


def _unsupported_python_message(
    version_info: tuple[int, int, int, str, int] | None = None,
) -> str | None:
    """Return an actionable error for interpreters known to break the MCP SDK.

    Python 3.14 prereleases before 3.14.0rc3 lack the ``prefer_fwd_module``
    argument of ``typing._eval_type``. Pydantic (used by the MCP SDK) passes it on
    every 3.14 interpreter, so importing ``mcp`` crashes with an opaque
    ``TypeError`` raised while building ``mcp_types`` models. Older uv releases
    installed 3.14.0rc2 as their managed "3.14", which ``uvx`` then selects.
    """
    major, minor, micro, releaselevel, serial = version_info or sys.version_info
    if (major, minor, micro) != (3, 14, 0) or releaselevel == "final":
        return None
    if releaselevel == "candidate" and serial >= 3:
        return None
    suffix = {"alpha": "a", "beta": "b", "candidate": "rc"}.get(releaselevel, releaselevel)
    return (
        f"Python 3.14.0{suffix}{serial} is a prerelease that the MCP SDK cannot run on. "
        "Install a released Python 3.14 (update uv with `uv self update`, then run "
        "`uv python install 3.14`), or pick another version: "
        "`uvx --python 3.13 lacuna-research-mcp`."
    )


def _with_tool_errors(tool_func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    # Keep MCP imports deferred until server creation, after the interpreter check.
    from mcp.server.mcpserver.exceptions import ToolError

    @wraps(tool_func)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return await tool_func(*args, **kwargs)
        except (LacunaMCPError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    return wrapped


def create_mcp() -> Any:
    configure_runtime_from_env()
    log_level = log_level_from_env()
    mcp_server = _load_mcp_server()
    app = mcp_server(
        "lacuna-research-search",
        instructions=SERVER_INSTRUCTIONS,
        version=PACKAGE_VERSION,
        lifespan=_lifespan,
        log_level=log_level,
    )
    annotations = _read_only_tool_annotations()
    for tool_func in TOOL_FUNCTIONS:
        app.tool(title=TOOL_TITLES[tool_func.__name__], annotations=annotations)(
            _with_tool_errors(tool_func)
        )
    return app


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lacuna-research-mcp", description="Run the Lacuna Research MCP server."
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="stdio for local MCP clients (default); streamable-http to serve over HTTP",
    )
    parser.add_argument("--host", default="127.0.0.1", help="streamable-http bind address")
    parser.add_argument("--port", type=int, default=8000, help="streamable-http bind port")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    unsupported = _unsupported_python_message()
    if unsupported is not None:
        raise SystemExit(unsupported)
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
    if args.transport == "stdio":
        app.run()
        return
    # Every tool is a single request/response call, so the HTTP server keeps no
    # per-client session state and answers with plain JSON instead of a stream.
    app.run(
        "streamable-http",
        host=args.host,
        port=args.port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
