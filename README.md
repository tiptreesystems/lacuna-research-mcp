# Lacuna Research MCP

MCP server for [Lacuna](https://lacuna.tiptreesystems.com), a research map for machine learning built by [Tiptree Systems](https://tiptreesystems.com).

Lacuna extracts concept elements from ML paper pages, clusters them into research directions, and keeps a source trail from every derived object back to the exact paper and page that produced it. At the snapshot described in the [Lacuna paper](https://arxiv.org/abs/2606.26246), the map contains 15,259,720 concept elements from 733,795 paper pages, organized into 27,017 research directions. This server exposes that map as MCP tools, so a coding agent or assistant can search the literature inside its existing tool loop, with every answer linking back to the underlying pages.

The server is standalone: it talks to the public Lacuna deployment at `https://lacuna.tiptreesystems.com` and does not depend on the Lacuna repository.

## Scope

The corpus covers machine learning and AI research: papers, research directions, authors' research output, venues, institutions, and generated research hypotheses. It does not contain affiliations, biographies, news, or non-research web content. Agents should answer questions outside that scope from other sources.

## What it exposes

- `search_lacuna`
  Uses Lacuna's public `/api/v1/search` endpoint for directions, papers, authors, venues, institutions, and hypotheses. Explicit paper searches (`search_type="paper"`) use the server's production lexical+semantic ranker when the other ranking arguments remain at their defaults. Pass `search_type="hypothesis"` (or `"hypotheses"` / `"proposal"` / `"proposals"`) for hypothesis search.
- `get_hypothesis(hypothesis_id_or_url, view="context")`
  Hypothesis/proposal. `view="context"` (default) is a compact single-fetch proposal context (summary, abstract, linked directions); `view="full"` returns the full two-endpoint merge with version history and signal counts.
- `get_direction(cluster_id_or_url, view="context")`
  Research direction/cluster. `view="context"` (default) requests the compact agent-oriented summary; `view="full"` returns the raw cluster record.
- `get_direction_papers(cluster_id_or_url, page, limit, view="compact")`
  Paginated papers attached to a direction. `view="compact"` (default) returns citation-ready rows (id, url, title, year, venue, a few authors, abstract snippet); `view="full"` returns the raw upstream paper records.
- `get_paper(artifact_id_or_url, view="context", figure_limit=None)`
  Paper lookup. `view="context"` (default) requests the compact agent-oriented context; other views are `"full"`, `"preview"`, `"blog"`, `"figures"`, `"concepts"`, or `"neighbors"`. In context view, `figure_limit` caps the figure preview (server default 3; pass 0 to suppress previews while keeping a `figures_truncated` signal).
- Author tools:
  `get_author`, `get_author_context(…, view="context")`, `get_author_impact`, `get_author_neighbors`. `get_author_context` defaults to the compact view (capped papers plus a readable `impact_directions` list instead of raw `impact_clusters` telemetry); `view="full"` returns the complete context and re-enables the `*_limit`/`full` slicing params.
- Venue and institution tools:
  `get_venue_context(…, view="context")`, `get_institution_context(…, view="context")`. Both default to compact (capped lists, duplicated blocks dropped; venue keeps a recent-activity slice that always includes the requested `year`).

## Wrapped APIs

| MCP tool | Lacuna API endpoint |
| --- | --- |
| `search_lacuna(query, search_type, limit, offset, date_from, date_to, venue, sort, ranking_profile, fields, debug)` | `GET /api/v1/search` (`fields` restricts/weights the text fields used for lexical ranking, e.g. `title^4,abstract`, and selects the experimental lexical ranker; for a default relevance-sorted paper search, this bypasses the production lexical+semantic ranker; `debug=true` echoes the requested/normalized type and ranking profile in `_mcp_meta`, off by default) |
| `get_hypothesis(hypothesis_id_or_url, view="context")` | `view="context"` → `GET /api/v1/context/hypothesis/{hypothesis_id}?view=compact`; `view="full"` → `GET /api/v1/hypotheses/{hypothesis_id}` and `GET /api/v1/context/hypothesis/{hypothesis_id}` |
| `get_direction(cluster_id_or_url, view="context")` | `view="context"` → `GET /api/v1/context/direction/{cluster_id}?view=compact`; `view="full"` → `GET /api/v1/clusters/{cluster_id}` |
| `get_direction_papers(cluster_id_or_url, page, limit, view="compact")` | `GET /api/v1/clusters/{cluster_id}/papers?view=compact` (default) or `?view=complete` |
| `get_paper(artifact_id_or_url, view="context", figure_limit=None)` | `view="context"` → `GET /api/v1/context/paper/{artifact_id}?view=compact` (`&figure_limit=N` when set); `view="full"` → `GET /api/v1/papers/{artifact_id}`; `view="preview"` → `…/preview`; `view="blog"` → `…/blog`; `view="figures"` → `…/figures`; `view="concepts"` → `…/concepts`; `view="neighbors"` → `…/neighbors` |
| `get_author(author_id_or_url, papers_limit, papers_offset, levels_limit, levels_offset, full)` | `GET /api/v1/authors/{author_id}` |
| `get_author_context(author_id_or_url, view="context", papers_limit, papers_offset, impact_clusters_limit, impact_clusters_offset, levels_limit, levels_offset, full)` | `view="context"` → `GET /api/v1/context/author/{author_id}?view=compact`; `view="full"` → `GET /api/v1/context/author/{author_id}` (slicing params apply only to `view="full"`) |
| `get_author_impact(author_id_or_url, impact_clusters_limit, impact_clusters_offset, full)` | `GET /api/v1/authors/{author_id}/impact` |
| `get_author_neighbors(author_id_or_url)` | `GET /api/v1/authors/{author_id}/neighbors` |
| `get_venue_context(venue_key_or_url, year, view="context")` | `view="context"` → `GET /api/v1/context/venue/{vkey}[/{year}]?view=compact`; `view="full"` → same route without `view` |
| `get_institution_context(institution_key_or_url, view="context")` | `view="context"` → `GET /api/v1/context/institution/{ikey}?view=compact`; `view="full"` → same route without `view` |

For id-or-URL arguments, pass either the raw id returned by `search_lacuna` or the corresponding Lacuna page URL. The MCP normalizes Lacuna-relative `url` and `*_url` fields to absolute URLs, and it also absolutifies Lacuna links inside fields named `summary_markdown`, `content`, or `description`.

Author endpoints can be very large for prolific authors. `get_author`, `get_author_impact`, and `get_author_context` with `view="full"` slice large `papers`, `impact_clusters`, and `levels.cluster` arrays by default with a limit of 50 and a maximum requested limit of 200. Responses include `*_total`, `*_returned`, `*_truncated`, and `truncation` metadata. Pass offsets to page through those arrays, or set `full=true` to return upstream arrays unsliced. (The default `get_author_context` compact view is capped server-side, so these MCP-side slicing params and the verbose truncation metadata apply only to `view="full"`.)

Search requests are capped at 50 results per call, and direction-paper page
requests are capped at 100 results per call.
In `search_lacuna`, `date_from` and `date_to` are inclusive publication-date
bounds. Accepted formats are `YYYY`, `YYYY-MM`, and `YYYY-MM-DD`; for example,
`date_from="2020", date_to="2022-03"` includes papers from January 1, 2020
through March 31, 2022.

`search_lacuna` exposes these ranking profiles:

- `default` / `lexical`
  The default profile for all searches. With `search_type="paper"`, `sort="relevance"`, and `fields` unset, it uses the server's production lexical+semantic ranker with graceful fallback. The MCP's default `search_type="all"` uses the server's default lexical ranking instead.
- `semantic`
  Use for embedding-based paper retrieval. The semantic query omits the normal lexical ranking leg, but the server can still overlay exact-title lexical matches. Only supported for `paper` and `all` searches (only papers have semantic embeddings).
- `bm25_title_abstract` / `bm25`
  Use for lexical matching constrained to title and abstract. Rejected for `author` and `institution` searches (those records have no title or abstract fields).

All searches use the server default unless `ranking_profile` is provided. The MCP rejects unsupported profile/type combinations because the server would otherwise fall back to substring search and silently ignore the requested ranking profile.

`sort` accepts `relevance` (default), `year_desc`, and `year_asc`. Year sorts cannot be combined with `ranking_profile="semantic"` — the server would silently ignore the sort — so the MCP rejects that combination; for recent-and-relevant queries, keep semantic ranking and constrain recency with `date_from`/`date_to` instead.

## Install

### With uv

Install the MCP server as a persistent command:

```bash
uv tool install git+https://github.com/tiptreesystems/lacuna-research-mcp.git
lacuna-research-mcp
```

Run it without installing a persistent command:

```bash
uvx --from git+https://github.com/tiptreesystems/lacuna-research-mcp.git lacuna-research-mcp
```

For local development from a checkout:

```bash
git clone https://github.com/tiptreesystems/lacuna-research-mcp.git
cd lacuna-research-mcp
uv sync --extra dev
uv run lacuna-research-mcp
```

### With pip

```bash
cd <path-to-lacuna-research-mcp>
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Run

After `uv tool install`, run:

```bash
lacuna-research-mcp
```

From a local checkout, run:

```bash
uv run lacuna-research-mcp
```

## Environment variables

- `LACUNA_SITE_URL`
  Defaults to `https://lacuna.tiptreesystems.com`
- `LACUNA_MCP_TIMEOUT`
  Defaults to `30`
- `LACUNA_MCP_MAX_RETRIES`
  Defaults to `2`; applies to timeouts, transport errors, and HTTP `429`, `502`, `503`, and `504` responses.
- `LACUNA_MCP_USER_AGENT`
  Defaults to `lacuna-research-mcp/{package_version}`
- `LACUNA_MCP_BEARER_TOKEN`
  Optional bearer token sent as `Authorization: Bearer ...` for private Lacuna deployments.

Environment variables are read once when the MCP server is created, or on the first direct tool/API call if the module is imported without calling `create_mcp()`.

## Implementation layout

The server is a thin MCP adapter over Lacuna's HTTP API. The implementation is split by responsibility:

- `lacuna_research_mcp/server.py`
  FastMCP app creation, tool registration, lifespan cleanup, and the `lacuna-research-mcp` CLI entrypoint.
- `lacuna_research_mcp/tools.py`
  MCP tool functions. Each tool normalizes its inputs, calls the matching Lacuna API endpoint through the shared client helpers, and returns JSON-compatible data.
- `lacuna_research_mcp/client.py`
  Runtime HTTP access to Lacuna: the event-loop-bound `httpx.AsyncClient`, retry handling, error wrapping, JSON parsing, URL normalization on responses, and `api_get`/`api_object`/`api_payload`.
- `lacuna_research_mcp/config.py`
  Runtime constants, `RuntimeConfig`, package user-agent construction, and environment parsing.
- `lacuna_research_mcp/ids.py`
  Helpers that accept either raw ids or Lacuna page URLs and extract safe API path segments.
- `lacuna_research_mcp/normalize.py`
  Response post-processing for relative Lacuna URLs and markdown links.
- `lacuna_research_mcp/truncation.py`
  Local slicing and metadata for large author-related arrays returned by upstream APIs.
- `lacuna_research_mcp/errors.py`
  User-facing exception type for Lacuna API access failures.

## Codex config snippet

Add this to your Codex MCP config wherever you keep MCP servers:

```toml
[mcp_servers.lacuna_research]
command = "uvx"
args = ["--from", "git+https://github.com/tiptreesystems/lacuna-research-mcp.git", "lacuna-research-mcp"]

[mcp_servers.lacuna_research.env]
LACUNA_SITE_URL = "https://lacuna.tiptreesystems.com"
```

## Claude Code

One command:

```bash
claude mcp add lacuna-research -- uvx --from git+https://github.com/tiptreesystems/lacuna-research-mcp.git lacuna-research-mcp
```

Or add this under the top-level `mcpServers` object in `~/.claude.json`:

```json
"lacuna-research": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/tiptreesystems/lacuna-research-mcp.git",
    "lacuna-research-mcp"
  ]
}
```

## Claude Desktop

Add this under `mcpServers` in `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
"lacuna-research": {
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/tiptreesystems/lacuna-research-mcp.git",
    "lacuna-research-mcp"
  ]
}
```

## First use

After connecting the server, call:

1. `search_lacuna(query="LLM jailbreak defense", search_type="hypothesis", limit=10)`
2. `search_lacuna(query="methods for detecting prompt injection attacks", search_type="papers", limit=10)` (production lexical+semantic paper ranking by default)
3. `get_hypothesis(hypothesis_id_or_url="bd35de182c2325ae")`
4. `get_paper(artifact_id_or_url="art_79c57fbfec094f26b79c422cf08fed34")` (defaults to `view="context"`)
5. `get_direction(cluster_id_or_url=25108)` (defaults to `view="context"`)

## Notes

- `get_paper` and `get_direction` default to `view="context"`. These context views request Lacuna's compact agent-oriented payloads by default to keep MCP responses small. Paper context includes `summary_markdown` when available (otherwise `abstract`), authors, and figures; direction context includes `summary_markdown`, capped papers/authors/related directions, and truncation markers. Use `view="full"` when you need the raw metadata, and the other paper views (`preview`, `blog`, `figures`, `concepts`, `neighbors`) when you want one isolated sub-resource.
- An explicit relevance-sorted paper search with no custom `fields` defaults to the server's production lexical+semantic ranker. Set `ranking_profile="semantic"` for embedding-based retrieval (with a possible exact-title overlay) or `"bm25_title_abstract"` for title-and-abstract lexical matching.
- Search type aliases are normalized client-side, so `papers`, `directions`, and `hypotheses` are accepted and mapped to the server's singular values.
- Most detail tools accept either the id returned by search or the corresponding Lacuna URL.
- Relative Lacuna URLs in `url`/`*_url` response fields and fields named `summary_markdown`, `content`, or `description` are normalized to absolute URLs.
- Venue and institution keys are opaque hashes (for example `d7bf22905bd6`), never human-readable names like `icml`. Find the key with `search_lacuna(search_type="venue")` first, or pass a `/venue/...` page URL.

## License

MIT. See [LICENSE](LICENSE).
