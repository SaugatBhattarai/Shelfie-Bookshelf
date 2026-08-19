from rapidfuzz import fuzz
from rapidfuzz.utils import default_process
from .catalog import load_catalog  # noqa: F401 — re-exported so run.py's existing import still works

# --- Config: the two big decisions, documented right where they're used ---

TITLE_WEIGHT = 0.65
AUTHOR_WEIGHT = 0.35

HIGH_SCORE_THRESHOLD = 0.85
HIGH_MARGIN_THRESHOLD = 0.10
REVIEW_SCORE_THRESHOLD = 0.60

ALTERNATES_LIMIT = 3


def _title_score(query_title, entry):
    """
    Best score across the canonical title AND any alt_titles —
    catches US/UK title splits and known alternate names.
    token_set_ratio (not partial_ratio) deliberately: partial_ratio lets a
    short title like "It" match as a near-perfect substring of "Atomic Habits",
    which is exactly the trap the catalog is built to contain.

    processor=default_process lowercases and strips punctuation before scoring.
    Without it rapidfuzz compares raw strings, and a spine printed "SNAP" scores
    25/100 against the catalog's "Snap" — all-caps spine art is common enough
    that this alone sent real books to unmatched.
    """
    candidates = [entry["title"]] + entry["alt_titles"]
    scores = [fuzz.token_set_ratio(query_title, c, processor=default_process)
              for c in candidates if c]
    return max(scores) / 100 if scores else 0.0


def _author_score(query_author, entry):
    if not query_author:
        return 0.0
    candidates = [entry["author"]] + entry["author_variants"]
    scores = [fuzz.token_set_ratio(query_author, c, processor=default_process)
              for c in candidates if c]
    return max(scores) / 100 if scores else 0.0


def match_book(title, author, catalog):
    """
    Returns (match_result: dict, alternates: list[dict])

    match_result: {catalog_id, title, author, score, margin, status}
    status is one of "high" | "review" | "unmatched"
    alternates: up to ALTERNATES_LIMIT other close candidates, for the
    review screen to show as options.
    """
    scored = []
    for entry in catalog:
        t_score = _title_score(title, entry)
        a_score = _author_score(author, entry)
        combined = (t_score * TITLE_WEIGHT) + (a_score * AUTHOR_WEIGHT)
        scored.append((combined, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] == 0.0:
        return _unmatched_result(), []

    top_score, top_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = round(top_score - second_score, 4)

    # Author as tie-breaker for shared titles: if the read had no author at all,
    # and the top match's title is ambiguous (another entry shares a very close
    # title score), don't let a coin-flip pick a canonical edition — force review.
    ambiguous_without_author = (
        not author and second_score >= top_score - 0.05
    )

    status = _classify(top_score, margin, ambiguous_without_author)

    match_result = {
        "catalog_id": top_entry["catalog_id"] if status != "unmatched" else None,
        "title": top_entry["title"] if status != "unmatched" else None,
        "author": top_entry["author"] if status != "unmatched" else None,
        "score": round(top_score, 4),
        "margin": margin,
        "status": status,
    }

    alternates = [
        {
            "catalog_id": entry["catalog_id"],
            "title": entry["title"],
            "score": round(score, 4),
        }
        for score, entry in scored[1:1 + ALTERNATES_LIMIT]
        if score >= REVIEW_SCORE_THRESHOLD  # don't show junk alternates
    ]

    return match_result, alternates


def _classify(score, margin, ambiguous_without_author):
    if ambiguous_without_author:
        return "review"
    if score >= HIGH_SCORE_THRESHOLD and margin >= HIGH_MARGIN_THRESHOLD:
        return "high"
    if score >= REVIEW_SCORE_THRESHOLD:
        return "review"
    return "unmatched"


def _unmatched_result():
    return {
        "catalog_id": None,
        "title": None,
        "author": None,
        "score": 0.0,
        "margin": 0.0,
        "status": "unmatched",
    }