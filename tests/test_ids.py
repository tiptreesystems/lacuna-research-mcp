from __future__ import annotations

import pytest

from lacuna_research_mcp import config, ids


def test_id_extractors_handle_urls_and_bad_cluster_ids() -> None:
    assert ids.extract_paper_id("https://lacuna.tiptreesystems.com/paper/a/b/art_abc") == "art_abc"
    assert (
        ids.extract_paper_id("https://lacuna.tiptreesystems.com/paper/slug/art_abc/extra")
        == "art_abc"
    )
    assert ids.extract_paper_id("art_abc") == "art_abc"
    assert ids.extract_cluster_id("25284") == 25284
    assert ids.extract_cluster_id("https://lacuna.tiptreesystems.com/direction/name-25284") == 25284
    assert ids.extract_cluster_id("https://lacuna.tiptreesystems.com/cluster/name-25284") == 25284

    with pytest.raises(ValueError, match="Invalid paper id or URL"):
        ids.extract_paper_id("https://example.com/not-a-paper/art_abc")
    with pytest.raises(ValueError, match="Invalid paper id or URL"):
        ids.extract_paper_id("https://lacuna.tiptreesystems.com/paper/slug-only")
    with pytest.raises(ValueError, match="Invalid paper id or URL"):
        ids.extract_paper_id("/not-a-paper/art_abc")
    with pytest.raises(ValueError, match="Invalid cluster id or direction URL"):
        ids.extract_cluster_id("https://example.com/other/25284")
    with pytest.raises(ValueError, match="Invalid cluster id or direction URL"):
        ids.extract_cluster_id("/other/25284")
    with pytest.raises(ValueError, match="Invalid cluster id or direction URL"):
        ids.extract_cluster_id("not-a-cluster-id")


def test_url_like_ids_must_match_expected_routes() -> None:
    assert ids.extract_route_key("orcid:0000-0001", "author") == "orcid:0000-0001"
    assert ids.extract_venue_key_year("venue_key:2024") == ("venue_key", 2024)

    with pytest.raises(ValueError, match="Invalid hypothesis id or URL"):
        ids.extract_hypothesis_id(f"{config.DEFAULT_SITE_URL}/hypotheses/abc")
    with pytest.raises(ValueError, match="Invalid author key or URL"):
        ids.extract_route_key(f"{config.DEFAULT_SITE_URL}/authors/abc", "author")
    with pytest.raises(ValueError, match="Invalid institution key or URL"):
        ids.extract_route_key("/institutions/abc", "institution")
    with pytest.raises(ValueError, match="Invalid venue key/year or URL"):
        ids.extract_venue_key_year(f"{config.DEFAULT_SITE_URL}/venues/abc")
