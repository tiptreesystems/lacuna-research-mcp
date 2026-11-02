---
name: lacuna-reading-gaps
description: Find potentially missing ML/AI papers in a reading list or bibliography using Lacuna. Use for reading-list expansion, missing baselines, or adjacent methods; recommendations are limited to the searches and corpus inspected.
---

# Find gaps in a reading list

Use the connected Lacuna Research MCP tools, allowing for client-specific tool
prefixes. If unavailable, point to the
[setup instructions](https://github.com/tiptreesystems/lacuna-research-mcp#install)
before doing research.

1. Read the supplied titles, DOI/arXiv IDs, or bibliography and the user's research
   question. Establish the intended scope and cutoff date from that context. Ask
   for the list if none is supplied. Preserve the original bibliography.
2. Resolve the core papers using `search_lacuna(search_type="paper", ...)` and
   `get_paper(..., view="context", figure_limit=0)`. Match titles, authors, year,
   and identifiers; mark unresolved or ambiguous entries rather than silently
   dropping them. Query individual public paper identifiers or concepts instead
   of uploading a whole private bibliography.
3. Search the question with two or three complementary terms: the central
   method, a competing approach, or the evaluation problem. Use explicit
   `search_type="paper"` for the default lexical+semantic paper search.
   When useful, find a direction with `search_type="cluster"`, then use returned
   numeric IDs with `get_direction` and `get_direction_papers`.
4. Read candidate papers before recommending them. Deduplicate against the input
   using DOI/arXiv identity and Lacuna's work/version metadata, not title alone.
   A conference version of an existing preprint is an update, not a new omission.
5. Suggest a small, prioritized set based on the user's question. Explain the
   missing role each serves: baseline, alternative method, evaluation, limitation,
   or adjacent direction. Cite canonical Lacuna URLs and available original papers.

Keep recommendations separate from unresolved input matches and optional updates.
Include the search terms and date filters so the user can inspect the coverage.
Say "potential gap in this list," not "missing from the literature." A direction
cluster is a retrieval aid, not proof of relevance; generated proposals are not
published evidence. Do not edit a Zotero library, bibliography, or shared document
unless the user asks for that change.

Example request: "My reading list has FlashAttention and FlashAttention-2.
For an experiment on long-context attention, what baselines or limitations
should I read about next?"
