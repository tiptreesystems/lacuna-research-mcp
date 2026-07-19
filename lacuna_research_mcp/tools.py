from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from lacuna_research_mcp.client import api_object, api_payload, ensure_mcp_meta
from lacuna_research_mcp.config import (
    DEFAULT_AUTHOR_LIST_LIMIT,
    DIRECTION_PAPERS_MAX_LIMIT,
    SEARCH_MAX_LIMIT,
)
from lacuna_research_mcp.ids import (
    extract_cluster_id,
    extract_hypothesis_id,
    extract_paper_id,
    extract_route_key,
    extract_venue_key_year,
    path_segment,
)
from lacuna_research_mcp.truncation import (
    truncate_author_payload_in_place,
    truncate_nested_author_payload_in_place,
    truncate_payload_list_in_place,
)

_HYPOTHESIS_PASSTHROUGH_FIELDS = ("title", "url", "markdown_url")

_SEARCH_TYPE_ALIASES = {
    "all": "all",
    "cluster": "cluster",
    "clusters": "cluster",
    "direction": "cluster",
    "directions": "cluster",
    "paper": "paper",
    "papers": "paper",
    "author": "author",
    "authors": "author",
    "institution": "institution",
    "institutions": "institution",
    "venue": "venue",
    "venues": "venue",
    "hypothesis": "hypothesis",
    "hypotheses": "hypothesis",
    "proposal": "hypothesis",
    "proposals": "hypothesis",
}

_SEARCH_RANKING_PROFILES = {
    "default": "default",
    "lexical": "default",
    "bm25": "bm25_title_abstract",
    "bm25_title_abstract": "bm25_title_abstract",
    "semantic": "semantic",
}

# Server search documents for these types lack the fields the profile ranks on,
# so the combination is guaranteed to return zero hits. "all" always includes
# papers, so it is never rejected.
_RANKING_PROFILE_UNSUPPORTED_TYPES: dict[str, tuple[frozenset[str], str]] = {
    "bm25_title_abstract": (
        frozenset({"author", "institution"}),
        "author and institution records have no title or abstract fields",
    ),
    "semantic": (
        frozenset({"author", "institution", "cluster", "hypothesis", "venue"}),
        "only papers have semantic embeddings",
    ),
}


def _normalize_search_type(search_type: str | None) -> str:
    value = "" if search_type is None else str(search_type).strip().lower()
    if not value:
        return "all"
    if value in _SEARCH_TYPE_ALIASES:
        return _SEARCH_TYPE_ALIASES[value]
    valid_values = ", ".join(sorted(_SEARCH_TYPE_ALIASES))
    raise ValueError(f"Invalid search_type {search_type!r}. Valid values: {valid_values}")


def _normalize_ranking_profile(ranking_profile: str | None, search_type: str) -> str:
    value = "" if ranking_profile is None else str(ranking_profile).strip().lower()
    if not value:
        return "default"
    if value in _SEARCH_RANKING_PROFILES:
        normalized = _SEARCH_RANKING_PROFILES[value]
        unsupported_types, reason = _RANKING_PROFILE_UNSUPPORTED_TYPES.get(
            normalized, (frozenset(), "")
        )
        if search_type in unsupported_types:
            raise ValueError(
                f"ranking_profile {ranking_profile!r} is not supported for "
                f"search_type {search_type!r} ({reason}); it would always return "
                "zero results. Use the default profile instead."
            )
        return normalized
    valid_values = ", ".join(sorted(_SEARCH_RANKING_PROFILES))
    raise ValueError(f"Invalid ranking_profile {ranking_profile!r}. Valid values: {valid_values}")


_PAPER_VIEW_ROUTES: dict[str, str] = {
    "context": "/api/v1/context/paper/{artifact_id}",
    "full": "/api/v1/papers/{artifact_id}",
    "preview": "/api/v1/papers/{artifact_id}/preview",
    "blog": "/api/v1/papers/{artifact_id}/blog",
    "figures": "/api/v1/papers/{artifact_id}/figures",
    "concepts": "/api/v1/papers/{artifact_id}/concepts",
    "neighbors": "/api/v1/papers/{artifact_id}/neighbors",
}

_DIRECTION_VIEW_ROUTES: dict[str, str] = {
    "context": "/api/v1/context/direction/{cluster_id}",
    "full": "/api/v1/clusters/{cluster_id}",
}

# Context tools whose server `context` route accepts a compact/complete `view`
# query param. The MCP-facing value "context" maps to the server's compact shape;
# "full" maps to the server's complete shape on the same route.
_HYPOTHESIS_VIEW_ROUTES: dict[str, str] = {"context": "compact", "full": "complete"}
_CONTEXT_VIEW_ROUTES: dict[str, str] = {"context": "compact", "full": "complete"}
# Direction papers is a list route (not a context envelope), so its values map
# straight through to the server `view` query param.
_DIRECTION_PAPERS_VIEW_ROUTES: dict[str, str] = {"compact": "compact", "full": "complete"}


def _normalize_view(view: str, routes: dict[str, str]) -> str:
    if view in routes:
        return view
    valid_values = ", ".join(routes)
    raise ValueError(f"Invalid view {view!r}. Valid values: {valid_values}")


PaperView = Literal["context", "full", "preview", "blog", "figures", "concepts", "neighbors"]
DirectionView = Literal["context", "full"]
HypothesisView = Literal["context", "full"]
ContextView = Literal["context", "full"]
DirectionPapersView = Literal["compact", "full"]


async def search_lacuna(
    query: str,
    search_type: str = "all",
    limit: int = 10,
    offset: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
    venue: str | None = None,
    sort: str = "relevance",
    ranking_profile: str | None = None,
    fields: str | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Search Lacuna's server-side API.

    Valid search_type values:
    - all
    - cluster, clusters, direction, directions
    - paper, papers
    - author, authors
    - institution, institutions
    - venue, venues
    - hypothesis, hypotheses, proposal, proposals

    The client normalizes aliases to the singular server-side type.

    The corpus covers machine learning and AI research: papers, research
    directions, authors' research output, venues, institutions, and generated
    hypotheses. It does not contain affiliations, biographies, news, or
    non-research web content; answer questions outside that scope from other
    sources rather than guessing from these results.

    ranking_profile controls paper ranking:
    - default / lexical (default): use the server's production paper ranker,
      which combines lexical and semantic retrieval with graceful fallback.
    - semantic: use semantic-only retrieval for conceptual queries when you
      explicitly want to exclude the lexical ranking leg.
    - bm25_title_abstract: use when you want lexical matching constrained to
      title and abstract fields.

    All searches default to the server's production ranking profile. semantic
    is only supported for paper and all searches (only papers have semantic
    embeddings); bm25_title_abstract is rejected for author and institution
    searches (those records have no title or abstract fields). Unsupported
    combinations raise an error instead of returning zero results.
    date_from and date_to are inclusive publication-date bounds. Accepted
    formats are YYYY, YYYY-MM, and YYYY-MM-DD.
    fields selects the server-side field projection for hits (e.g. a lean field
    set); passed straight through to the search API.
    debug echoes the requested/normalized type and ranking profile back in
    `_mcp_meta`; off by default to keep responses lean.
    """
    normalized_type = _normalize_search_type(search_type)
    normalized_ranking_profile = _normalize_ranking_profile(ranking_profile, normalized_type)
    params: dict[str, Any] = {
        "q": query,
        "type": normalized_type,
        "limit": max(1, min(limit, SEARCH_MAX_LIMIT)),
        "offset": max(0, offset),
        "sort": sort,
        "ranking_profile": normalized_ranking_profile,
    }
    if date_from is not None:
        params["date_from"] = date_from
    if date_to is not None:
        params["date_to"] = date_to
    if venue:
        params["venue"] = venue
    if fields:
        params["fields"] = fields

    payload = await api_payload("/api/v1/search", params=params)
    if debug:
        ensure_mcp_meta(payload).update(
            {
                "requested_type": search_type,
                "normalized_type": normalized_type,
                "requested_ranking_profile": ranking_profile,
                "normalized_ranking_profile": normalized_ranking_profile,
            }
        )
    return payload


async def _paper_payload(
    artifact_id_or_url: str,
    route_template: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_id = extract_paper_id(artifact_id_or_url)
    payload = await api_payload(
        route_template.format(artifact_id=path_segment(artifact_id)),
        params=params,
    )
    payload["artifact_id"] = artifact_id
    return payload


async def get_hypothesis(
    hypothesis_id_or_url: str,
    view: HypothesisView = "context",
) -> dict[str, Any]:
    """Fetch a hypothesis from Lacuna's server-side API.

    view selects the response shape:

    - "context" (default, recommended): compact single-fetch proposal context —
      summary_markdown, abstract, and linked directions, with the raw upstream
      record (whose markdown duplicates summary_markdown) dropped server-side.
    - "full": the complete two-endpoint merge, including the raw hypothesis record,
      version history, and signal counts. Larger; use only when you need versions
      or signals.
    """
    normalized_view = _normalize_view(view, _HYPOTHESIS_VIEW_ROUTES)
    hypothesis_id = extract_hypothesis_id(hypothesis_id_or_url)
    quoted_hypothesis_id = path_segment(hypothesis_id)
    if normalized_view == "context":
        payload = await api_object(
            f"/api/v1/context/hypothesis/{quoted_hypothesis_id}",
            params={"view": "compact"},
        )
        payload["hypothesis_id"] = hypothesis_id
        return payload
    payload = await api_payload(f"/api/v1/hypotheses/{quoted_hypothesis_id}")
    context = await api_object(f"/api/v1/context/hypothesis/{quoted_hypothesis_id}")
    payload["hypothesis_id"] = hypothesis_id
    payload["context"] = context
    for field in _HYPOTHESIS_PASSTHROUGH_FIELDS:
        if field in context:
            payload[field] = context[field]
    payload["summary_markdown"] = context.get("summary_markdown", "")
    payload["abstract"] = context.get("abstract", {})
    payload["directions"] = context.get("directions", [])
    return payload


async def get_direction(
    cluster_id_or_url: str | int,
    view: DirectionView = "context",
) -> dict[str, Any]:
    """Fetch a Lacuna research direction/cluster.

    view selects the response shape (`context` typically contains the fields
    `full` provides plus the agent-oriented summary content):

    - "context" (default, recommended): compact agent-oriented summary with
      summary_markdown, capped papers/authors/related_directions, and
      truncation markers.
    - "full": raw upstream cluster record only. Cheaper than context when you
      only need basic cluster metadata.
    """
    cluster_id = extract_cluster_id(cluster_id_or_url)
    normalized_view = _normalize_view(view, _DIRECTION_VIEW_ROUTES)
    route_template = _DIRECTION_VIEW_ROUTES[normalized_view]
    params = {"view": "compact"} if normalized_view == "context" else None
    payload = await api_payload(route_template.format(cluster_id=cluster_id), params=params)
    payload["cluster_id"] = cluster_id
    return payload


async def get_direction_papers(
    cluster_id_or_url: str | int,
    page: int = 1,
    limit: int = 24,
    view: DirectionPapersView = "compact",
) -> dict[str, Any]:
    """Fetch paginated papers associated with a Lacuna research direction/cluster.

    view selects the per-paper shape:

    - "compact" (default, recommended): citation-ready rows (id, url, title, year,
      venue, a few authors, abstract snippet). Drops the raw upstream info blob and
      levels.cluster internals that otherwise dominate the payload.
    - "full": the complete upstream paper records. Much larger; use only when you
      need the raw metadata (openalex/dblp/arxiv ids, etc.).
    """
    cluster_id = extract_cluster_id(cluster_id_or_url)
    normalized_view = _normalize_view(view, _DIRECTION_PAPERS_VIEW_ROUTES)
    payload = await api_payload(
        f"/api/v1/clusters/{cluster_id}/papers",
        params={
            "page": max(1, page),
            "limit": max(1, min(limit, DIRECTION_PAPERS_MAX_LIMIT)),
            "view": _DIRECTION_PAPERS_VIEW_ROUTES[normalized_view],
        },
    )
    payload["cluster_id"] = cluster_id
    return payload


async def get_paper(
    artifact_id_or_url: str,
    view: PaperView = "context",
    figure_limit: int | None = None,
) -> dict[str, Any]:
    """Fetch a Lacuna paper by artifact id or paper URL.

    view selects the response shape. `context` requests Lacuna's compact
    agent-oriented context by default, while the four single-field views
    (blog/figures/concepts/neighbors) return isolated sub-resources:

    - "context" (default, recommended): agent-oriented summary with
      summary_markdown, authors, and a small figure preview. Start here for almost
      everything.
    - "full": raw upstream paper record only. Cheaper than context when you
      only need basic metadata.
    - "preview": compact card with unique fields `excerpt`, `excerpt_kind`,
      `bookmarked`. Use for citation-style display.
    - "blog": just the summary_markdown content, without the rest of the
      context envelope.
    - "figures": just the figures list.
    - "concepts": just the concepts list.
    - "neighbors": just the related-papers list.

    figure_limit (context view only) caps the figure preview (server default 3).
    Pass 0 to suppress figure previews while keeping a `figures_truncated` signal.
    """
    normalized_view = _normalize_view(view, _PAPER_VIEW_ROUTES)
    route_template = _PAPER_VIEW_ROUTES[normalized_view]
    params: dict[str, Any] | None = None
    if normalized_view == "context":
        params = {"view": "compact"}
        if figure_limit is not None:
            if figure_limit < 0:
                raise ValueError("figure_limit must be greater than or equal to 0")
            params["figure_limit"] = figure_limit
    return await _paper_payload(artifact_id_or_url, route_template, params=params)


async def get_author(
    author_id_or_url: str,
    papers_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    papers_offset: int = 0,
    levels_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    levels_offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Fetch a Lacuna author by author id or author URL.

    Author profiles describe research output only (papers, directions, impact).
    Affiliations, employment, and biography are out of scope of the corpus; do
    not infer or guess them from this data.

    Large paper lists are sliced by default for MCP usability. Set full=True to
    return upstream arrays unsliced.
    """
    author_id = extract_route_key(author_id_or_url, "author")
    payload = await api_payload(f"/api/v1/authors/{path_segment(author_id)}")
    truncate_author_payload_in_place(
        payload,
        papers_limit=papers_limit,
        papers_offset=papers_offset,
        levels_limit=levels_limit,
        levels_offset=levels_offset,
        full=full,
    )
    payload["author_id"] = author_id
    return payload


async def get_author_context(
    author_id_or_url: str,
    view: ContextView = "context",
    papers_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    papers_offset: int = 0,
    impact_clusters_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    impact_clusters_offset: int = 0,
    levels_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    levels_offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Fetch agent-oriented context for a Lacuna author.

    Author profiles describe research output only (papers, directions, impact).
    Affiliations, employment, and biography are out of scope of the corpus; do
    not infer or guess them from this data.

    view selects the response shape:

    - "context" (default, recommended): Lacuna's compact author context — capped
      readable papers and an `impact_directions` list (named research directions)
      in place of the raw numeric `impact_clusters` telemetry, with the duplicated
      nested author record dropped server-side.
    - "full": the complete author context (raw `impact_clusters`, nested author
      record). The papers_limit/offset, impact_clusters_limit/offset,
      levels_limit/offset, and full= params apply only to this view, slicing the
      upstream arrays MCP-side.
    """
    normalized_view = _normalize_view(view, _CONTEXT_VIEW_ROUTES)
    author_id = extract_route_key(author_id_or_url, "author")
    if normalized_view == "context":
        payload = await api_payload(
            f"/api/v1/context/author/{path_segment(author_id)}",
            params={"view": "compact"},
        )
        payload["author_id"] = author_id
        return payload
    payload = await api_payload(f"/api/v1/context/author/{path_segment(author_id)}")
    truncate_author_payload_in_place(
        payload,
        papers_limit=papers_limit,
        papers_offset=papers_offset,
        levels_limit=levels_limit,
        levels_offset=levels_offset,
        full=full,
    )
    truncate_payload_list_in_place(
        payload,
        "impact_clusters",
        limit=impact_clusters_limit,
        offset=impact_clusters_offset,
        full=full,
    )
    truncate_nested_author_payload_in_place(
        payload,
        papers_limit=papers_limit,
        papers_offset=papers_offset,
        levels_limit=levels_limit,
        levels_offset=levels_offset,
        full=full,
    )
    payload["author_id"] = author_id
    return payload


async def get_author_impact(
    author_id_or_url: str,
    impact_clusters_limit: int = DEFAULT_AUTHOR_LIST_LIMIT,
    impact_clusters_offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Fetch Lacuna's impact clusters for an author.

    Large impact_clusters arrays are sliced by default for MCP usability. Set
    full=True to return upstream arrays unsliced.
    """
    author_id = extract_route_key(author_id_or_url, "author")
    payload = await api_payload(f"/api/v1/authors/{path_segment(author_id)}/impact")
    truncate_payload_list_in_place(
        payload,
        "impact_clusters",
        limit=impact_clusters_limit,
        offset=impact_clusters_offset,
        full=full,
    )
    payload["author_id"] = author_id
    return payload


async def get_author_neighbors(author_id_or_url: str) -> dict[str, Any]:
    """Fetch neighboring/similar Lacuna authors."""
    author_id = extract_route_key(author_id_or_url, "author")
    payload = await api_payload(f"/api/v1/authors/{path_segment(author_id)}/neighbors")
    payload["author_id"] = author_id
    return payload


async def get_venue_context(
    venue_key_or_url: str,
    year: int | None = None,
    view: ContextView = "context",
) -> dict[str, Any]:
    """Fetch agent-oriented context for a Lacuna venue, optionally scoped to a year.

    Venue keys are opaque hashes (e.g. "d7bf22905bd6"), never human-readable
    names like "icml". Find the key first via search_lacuna(search_type="venue")
    or pass a /venue/... page URL.

    view selects the response shape:

    - "context" (default, recommended): compact venue context — capped top authors,
      non-placeholder top clusters, and a recent-activity slice (the requested
      `year` is always included), with the duplicated venue block and full year
      histogram dropped server-side.
    - "full": the complete venue context (full year histogram, all top authors/
      clusters, duplicated venue record).
    """
    normalized_view = _normalize_view(view, _CONTEXT_VIEW_ROUTES)
    params = {"view": "compact"} if normalized_view == "context" else None
    venue_key, extracted_year = extract_venue_key_year(venue_key_or_url, year)
    quoted_venue_key = path_segment(venue_key)
    if extracted_year is None:
        payload = await api_payload(f"/api/v1/context/venue/{quoted_venue_key}", params=params)
    else:
        payload = await api_payload(
            f"/api/v1/context/venue/{quoted_venue_key}/{extracted_year}", params=params
        )
    payload["venue_key"] = venue_key
    return payload


async def get_institution_context(
    institution_key_or_url: str,
    view: ContextView = "context",
) -> dict[str, Any]:
    """Fetch agent-oriented context for a Lacuna institution.

    view selects the response shape:

    - "context" (default, recommended): compact institution context — capped top
      authors with the duplicated institution block dropped server-side.
    - "full": the complete institution context (all authors, duplicated record).
    """
    normalized_view = _normalize_view(view, _CONTEXT_VIEW_ROUTES)
    params = {"view": "compact"} if normalized_view == "context" else None
    institution_key = extract_route_key(institution_key_or_url, "institution")
    payload = await api_payload(
        f"/api/v1/context/institution/{path_segment(institution_key)}", params=params
    )
    payload["institution_key"] = institution_key
    return payload


TOOL_FUNCTIONS: tuple[Callable[..., Any], ...] = (
    search_lacuna,
    get_hypothesis,
    get_direction,
    get_direction_papers,
    get_paper,
    get_author,
    get_author_context,
    get_author_impact,
    get_author_neighbors,
    get_venue_context,
    get_institution_context,
)
