import csv
from pathlib import Path


def _find_catalog_path():
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "catalog.csv",   # repo_root/catalog.csv
        here.parents[2] / "catalog.csv",   # backend/catalog.csv (fallback)
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"catalog.csv not found. Checked: {[str(c) for c in candidates]}"
    )


def _split_list(raw):
    return [t.strip() for t in (raw or "").split(";") if t.strip()]


def load_catalog(path=None):
    """
    Loads catalog.csv into a list of dicts.

    Real columns: id, title, alt_titles, author, author_variants, series,
                  volume, year, edition, is_omnibus, contains_ids

    - alt_titles / author_variants / contains_ids are semicolon-separated.
    - is_omnibus is a truthy string ("true"/"1"/"yes") -> bool.
    - contains_ids links an omnibus entry to the individual volume ids it collects.
    """
    path = path or _find_catalog_path()
    catalog = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            catalog.append({
                "catalog_id": row.get("id", "").strip(),
                "title": row.get("title", "").strip(),
                "alt_titles": _split_list(row.get("alt_titles")),
                "author": row.get("author", "").strip(),
                "author_variants": _split_list(row.get("author_variants")),
                "series": row.get("series", "").strip(),
                "volume": row.get("volume", "").strip(),
                "year": row.get("year", "").strip(),
                "edition": row.get("edition", "").strip(),
                "is_omnibus": (row.get("is_omnibus", "").strip().lower() in ("true", "1", "yes")),
                "contains_ids": _split_list(row.get("contains_ids")),
            })

    if not catalog:
        raise ValueError(f"Catalog loaded from {path} is empty.")

    return catalog