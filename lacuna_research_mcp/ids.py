from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse


def path_segment(value: str | int) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("Path segment must not be empty")
    return quote(text, safe="")


def _looks_like_url_or_path(value: str) -> bool:
    parsed = urlparse(value)
    return value.startswith("/") or bool(parsed.netloc) or "://" in value


def extract_hypothesis_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"/hypothesis/([^/?#]+)", value)
    if match:
        value = match.group(1)
    slug_match = re.search(r"([0-9a-f]{16})$", value)
    if slug_match:
        return slug_match.group(1)
    if _looks_like_url_or_path(value):
        raise ValueError(f"Invalid hypothesis id or URL: {value!r}")
    return value


def extract_paper_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"/paper/([^?#]+)", value)
    if match:
        parts = [part for part in match.group(1).strip("/").split("/") if part]
        for part in reversed(parts):
            if part.startswith("art_"):
                return part
        raise ValueError(f"Invalid paper id or URL: {value!r}")
    if _looks_like_url_or_path(value):
        raise ValueError(f"Invalid paper id or URL: {value!r}")
    return value


def extract_cluster_id(value: str | int) -> int:
    if isinstance(value, int):
        cluster_id = value
    else:
        text = str(value).strip()
        match = re.search(r"/(?:direction|cluster)/[^/?#]*?(\d+)(?:[/?#]|$)", text)
        if match:
            cluster_id = int(match.group(1))
        elif _looks_like_url_or_path(text):
            raise ValueError(f"Invalid cluster id or direction URL: {text!r}")
        else:
            try:
                cluster_id = int(text)
            except ValueError as exc:
                raise ValueError(f"Invalid cluster id or direction URL: {text!r}") from exc
    if cluster_id <= 0:
        raise ValueError(f"Invalid cluster id: must be positive, got {cluster_id}")
    return cluster_id


def extract_route_key(value: str, route_name: str) -> str:
    value = value.strip()
    match = re.search(rf"/{re.escape(route_name)}/([^?#]+)", value)
    if match:
        return unquote(match.group(1).rstrip("/").split("/")[-1])
    if _looks_like_url_or_path(value):
        raise ValueError(f"Invalid {route_name} key or URL: {value!r}")
    return value


def extract_venue_key_year(value: str, year: int | None = None) -> tuple[str, int | None]:
    value = value.strip()
    match = re.search(r"/venue/([^/?#]+)(?:/(\d{4}))?", value)
    if match:
        extracted_year = int(match.group(2)) if match.group(2) else None
        return unquote(match.group(1)), year if year is not None else extracted_year

    key_year_match = re.fullmatch(r"([^:]+):(\d{4})", value)
    if key_year_match:
        extracted_year = int(key_year_match.group(2))
        return key_year_match.group(1), year if year is not None else extracted_year

    if _looks_like_url_or_path(value):
        raise ValueError(f"Invalid venue key/year or URL: {value!r}")
    return value, year
