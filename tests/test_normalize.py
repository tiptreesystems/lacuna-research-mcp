from __future__ import annotations

import logging
from typing import Any

import pytest

from lacuna_research_mcp import config, normalize


def test_url_and_markdown_normalization() -> None:
    payload = {
        "url": "/paper/slug/art_1",
        "pdf_url": "/pdf/art_1",
        "summary_markdown": ("See /paper/slug/art_1, /author/name/aut_1, and /cluster/name-25284."),
        "items": [{"url": "/venue/v1"}],
    }

    normalized = normalize.normalize_url_fields(payload)

    assert normalized["url"] == f"{config.DEFAULT_SITE_URL}/paper/slug/art_1"
    assert normalized["pdf_url"] == f"{config.DEFAULT_SITE_URL}/pdf/art_1"
    assert f"{config.DEFAULT_SITE_URL}/paper/slug/art_1" in normalized["summary_markdown"]
    assert f"{config.DEFAULT_SITE_URL}/author/name/aut_1" in normalized["summary_markdown"]
    assert f"{config.DEFAULT_SITE_URL}/cluster/name-25284" in normalized["summary_markdown"]
    assert normalized["items"][0]["url"] == f"{config.DEFAULT_SITE_URL}/venue/v1"


def test_markdown_absolutification_applies_only_to_markdown_like_fields() -> None:
    payload = {
        "content": "See /paper/slug/art_1 for details.",
        "description": "Related to /paper/slug/art_3.",
        "versions": [{"markdown": "Cites /paper/slug/art_4."}],
        "title": "Token-Level Alignment of Informal Mathematics",
        "abstract": "Plain prose with no Lacuna links.",
        "note": "Path-like /paper/slug/art_2 inside arbitrary field.",
    }

    normalized = normalize.normalize_url_fields(payload)

    assert normalized["content"] == f"See {config.DEFAULT_SITE_URL}/paper/slug/art_1 for details."
    assert normalized["description"] == f"Related to {config.DEFAULT_SITE_URL}/paper/slug/art_3."
    assert normalized["versions"][0]["markdown"] == (
        f"Cites {config.DEFAULT_SITE_URL}/paper/slug/art_4."
    )
    assert normalized["note"] == "Path-like /paper/slug/art_2 inside arbitrary field."
    assert normalized["title"] == "Token-Level Alignment of Informal Mathematics"
    assert normalized["abstract"] == "Plain prose with no Lacuna links."


def test_url_normalization_preserves_safe_absolute_urls_and_unsafe_strings() -> None:
    assert normalize.make_absolute_lacuna_url("/paper/slug/art_1") == (
        f"{config.DEFAULT_SITE_URL}/paper/slug/art_1"
    )
    assert normalize.make_absolute_lacuna_url(f"{config.DEFAULT_SITE_URL}/paper/slug/art_1") == (
        f"{config.DEFAULT_SITE_URL}/paper/slug/art_1"
    )
    assert normalize.make_absolute_lacuna_url("https://doi.org/10.1234/example") == (
        "https://doi.org/10.1234/example"
    )
    assert normalize.make_absolute_lacuna_url("http://example.test/source") == (
        "http://example.test/source"
    )
    assert normalize.make_absolute_lacuna_url("//evil.example/x") is None
    assert normalize.make_absolute_lacuna_url("javascript:alert(1)") is None
    assert normalize.make_absolute_lacuna_url("data:text/html,x") is None

    normalized = normalize.normalize_url_fields(
        {
            "url": "//evil.example/x",
            "pdf_url": "javascript:alert(1)",
            "doi_url": "https://doi.org/10.1234/example",
            "items": [{"url": "https://publisher.example/paper"}],
        }
    )

    assert normalized == {
        "url": "//evil.example/x",
        "pdf_url": "javascript:alert(1)",
        "doi_url": "https://doi.org/10.1234/example",
        "items": [{"url": "https://publisher.example/paper"}],
    }


def test_markdown_normalization_preserves_sentence_punctuation() -> None:
    markdown = (
        "See /paper/slug/art_1. Compare /author/name/aut_1, "
        "then /venue/v1: done; and /paper/slug/art_2?tab=abstract."
    )

    assert normalize.absolutify_lacuna_markdown(markdown) == (
        f"See {config.DEFAULT_SITE_URL}/paper/slug/art_1. "
        f"Compare {config.DEFAULT_SITE_URL}/author/name/aut_1, "
        f"then {config.DEFAULT_SITE_URL}/venue/v1: done; "
        f"and {config.DEFAULT_SITE_URL}/paper/slug/art_2?tab=abstract."
    )


def test_url_normalization_has_depth_cap(caplog: pytest.LogCaptureFixture) -> None:
    payload: dict[str, Any] = {"url": "/paper/root/art_0"}
    for _ in range(config.MAX_NORMALIZE_DEPTH + 2):
        payload = {"child": payload}

    caplog.set_level(logging.WARNING, logger=normalize.__name__)
    normalized = normalize.normalize_url_fields(payload)

    assert isinstance(normalized, dict)
    assert "Skipping URL normalization beyond max depth" in caplog.text
