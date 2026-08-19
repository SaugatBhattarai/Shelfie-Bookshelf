from .timing import stage
from .detector import detect_spines
from .vlm import read_spines
from .matcher import match_book, load_catalog  # adjust names to your actual module

CATALOG = load_catalog()  # load once at module level, not per-request

def run_pipeline(image_path):
    timings, errors = {}, []

    with stage(timings, "detect"):
        spines = detect_spines(image_path)

    if not spines:
        errors.append({"stage": "detect", "detail": "No book spines detected in image."})
        return [], errors, timings

    with stage(timings, "vlm"):
        reads, vlm_errors, _ = read_spines(spines)
    errors.extend(vlm_errors)

    with stage(timings, "match"):
        detections = []
        for r in reads:
            title = r["raw_read"].get("title")
            author = r["raw_read"].get("author")

            if not title:
                # nothing to match against — goes straight to unmatched, not a matcher call
                match_result = {"catalog_id": None, "title": None, "author": None,
                                 "score": 0.0, "margin": 0.0, "status": "unmatched"}
                alternates = []
            else:
                match_result, alternates = match_book(title, author, CATALOG)

            detections.append({
                "box": r["box"],
                "detection_confidence": r["detection_confidence"],
                "raw_read": r["raw_read"],
                "match": match_result,
                "alternates": alternates,
            })

    return detections, errors, timings