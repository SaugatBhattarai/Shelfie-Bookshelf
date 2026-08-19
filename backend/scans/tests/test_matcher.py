import pytest
from scans.pipeline.matcher import match_book, _classify
from scans.pipeline.catalog import load_catalog


def _entry(catalog_id, title, author, alt_titles=None, author_variants=None,
           is_omnibus=False, contains_ids=None, series="", volume="", year="", edition=""):
    """Helper to build a full catalog entry without repeating every key by hand."""
    return {
        "catalog_id": catalog_id,
        "title": title,
        "alt_titles": alt_titles or [],
        "author": author,
        "author_variants": author_variants or [],
        "series": series,
        "volume": volume,
        "year": year,
        "edition": edition,
        "is_omnibus": is_omnibus,
        "contains_ids": contains_ids or [],
    }


@pytest.fixture
def catalog():
    return [
        # --- two editions of the same book ---
        _entry("bk_dune_1965", "Dune", "Frank Herbert",
               alt_titles=["Dune (1965 Chilton)"], edition="1965 Chilton"),
        _entry("bk_dune_2019", "Dune", "Frank Herbert",
               alt_titles=["Dune (2019 Ace)"], edition="2019 Ace"),

        # --- US/UK title split ---
        _entry("bk_hp1_us", "Harry Potter and the Sorcerer's Stone", "J.K. Rowling",
               alt_titles=["Harry Potter and the Philosopher's Stone"]),

        # --- shared title, different authors ---
        _entry("bk_stand_king", "The Stand", "Stephen King"),
        _entry("bk_stand_other", "The Stand", "Alex Rivera"),

        # --- omnibus vs individual volume ---
        _entry("bk_lotr_omnibus", "The Lord of the Rings: The Complete Trilogy", "J.R.R. Tolkien",
               alt_titles=["Lord of the Rings Omnibus"], is_omnibus=True,
               contains_ids=["bk_lotr_fellowship", "bk_lotr_towers", "bk_lotr_king"]),
        _entry("bk_lotr_fellowship", "The Fellowship of the Ring", "J.R.R. Tolkien", series="Lord of the Rings", volume="1"),

        # --- substring trap ---
        _entry("bk_it", "It", "Stephen King"),
        _entry("bk_atomic_habits", "Atomic Habits", "James Clear"),

        # --- author name variants (accents / transliteration) ---
        _entry("bk_100_years", "One Hundred Years of Solitude", "Gabriel García Márquez",
               author_variants=["Gabriel Garcia Marquez", "G. García Márquez"]),

        # --- clean, unambiguous control entry ---
        _entry("bk_dispossessed", "The Dispossessed", "Ursula K. Le Guin",
               author_variants=["Ursula LeGuin"]),
    ]


# --- Substring trap: prevents "It" from matching inside "Atomic Habits" ---

def test_substring_trap_does_not_false_match(catalog):
    match, _ = match_book("It", "Stephen King", catalog)
    assert match["catalog_id"] == "bk_it"
    assert match["catalog_id"] != "bk_atomic_habits"


def test_short_title_does_not_match_longer_unrelated_title(catalog):
    match, _ = match_book("Atomic Habits", "James Clear", catalog)
    assert match["catalog_id"] == "bk_atomic_habits"


# --- Two editions, identical/near-identical score -> margin forces review ---

def test_ambiguous_editions_score_high_but_low_margin_forces_review(catalog):
    match, alternates = match_book("Dune", "Frank Herbert", catalog)
    assert match["status"] == "review"
    assert match["margin"] < 0.10
    assert len(alternates) >= 1


# --- US/UK title split resolves via alt_titles ---

def test_uk_title_matches_via_alt_titles(catalog):
    match, _ = match_book("Harry Potter and the Philosopher's Stone", "J.K. Rowling", catalog)
    assert match["catalog_id"] == "bk_hp1_us"
    assert match["status"] == "high"


# --- Shared title, different authors: author acts as tie-breaker ---

def test_shared_title_resolved_by_author(catalog):
    match, _ = match_book("The Stand", "Stephen King", catalog)
    assert match["catalog_id"] == "bk_stand_king"
    assert match["status"] == "high"


def test_shared_title_no_author_stays_review_not_arbitrary_pick(catalog):
    match, alternates = match_book("The Stand", None, catalog)
    assert match["status"] == "review"
    assert len(alternates) >= 1  # both "The Stand" entries should surface as options


# --- Omnibus vs individual volume: distinct titles, shouldn't cross-match ---

def test_omnibus_and_individual_volume_stay_distinct(catalog):
    omnibus_match, _ = match_book("Lord of the Rings Omnibus", "J.R.R. Tolkien", catalog)
    volume_match, _ = match_book("The Fellowship of the Ring", "J.R.R. Tolkien", catalog)
    assert omnibus_match["catalog_id"] == "bk_lotr_omnibus"
    assert volume_match["catalog_id"] == "bk_lotr_fellowship"
    assert omnibus_match["catalog_id"] != volume_match["catalog_id"]


def test_omnibus_entry_tracks_its_contained_volumes(catalog):
    omnibus = next(e for e in catalog if e["catalog_id"] == "bk_lotr_omnibus")
    assert "bk_lotr_fellowship" in omnibus["contains_ids"]


# --- Author name variants: initials, accents, transliteration ---

def test_author_unaccented_variant_matches_accented_catalog_entry(catalog):
    match, _ = match_book("One Hundred Years of Solitude", "Gabriel Garcia Marquez", catalog)
    assert match["catalog_id"] == "bk_100_years"
    assert match["status"] == "high"


def test_author_variant_list_is_actually_used(catalog):
    # Query author matches a *variant*, not the canonical author string directly —
    # this only passes if _author_score checks author_variants, not just entry["author"].
    match, _ = match_book("The Dispossessed", "Ursula LeGuin", catalog)
    assert match["catalog_id"] == "bk_dispossessed"
    assert match["status"] == "high"


# --- Unmatched: nothing in the catalog resembles this at all ---

def test_completely_unrelated_title_is_unmatched(catalog):
    match, _ = match_book("Xyzzyx Nonexistent Book Title", "Nobody Real", catalog)
    assert match["status"] == "unmatched"
    assert match["catalog_id"] is None
    assert match["title"] is None
    assert match["author"] is None


def test_unmatched_never_leaks_a_real_catalog_id(catalog):
    # Regression test: previously a low-score top candidate could still leak
    # its real catalog_id/title/author even though status was "unmatched".
    match, _ = match_book("Completely Made Up Nonsense Title Zzyzx", "Nobody", catalog)
    if match["status"] == "unmatched":
        assert match["catalog_id"] is None
        assert match["title"] is None
        assert match["author"] is None


# --- Classification boundary tests (unit-level, no catalog needed) ---

@pytest.mark.parametrize("score,margin,ambiguous,expected", [
    (0.90, 0.15, False, "high"),
    (0.90, 0.05, False, "review"),      # high score but low margin -> review, not high
    (0.70, 0.30, False, "review"),
    (0.40, 0.10, False, "unmatched"),
    (0.95, 0.20, True, "review"),       # ambiguous-without-author overrides high score
])
def test_classify_boundaries(score, margin, ambiguous, expected):
    assert _classify(score, margin, ambiguous) == expected


# --- Catalog loading (real catalog.csv, not the fixture) ---

def test_real_catalog_loads_and_has_required_columns():
    catalog = load_catalog()
    assert len(catalog) >= 100
    for entry in catalog[:5]:
        assert entry["catalog_id"]
        assert entry["title"]
        assert isinstance(entry["alt_titles"], list)
        assert isinstance(entry["author_variants"], list)
        assert isinstance(entry["is_omnibus"], bool)


def test_real_catalog_path_resolves_from_repo_root():
    from scans.pipeline.catalog import _find_catalog_path
    path = _find_catalog_path()
    assert path.name == "catalog.csv"
    assert path.exists()