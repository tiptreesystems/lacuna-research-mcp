import pytest
from mcp import Client

from lacuna_research_mcp import server, tools
from lacuna_research_mcp.ids import extract_paper_id, extract_work_page_id
from lacuna_research_mcp.tools import _WORK_INTERNAL_FIELDS


@pytest.mark.parametrize(
    "value",
    [
        "/work/title/wrk_example/version/art_old",
        "https://lacuna.tiptreesystems.com/work/title/wrk_example/version/art_old/md?q=1#section",
    ],
)
def test_version_url_preserves_paper_id(value):
    assert extract_paper_id(value) == "art_old"


@pytest.mark.parametrize("search_type", ["paper", "all", "work", "works"])
async def test_search_preserves_paper_identity(monkeypatch, search_type):
    async def api_payload(path, *, params):
        assert path == "/api/v1/search"
        assert params["type"] == ("all" if search_type == "all" else "paper")
        return {
            "type_filter": params["type"],
            "total_results": 2,
            "results": [
                {
                    "type": "paper",
                    "id": "art_main",
                    "work_id": "wrk_example",
                    "presentation_artifact_id": "art_main",
                    "title": "Selected title",
                    "versions": [{"artifact_id": "art_old"}],
                },
                {"type": "paper", "id": "art_book"},
            ],
        }

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.search_lacuna("attention", search_type=search_type)
    assert result["type_filter"] == ("all" if search_type == "all" else "paper")
    assert result["total_results"] == 2
    paper = result["results"][0]
    assert paper["type"] == "paper" and paper["id"] == "art_main"
    assert not _WORK_INTERNAL_FIELDS & paper.keys()
    assert paper["versions"][0]["artifact_id"] == "art_old"
    assert result["results"][1] == {"type": "paper", "id": "art_book"}


async def test_exact_paper_content_with_versions(monkeypatch):
    async def api_payload(path, *, params):
        assert path == "/api/v1/context/paper/art_old"
        assert params == {"view": "compact", "include_resources": True}
        return {
            "type": "paper",
            "id": "art_old",
            "work_id": "wrk_example",
            "work_url": "https://lacuna.test/work/title/wrk_example",
            "presentation_artifact_id": "art_main",
            "title": "Old title",
            "summary_markdown": "Old content",
            "versions": [{"artifact_id": "art_old"}, {"artifact_id": "art_main"}],
            "resources": [{"url": "https://github.com/example/code"}],
        }

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.get_paper("/work/title/wrk_example/version/art_old")
    assert result["id"] == "art_old" and result["type"] == "paper"
    assert result["title"] == "Old title" and result["summary_markdown"] == "Old content"
    assert len(result["versions"]) == 2 and len(result["resources"]) == 1
    assert not _WORK_INTERNAL_FIELDS & result.keys()
    assert result["presentation_artifact_id"] == "art_main"


@pytest.mark.parametrize("view", ["context", "full", "figures"])
@pytest.mark.parametrize("value", ["/work/title/wrk_example", "wrk_example"])
async def test_main_page_url_resolves_internally(monkeypatch, view, value):
    calls = []

    async def api_payload(path, *, params):
        calls.append(path)
        if path == "/api/v1/context/work/wrk_example":
            return {
                "type": "work",
                "id": "wrk_example",
                "context_key": "work:wrk_example",
                "presentation_artifact_id": "art_main",
                "summary_markdown": "Selected content",
                "versions": [{"artifact_id": "art_old"}],
            }
        if view == "full":
            assert path == "/api/v1/papers/art_main"
            assert params == {"include_resources": True}
            return {"id": "art_main", "title": "Raw record"}
        assert path == "/api/v1/papers/art_main/figures"
        return {"figures": []}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.get_paper(value, view=view)
    assert result["artifact_id"] == "art_main"
    if view == "context":
        assert result["id"] == "art_main" and result["type"] == "paper"
        assert result["context_key"] == "paper:art_main"
        assert result["summary_markdown"] == "Selected content"
        assert len(calls) == 1
    else:
        assert len(calls) == 2
        if view == "full":
            assert result == {"id": "art_main", "title": "Raw record", "artifact_id": "art_main"}


async def test_only_paper_tool_registered(monkeypatch):
    async def api_payload(path, *, params):
        assert path == "/api/v1/context/paper/art_main"
        return {"type": "paper", "id": "art_main", "versions": [{"artifact_id": "art_old"}]}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    app = server.create_mcp()
    listed = {tool.name: tool for tool in await app.list_tools()}
    assert len(listed) == 12
    assert "get_work" not in listed and "get_paper" in listed
    assert "get_work" not in server.SERVER_INSTRUCTIONS
    async with Client(app) as client:
        result = await client.call_tool("get_paper", {"artifact_id_or_url": "art_main"})
        assert not result.is_error
        assert result.structured_content["versions"][0]["artifact_id"] == "art_old"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/work/wrk_example", "wrk_example"),
        ("wrk_example", "wrk_example"),
        ("  wrk_example  ", "wrk_example"),
        ("wrk_", None),
        ("wrk_example/version/art_old", None),
        ("/work/title/wrk_example/md", "wrk_example"),
        ("https://lacuna.test/work/title/wrk_example?next=/version/art_old#section", "wrk_example"),
        ("/work/title/wrk_example/version/art_old", None),
        ("/paper/title/art_old?next=/work/title/wrk_example", None),
        ("art_old", None),
    ],
)
def test_main_work_page_id(value, expected):
    assert extract_work_page_id(value) == expected


async def test_paper_blog_omits_work_fields_without_type(monkeypatch):
    async def api_payload(path, *, params):
        assert path == "/api/v1/papers/art_old/blog"
        return {
            "content": "Old content",
            "work_id": "wrk_example",
            "work_url": "/work/title/wrk_example",
        }

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await tools.get_paper("art_old", view="blog")
    assert result == {"artifact_id": "art_old", "content": "Old content"}


@pytest.mark.parametrize("has_versions", [False, True])
@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("search_lacuna", {"query": "topic"}),
        ("get_paper", {"artifact_id_or_url": "art_main"}),
        ("get_paper", {"artifact_id_or_url": "art_main", "view": "full"}),
        ("get_direction", {"cluster_id_or_url": 1}),
        ("get_direction_papers", {"cluster_id_or_url": 1}),
        ("get_author_context", {"author_id_or_url": "aut_one"}),
        ("get_author_papers", {"author_id_or_url": "aut_one"}),
    ],
)
async def test_paper_metadata_filtering(monkeypatch, has_versions, tool, arguments):
    paper = {
        "type": "paper",
        "id": "art_main",
        "artifact_id": "art_main",
        "presentation_artifact_id": "art_main",
        "version_count": 2,
        "versions": [{"artifact_id": "art_old"}] if has_versions else [],
        "resources": [],
        "work_id": "wrk_one",
        "work_url": "/work/title/wrk_one",
        "identity_anchor_artifact_id": "art_anchor",
        "matched_artifact_id": "art_match",
    }
    other = {"type": "hypothesis", "versions": [], "resources": []}
    embedded_paper = {key: value for key, value in paper.items() if key != "type"}

    async def api_payload(path, *, params):
        if tool == "get_paper":
            return {
                **paper,
                "paper": dict(embedded_paper),
                "related_papers": [dict(embedded_paper)],
            }
        if tool == "search_lacuna":
            return {"results": [dict(paper), dict(other)], "total_results": 2}
        return {"papers": [dict(embedded_paper)], "author": {"papers": [dict(embedded_paper)]}}

    monkeypatch.setattr(tools, "api_payload", api_payload)
    result = await getattr(tools, tool)(**arguments)
    if tool == "get_paper":
        papers = [result, result["paper"], result["related_papers"][0]]
    elif tool == "search_lacuna":
        papers = [result["results"][0]]
        assert result["results"][1] == other
        assert result["total_results"] == 2
    else:
        papers = [result["papers"][0], result["author"]["papers"][0]]
    for item in papers:
        assert not _WORK_INTERNAL_FIELDS & item.keys()
        assert item["artifact_id"] == "art_main"
        assert item["presentation_artifact_id"] == "art_main"
        assert item["version_count"] == 2
        assert "resources" not in item
        if has_versions:
            assert item["versions"] == [{"artifact_id": "art_old"}]
        else:
            assert "versions" not in item
    assert paper["work_id"] == "wrk_one"
