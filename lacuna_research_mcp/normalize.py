from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from lacuna_research_mcp.config import DEFAULT_SITE_URL, MAX_NORMALIZE_DEPTH

logger = logging.getLogger(__name__)

_RELATIVE_LACUNA_URL_RE = re.compile(
    r"(?<!\w)"
    r"(/"
    r"(?:author|cluster|direction|figures|hypothesis|institution|paper|pdf|venue)"
    r"""/[^\s)"'>]+)"""
)
_MARKDOWN_FIELD_NAMES = frozenset({"markdown", "summary_markdown", "content", "description"})


def make_absolute_lacuna_url(
    path_or_url: str | None, site_url: str = DEFAULT_SITE_URL
) -> str | None:
    value = str(path_or_url or "").strip()
    if not value:
        return None

    site_url = site_url.rstrip("/")
    parsed_site_url = urlparse(site_url)
    parsed_value = urlparse(value)
    if parsed_value.scheme or parsed_value.netloc:
        if parsed_value.scheme in {"http", "https"} and parsed_value.netloc:
            return value
        return None

    absolute_url = urljoin(f"{site_url}/", value)
    parsed_absolute_url = urlparse(absolute_url)
    if (
        parsed_absolute_url.scheme in {"http", "https"}
        and parsed_absolute_url.netloc == parsed_site_url.netloc
    ):
        return absolute_url
    return None


def absolutify_lacuna_markdown(markdown: str, site_url: str = DEFAULT_SITE_URL) -> str:
    if not markdown:
        return ""

    def replace_relative_url(match: re.Match[str]) -> str:
        matched_url = match.group(1)
        url = matched_url.rstrip(".,;:")
        suffix = matched_url[len(url) :]
        return (make_absolute_lacuna_url(url, site_url) or url) + suffix

    return _RELATIVE_LACUNA_URL_RE.sub(
        replace_relative_url,
        markdown,
    )


def normalize_url_fields(
    payload: object,
    *,
    site_url: str = DEFAULT_SITE_URL,
) -> object:
    def normalize_value(value: object, depth: int) -> object:
        if depth > MAX_NORMALIZE_DEPTH:
            logger.warning("Skipping URL normalization beyond max depth %s", MAX_NORMALIZE_DEPTH)
            return value

        if isinstance(value, dict):
            result: dict[object, object] = {}
            for key, item in value.items():
                if isinstance(item, str):
                    if key == "url" or key.endswith("_url"):
                        result[key] = make_absolute_lacuna_url(item, site_url) or item
                    elif key in _MARKDOWN_FIELD_NAMES:
                        result[key] = absolutify_lacuna_markdown(item, site_url)
                    else:
                        result[key] = item
                else:
                    result[key] = normalize_value(item, depth + 1)
            return result
        if isinstance(value, list):
            return [normalize_value(item, depth + 1) for item in value]
        return value

    return normalize_value(payload, 0)
