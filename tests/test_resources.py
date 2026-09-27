import httpx
import pytest
from mcp import Client

from lacuna_research_mcp import client, config, server, tools
from lacuna_research_mcp.errors import LacunaMCPError


@pytest.mark.parametrize("view", ["context", "full"])
@pytest.mark.parametrize("include", [None, True, False])
async def test_resources_forwarding(monkeypatch, view, include):
    calls = []

    async def api_payload(path, *, params):
        calls.append((path, params))
        payload = {"id": "art_test", "title": "Paper record"}
        if params["include_resources"]:
            payload["resources"] = [{"id": "art_code", "url": "https://github.com/example/code"}]
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
        assert result["resources"][0]["id"] == "art_code"
        assert result["resources"][0]["url"] == "https://github.com/example/code"


@pytest.mark.parametrize("view", ["preview", "blog", "figures", "concepts", "neighbors"])
async def test_isolated_views_unchanged(monkeypatch, view):
    async def api_payload(path, *, params):
        assert params is None
        return {}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    await tools.get_paper("art_test", view=view)


@pytest.mark.parametrize("view", ["context", "full"])
async def test_mcp_resource_defaults_and_call(monkeypatch: pytest.MonkeyPatch, view: str) -> None:
    async def api_payload(path, *, params=None):
        if path == "/api/v1/resources/art_code":
            return {"id": "art_code", "title": "Example code"}
        assert params["include_resources"] is True
        return {"resources": [{"id": "art_code", "url": "https://github.com/example/code"}]}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    app = server.create_mcp()
    listed = {tool.name: tool for tool in await app.list_tools()}
    assert listed["get_paper"].input_schema["properties"]["include_resources"]["default"] is True
    async with Client(app) as client:
        result = await client.call_tool(
            "get_paper", {"artifact_id_or_url": "art_test", "view": view}
        )
        assert not result.is_error
        resource = result.structured_content["resources"][0]
        assert resource["id"] == "art_code"
        assert resource["url"].startswith("https://github.com/")
        detail = await client.call_tool("get_resource", {"resource_id_or_url": resource["id"]})
        assert not detail.is_error
        assert detail.structured_content["id"] == resource["id"]
        assert detail.structured_content["title"] == "Example code"


def _capture_search(monkeypatch):
    calls = []

    async def api_payload(path, *, params=None):
        calls.append((path, params))
        return {"results": []}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    return calls


def _fail_api(monkeypatch):
    async def api_payload(path, *, params=None):
        raise AssertionError("api_payload should not be called")

    monkeypatch.setattr(tools, "api_payload", api_payload)


@pytest.mark.parametrize("search_type", ["resource", "resources", " Resource "])
async def test_resource_search_type_aliases(monkeypatch, search_type):
    calls = _capture_search(monkeypatch)
    await tools.search_lacuna("ImageNet", search_type=search_type)
    path, params = calls[0]
    assert path == "/api/v1/search"
    assert params["type"] == "resource"
    assert "kind" not in params
    assert "provider" not in params


@pytest.mark.parametrize(
    ("resource_kind", "expected"),
    [
        ("dataset", ["dataset"]),
        ("Datasets", ["Datasets"]),
        ("code", ["code"]),
        ("software,model", ["software,model"]),
        (["dataset", "model", "dataset"], ["dataset", "model", "dataset"]),
        (["demo"], ["demo"]),
        ("benchmark", ["benchmark"]),
    ],
)
async def test_resource_kind_forwarded_as_repeated_kind(monkeypatch, resource_kind, expected):
    calls = _capture_search(monkeypatch)
    await tools.search_lacuna("ImageNet", search_type="resource", resource_kind=resource_kind)
    assert calls[0][1]["kind"] == expected


async def test_resource_provider_forwarded_and_allowed_with_all(monkeypatch):
    calls = _capture_search(monkeypatch)
    await tools.search_lacuna(
        "ImageNet", search_type="all", resource_kind="dataset", provider=["HuggingFace", "zenodo"]
    )
    params = calls[0][1]
    assert params["type"] == "all"
    assert params["kind"] == ["dataset"]
    assert params["provider"] == ["HuggingFace", "zenodo"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"resource_kind": "datasets"}, "Invalid kind: 'datasets'."),
        ({"provider": "gitlab"}, "Invalid provider: 'gitlab'."),
        (
            {"search_type": "paper", "resource_kind": "dataset"},
            "kind/provider filters require type=resource or type=all.",
        ),
    ],
)
async def test_resource_filter_errors_come_from_server(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict, message: str
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"error": message})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:

        async def get_http_client() -> httpx.AsyncClient:
            return http_client

        monkeypatch.setattr(client, "get_http_client", get_http_client)
        with pytest.raises(LacunaMCPError) as exc_info:
            await tools.search_lacuna("ImageNet", **kwargs)
    assert message in str(exc_info.value)
    assert len(requests) == 1
    if "resource_kind" in kwargs:
        assert requests[0].url.params.get_list("kind") == [kwargs["resource_kind"]]
    if "provider" in kwargs:
        assert requests[0].url.params.get_list("provider") == [kwargs["provider"]]


async def test_blank_resource_filters_do_not_restrict_all_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_search(monkeypatch)
    await tools.search_lacuna(
        "ImageNet", resource_kind=[" "], provider="", date_from="2024", sort="year_desc"
    )
    assert calls[0][1]["date_from"] == "2024"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"search_type": "resource", "date_from": "2020"}, "date_from not supported"),
        (
            {"search_type": "all", "resource_kind": "dataset", "venue": "icml"},
            "venue not supported",
        ),
        ({"search_type": "resource", "sort": "year_desc"}, "not supported for resource search"),
        ({"search_type": "resource", "ranking_profile": "semantic"}, "semantic embeddings"),
        (
            {"search_type": "all", "provider": "github", "ranking_profile": "semantic"},
            "semantic embeddings",
        ),
        ({"search_type": "resource", "fields": "abstract"}, "does not exist on search_type"),
        (
            {"search_type": "all", "resource_kind": "model", "fields": "name"},
            "does not exist on search_type 'resource'",
        ),
        ({"search_type": "paper", "fields": "description"}, "does not exist on search_type"),
    ],
)
async def test_resource_search_rejects_unsupported_combinations(monkeypatch, kwargs, message):
    _fail_api(monkeypatch)
    with pytest.raises(ValueError, match=message):
        await tools.search_lacuna("ImageNet", **kwargs)


async def test_resource_search_accepts_resource_fields_and_bm25(monkeypatch):
    calls = _capture_search(monkeypatch)
    await tools.search_lacuna(
        "image classification benchmark",
        search_type="resource",
        resource_kind="dataset",
        ranking_profile="bm25",
        fields="title^2,description,topics,paper_titles,provider_key",
    )
    params = calls[0][1]
    assert params["ranking_profile"] == "bm25_title_abstract"
    assert params["fields"] == "title^2,description,topics,paper_titles,provider_key"


@pytest.mark.parametrize(
    "value",
    [
        "art_072e",
        "/resource/penfever-janus-dataset/art_072e",
        "https://lacuna.tiptreesystems.com/resource/penfever-janus-dataset/art_072e?tab=papers",
    ],
)
async def test_get_resource_accepts_id_or_url(monkeypatch, value):
    calls = []

    async def api_payload(path, *, params=None):
        calls.append((path, params))
        return {"id": "art_072e", "kind": "dataset"}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.get_resource(value)
    assert calls == [("/api/v1/resources/art_072e", None)]
    assert result["resource_id"] == "art_072e"


async def test_mcp_resource_search_over_http(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "query": "ImageNet",
                "type_filter": "resource",
                "total_results": 1,
                "results": [
                    {
                        "type": "resource",
                        "id": "art_072e",
                        "kind": "dataset",
                        "provider": "huggingface",
                        "linked_paper_count": 1,
                        "context_url": "/resource/penfever-janus-dataset/art_072e",
                        "url": "https://huggingface.co/datasets/penfever/JANuS_dataset",
                        "description": "See [paper](/paper/robust/art_9c0c).",
                    }
                ],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def get_http_client():
        return http_client

    monkeypatch.setattr(client, "get_http_client", get_http_client)
    app = server.create_mcp()
    listed = {tool.name: tool for tool in await app.list_tools()}
    properties = listed["search_lacuna"].input_schema["properties"]
    assert "resource_kind" in properties
    assert "provider" in properties
    assert 'resource_kind="dataset"' in listed["search_lacuna"].description
    assert "get_resource" in listed
    async with Client(app) as mcp_client:
        result = await mcp_client.call_tool(
            "search_lacuna",
            {
                "query": "ImageNet",
                "search_type": "resource",
                "resource_kind": ["dataset", "model"],
                "provider": "huggingface",
            },
        )
    await http_client.aclose()

    assert not result.is_error
    assert len(requests) == 1
    query = requests[0].url.params
    assert requests[0].url.path == "/api/v1/search"
    assert query["type"] == "resource"
    assert query.get_list("kind") == ["dataset", "model"]
    assert query.get_list("provider") == ["huggingface"]
    item = result.structured_content["results"][0]
    assert item["context_url"] == (
        f"{config.DEFAULT_SITE_URL}/resource/penfever-janus-dataset/art_072e"
    )
    assert item["url"] == "https://huggingface.co/datasets/penfever/JANuS_dataset"
    assert f"{config.DEFAULT_SITE_URL}/paper/robust/art_9c0c" in item["description"]
