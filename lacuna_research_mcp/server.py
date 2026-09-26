from __future__ import annotations

import sys
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


def _unsupported_python_message(version_info: tuple[Any, ...] | None = None) -> str | None:
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
        app.tool(annotations=annotations)(tool_func)
    return app


def main() -> None:
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
    app.run()


if __name__ == "__main__":
    main()
