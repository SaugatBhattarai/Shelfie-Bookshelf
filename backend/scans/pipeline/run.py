from .timing import stage

STUB_DETECTIONS = [
    {
        "box": [12, 0, 78, 340],
        "detection_confidence": 0.81,
        "raw_read": {"title": "The Dispossessed", "author": "Ursula LeGuin"},
        "match": {
            "catalog_id": "bk_0042", "title": "The Dispossessed",
            "author": "Ursula K. Le Guin",
            "score": 0.91, "margin": 0.44, "status": "high",
        },
        "alternates": [],
    },
    {
        "box": [80, 0, 141, 340],
        "detection_confidence": 0.55,
        "raw_read": {"title": "Dune", "author": "Frank Herbert"},
        "match": {
            "catalog_id": "bk_0007", "title": "Dune (1965 Chilton)",
            "author": "Frank Herbert",
            "score": 0.94, "margin": 0.02, "status": "review",
        },
        "alternates": [
            {"catalog_id": "bk_0008", "title": "Dune (2019 Ace)", "score": 0.92},
        ],
    },
    {
        "box": [143, 0, 190, 340],
        "detection_confidence": 0.44,
        "raw_read": {"title": "RIVE", "author": None},
        "match": {"catalog_id": None, "title": None, "author": None,
                  "score": 0.31, "margin": 0.02, "status": "unmatched"},
        "alternates": [],
    },
]


def run_pipeline(image_path):
    """Photo path -> (detections, errors, timings_ms).

    Phase 3 fills detect, phase 4 fills vlm, phase 2 fills match.
    """
    timings, errors = {}, []

    with stage(timings, "detect"):
        pass          # boxes = detect_spines(image_path)

    with stage(timings, "vlm"):
        pass          # reads = read_spines(crops)

    with stage(timings, "match"):
        pass          # detections = match_all(reads)

    return STUB_DETECTIONS, errors, timings