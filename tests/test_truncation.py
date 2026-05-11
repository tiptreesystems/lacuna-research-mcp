from __future__ import annotations

from lacuna_research_mcp import config, truncation


def test_list_truncation_caps_and_records_metadata() -> None:
    payload = {"papers": list(range(5)), "levels": {"cluster": list(range(4))}}

    assert truncation.truncate_payload_list_in_place(
        payload,
        "papers",
        limit=500,
        offset=1,
        full=False,
    )
    assert payload["papers"] == [1, 2, 3, 4]
    assert payload["papers_limit"] == config.LOCAL_LIST_MAX_LIMIT
    assert payload["truncation"]["papers"] == {
        "total": 5,
        "offset": 1,
        "limit": config.LOCAL_LIST_MAX_LIMIT,
        "returned": 4,
        "truncated": True,
    }

    assert truncation.truncate_levels_clusters_in_place(payload, limit=2, offset=0, full=False)
    assert payload["levels"]["cluster"] == [0, 1]
    assert payload["levels_cluster_total"] == 4
    assert payload["truncation"]["levels.cluster"] == {
        "total": 4,
        "offset": 0,
        "limit": 2,
        "returned": 2,
        "truncated": True,
    }


def test_list_truncation_replaces_non_dict_metadata() -> None:
    payload = {"papers": list(range(3)), "truncation": None}

    assert truncation.truncate_payload_list_in_place(
        payload, "papers", limit=2, offset=0, full=False
    )
    assert payload["truncation"]["papers"] == {
        "total": 3,
        "offset": 0,
        "limit": 2,
        "returned": 2,
        "truncated": True,
    }

    levels_payload = {
        "truncation": "upstream string",
        "levels": {"cluster": list(range(3)), "truncation": None},
    }

    assert truncation.truncate_levels_clusters_in_place(
        levels_payload, limit=2, offset=0, full=False
    )
    assert levels_payload["levels"]["truncation"]["cluster"] == {
        "total": 3,
        "offset": 0,
        "limit": 2,
        "returned": 2,
        "truncated": True,
    }
    assert levels_payload["truncation"]["levels.cluster"] == {
        "total": 3,
        "offset": 0,
        "limit": 2,
        "returned": 2,
        "truncated": True,
    }
