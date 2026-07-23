<!-- mcp-name: io.github.tiptreesystems/lacuna-research-mcp -->

<p align="center">
  <img src="https://raw.githubusercontent.com/tiptreesystems/lacuna-research-mcp/main/assets/banner.svg" alt="Lacuna Research MCP — Empower your coding agent for machine learning research" width="100%" />
</p>
<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.11+" /></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-server-7C3AED" alt="MCP server" /></a>
  <a href="https://github.com/tiptreesystems/lacuna-research-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT license" /></a>
</p>

# Lacuna Research MCP

### 🔬 Ground your coding agent in novel ideas, papers, and the ML landscape



Lacuna Research MCP gives AI researchers' coding agents:

- **Novel research proposals.** Explore novel research ideas generated with [Alien Science](https://openreview.net/pdf?id=XZWkDET1ia).
- **Research directions.** Navigate concept clusters with linked papers, authors, and proposals.
- **Agent-ready literature.** Search recent papers in markdown with source links.
- **Researcher intelligence.** Trace authors, publications, directions, impact, and related researchers.
- **Landscape mapping.** Compare venues, institutions, leading researchers, and publication activity.

[Lacuna](https://lacuna.tiptreesystems.com), built by [Tiptree Systems](https://tiptreesystems.com), is a research map of machine learning: a heterogeneous knowledge graph linking papers, research directions, authors, venues, institutions, and generated research proposals, with a source trail from every derived object back to the exact paper and page that produced it. Its pipeline reconciles scholarly records from OpenAlex, OpenReview, DBLP, and arXiv; extracts concept elements from paper text and clusters them into research directions ([Lacuna paper](https://arxiv.org/abs/2606.26246)); and samples novel research proposals from those directions with [Alien Science](https://arxiv.org/abs/2603.01092). The map spans more than **730,000 papers**, **190,000+ author profiles**, **38,000+ research directions**, and **3,000+ research proposals** built from over **15 million concept elements** — and it grows continuously as new arXiv and other AI papers are ingested.

[Install](#install) · [First use](#first-use) · [Tools](#what-it-exposes) · [API reference](#wrapped-apis) · [Configuration](#environment-variables)

## Install

The easiest way to install Lacuna Research MCP is to ask your coding agent, such as Codex or Claude Code:

> Install and configure the `lacuna-research-mcp` package from PyPI for this client.

For manual setup, the instructions below use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to run the latest tagged release from PyPI. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first; Lacuna Research MCP requires Python 3.11 or newer.

### Codex

Add the server with the Codex CLI:

```bash
codex mcp add lacuna-research -- uvx lacuna-research-mcp
```

Alternatively, add the following to `~/.codex/config.toml` (or to `.codex/config.toml` in a trusted project for project-only setup):

```toml
[mcp_servers.lacuna-research]
command = "uvx"
args = ["lacuna-research-mcp"]
```

Run `codex mcp list` to verify the server is configured. The Codex app, CLI, and IDE extension share this configuration on the same machine.

### Claude Code

Add the server for all of your projects with the Claude Code CLI:

```bash
claude mcp add --scope user lacuna-research -- uvx lacuna-research-mcp
```

Omit `--scope user` to add it only to the current project. Alternatively, add the following under the top-level `mcpServers` object in `~/.claude.json`:

```json
{
  "mcpServers": {
    "lacuna-research": {
      "type": "stdio",
      "command": "uvx",
      "args": ["lacuna-research-mcp"]
    }
  }
}
```

Run `claude mcp get lacuna-research` to verify the server is configured.

### Claude Desktop

Open **Settings → Developer → Edit Config**, then add the server under `mcpServers` in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lacuna-research": {
      "command": "uvx",
      "args": ["lacuna-research-mcp"]
    }
  }
}
```

Restart Claude Desktop after saving the file.

### Other MCP clients

For any client that supports local stdio MCP servers, use this standard configuration:

```json
{
  "mcpServers": {
    "lacuna-research": {
      "command": "uvx",
      "args": ["lacuna-research-mcp"]
    }
  }
}
```

### Standalone command

Install the MCP server as a persistent command:

```bash
uv tool install lacuna-research-mcp
lacuna-research-mcp
```

Run it without installing a persistent command:

```bash
uvx lacuna-research-mcp
```

### Latest development version

PyPI contains tagged releases. To try the latest code from the `main` branch instead:

```bash
uvx --from git+https://github.com/tiptreesystems/lacuna-research-mcp.git lacuna-research-mcp
```

### Local development

With uv:

```bash
git clone https://github.com/tiptreesystems/lacuna-research-mcp.git
cd lacuna-research-mcp
uv sync --extra dev
uv run lacuna-research-mcp
```

With pip:

```bash
cd <path-to-lacuna-research-mcp>
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## First use

After connecting the server, call:

1. `search_lacuna(query="LLM jailbreak defense", search_type="hypothesis", limit=10)`
2. `search_lacuna(query="methods for detecting prompt injection attacks", search_type="papers", limit=10)` (production lexical+semantic paper ranking by default)
3. `get_hypothesis(hypothesis_id_or_url="bd35de182c2325ae")`
4. `get_paper(artifact_id_or_url="art_79c57fbfec094f26b79c422cf08fed34")` (defaults to `view="context"`)
5. `get_direction(cluster_id_or_url=25108)` (defaults to `view="context"`)

## Scope

The corpus covers machine learning and AI research: papers, research directions, authors' research output, venues, institutions, and generated research hypotheses. It does not contain biographies, news, or non-research web content. Agents should answer questions outside that scope from other sources.

## What it exposes

- `search_lacuna`
  Uses Lacuna's public `/api/v1/search` endpoint for directions, papers, authors, venues, institutions, and hypotheses. Explicit paper searches (`search_type="paper"`) use the server's production lexical+semantic ranker when the other ranking arguments remain at their defaults. Pass `search_type="hypothesis"` (or `"hypotheses"` / `"proposal"` / `"proposals"`) for hypothesis search.
- `get_hypothesis(hypothesis_id_or_url, view="context")`
  Hypothesis/proposal. `view="context"` (default) is a compact single-fetch proposal context (summary, abstract, linked directions); `view="full"` returns the server's version record with version history and signal counts. Proposal bodies are in `versions[].markdown`.
- `get_direction(cluster_id_or_url, view="context")`
  Research direction/cluster. `view="context"` (default) requests the compact agent-oriented summary; `view="full"` returns the raw cluster record.
- `get_direction_papers(cluster_id_or_url, page, limit, view="compact")`
  Paginated papers attached to a direction. `view="compact"` (default) returns citation-ready rows (id, url, title, year, venue, a few authors, abstract snippet); `view="full"` returns the raw upstream paper records.
- `get_paper(artifact_id_or_url, view="context", figure_limit=None)`
  Paper lookup. `view="context"` (default) requests the compact agent-oriented context; other views are `"full"`, `"preview"`, `"blog"`, `"figures"`, `"concepts"`, or `"neighbors"`. In context view, `figure_limit` caps the figure preview (server default 3; pass 0 to suppress previews while keeping a `figures_truncated` signal).
- Author tools:
  `get_author_context(…, view="context")`, `get_author_papers`, `get_author_directions`, and `get_author_neighbors`. Start with `get_author_context`, which defaults to the compact agent-oriented view (capped papers plus a readable `impact_directions` list instead of raw `impact_clusters` telemetry). Use the dedicated papers, directions, and neighbors tools to page through those collections without repeating the author context. `view="full"` returns the server-bounded full-shape context (collections remain capped at 100). Pass `include_neighbors=true` to explicitly include similar authors; this may add significant server latency.
- Venue and institution tools:
  `get_venue_context(…, view="context")`, `get_institution_context(…, view="context")`, `get_institution_authors`. Context tools default to compact (capped lists, duplicated blocks dropped; venue keeps a recent-activity slice that always includes the requested `year`). Use `get_institution_authors` to page through an institution's complete author list.

## Wrapped APIs

| MCP tool | Lacuna API endpoint |
| --- | --- |
| `search_lacuna(query, search_type, limit, offset, date_from, date_to, venue, sort, ranking_profile, fields)` | `GET /api/v1/search` (`fields` restricts/weights the text fields used for lexical ranking, e.g. `title^4,abstract`, and selects the experimental lexical ranker; for a default relevance-sorted paper search, this bypasses the production lexical+semantic ranker. Allowed fields are `title`, `abstract`, `summary`, `concepts`, `name`, `top_names`, `venue`, each valid only for the types that carry it — `title`: paper/cluster/venue/hypothesis; `abstract`/`summary`/`concepts`: paper; `name`: author/institution/venue; `top_names`: cluster/hypothesis; `venue`: paper/venue (`search_type="all"` spans all). Weights must satisfy `0 < weight <= 100`. Unknown fields, out-of-range weights, type-incompatible fields, and `fields` combined with `ranking_profile="semantic"` are rejected, since the server would otherwise silently drop, cap, or ignore them.) |
| `get_hypothesis(hypothesis_id_or_url, view="context")` | `view="context"` → `GET /api/v1/context/hypothesis/{hypothesis_id}?view=compact`; `view="full"` → `GET /api/v1/hypotheses/{hypothesis_id}` |
| `get_direction(cluster_id_or_url, view="context")` | `view="context"` → `GET /api/v1/context/direction/{cluster_id}?view=compact`; `view="full"` → `GET /api/v1/clusters/{cluster_id}` |
| `get_direction_papers(cluster_id_or_url, page, limit, view="compact")` | `GET /api/v1/clusters/{cluster_id}/papers?view=compact` (default) or `?view=complete` |
| `get_paper(artifact_id_or_url, view="context", figure_limit=None)` | `view="context"` → `GET /api/v1/context/paper/{artifact_id}?view=compact` (`&figure_limit=N` when set); `view="full"` → `GET /api/v1/papers/{artifact_id}`; `view="preview"` → `…/preview`; `view="blog"` → `…/blog`; `view="figures"` → `…/figures`; `view="concepts"` → `…/concepts`; `view="neighbors"` → `…/neighbors` |
| `get_author_papers(author_id_or_url, limit=50, offset=0)` | `GET /api/v1/authors/{author_id}/papers` |
| `get_author_directions(author_id_or_url, limit=50, offset=0)` | `GET /api/v1/authors/{author_id}/directions` |
| `get_author_context(author_id_or_url, view="context", include_neighbors=false)` | `view="context"` → `GET /api/v1/context/author/{author_id}?view=compact`; `view="full"` → `GET /api/v1/context/author/{author_id}` (`include_neighbors=true` explicitly requests similar authors) |
| `get_author_neighbors(author_id_or_url, limit=8, offset=0)` | `GET /api/v1/authors/{author_id}/neighbors` |
| `get_venue_context(venue_key_or_url, year, view="context")` | `view="context"` → `GET /api/v1/context/venue/{vkey}[/{year}]?view=compact`; `view="full"` → same route without `view` |
| `get_institution_context(institution_key_or_url, view="context")` | `view="context"` → `GET /api/v1/context/institution/{ikey}?view=compact`; `view="full"` → same route without `view` |
| `get_institution_authors(institution_key_or_url, limit=50, offset=0)` | `GET /api/v1/institutions/{ikey}/authors` |

For id-or-URL arguments, pass either the raw id returned by `search_lacuna` or the corresponding Lacuna page URL. The MCP normalizes Lacuna-relative `url` and `*_url` fields to absolute URLs, and it also absolutifies Lacuna links inside fields named `summary_markdown`, `article_markdown`, `markdown`, `content`, or `description`.

`get_author_context` is bounded server-side in both views. The default compact view returns a curated briefing; `view="full"` returns the larger complete shape with embedded collections capped at 100. Use `get_author_papers` and `get_author_directions` rather than trying to page embedded context collections.

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
- `LACUNA_MCP_LOG_LEVEL`
  Defaults to `WARNING` (one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). The default keeps normal operation quiet; lower it only for debugging, since `INFO`/`DEBUG` let the HTTP client log full request URLs — including the search query string — to stderr, which some MCP hosts retain.

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
- `lacuna_research_mcp/errors.py`
  User-facing exception type for Lacuna API access failures.

## Notes

- `get_paper` and `get_direction` default to `view="context"`. These context views request Lacuna's compact agent-oriented payloads by default to keep MCP responses small. Paper context includes `summary_markdown` when available (otherwise `abstract`), authors, and figures; direction context includes `summary_markdown`, capped papers/authors/related directions, and truncation markers. Use `view="full"` when you need the raw metadata, and the other paper views (`preview`, `blog`, `figures`, `concepts`, `neighbors`) when you want one isolated sub-resource.
- An explicit relevance-sorted paper search with no custom `fields` defaults to the server's production lexical+semantic ranker. Set `ranking_profile="semantic"` for embedding-based retrieval (with a possible exact-title overlay) or `"bm25_title_abstract"` for title-and-abstract lexical matching.
- Search type aliases are normalized client-side, so `papers`, `directions`, and `hypotheses` are accepted and mapped to the server's singular values.
- Most detail tools accept either the id returned by search or the corresponding Lacuna URL.
- Relative Lacuna URLs in `url`/`*_url` response fields and fields named `summary_markdown`, `article_markdown`, `markdown`, `content`, or `description` are normalized to absolute URLs.
- Venue and institution keys are opaque hashes (for example `d7bf22905bd6`), never human-readable names like `icml`. Find the key with `search_lacuna(search_type="venue")` first, or pass a `/venue/...` page URL.

## Citation

If you find our work helpful, feel free to cite the papers behind Lacuna's research-proposal generation and research map.

**Research-proposal generation — Alien Science**

```bibtex
@inproceedings{artiles2026alien,
  title     = {Alien Science: Sampling Coherent but Cognitively Unavailable Research Directions from Idea Atoms},
  author    = {Artiles, Alejandro H. and Weiss, Martin and Brinkmann, Levin and Goyal, Anirudh and Rahaman, Nasim},
  booktitle = {ICLR 2026 Workshop on Post-AGI Science and Society},
  year      = {2026},
  url       = {https://openreview.net/forum?id=XZWkDET1ia}
}
```

**Research map — Lacuna**

```bibtex
@misc{weiss2026lacunaresearchmapmachine,
  title         = {Lacuna: A Research Map for Machine Learning},
  author        = {Martin Weiss and Miles Q. Li and Alejandro H. Artiles and Yacine Mkhinini and Chris Pal and Hugo Larochelle and Nasim Rahaman},
  year          = {2026},
  eprint        = {2606.26246},
  archivePrefix = {arXiv},
  primaryClass  = {cs.DL},
  url           = {https://arxiv.org/abs/2606.26246}
}
```

## License

MIT. See [LICENSE](https://github.com/tiptreesystems/lacuna-research-mcp/blob/main/LICENSE).
