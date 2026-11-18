"""Interactive views (MCP Apps) that hosts such as Claude can render for a tool.

A view is one self-contained HTML document, served as a ``ui://`` resource. A
tool points at its view through ``_meta.ui.resourceUri``; hosts that do not
render views ignore both and use the tool result as before.
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources
from typing import Any

# The MIME type the MCP Apps extension requires for a view resource.
VIEW_MIME_TYPE = "text/html;profile=mcp-app"

# One view draws every card.
CARD_URI = "ui://lacuna-research/card"

# The tools whose result gets a card: the ones that return one thing. A host
# draws a card for every call, and one answer makes several search and list
# calls, so those tools have none.
CARD_TOOLS = frozenset(
    {
        "get_paper",
        "get_author_context",
        "get_direction",
        "get_hypothesis",
        "get_venue_context",
        "get_institution_context",
        "get_resource",
    }
)

# A host blocks every origin a view does not declare. Paper figures come from
# Lacuna, which redirects each one to its media host, where author photos also
# live. The card's own script is part of the document, so no other origin is
# needed.
_VIEW_RESOURCE_ORIGINS = [
    "https://lacuna.tiptreesystems.com",
    "https://media.lacuna.tiptreesystems.com",
]


# The MCP Apps client the card talks to its host through: the unmodified
# dist/src/app-with-deps.js of @modelcontextprotocol/ext-apps at this version,
# kept in vendor/ with its licence.
_CLIENT_FILE = "vendor/mcp-ext-apps-1.7.5.js"
_CLIENT_PLACEHOLDER = "<!-- MCP_APPS_CLIENT -->"
_CLIENT_EXPORTS = re.compile(r"export\{([^{}]*)\};?\s*$")


def _client_script() -> str:
    """The client as an inline script that leaves its exports on a global.

    One inline module cannot import another, so the file's closing
    ``export{a as App,...}`` becomes ``globalThis.LacunaCardClient={App:a,...}``.
    """
    source = resources.files(__package__).joinpath(_CLIENT_FILE).read_text(encoding="utf-8")
    exports = _CLIENT_EXPORTS.search(source)
    if exports is None or "</script" in source.lower():
        raise RuntimeError(f"{_CLIENT_FILE} is not the module the card expects")
    names = (pair.split(" as ") for pair in exports.group(1).split(","))
    members = ",".join(f"{exported.strip()}:{local.strip()}" for local, exported in names)
    body = source[: exports.start()] + f"globalThis.LacunaCardClient={{{members}}};"
    return f'<script type="module">{body}</script>'


@cache
def _card_document() -> str:
    page = resources.files(__package__).joinpath("card.html").read_text(encoding="utf-8")
    if page.count(_CLIENT_PLACEHOLDER) != 1:
        raise RuntimeError("card.html must hold the client placeholder exactly once")
    return page.replace(_CLIENT_PLACEHOLDER, _client_script())


def card_html() -> str:
    """The card as one document, with the client it needs written into it."""
    return _card_document()


def view_tool_meta(resource_uri: str) -> dict[str, Any]:
    """Tool ``_meta`` naming the view that renders the tool's result."""
    # Older hosts read the flat key, newer ones the nested one.
    return {"ui": {"resourceUri": resource_uri}, "ui/resourceUri": resource_uri}


def view_resource_meta() -> dict[str, Any]:
    """Resource ``_meta`` for a view: what its sandbox may load, and its frame."""
    return {
        "ui": {"csp": {"resourceDomains": list(_VIEW_RESOURCE_ORIGINS)}, "prefersBorder": False}
    }
