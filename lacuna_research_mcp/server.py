from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from lacuna_research_mcp.client import close_http_client, configure_runtime_from_env
from lacuna_research_mcp.config import PACKAGE_VERSION, log_level_from_env
from lacuna_research_mcp.tools import TOOL_FUNCTIONS

# Kept so the self-contained scope/workflow summary lands within the first 512
# characters that some MCP clients (e.g. Codex) surface; the tool enumeration
# follows after that boundary.
SERVER_INSTRUCTIONS = (
    "Lacuna is a read-only knowledge graph of machine learning and AI research: "
    "papers, research directions (clusters), authors, venues, institutions, and "
    "generated hypotheses. It does not cover biographies, news, or non-research "
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
    "and get_hypothesis."
)


def _load_fast_mcp() -> Any:
    # Deferred so main() can turn a missing optional MCP dependency into a clear CLI error.
    from mcp.server.fastmcp import FastMCP

    return FastMCP


def _read_only_tool_annotations() -> Any:
    # Deferred import mirrors _load_fast_mcp so a missing mcp dependency still
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


def _set_server_version(app: Any) -> None:
    # FastMCP 1.x does not expose an application-version constructor argument.
    # Its low-level server otherwise falls back to the MCP SDK package version
    # in the initialize handshake.
    low_level_server = getattr(app, "_mcp_server", None)
    if low_level_server is not None:
        low_level_server.version = PACKAGE_VERSION


@asynccontextmanager
async def _lifespan(_server: Any) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_http_client()


def create_mcp() -> Any:
    configure_runtime_from_env()
    log_level = log_level_from_env()
    fast_mcp = _load_fast_mcp()
    app = fast_mcp(
        "lacuna-research-search",
        instructions=SERVER_INSTRUCTIONS,
        lifespan=_lifespan,
        log_level=log_level,
    )
    _set_server_version(app)
    annotations = _read_only_tool_annotations()
    for tool_func in TOOL_FUNCTIONS:
        app.tool(annotations=annotations)(tool_func)
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
