from __future__ import annotations

from typing import Any

from lacuna_research_mcp.config import LOCAL_LIST_MAX_LIMIT


def _ensure_truncation_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("truncation")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["truncation"] = metadata
    return metadata


def truncate_payload_list_in_place(
    payload: dict[str, Any],
    key: str,
    *,
    limit: int,
    offset: int,
    full: bool,
) -> bool:
    items = payload.get(key)
    if not isinstance(items, list):
        return False

    total = len(items)
    if full:
        truncated_items = items
        safe_offset = 0
        safe_limit = total
        truncated = False
    else:
        safe_offset = max(0, offset)
        safe_limit = max(0, min(limit, LOCAL_LIST_MAX_LIMIT))
        truncated_items = items[safe_offset : safe_offset + safe_limit]
        truncated = safe_offset > 0 or safe_offset + safe_limit < total
        payload[key] = truncated_items

    returned = len(truncated_items)
    payload[f"{key}_total"] = total
    payload[f"{key}_offset"] = safe_offset
    payload[f"{key}_limit"] = safe_limit
    payload[f"{key}_returned"] = returned
    payload[f"{key}_truncated"] = truncated
    payload["truncated"] = bool(payload.get("truncated")) or truncated
    _ensure_truncation_metadata(payload)[key] = {
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "returned": returned,
        "truncated": truncated,
    }
    return truncated


def truncate_levels_clusters_in_place(
    payload: dict[str, Any],
    *,
    limit: int,
    offset: int,
    full: bool,
) -> bool:
    levels = payload.get("levels")
    if not isinstance(levels, dict):
        return False

    truncated = truncate_payload_list_in_place(
        levels,
        "cluster",
        limit=limit,
        offset=offset,
        full=full,
    )
    level_truncation = levels.get("truncation")
    metadata = level_truncation.get("cluster") if isinstance(level_truncation, dict) else None
    if isinstance(metadata, dict):
        _ensure_truncation_metadata(payload)["levels.cluster"] = metadata
        payload["levels_cluster_total"] = metadata["total"]
        payload["levels_cluster_offset"] = metadata["offset"]
        payload["levels_cluster_limit"] = metadata["limit"]
        payload["levels_cluster_returned"] = metadata["returned"]
        payload["levels_cluster_truncated"] = metadata["truncated"]
    payload["truncated"] = bool(payload.get("truncated")) or truncated
    return truncated


def truncate_author_payload_in_place(
    payload: dict[str, Any],
    *,
    papers_limit: int,
    papers_offset: int,
    levels_limit: int,
    levels_offset: int,
    full: bool,
) -> bool:
    papers_truncated = truncate_payload_list_in_place(
        payload,
        "papers",
        limit=papers_limit,
        offset=papers_offset,
        full=full,
    )
    levels_truncated = truncate_levels_clusters_in_place(
        payload,
        limit=levels_limit,
        offset=levels_offset,
        full=full,
    )
    return papers_truncated or levels_truncated


def truncate_nested_author_payload_in_place(
    payload: dict[str, Any],
    *,
    papers_limit: int,
    papers_offset: int,
    levels_limit: int,
    levels_offset: int,
    full: bool,
) -> bool:
    author_payload = payload.get("author")
    if not isinstance(author_payload, dict):
        return False
    nested_truncated = truncate_author_payload_in_place(
        author_payload,
        papers_limit=papers_limit,
        papers_offset=papers_offset,
        levels_limit=levels_limit,
        levels_offset=levels_offset,
        full=full,
    )
    payload["truncated"] = bool(payload.get("truncated")) or nested_truncated
    return nested_truncated
