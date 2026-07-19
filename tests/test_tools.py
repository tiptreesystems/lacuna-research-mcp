from __future__ import annotations

from typing import Any

import pytest

from lacuna_research_mcp import config, tools


def test_search_type_aliases_and_invalid_values() -> None:
    assert tools._normalize_search_type("papers") == "paper"
    assert tools._normalize_search_type("directions") == "cluster"
    assert tools._normalize_search_type("") == "all"
    assert tools._normalize_search_type(None) == "all"

    with pytest.raises(ValueError, match="Invalid search_type 'foo'"):
        tools._normalize_search_type("foo")


def test_search_ranking_profile_defaults_aliases_and_invalid_values() -> None:
    assert tools._normalize_ranking_profile(None, "paper") == "default"
    assert tools._normalize_ranking_profile("", "paper") == "default"
    assert tools._normalize_ranking_profile(None, "all") == "default"
    assert tools._normalize_ranking_profile("lexical", "paper") == "default"
    assert tools._normalize_ranking_profile("bm25", "paper") == "bm25_title_abstract"
    assert tools._normalize_ranking_profile("semantic", "paper") == "semantic"

    with pytest.raises(ValueError, match="Invalid ranking_profile 'hybrid'"):
        tools._normalize_ranking_profile("hybrid", "paper")


def test_search_ranking_profile_type_compatibility() -> None:
    assert tools._normalize_ranking_profile("semantic", "all") == "semantic"
    assert tools._normalize_ranking_profile("lexical", "author") == "default"

    with pytest.raises(ValueError, match="not supported for search_type 'author'"):
        tools._normalize_ranking_profile("bm25", "author")
    with pytest.raises(ValueError, match="not supported for search_type 'institution'"):
        tools._normalize_ranking_profile("bm25_title_abstract", "institution")


@pytest.mark.parametrize(
    "search_type",
    ["all", "paper", "cluster", "hypothesis", "venue"],
)
def test_bm25_profile_accepts_every_supported_search_type(search_type: str) -> None:
    assert tools._normalize_ranking_profile("bm25", search_type) == "bm25_title_abstract"


@pytest.mark.parametrize(
    "search_type",
    ["author", "institution", "cluster", "hypothesis", "venue"],
)
def test_semantic_profile_rejects_every_unsupported_search_type(search_type: str) -> None:
    with pytest.raises(
        ValueError,
        match="fall back to substring search and silently ignore the requested ranking profile",
    ):
        tools._normalize_ranking_profile("semantic", search_type)


async def test_search_rejects_unsupported_profile_before_api_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        raise AssertionError("api_payload should not be called")

    monkeypatch.setattr(tools, "api_payload", fail_api_payload)

    with pytest.raises(ValueError, match="not supported for search_type 'author'"):
        await tools.search_lacuna("smith", search_type="authors", ranking_profile="semantic")


def test_search_sort_normalization_and_invalid_values() -> None:
    assert tools._normalize_sort(None) == "relevance"
    assert tools._normalize_sort("") == "relevance"
    assert tools._normalize_sort("relevance") == "relevance"
    assert tools._normalize_sort("Year_Desc") == "year_desc"
    assert tools._normalize_sort("year_asc") == "year_asc"

    with pytest.raises(ValueError, match="Invalid sort 'date'"):
        tools._normalize_sort("date")


@pytest.mark.parametrize("sort", ["year_desc", "year_asc"])
async def test_search_rejects_semantic_year_sort_before_api_call(
    monkeypatch: pytest.MonkeyPatch, sort: str
) -> None:
    async def fail_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        raise AssertionError("api_payload should not be called")

    monkeypatch.setattr(tools, "api_payload", fail_api_payload)

    with pytest.raises(ValueError, match="not supported with ranking_profile 'semantic'"):
        await tools.search_lacuna(
            "graph retrieval", search_type="paper", ranking_profile="semantic", sort=sort
        )


async def test_search_passes_year_sort_with_default_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_params: dict[str, Any] = {}

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert params is not None
        seen_params.update(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.search_lacuna("graph retrieval", search_type="paper", sort="year_desc")

    assert seen_params["sort"] == "year_desc"
    assert seen_params["ranking_profile"] == "default"


async def test_search_metadata_uses_mcp_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/search"
        assert params is not None
        assert params["type"] == "paper"
        assert params["ranking_profile"] == "default"
        return {"requested_type": "upstream", "normalized_type": "upstream"}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payload = await tools.search_lacuna("alignment", search_type="papers", debug=True)

    assert payload["requested_type"] == "upstream"
    assert payload["normalized_type"] == "upstream"
    assert payload["_mcp_meta"] == {
        "requested_type": "papers",
        "normalized_type": "paper",
        "requested_ranking_profile": None,
        "normalized_ranking_profile": "default",
    }


async def test_search_omits_mcp_meta_echo_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payload = await tools.search_lacuna("alignment", search_type="papers")

    assert "_mcp_meta" not in payload


async def test_search_accepts_explicit_paper_ranking_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_params: dict[str, Any] = {}

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/search"
        assert params is not None
        captured_params.update(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payload = await tools.search_lacuna(
        "attention is all you need",
        search_type="paper",
        ranking_profile="lexical",
        debug=True,
    )

    assert captured_params["ranking_profile"] == "default"
    assert payload["_mcp_meta"]["requested_ranking_profile"] == "lexical"
    assert payload["_mcp_meta"]["normalized_ranking_profile"] == "default"


async def test_search_passes_inclusive_date_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_params: dict[str, Any] = {}

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/search"
        assert params is not None
        captured_params.update(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.search_lacuna(
        "alignment",
        search_type="papers",
        date_from="2020",
        date_to="2022-03",
    )

    assert captured_params["date_from"] == "2020"
    assert captured_params["date_to"] == "2022-03"
    assert "year_from" not in captured_params
    assert "year_to" not in captured_params


async def test_detail_ids_are_quoted_in_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    captured_params: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(path)
        captured_params.append(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.get_paper("art_ok/extra?debug=1")
    await tools.get_author("author_ok/extra?debug=1")
    await tools.get_venue_context("venue_ok/2025?debug=1")
    await tools.get_institution_context("inst_ok/extra?debug=1")

    assert captured == [
        "/api/v1/context/paper/art_ok%2Fextra%3Fdebug%3D1",
        "/api/v1/authors/author_ok%2Fextra%3Fdebug%3D1",
        "/api/v1/context/venue/venue_ok%2F2025%3Fdebug%3D1",
        "/api/v1/context/institution/inst_ok%2Fextra%3Fdebug%3D1",
    ]
    # venue/institution context now default to the compact server view.
    assert captured_params == [{"view": "compact"}, None, {"view": "compact"}, {"view": "compact"}]


async def test_paper_views_map_to_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    captured_params: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(path)
        captured_params.append(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    views = ("context", "full", "preview", "blog", "figures", "concepts", "neighbors")
    payloads = [await tools.get_paper("art_ok/extra?debug=1", view=v) for v in views]

    assert captured == [
        "/api/v1/context/paper/art_ok%2Fextra%3Fdebug%3D1",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1/preview",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1/blog",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1/figures",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1/concepts",
        "/api/v1/papers/art_ok%2Fextra%3Fdebug%3D1/neighbors",
    ]
    assert captured_params == [{"view": "compact"}, None, None, None, None, None, None]
    assert all(payload["artifact_id"] == "art_ok/extra?debug=1" for payload in payloads)


async def test_direction_views_map_to_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    captured_params: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(path)
        captured_params.append(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payloads = [await tools.get_direction(17311, view=v) for v in ("context", "full")]

    assert captured == [
        "/api/v1/context/direction/17311",
        "/api/v1/clusters/17311",
    ]
    assert captured_params == [{"view": "compact"}, None]
    assert all(payload["cluster_id"] == 17311 for payload in payloads)


async def test_invalid_view_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid view 'foo'"):
        await tools.get_paper("art_abc", view="foo")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid view 'foo'"):
        await tools.get_direction(17311, view="foo")  # type: ignore[arg-type]


async def test_url_derived_ids_are_unquoted_before_api_path_quoting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(path)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.get_author(f"{config.DEFAULT_SITE_URL}/author/profile/Smith%20Alice")
    await tools.get_venue_context(f"{config.DEFAULT_SITE_URL}/venue/ACM%2FSIGIR/2024")
    await tools.get_institution_context(f"{config.DEFAULT_SITE_URL}/institution/ACME%2FResearch")

    assert captured == [
        "/api/v1/authors/Smith%20Alice",
        "/api/v1/context/venue/ACM%2FSIGIR/2024",
        "/api/v1/context/institution/ACME%2FResearch",
    ]


async def test_hypothesis_id_is_quoted_in_both_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str]] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(("payload", path))
        return {"_mcp_meta": {"source": "server_api"}, "versions": []}

    async def fake_api_object(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append(("object", path))
        return {"title": "Hypothesis"}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)
    monkeypatch.setattr(tools, "api_object", fake_api_object)

    payload = await tools.get_hypothesis("abc/def?debug=1", view="full")

    assert captured == [
        ("payload", "/api/v1/hypotheses/abc%2Fdef%3Fdebug%3D1"),
        ("object", "/api/v1/context/hypothesis/abc%2Fdef%3Fdebug%3D1"),
    ]
    assert payload["_mcp_meta"] == {"source": "server_api"}
    assert payload["title"] == "Hypothesis"


async def test_hypothesis_context_view_single_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_api_object(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append((path, params))
        return {"summary_markdown": "body", "directions": []}

    def fail_payload(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("compact hypothesis context must not hit the versions endpoint")

    monkeypatch.setattr(tools, "api_object", fake_api_object)
    monkeypatch.setattr(tools, "api_payload", fail_payload)

    payload = await tools.get_hypothesis("abc/def?debug=1")

    assert captured == [("/api/v1/context/hypothesis/abc%2Fdef%3Fdebug%3D1", {"view": "compact"})]
    assert payload["hypothesis_id"] == "abc/def?debug=1"
    assert "versions" not in payload


async def test_direction_papers_view_maps_to_server_param(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/clusters/17311/papers"
        captured.append(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.get_direction_papers(17311)
    await tools.get_direction_papers(17311, view="full")

    assert captured[0]["view"] == "compact"
    assert captured[1]["view"] == "complete"


async def test_paper_context_figure_limit_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        captured.append(params)
        return {}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    await tools.get_paper("art_ok", figure_limit=0)
    await tools.get_paper("art_ok")

    assert captured[0] == {"view": "compact", "figure_limit": 0}
    assert captured[1] == {"view": "compact"}


async def test_paper_context_rejects_negative_figure_limit() -> None:
    with pytest.raises(ValueError, match="figure_limit must be greater than or equal to 0"):
        await tools.get_paper("art_ok", figure_limit=-1)


async def test_author_context_truncates_nested_author_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/context/author/aut_1"
        return {
            "author": {
                "papers": list(range(3)),
                "levels": {"cluster": list(range(3))},
            }
        }

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payload = await tools.get_author_context("aut_1", view="full", papers_limit=1, levels_limit=1)

    assert payload["author"]["papers"] == [0]
    assert payload["author"]["levels"]["cluster"] == [0]
    assert payload["truncated"] is True
    assert payload["author_id"] == "aut_1"


async def test_author_context_compact_skips_local_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any] | None] = []

    async def fake_api_payload(
        path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert path == "/api/v1/context/author/aut_1"
        captured.append(params)
        # Server compact shape: no nested author block, capped server-side.
        return {"papers": list(range(3)), "impact_directions": []}

    monkeypatch.setattr(tools, "api_payload", fake_api_payload)

    payload = await tools.get_author_context("aut_1", papers_limit=1)

    assert captured == [{"view": "compact"}]
    # MCP-side truncation is skipped in compact mode, so papers are untouched and
    # the verbose truncation metadata is not added.
    assert payload["papers"] == [0, 1, 2]
    assert "papers_total" not in payload
    assert "truncated" not in payload
    assert payload["author_id"] == "aut_1"
