import pytest
from mcp import Client

from lacuna_research_mcp import server, tools


@pytest.mark.parametrize("view", ["context", "full"])
@pytest.mark.parametrize("include", [None, True, False])
async def test_resources_forwarding(monkeypatch, view, include):
    calls = []

    async def api_payload(path, *, params):
        calls.append((path, params))
        payload = {"id": "art_test", "title": "Paper record"}
        if params["include_resources"]:
            payload["resources"] = [{"url": "https://github.com/example/code"}]
        return payload

    monkeypatch.setattr(tools, "api_payload", api_payload)
    kwargs = {} if include is None else {"include_resources": include}
    result = await tools.get_paper("art_test", view=view, **kwargs)
    assert len(calls) == 1
    expected_params = {"include_resources": True if include is None else include}
    if view == "context":
        expected_params["view"] = "compact"
        assert calls[0] == ("/api/v1/context/paper/art_test", expected_params)
    else:
        assert calls[0] == ("/api/v1/papers/art_test", expected_params)
    assert result["artifact_id"] == "art_test"
    if include is False:
        assert "resources" not in result
    else:
        assert result["resources"][0]["url"] == "https://github.com/example/code"


@pytest.mark.parametrize("view", ["preview", "blog", "figures", "concepts", "neighbors"])
async def test_isolated_views_unchanged(monkeypatch, view):
    async def api_payload(path, *, params):
        assert params is None
        return {}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    await tools.get_paper("art_test", view=view)


async def test_mcp_resource_defaults_and_call(monkeypatch):
    async def api_payload(path, *, params):
        assert params["include_resources"] is True
        return {"resources": [{"url": "https://github.com/example/code"}]}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    app = server.create_mcp()
    listed = {tool.name: tool for tool in await app.list_tools()}
    assert listed["get_paper"].input_schema["properties"]["include_resources"]["default"] is True
    async with Client(app) as client:
        result = await client.call_tool("get_paper", {"artifact_id_or_url": "art_test"})
        assert not result.is_error
        assert result.structured_content["resources"][0]["url"].startswith("https://github.com/")
