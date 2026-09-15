from typing import Any

import pytest
from mcp import Client

from lacuna_research_mcp import server, tools
from lacuna_research_mcp.ids import extract_route_key


@pytest.mark.parametrize(
    "value",
    [
        "wrk_example",
        "/work/wrk_example",
        "https://lacuna.tiptreesystems.com/work/a-title/wrk_example",
        "/work/a-title/wrk_example/md?view=full#section",
    ],
)
def test_work_id_and_urls(value):
    assert extract_route_key(value, "work") == "wrk_example"


@pytest.mark.parametrize("value", ["/paper/title/art_example", "/work/no-work-id"])
def test_work_rejects_wrong_urls(value):
    with pytest.raises(ValueError):
        extract_route_key(value, "work")


@pytest.mark.parametrize(
    "view,figure_limit,expected",
    [
        ("context", None, {"view": "compact"}),
        ("context", 0, {"view": "compact", "figure_limit": 0}),
        ("full", None, {"view": "complete"}),
    ],
)
async def test_work_context_request(monkeypatch, view, figure_limit, expected):
    async def api_payload(path, *, params):
        assert path == "/api/v1/context/work/wrk_example"
        assert params == {**expected, "include_resources": True}
        return {"type": "work", "id": "wrk_example", "versions": [{"artifact_id": "art_version"}]}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.get_work("/work/title/wrk_example", view=view, figure_limit=figure_limit)
    assert result["versions"][0]["artifact_id"] == "art_version"


@pytest.mark.parametrize("kwargs", [{"view": "preview"}, {"figure_limit": -1}])
async def test_work_invalid_options_before_request(monkeypatch, kwargs):
    async def no_request(*args, **kwargs):
        raise AssertionError("Unexpected HTTP request")

    monkeypatch.setattr(tools, "api_payload", no_request)
    with pytest.raises(ValueError):
        await tools.get_work("wrk_example", **kwargs)


@pytest.mark.parametrize("search_type", ["work", "works"])
async def test_work_search_fields(monkeypatch, search_type):
    async def api_payload(path, *, params):
        assert path == "/api/v1/search"
        assert params["type"] == "work"
        assert params["fields"] == "title^4,abstract,summary,concepts,venue"
        return {"results": [{"type": "work", "id": "wrk_example"}]}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.search_lacuna(
        "attention", search_type=search_type, fields="title^4,abstract,summary,concepts,venue"
    )
    assert result["results"][0]["id"] == "wrk_example"
    assert tools._normalize_ranking_profile("semantic", "work") == "semantic"
    with pytest.raises(ValueError, match="does not exist"):
        tools._normalize_fields("name", "work")


async def test_work_tool_registered_and_callable(monkeypatch):
    async def api_payload(path: str, *, params: dict[str, Any] | None = None):
        assert path == "/api/v1/context/work/wrk_example"
        return {"type": "work", "id": "wrk_example", "versions": []}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    app = server.create_mcp()
    listed = {tool.name: tool for tool in await app.list_tools()}
    assert len(listed) == 13
    assert "get_work" in listed and "get_paper" in listed
    assert listed["get_work"].annotations.read_only_hint is True
    async with Client(app) as client:
        result = await client.call_tool("get_work", {"work_id_or_url": "/work/title/wrk_example"})
        assert not result.is_error


async def test_work_rejects_unsupported_author_filter(monkeypatch):
    async def no_request(*args, **kwargs):
        raise AssertionError("Unexpected HTTP request")

    monkeypatch.setattr(tools, "api_payload", no_request)
    with pytest.raises(ValueError, match="author_id_or_url requires"):
        await tools.search_lacuna("attention", search_type="work", author_id_or_url="aut_example")
