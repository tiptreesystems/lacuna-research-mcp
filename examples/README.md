# Trace code to papers with MCP

Find the research behind a public ML repository and keep the source trail.
The example searches Lacuna for a code resource, checks its identity, follows
its recorded publication links, and returns paper and source URLs.

## Run the example

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone this
repository, and run from its root:

```bash
uv run examples/code_to_paper.py
```

The script installs its declared MCP dependency in an isolated environment.
It needs Python 3.11+ and internet access. It calls Lacuna's public, read-only
MCP endpoint; no Lacuna account or model API key is required.

To trace another repository, set both its identity and search query:

```bash
uv run examples/code_to_paper.py \
  --repository Dao-AILab/flash-attention --query FlashAttention --max-papers 3
```

The default example returns the recorded `official_code_for` link to
*FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*.
The JSON includes the tool calls, retrieval time, resource collection timestamp,
Lacuna URLs, relationship evidence, and original paper links. Results can change
as the corpus is updated.

## Work through the tutorial

Open [code_to_paper.ipynb](code_to_paper.ipynb) in Jupyter or your editor's notebook
view. Run the cells from top to bottom. The notebook is self-contained and includes
an architecture diagram, a paper-search baseline, failure cases, and an exercise.

This is the retrieval component of a research agent. Its decisions are explicit
Python rules; it does not call a language model. An agent can use the same MCP
tools with the [code-to-paper skill](../skills/lacuna-code-to-paper/SKILL.md).

## What to check

- Confirm repository identity before following a result. The example stops on
  missing or ambiguous matches instead of selecting the highest-ranked result.
- Inspect original sources before making a claim about an implementation.
  A recorded relationship can be stale or incomplete.
- Treat an empty result as missing evidence. It does not prove that a repository
  has no associated papers.
- Use a public repository name. This example doesn't read or upload local code.

See the [MCP server](https://github.com/tiptreesystems/lacuna-research-mcp) for
installation instructions, the other research skills, and the tool reference.
