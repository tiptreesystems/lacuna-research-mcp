"""Interactive views (MCP Apps) that hosts such as Claude can render for a tool.

A view is one self-contained HTML document, served as a ``ui://`` resource. A
tool points at its view through ``_meta.ui.resourceUri``; hosts that do not
render views ignore both and use the tool result as before.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

# The MIME type the MCP Apps extension requires for a view resource.
VIEW_MIME_TYPE = "text/html;profile=mcp-app"

PAPER_CARD_URI = "ui://lacuna-research/paper-card"

# A host blocks every origin a view does not declare. The card loads the MCP
# Apps client from the first; paper figures come from Lacuna, which redirects
# each one to its media host.
_VIEW_RESOURCE_ORIGINS = [
    "https://unpkg.com",
    "https://lacuna.tiptreesystems.com",
    "https://media.lacuna.tiptreesystems.com",
]


def paper_card_html() -> str:
    return resources.files(__package__).joinpath("paper_card.html").read_text(encoding="utf-8")


def view_tool_meta(resource_uri: str) -> dict[str, Any]:
    """Tool ``_meta`` naming the view that renders the tool's result."""
    # Older hosts read the flat key, newer ones the nested one.
    return {"ui": {"resourceUri": resource_uri}, "ui/resourceUri": resource_uri}


def view_resource_meta() -> dict[str, Any]:
    """Resource ``_meta`` for a view: what its sandbox may load, and its frame."""
    return {
        "ui": {"csp": {"resourceDomains": list(_VIEW_RESOURCE_ORIGINS)}, "prefersBorder": False}
    }


# Tool name -> the view that renders its result.
TOOL_VIEWS: dict[str, str] = {"get_paper": PAPER_CARD_URI}
