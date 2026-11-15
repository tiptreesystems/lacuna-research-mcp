"""MCP prompts: named starting points that clients show to users.

Each prompt returns one user message that states the task and the Lacuna route
for it. The routes follow the Lacuna skills (lacuna-prior-work in this repo and
the research-map, find-researchers and paper-context skills in the Claude
plugin), then were revised from Claude Code runs on real examples, where the
model reviewed the prompt it had just followed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

# Claude Code splits slash-command text on whitespace and passes only the first
# word to a single-argument prompt ("diffusion model distillation" arrives as
# "diffusion"), while the model still sees the full text the user typed.
_FULL_TEXT = (
    "If the text the user typed after this command is longer than the line "
    "above, use the user's full text instead; some clients pass only the first word."
)

_CITE = (
    "Copy every Lacuna `url` exactly as a tool returns it, for each paper, "
    "direction and hypothesis you mention and for each author you discuss; URL "
    "forms vary (/work/, /paper/, /direction/), so never rebuild, shorten or "
    "invent one, and cite the URL from the call you relied on. Results are capped "
    'and paginated: phrase absences as "not in the results I examined".'
)


def prior_work(
    idea: Annotated[
        str,
        Field(description="The method, experiment or research idea to check, in a sentence or two"),
    ],
) -> str:
    """Check prior ML/AI work for a proposed method, experiment or idea."""
    return (
        f"Check prior work for this ML/AI idea: {idea}\n{_FULL_TEXT}\n\n"
        "Use the Lacuna Research tools. Send only research concepts, never private "
        "code or documents.\n"
        "1. Decompose: state the method, the mechanism or problem it targets, and the "
        "claimed difference (if the user did not state one, infer it and say it is "
        "your assumption). Name the 2 to 4 components whose combination is the "
        "claim, and show them in the answer.\n"
        '2. search_lacuna(search_type="paper"): once by the method\'s name (or its key terms if it has no name), once by a '
        'plain description of the mechanism with ranking_profile="semantic" (this '
        "usually finds the closest matches), and for up to 3 pairs of components "
        "(semantic) to catch the same mechanism under another name. No date filters "
        "unless I ask. Lexical results include same-term papers from unrelated "
        "fields, and semantic results can drift to older, loosely related work; ignore both.\n"
        "3. Only if that gives fewer than about 3 relevant papers, try "
        'search_type="cluster" and get_direction_papers on a specific direction; '
        "skip directions with more than a few hundred papers.\n"
        "4. Read the 4 to 8 closest candidates with get_paper, treating versions of "
        "one work as one contribution. Default views are generated summaries: for "
        "the single closest match, confirm the mechanism and any number you quote in "
        'view="fulltext". Also look for papers on how the mechanism fails (for '
        "example, models gaming or evading the signal).\n\n"
        "Answer in this order, concisely:\n"
        "- Verdict (2 to 3 sentences): the closest prior work, what still looks new, "
        "and a novelty risk (high, medium or low), given separately for the general "
        "idea and for its specific version when they differ.\n"
        "- Closest work: for the 3 to 5 closest papers, the shared mechanism, real "
        "differences, evaluation overlap and date; others in one line each. Lacuna's "
        "date is the indexed version's, not first release: flag recent dates as "
        "possibly concurrent and check the paper for an earlier version.\n"
        "- Implications: baselines and benchmarks to include, and the one experiment "
        "that would establish the difference.\n"
        "- Search log: queries (with ranking profile) and papers read, marking "
        "summary versus full text.\n\n"
        "Missing matches do not establish novelty, and get_hypothesis results are "
        "generated proposals, not published evidence. " + _CITE
    )


def research_map(
    topic: Annotated[
        str, Field(description="The ML/AI research topic to map, e.g. test-time training")
    ],
) -> str:
    """Map what has been tried on an ML/AI research topic and what is still open."""
    return (
        f"Map the ML/AI research on: {topic}\n{_FULL_TEXT}\n\n"
        "Use the Lacuna Research tools, about 10 to 14 calls.\n"
        '1. One search_lacuna(search_type="cluster", limit=10). Sort the results '
        "into core (1 to 4 directions specifically about the topic) and off-topic.\n"
        "2. get_direction on each core direction. Then open at most one more from "
        "their related_directions, usually the broader parent (umbrella); it can "
        "replace a weak core pick. The direction summary is the best source of key "
        "papers and method lines; authors named with those papers say who leads a "
        "line, while the direction's author list is ranked by paper count and favors "
        "prolific application authors.\n"
        "3. Fill in year and venue for the 4 to 6 most important papers with "
        'get_paper(view="preview"). Summaries favor recent work, so always run one '
        'search_lacuna(search_type="paper") for the founding papers of the field. '
        "Use get_direction_papers only if a core "
        "summary cites fewer than 3 papers: its lists are newest first and full of "
        "recent applications.\n"
        '4. One search_lacuna(search_type="hypothesis"). Results are noisy: open '
        "the 1 or 2 that are plainly about the topic, not just the top-ranked, and "
        "say so if none is.\n\n"
        "Write about 600 to 900 words:\n"
        "- How Lacuna splits the topic: a small table of directions with size and "
        "role.\n"
        "- Lines of work, organized by method: 2 to 4 key papers each (title, year, "
        'venue, or "not returned") and 1 or 2 leading authors; then applications '
        "in one grouped list. Say whether the founding papers appear or only recent "
        "ones.\n"
        "- What is still open: each item tied to a paper's stated limitation, a "
        "direction summary, or a Lacuna hypothesis labelled as generated.\n"
        "- Directions seen but not opened, related and off-topic listed separately.\n\n"
        "The same paper can carry different IDs, and a hypothesis may name a direction "
        "differently: do not present one entity as two. Write venues plainly (ICLR, "
        'arXiv) and do not present "Crossref" as a venue. ' + _CITE
    )


def find_researchers(
    topic: Annotated[
        str, Field(description="The ML/AI topic, optionally with an institution or venue")
    ],
) -> str:
    """Find ML/AI researchers working on a topic."""
    return (
        f"Find ML/AI researchers working on: {topic}\n{_FULL_TEXT}\n\n"
        "Use the Lacuna Research tools. Author search matches person names only (a "
        'query containing "Mila" returns people named Mila), so never put the topic '
        'or an institution in search_lacuna(search_type="author").\n'
        "0. If the request names an institution or venue, do this first: find it "
        'with search_type="institution" or "venue" and read its context and '
        "get_institution_authors (limit at most 200; sorted by paper count), so you "
        "can check candidates against it in the steps below.\n"
        '1. search_lacuna(search_type="cluster"). The search is lexical: drop '
        'directions that match only on a generic word (for example "world" or '
        '"learning"). If the best direction looks missing, one more specific query '
        "is fine. Open the best 2 or 3 with get_direction and collect people from "
        "both `authors` and `top_author_profiles`.\n"
        "2. get_author_context on the 4 to 6 strongest candidates. Rank by how much of "
        "their work in the last 2 years is on the topic, not by career paper count. "
        "If their impact_directions include a better-matching direction you have not "
        "opened, open it and add its strong authors.\n"
        "3. For each person you keep, pick 2 or 3 on-topic papers from "
        "get_author_papers (newest first; page with offset) and the profile; their "
        "newest papers are often off-topic. Cite a paper without year or venue as "
        '"not listed".\n'
        "4. With an institution or venue, keep only people who match it, follow "
        "co-authors of the matches, and if fewer than 3 people meet both conditions, "
        "say so and list close collaborators elsewhere separately.\n\n"
        "Output:\n"
        "- 3 to 5 people: name, listed affiliation, main directions, 2 or 3 on-topic "
        "papers with year and venue, and one sentence on why, citing that evidence.\n"
        '- "Also in these directions, not checked": up to 5 names.\n'
        "- One line on coverage: directions opened, and relevant ones seen but not "
        "opened.\n\n"
        "Author profiles include role titles, dates and narrative biography: do not "
        'repeat any of it. Use only the top-level affiliation, labelled "listed '
        'affiliation" ("none listed" if absent), never infer seniority or current employer, and do not look up '
        "contact details. " + _CITE
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
        f"Explain this paper and place it in context: {paper}\n{_FULL_TEXT}\n\n"
        "Use the Lacuna Research tools.\n"
        "1. get_paper takes an arXiv ID, DOI, an arXiv, DOI or OpenReview URL, or a "
        "Lacuna URL directly. For a title, run one "
        'search_lacuna(search_type="paper") with the exact title and fetch the best '
        "match. If the paper is not in Lacuna, say so and stop.\n"
        "2. Read the default view. Its summary is generated by Lacuna: attribute its "
        'numbers to Lacuna\'s summary unless you check them in view="fulltext".\n'
        '3. Call view="neighbors". Neighbors are topical overlap, not citations '
        "(Lacuna has no citation graph), and can include proceedings front matter or "
        "workshop proposals: drop those. If few real papers remain, run one "
        'search_lacuna(search_type="paper", ranking_profile="semantic") on the '
        "paper's core idea. Pick 2 or 3 comparisons by how much they explain (a "
        "predecessor, a rival, a successor), not by neighbor rank, and read them with "
        "get_paper (default view, figure_limit=0) so comparisons rest on their content, "
        "not titles. get_paper does not return the paper's research direction; name "
        "one only from a cluster search, marked as your match.\n"
        "4. List other versions. Code, "
        "data and model links can sit in a resources field or only inside the "
        "summary: check both.\n\n"
        "Output, about 350 to 500 words of prose (URLs not counted):\n"
        "- Header: title, authors as plain names, venue and year as Lacuna lists "
        "them (a listed venue may not mean acceptance; say accepted only if the "
        "payload says so), and the work's Lacuna URL (/work/<slug>, not a "
        "/version/ URL).\n"
        "- What it does: problem, approach and main result in 2 or 3 sentences.\n"
        "- Key results: one attribution line, then 3 to 5 bullets with numbers, "
        "plus the authors' stated limitations in one line.\n"
        "- Where it sits: the closest related papers and what this one changes, "
        "marked as your reading.\n"
        "- Versions and resources.\n\n" + _CITE
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
