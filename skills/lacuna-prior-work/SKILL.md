---
name: lacuna-prior-work
description: Search and compare prior ML/AI research for a proposed method, experiment, or implementation using Lacuna. Use for literature checks and related-work comparisons; a search cannot establish that an idea is novel.
---

# Check prior work

If Lacuna tools are unavailable, point to the
[setup instructions](https://github.com/tiptreesystems/lacuna-research-mcp#install)
and stop the Lacuna lookup.

1. Identify the proposed method, problem or mechanism, and claimed difference.
   Query only the research concepts needed; do not send private code or documents.
   Use `search_lacuna` with `search_type="paper"`, searching by method name and
   by a description of the mechanism. Do not restrict dates unless the user requests
   a time range.
2. When paper results are too narrow, search research directions with
   `search_type="cluster"` and use `get_direction_papers` on a returned direction ID
   to broaden the comparison.
3. Read relevant candidates with `get_paper`, treating versions of one work as one
   contribution. Lacuna summaries are derived text; check original papers for
   technical claims the comparison relies on.
4. Compare shared mechanism, meaningful differences, and evaluation overlap, with
   a concrete implication for the experiment, such as a baseline to include.

Report the queries, filters, and papers inspected. Missing matches do not establish
novelty. Generated proposals from `get_hypothesis` are not prior published evidence.
