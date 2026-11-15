"""MCP prompts: named starting points that clients show to users.

Each prompt returns one user message that states the task and the Lacuna route
for it. The routes follow the Lacuna skills (lacuna-prior-work in this repo and
the research-map, find-researchers and paper-context skills in the Claude
plugin), cut down to what a single message needs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

_CITE = (
    "Cite the complete Lacuna URL the tools return for every paper, direction, "
    "author and hypothesis you mention; never shorten or invent one. Payloads are "
    'capped and paginated, so phrase negative claims as "not in the results I '
    'examined".'
)


def prior_work(
    idea: Annotated[
        str,
        Field(description="The method, experiment or research idea to check, in a sentence or two"),
    ],
) -> str:
    """Check prior ML/AI work for a proposed method, experiment or idea."""
    return (
        f"Check prior work for this ML/AI idea:\n\n{idea}\n\n"
        "Use the Lacuna Research tools.\n"
        "1. Name the method, the problem or mechanism, and the claimed difference. "
        "Query only the research concepts needed; do not send private code or documents.\n"
        '2. search_lacuna(search_type="paper") by method name and again by a '
        "description of the mechanism. Do not restrict dates unless I ask.\n"
        '3. If paper results are too narrow, search_lacuna(search_type="cluster") '
        "and get_direction_papers on the closest direction.\n"
        "4. Read the relevant candidates with get_paper, treating versions of one "
        "work as one contribution.\n\n"
        "Compare shared mechanism, meaningful differences and evaluation overlap, "
        "and end with a concrete implication, such as a baseline to include. Report "
        "the queries and papers inspected. Missing matches do not establish novelty, "
        "and generated proposals from get_hypothesis are not published evidence. " + _CITE
    )


def research_map(
    topic: Annotated[
        str, Field(description="The ML/AI research topic to map, e.g. test-time training")
    ],
) -> str:
    """Map what has been tried on an ML/AI research topic and what is still open."""
    return (
        f"Map the ML/AI research on: {topic}\n\n"
        "Use the Lacuna Research tools.\n"
        '1. One search_lacuna(search_type="cluster") for the topic. Keep the 2 to 4 '
        "directions that are actually about it.\n"
        "2. get_direction on each kept direction; widen through its "
        "related_directions rather than running more searches.\n"
        "3. get_direction_papers on the two or three main directions for "
        "representative papers.\n"
        '4. search_lacuna(search_type="hypothesis") and get_hypothesis on the top '
        "one or two for open questions.\n\n"
        "Write: how Lacuna splits the topic; what has been tried, per line of work, "
        "with key papers (title, year, venue); what is still open, each item tied to "
        "a paper's stated limitation, a direction summary or a Lacuna hypothesis "
        "(marked as generated); and directions you saw but did not open. "
        "Do not loop on paraphrased queries. " + _CITE
    )


def find_researchers(
    topic: Annotated[
        str, Field(description="The ML/AI topic, optionally with an institution or venue")
    ],
) -> str:
    """Find ML/AI researchers working on a topic."""
    return (
        f"Find ML/AI researchers working on: {topic}\n\n"
        "Use the Lacuna Research tools. Author search matches names, not topics, so "
        'do not call search_lacuna(search_type="author") with the topic.\n'
        '1. search_lacuna(search_type="cluster") for the topic and get_direction on '
        "the closest directions; take the authors they list.\n"
        "2. get_author_context on the strongest 3 to 5 to confirm what they work on.\n"
        "3. If the topic names an institution or venue, use "
        'search_lacuna(search_type="institution" or "venue") and its context tool '
        "to narrow the list.\n\n"
        "Return a short list: name, main directions, two or three representative "
        'recent papers, and why each person is on the list. Say "listed '
        'affiliation" and never infer current employer, seniority or biography; do '
        "not look up email addresses or personal details. " + _CITE
    )


def paper_context(
    paper: Annotated[
        str,
        Field(
            description="An arXiv ID, DOI, arXiv/OpenReview/Lacuna URL, or the paper's exact title"
        ),
    ],
) -> str:
    """Explain an ML/AI paper and place it among related work."""
    return (
        f"Explain this paper and place it in context: {paper}\n\n"
        "Use the Lacuna Research tools.\n"
        "1. get_paper accepts an arXiv ID, a DOI, an arXiv, DOI or OpenReview URL, "
        "or a Lacuna paper URL directly. With only a title, run one "
        'search_lacuna(search_type="paper") with the exact title, then get_paper '
        "on the match.\n"
        '2. Read the default view first. Ask for view="neighbors", "figures" or '
        '"fulltext" only when the default is not enough.\n'
        "3. Place it using the paper's own directions and neighbors; call "
        "get_direction on its main direction only if you need to describe that line "
        "of work.\n\n"
        "Write: what the paper does (problem, approach, main result) in two or "
        "three sentences; where it sits and what it changes relative to the "
        "closest related papers; other versions and linked code, datasets or models "
        "when present. Use the paper's own claims for results and mark Lacuna's "
        "generated summary as a summary. If the paper is not in Lacuna, say so. " + _CITE
    )


PROMPT_FUNCTIONS: tuple[Callable[..., str], ...] = (
    prior_work,
    research_map,
    find_researchers,
    paper_context,
)

PROMPT_TITLES: dict[str, str] = {
    "prior_work": "Check prior work",
    "research_map": "Map a research area",
    "find_researchers": "Find researchers on a topic",
    "paper_context": "Explain a paper in context",
}
