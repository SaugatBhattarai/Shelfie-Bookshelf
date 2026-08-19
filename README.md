# Shelfie — Bookshelf → Library Inventory

Take a photo of a bookshelf. Get back a structured list of books, matched against a canonical
catalog, with a confidence score on every row. Confirm the ones you want, and they persist to
your library.

```
Expo app  ──photo──▶  Django REST API  ──▶  YOLOv8n (local, CPU)  ──▶  spine crops
                                                                          │
                                                    hosted vision-language model (OpenAI)
                                                                          │
                                                             title + author per spine
                                                                          │
                                                    fuzzy match vs catalog.csv (320 entries)
                                                                          │
                                        high ──▶ pre-selected   review ──▶ user decides   unmatched ──▶ user decides
                                                                          │
                                                                   SQLite library
```

**Status: working end to end.** Photo in, matched books out, confirmed books persist. There are
real limitations and one known-broken area, all written up in
[Known issues and what I'd do next](#13-known-issues-and-what-id-do-with-another-day). Nothing in
this README is aspirational — every number below was measured on the machine described in
[section 7](#7-measured-latency-and-cost).

---

## Table of contents

| # | Section | Read this if you want to… |
|---|---------|---------------------------|
| 1 | [What you need before you start](#1-what-you-need-before-you-start) | check prerequisites |
| 2 | [Quick start](#2-quick-start-clean-clone-to-running-app) | get it running |
| 3 | [Connecting the phone to the backend](#3-connecting-the-phone-to-the-backend-the-step-that-trips-everyone-up) | fix "Network request failed" |
| 4 | [What the spine detector actually sees](#4-what-the-spine-detector-actually-sees) | see the YOLO output |
| 5 | [Architecture, explained from scratch](#5-architecture-explained-from-scratch) | understand the code |
| 6 | [Local vs hosted: what runs where and why](#6-local-vs-hosted-what-runs-where-and-why) | understand the routing decision |
| 7 | [Measured latency and cost](#7-measured-latency-and-cost) | see the numbers |
| 8 | [The catalog](#8-the-catalog-how-i-built-it-and-what-i-broke-on-purpose) | understand catalog.csv |
| 9 | [Matching and confidence](#9-matching-and-confidence-the-core-of-the-task) | understand the scoring |
| 10 | [Human in the loop](#10-human-in-the-loop) | understand the review step |
| 11 | [Graceful failure](#11-graceful-failure) | see how each failure mode is handled |
| 12 | [Tests](#12-tests) | run the tests |
| 13 | [Known issues / next day](#13-known-issues-and-what-id-do-with-another-day) | see what's unfinished |
| 14 | [API reference](#14-api-reference) | call the API directly |
| 15 | [Repository map](#15-repository-map) | find a file |

---

## 1. What you need before you start

| Tool | Version I used | Why |
|------|----------------|-----|
| Python | 3.13.1 | backend + both models' glue code |
| Node.js | 24.19.0 | to run the Expo CLI |
| An OpenAI API key | — | the hosted vision-language model. **The backend will not start without it** — see [2.3](#23-set-your-api-key-required) |
| A phone with Expo Go, **or** an Android/iOS simulator | Expo SDK 54 | to run the app |

You do **not** need a GPU. All local inference is CPU-only, which is what the task asked for.
You do **not** need to download model weights — `backend/yolov8n.pt` (6.5 MB) is committed to the
repo, so a clean clone works without an extra download step.

**Disk/time budget for a clean clone:** the Python dependencies include PyTorch, which is a ~2.5 GB
install and the slowest part of setup by a wide margin. Budget 5–10 minutes for `pip install`.

---

## 2. Quick start: clean clone to running app

Every command below is written out in full. If you are new to Django or Expo, run them in order and
don't skip any.

### 2.1 Get the code

```bash
git clone <your-repo-url> shelfie
cd shelfie
```

### 2.2 Backend: create a virtual environment and install

A *virtual environment* is a private folder of Python packages for this project only, so it can't
collide with anything else on your machine.

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

You'll know the venv is active because your prompt is prefixed with `(.venv)`. Every backend command
from here on assumes it's active.

### 2.3 Set your API key (required)

```bash
# from the backend/ directory
cp .env-example .env        # Windows PowerShell: Copy-Item .env-example .env
```

Then open `backend/.env` and put your real key in:

```
OPENAI_API_KEY=sk-...
```

> **This is not optional and it is not lazy.** `scans/pipeline/vlm.py` constructs the OpenAI client
> at module import time, and `scans/views.py` imports it, so Django fails to start at all if the key
> is missing. The error you'd see is:
> `OpenAIError: Missing credentials. Please pass an api_key ... or set the OPENAI_API_KEY environment variable.`
> If you see that, your `.env` is missing or in the wrong directory. It belongs in `backend/.env`,
> next to `manage.py`. (Making the client lazy so the server boots without a key is on the
> [next-day list](#13-known-issues-and-what-id-do-with-another-day).)

### 2.4 Create the database and start the server

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

`migrate` creates `backend/db.sqlite3` with two tables (`Scan`, `LibraryEntry`). The database file is
gitignored, so you always start from an empty library — that's intentional, so a grader's first run
is clean.

`0.0.0.0` (rather than the default `127.0.0.1`) makes the server reachable from your phone over
Wi-Fi. Without it, the phone gets a connection refused.

**Check it works.** Open <http://localhost:8000/api/> in a browser. You should see:

```json
{
  "service": "shelfie-api",
  "status": "ok",
  "project_root": "...",
  "endpoints": { "scan": "http://localhost:8000/api/scans/", "library": "http://localhost:8000/api/library/" }
}
```

`project_root` is in there deliberately: if two copies of this project are ever running on port
8000, that field is the only quick way to tell which one answered you.

### 2.5 Mobile app

In a **second terminal**, leave the backend running and:

```bash
cd mobile
npm install
```

Now open `mobile/api.js` and change the first line to your computer's LAN IP:

```js
export const BASE = "http://192.168.1.42:8000";   // ← your machine's IP, not mine
```

See [section 3](#3-connecting-the-phone-to-the-backend-the-step-that-trips-everyone-up) for how to
find that IP. Then:

```bash
npx expo start
```

Scan the QR code with Expo Go (Android) or the Camera app (iOS). Press **Pick photo**, choose one of
the shelf photos in [`photos/`](photos/), and wait — a busy 20-shelf photo takes about a minute, and
[section 7](#7-measured-latency-and-cost) explains exactly where that minute goes.

---

## 3. Connecting the phone to the backend (the step that trips everyone up)

The phone and the laptop are two different computers. `localhost` on the phone means *the phone*, so
the app has to be pointed at the laptop's address on the local network.

**Find your machine's LAN IP:**

| OS | Command | Look for |
|----|---------|----------|
| Windows | `ipconfig` | "IPv4 Address" under your active Wi-Fi adapter |
| macOS | `ipconfig getifaddr en0` | the whole output |
| Linux | `hostname -I` | the first address |

Put that address into `mobile/api.js` as shown above, then restart Expo.

**Checklist when you get `Network request failed`:**

1. Phone and laptop on the **same Wi-Fi network** (a phone on cellular data cannot see your laptop).
2. Backend started with `runserver 0.0.0.0:8000`, not plain `runserver`.
3. `BASE` in `mobile/api.js` has no trailing slash and includes `:8000`.
4. Your OS firewall is allowing inbound connections on port 8000 — on Windows this prompts the first
   time and it is easy to click "Cancel" by reflex.
5. Sanity check from the phone's browser: open `http://<your-ip>:8000/api/`. If that JSON doesn't
   load in the phone's browser, the problem is the network, not the app.

`ALLOWED_HOSTS = ["*"]` is already set in `backend/config/settings.py` so Django accepts requests
addressed to a raw IP. That is a development-only setting and is fine here — it would not be fine in
production.

---

## 4. What the spine detector actually sees

This is the raw output of the local model, before anything is sent to a hosted API. Green boxes are
the regions YOLOv8n classified as COCO class 73 (`book`); the label on each box is
`<index> <detection confidence>`.

![YOLOv8n spine detection on photos/12.jpg — 18 boxes](docs/spine_detection_example.jpg)

*Generated from [`photos/12.jpg`](photos/12.jpg) — 18 boxes, detection confidence 0.26–0.78.*

Three things are worth reading off this image, because they explain design decisions further down:

1. **The boxes are loose and they overlap.** Look at the cluster around "Sugar and Spite" — several
   boxes cover the same physical book, and some boxes span two neighbouring spines. This is exactly
   why the same title can appear more than once in a scan result, which is a
   [known issue](#13-known-issues-and-what-id-do-with-another-day).
2. **Detection confidence is low in absolute terms** (0.26–0.78). That's expected: YOLOv8n is trained
   on COCO, where a "book" is usually a chunky object lying on a table, not a 2 cm vertical sliver
   on a library shelf. It is still good enough to find *where* the spines are, which is all this
   stage is asked to do.
3. **The titles are printed in every possible orientation and case** — `SNAP`, `OVERKILL`,
   `THE SECOND RIDER` in full caps, sideways. That observation is what caught the case-sensitivity
   bug described in [section 9.4](#94-a-bug-the-measurement-found).

**To see this for a different photo,** there's a throwaway script in the repo:

```bash
cd backend
python spine_test_yolo.py     # opens an OpenCV window showing detections
```

Heads up on a clean clone: its `IMG` path points at a file under `backend/media/scans/`, which is
gitignored — so edit that one line to point at something in `photos/` before running it. It's a
scratch script I kept in the repo because it's how I actually looked at detector output while
building, not because it's polished.

<!-- ─────────────── SCREENSHOT PLACEHOLDERS ───────────────
     Drop PNGs into docs/ with these exact names and the images below will appear.
     Suggested captures, taken from the running app:
       docs/app_scan_result.png  — the result list right after a scan, showing the
                                   green / amber / red status colours on one screen
       docs/app_review.png       — a low-confidence row with its "also matched" alternates
       docs/app_library.png      — the saved library list
─────────────────────────────────────────────────────────── -->

### App screenshots

| Scan result | Review of a low-confidence row | Saved library |
|---|---|---|
| ![Scan result screen](docs/app_scan_result.png) | ![Review screen](docs/app_review.png) | ![Library list](docs/app_library.png) |

> **Placeholder:** the three files above are not in the repo yet. Take the screenshots from the
> running app, save them into `docs/` under exactly those filenames, and this table renders itself.
> Until then GitHub shows three broken-image icons — that is the placeholder doing its job.

---

## 5. Architecture, explained from scratch

This section assumes you know what an HTTP request is and not much else about this stack.

### 5.1 The two halves

The repo is two independent programs that talk over HTTP:

* **`mobile/`** — a React Native app run through Expo. It draws the UI and makes `fetch` calls. It
  contains no matching logic and no model code at all. It is deliberately thin.
* **`backend/`** — a Django project. It receives the photo, runs the whole pipeline, and owns the
  database.

Keeping *all* intelligence server-side is the main structural decision in the project. The phone
never sees the catalog, never runs a model, and never computes a score. That means the matching
logic can be changed and re-measured without rebuilding the app — which matters a lot when you're
iterating on scoring under a deadline.

### 5.2 Django project layout, for anyone new to Django

A Django *project* is the container; a Django *app* is a module inside it.

```
backend/
├── manage.py              # the command-line entry point: migrate, runserver, ...
├── config/                # the PROJECT: settings and the root URL table
│   ├── settings.py        # database, installed apps, MEDIA_ROOT, upload size limits
│   └── urls.py            # routes /api/... into the scans app; serves /media/ in DEBUG
└── scans/                 # the APP: everything Shelfie-specific
    ├── models.py          # database tables, defined as Python classes
    ├── views.py           # the HTTP endpoints
    ├── serializers.py     # turns model objects into JSON
    ├── urls.py            # the app's own URL table
    └── pipeline/          # plain Python, no Django imports except settings — the actual work
```

The important boundary is `scans/pipeline/`. Those modules are ordinary functions taking and
returning plain dicts. They know nothing about HTTP. That is what makes the matcher unit-testable
without spinning up a server or a database — see [section 12](#12-tests).

### 5.3 The life of one request, function by function

When you press **Pick photo**, this is the exact path through the code.

**Step 1 — the app uploads.** [`mobile/api.js`](mobile/api.js) `uploadShelf()` builds a
`multipart/form-data` body with the image and POSTs it to `/api/scans/`. Photos are captured at
`quality: 0.7` in [`mobile/App.js`](mobile/App.js) — that's a JPEG compression setting, chosen
because full-quality phone photos are 5–10 MB and the upload is the one part of this flow the user
watches with nothing on screen. `settings.py` caps uploads at 20 MB.

**Step 2 — the view saves the file.** [`scans/views.py`](backend/scans/views.py) `ScanView.post()`
first checks that an image is actually present (`400` if not), then creates a `Scan` row. Saving
before processing is deliberate: if the pipeline explodes, the original photo is still on disk to
debug with.

**Step 3 — the pipeline runs.** [`scans/pipeline/run.py`](backend/scans/pipeline/run.py)
`run_pipeline()` is the orchestrator, and it's short enough to read in one go. It calls three stages
in sequence and wraps each in the `stage()` context manager from
[`timing.py`](backend/scans/pipeline/timing.py), which records wall-clock milliseconds into a dict.
Those timings are returned to the app in every response, so latency is observable in the product
rather than in a log file somewhere.

**Step 4 — detect (local).**
[`scans/pipeline/detector.py`](backend/scans/pipeline/detector.py) `detect_spines()` loads YOLOv8n
once into a module-level global (`get_model()`), runs it with `classes=[73]` — COCO's `book` class —
at `conf_threshold=0.25`, then crops each box out of the original image with OpenCV and writes it to
`media/crops/<uuid>/spine_N.jpg`. It returns a list of
`{box, detection_confidence, crop_path}`.

If it finds nothing it returns an empty list rather than raising. `run_pipeline` catches that,
appends a structured error, and returns early — **the hosted API is never called for a photo with no
books in it.** That's the first cost control in the pipeline.

**Step 5 — read (hosted).** [`scans/pipeline/vlm.py`](backend/scans/pipeline/vlm.py) `read_spines()`
loops over the crops and calls `read_spine()` on each one, which base64-encodes the crop and sends it
to the vision-language model with a short prompt demanding raw JSON and this instruction:

> *"If you cannot confidently read the title, use null for that field. Never guess or hallucinate a
> title you cannot actually see."*

That last sentence is load-bearing. A model that guesses produces a plausible title that then matches
the catalog at high confidence, and the user gets a book they don't own added silently. A `null` is
recoverable; a confident hallucination is not.

The call sets `response_format={"type": "json_object"}`, a 15-second timeout, and retries rate limits
three times with exponential backoff. `read_spine()` **never raises** — every failure path returns
`({"title": None, "author": None}, {"stage": "vlm", "detail": ...})`, so one bad spine can't take
down a 30-spine scan. Details in [section 11](#11-graceful-failure).

**Step 6 — match (local, no model).** For each read, `run_pipeline` calls
[`matcher.py`](backend/scans/pipeline/matcher.py) `match_book(title, author, CATALOG)`. If the VLM
returned no title at all, the matcher is skipped entirely and the row is marked `unmatched` — there's
nothing to match on, and it saves 320 string comparisons. The catalog is loaded **once at module
import**, not per request. Full scoring detail is in [section 9](#9-matching-and-confidence-the-core-of-the-task).

**Step 7 — respond.** The view returns a single JSON object: `scan_id`, `detections[]`, `errors[]`,
`timings_ms`. Note that **`errors` is a list alongside the results, not an alternative to them** — a
scan where 3 of 20 spines failed still returns 17 usable books plus 3 error entries. See
[section 14](#14-api-reference) for the exact shape.

**Step 8 — the user decides, then confirms.** [`mobile/App.js`](mobile/App.js) renders one row per
detection, colour-coded by status, and pre-selects only the `high` rows. Tapping any row toggles it.
**Add N to library** POSTs the selected rows to `/api/library/`, which writes `LibraryEntry` rows and
returns the saved library.

### 5.4 The data model

Two tables, both in [`scans/models.py`](backend/scans/models.py):

| Model | Fields | Notes |
|-------|--------|-------|
| `Scan` | `image`, `created_at` | the uploaded photo. One row per upload. |
| `LibraryEntry` | `catalog_id`, `title`, `author`, `source_scan` (FK), `confirmed_at` | one row per **user-confirmed** book |

Two deliberate choices here:

* **Only confirmed books are stored as library entries.** Detections are not persisted. A row in
  `LibraryEntry` always means "a human said yes to this", which keeps the library's meaning
  unambiguous.
* **`catalog_id` is a plain `CharField`, not a foreign key to a `CatalogBook` table.** The catalog
  lives in `catalog.csv` and is loaded into memory. With 320 entries and a full scan doing ~16
  lookups, in-memory scoring costs 9 ms per book (measured) — a database would add complexity and
  a migration step for no gain at this size. `catalog_id` is blank for books the user confirmed
  that had no catalog match, so free-text books are first-class, not an error state.

---

## 6. Local vs hosted: what runs where and why

| Stage | Where | Model | Why there |
|-------|-------|-------|-----------|
| Find the spines | **Local**, CPU | YOLOv8n (COCO, off-the-shelf) | "Where are the rectangles" is a solved localisation problem. It costs 159 ms and $0 locally. Paying a hosted model to do it would add a network round trip and a per-image fee for a worse answer, because a VLM asked for bounding boxes returns approximate coordinates. |
| Read the text on each spine | **Hosted** | OpenAI vision-language model | Spine text is rotated 90°, arched over cover art, in mixed fonts, at low resolution. Classical OCR (I tried Tesseract's mental model first) needs deskewing per spine and still fails on stylised type. A VLM reads it and *also* structures it into `{title, author}` in a single call, which a plain OCR pass does not. |
| Match to the catalog | **Local**, no model | rapidfuzz | Deterministic, testable, 9 ms per book, free. Asking an LLM "which catalog entry is this?" would cost money per book, be non-reproducible run to run, and be impossible to unit-test — and this is the part of the task most worth being able to defend line by line. |

**The routing principle:** the hosted model is used for exactly one thing — turning pixels into text —
and it is called on the smallest possible image, as few times as possible. Everything upstream
(locating spines) and everything downstream (matching, scoring, confidence) is local, deterministic,
and free.

**What that buys, concretely.** Cropping first means each API call carries a ~2 cm strip of shelf
rather than a 1200×1600 photo, which is why a spine read costs only **283 prompt tokens, measured**.
The obvious alternative — send the whole shelf photo once and ask for every book at a time — would
use fewer tokens overall, but accuracy would drop — the model has to attend to 18
regions at once, and there's no per-spine confidence or crop to show the user in the review step.
The per-spine design costs more tokens and buys per-book traceability: every row in the review screen
has its own crop, its own read, and its own score.

---

## 7. Measured latency and cost

All numbers below were measured, not estimated. Anything I could not measure is marked as such.

**Test machine:** Intel Core i7-8750H (6 cores / 12 threads, 2.20 GHz), 16 GB RAM, Windows 11,
Python 3.13.1, **CPU-only inference, no GPU**. Home Wi-Fi.
**Test set:** the 23 photos in [`photos/`](photos/), shot at Toronto Public Library. 22 are
1200×1600; `23.jpeg` is a 227×306 thumbnail included on purpose as a degenerate case.

### 7.1 Local detection — 23 photos

| Metric | Value |
|--------|-------|
| Model load (once per process) | 1,255–2,000 ms |
| **First inference after load (cold)** | **13,596 ms** — one-off graph warm-up |
| Detection, median | **159 ms / image** |
| Detection, mean | 170 ms / image |
| Detection, min / max | 102 ms / 368 ms |
| Boxes found | 432 across 23 photos |
| Boxes per photo: median / min / max | 16 / 3 / 45 |
| Cost | **$0.00** |

> The 13.6 s cold first inference is real and I'd rather flag it than hide it: **the very first scan
> after starting the server is about 13 seconds slower than every scan after it.** Fixing it is a
> warm-up call at Django startup — on the [next-day list](#13-known-issues-and-what-id-do-with-another-day).

### 7.2 Hosted VLM read — 26 spines across 2 photos

Measured live against the model pinned in `vlm.py` (`VLM_MODEL = "gpt-5.6-sol"`), calls issued
sequentially, one per spine.

| Metric | Value |
|--------|-------|
| Per-spine latency, p50 | **2,045 ms** |
| Per-spine latency, p90 | 4,767 ms |
| Per-spine latency, min / max | 1,410 ms / 5,625 ms |
| Prompt tokens per spine (mean / median) | **283 / 272** |
| Completion tokens per spine (mean / median) | **59 / 52** |
| Failed reads | 2 of 26 (**7.7 %**) — empty response body, handled |

**Per image**, using the measured median of 16 spines per photo:

| Metric | Per image (16 spines) |
|--------|----------------------|
| VLM wall-clock | **≈ 41 s** (16 × 2.6 s mean, sequential) |
| Prompt tokens | **≈ 4,530** |
| Completion tokens | **≈ 950** |
| Total tokens | **≈ 5,480** |

**On dollar cost:** I'm reporting tokens rather than dollars deliberately. Tokens are what I
measured and they don't go stale; the dollar figure is `tokens × your provider's current rate`, and
that rate depends on which model tier is selected in `vlm.py` at run time — the file has three
candidates commented in, and I benchmarked against them during development. Multiply 4,530 input +
950 output tokens per image by your posted per-million rate to get your number. At any current
small-vision-model rate this lands in the fractions-of-a-cent-per-image range; at a frontier-tier
rate it is a few cents.

### 7.3 End-to-end, whole pipeline

Two real scans, every stage measured:

| Photo | Spines | Detect | VLM (sequential) | Match | **Total** |
|-------|--------|--------|------------------|-------|-----------|
| `photos/9.jpg` | 8 | 3,096 ms¹ | 20,929 ms | ~73 ms² | **≈ 24.1 s** |
| `photos/12.jpg` | 18 | 167 ms | 46,492 ms | ~164 ms² | **≈ 46.8 s** |

¹ first call in the process, so it carries part of the warm-up cost described above.
² detect and VLM are measured wall-clock; the match column is derived from the measured
9.1 ms per book × the number of spines, since matching is too fast to time reliably per scan.

Catalog load costs 3.3 ms and happens once at import. `match_book()` costs 9.1 ms per book against
all 320 entries.

**Read that table as one sentence: 99 % of the wall clock is the hosted model, and it is 99 % of it
because the calls are sequential.** The single highest-value optimisation in this repo is running the
per-spine VLM calls concurrently — a thread pool of 8 would cut a 47-second scan to roughly 6
seconds for no accuracy change and no extra cost. It's the first thing on the
[next-day list](#13-known-issues-and-what-id-do-with-another-day), and it's not done because
correctness of the matcher was worth more of the eight hours than latency.

### 7.4 Match quality on the benchmark set

Of the 26 spines in the benchmark, after the fix in [9.4](#94-a-bug-the-measurement-found):

| Outcome | Count | Notes |
|---------|-------|-------|
| `high` — pre-selected for the user | 23 | |
| `unmatched` — surfaced for the user to fix | 1 | "Overkill" — genuinely not in my catalog. A **correct** refusal, not a miss. |
| unreadable — VLM returned nothing | 2 | surfaced as "Unreadable spine" rows, not dropped |

Note that the 23 `high` matches include several **duplicates of the same physical book**, caused by
overlapping YOLO boxes — see [known issues](#13-known-issues-and-what-id-do-with-another-day). Match
precision is good; box de-duplication is the weak link.

---

## 8. The catalog: how I built it, and what I broke on purpose

`catalog.csv` — **320 entries**, well past the 100 minimum.

### 8.1 Where the data came from

**I built it from my own photographs, not from a public dataset or a model's memory.** I went to my
local Toronto Public Library branch and photographed shelves — the 23 images in [`photos/`](photos/)
are those photos, and they are the same images the pipeline is benchmarked on. I then transcribed
the titles and authors off those spines to form the catalog.

That decision is the single most useful thing I did for this task, for one reason: **the catalog and
the test images come from the same real-world distribution.** It is mid-list contemporary fiction —
Grisham, Lee Child, M. C. Beaton, Louise Penny, Val McDermid, Simon Beaufort — which is exactly what
a public library shelf and a normal person's shelf actually hold. A catalog assembled from a
"best books of all time" list would look impressive and match nothing.

The derived columns (`alt_titles`, `author_variants`, `edition`, `series`/`volume`, the omnibus
links) were filled in with LLM assistance on top of that transcribed base and then reviewed by hand —
see [AI_USAGE.md](AI_USAGE.md).

**Weighting toward books people actually own** was the explicit instruction in the brief, and the TPL
approach satisfies it by construction rather than by my guessing what's popular. The trade-off, and I
own it: the catalog is skewed toward **mystery and thriller**, because that's the aisle I
photographed. A shelf of technical books or literary classics will match less well. Classics
(`Crime and Punishment`, `The Scarlet Letter`, `The Awakening`, `Dune`, `The Stand`,
`One Hundred Years of Solitude`) were added on top specifically to cover the ambiguity cases below
and to widen the hit rate on someone else's shelf.

### 8.2 The columns

| Column | Meaning | Used by the matcher? |
|--------|---------|----------------------|
| `id` | stable key, `bk_001`… | yes — returned as `catalog_id` |
| `title` | canonical title | **yes** — primary signal |
| `alt_titles` | `;`-separated alternates: UK/US titles, subtitled forms, original-language titles | **yes** — scored equally with `title`, best wins |
| `author` | canonical author | **yes** |
| `author_variants` | `;`-separated: `Lastname, Firstname`, initials, unaccented forms | **yes** — scored equally with `author`, best wins |
| `series`, `volume` | series name and position | not yet — reserved for disambiguation, see next-day list |
| `year`, `edition` | e.g. `1965`, `Chilton First Edition` | not yet — shown to a human would help, see next-day list |
| `is_omnibus` | `TRUE`/`FALSE` | loaded and tested, not yet used in scoring |
| `contains_ids` | for an omnibus, the `id`s of the volumes it collects | loaded and tested, not yet used in scoring |

Being straight about it: `series`, `volume`, `year`, `edition`, `is_omnibus` and `contains_ids` are
parsed by [`catalog.py`](backend/scans/pipeline/catalog.py) and covered by tests, but the scoring
function only consumes titles and authors today. They're the columns a better matcher would use, and
I'd rather ship the data and say the scorer doesn't use it yet than pretend otherwise.

### 8.3 The ambiguity I put in deliberately

Every case the brief asked for is present, and each one is there to break a naive string comparison:

| Required trap | In the catalog as | Why it breaks exact matching |
|---|---|---|
| **Two editions of the same book** | `bk_305` / `bk_306` Dune (Chilton 1965 / Ace 2019); `bk_088` / `bk_089` The Scarlet Letter; `bk_318` / `bk_319` Crime and Punishment; `bk_014` / `bk_015` The Guardians; `bk_186` / `bk_187` The Awakening | Title *and* author are identical. No string comparison can pick a winner — the only correct behaviour is to ask the human, which is what the margin rule does. |
| **Same book, two different titles** | `bk_171` / `bk_172` *The Elegance of the Hedgehog* / *L'elegance du herisson*; `bk_094` *Your Neighbour's Wife* / *Your Neighbor's Wife* (UK/US spelling); `bk_009` *Diary of a Country Prosecutor* / *The Maze of Justice*; `bk_007` *Older Brother* / *Grand frere* | The spine may show either form. Only an `alt_titles` lookup finds it. |
| **Different books sharing a title** | `bk_313` *The Stand* (Stephen King) vs `bk_314` *The Stand* (Nicholas Sparks); `bk_047` / `bk_048` *Paradise* (Gurnah / Morrison); `bk_085` / `bk_086` *Anthem* (Hawley / Rand); `bk_080` / `bk_081` *The Return* (Harrison / Sparks); `bk_125` / `bk_126` *Shiver* (Reynolds / Stiefvater); `bk_245` / `bk_246` *Still Life* (McDermid / Penny) | Title alone is worthless here. The author has to carry weight — and when the VLM can't read an author, the honest answer is "I don't know", which is why that case is forced to review. |
| **Omnibus alongside its volumes** | `bk_310` *The Lord of the Rings* → `bk_307;bk_308;bk_309`; `bk_028` *The Gray Man Collection: Books 1-3* → `bk_025;bk_026;bk_027`; `bk_184` *Jack Reacher: Books 25-27*; `bk_207` *Agatha Raisin: The First Three Novels*; `bk_297` *The Long Earth Collection* | A collected edition's spine text overlaps heavily with its volumes'. `contains_ids` records the relationship. |
| **Titles that are substrings of others** | `bk_010` *The Shores of Tripoli* vs its subtitled form; `bk_192` *Robert Ludlum's The Bourne Evolution* vs *The Bourne Evolution*; `bk_254` *Food* vs *Food: What the Heck Should I Cook?*; `bk_018` *The Exchange* vs *The Exchange: After The Firm* | This is the trap that rules out `partial_ratio` scoring — see [9.2](#92-why-token_set_ratio-and-not-something-simpler). |
| **Author name in multiple forms** | `Lastname, Firstname` on 319 of 320 entries; `Gabriel García Márquez` / `Gabriel Garcia Marquez`; `M. C. Beaton`; `Lee Child and Andrew Child`; `Terry Pratchett and Stephen Baxter` | Spines print authors as `LEE CHILD`, catalogs store `Child, Lee`. Both must score the same. |

### 8.4 About `catalog1.csv`

`catalog1.csv` (126 entries) is my **first draft**: a purely LLM-generated catalog of well-known
titles, produced before I had my own photos. It is **not loaded by the application** —
[`catalog.py`](backend/scans/pipeline/catalog.py) resolves `catalog.csv` only. I've left it in the
repo because the diff between the two files is an honest record of the biggest single improvement
in this project: replacing a plausible-looking synthetic catalog with one built from the same shelves
I test against. Delete it if it's noise to you.

---

## 9. Matching and confidence (the core of the task)

All of this lives in [`backend/scans/pipeline/matcher.py`](backend/scans/pipeline/matcher.py) — about
100 lines, no model, no network, fully deterministic.

### 9.1 The scoring function

For a VLM read of `(title, author)`, every one of the 320 catalog entries is scored:

```
title_score  = max( token_set_ratio(read_title,  entry.title),
                    token_set_ratio(read_title,  each alt_title) )      / 100

author_score = max( token_set_ratio(read_author, entry.author),
                    token_set_ratio(read_author, each author_variant) ) / 100
                (0.0 if the VLM read no author at all)

score = 0.65 × title_score  +  0.35 × author_score
```

Then the list is sorted and two numbers come out of it:

* **`score`** — how good the best candidate is.
* **`margin`** — `best_score − second_best_score`. **This is the number that makes the confidence
  meaningful**, and it's the part I'd point to if you asked me what's non-obvious here. A high score
  on its own is not confidence. Two copies of *Dune* both score 1.00; the top score says "this is
  certainly Dune", and only the margin (0.00) says "and I cannot tell you which edition". Score
  measures *quality*; margin measures *uniqueness*. You need both.

**Why 0.65 / 0.35?** The title is the more reliable signal — it's larger on the spine, it's what the
VLM reads most accurately, and it's the field the catalog indexes on. But the author has to carry
enough weight to break a shared-title tie, and 0.35 does that: for *The Stand*, both entries score
1.00 on title, so the entire decision falls to the author term. The weights also produce a useful
side effect — **a read with a title but no author caps out at 0.65, below the 0.85 `high` threshold,
so it can never be silently auto-accepted.** A book we can't fully identify always reaches a human.
That falls out of the arithmetic rather than needing a special case, which is why I like it.

### 9.2 Why `token_set_ratio` and not something simpler

| Approach | Why not |
|---|---|
| Exact string equality | Dies on the first `THE SECOND RIDER` vs `The Second Rider`, and on every OCR slip. |
| `ratio` (plain Levenshtein) | Word-order sensitive. `Beaton, M. C.` vs `M. C. Beaton` scores badly despite being the same person. |
| `partial_ratio` | **Actively dangerous with this catalog.** It scores a short string against its best-matching substring of the long one, so *It* matches perfectly inside *Atomic Habits*, and *Food* inside *Food: What the Heck Should I Cook?*. My catalog is built full of substring traps precisely to make this fail. There's a test for it: `test_substring_trap_does_not_false_match`. |
| **`token_set_ratio`** ✔ | Compares sets of words, so word order doesn't matter (`Beaton, M. C.` ≡ `M. C. Beaton`) and extra words are tolerated (subtitles), while a genuinely short title still can't hide inside a long unrelated one. |

Every call passes `processor=default_process`, which lowercases and strips punctuation before
comparing. See [9.4](#94-a-bug-the-measurement-found) for why that line exists.

### 9.3 From score to a decision the UI can act on

```
if the read had no author AND the runner-up is within 0.05 of the leader → review
elif score ≥ 0.85 AND margin ≥ 0.10                                       → high
elif score ≥ 0.60                                                          → review
else                                                                       → unmatched
```

| Status | What it means | What the app does |
|--------|---------------|-------------------|
| `high` | Confident and unambiguous | Row is **pre-selected**. User can still untick it. |
| `review` | Something is there, but I'm not sure enough to decide for you | Row shown **unselected**, amber status line, listing up to 3 alternates |
| `unmatched` | Nothing in the catalog is close, or the spine was unreadable | Row shown **unselected**, red status line, with the raw VLM text so the user can still add it manually |

Two details worth calling out:

* **The first rule exists to stop coin-flips.** If the VLM read a title but no author, and two
  catalog entries are within 0.05 of each other, then picking the higher one is arbitrary. That case
  is forced to `review` even at score 0.95. Test: the `(0.95, 0.20, True, "review")` case in
  `test_classify_boundaries`.
* **`unmatched` returns `catalog_id: None`, `title: None`, `author: None`** — a weak top candidate's
  identity is never leaked into a row the UI might display as a suggestion. There's a regression test
  for exactly that: `test_unmatched_never_leaks_a_real_catalog_id`.

**Worked examples.** Every row below is real output from `match_book()` against the shipped
`catalog.csv`, not an illustration:

| VLM read | Top match | score | margin | Status | Why |
|---|---|---|---|---|---|
| `Snap` / `Belinda Bauer` | Snap — Belinda Bauer | 1.00 | 0.59 | **high** | Unambiguous. Pre-selected for the user. |
| `The Stand` / `Stephen King` | The Stand — Stephen King | 1.00 | 0.25 | **high** | Two books share this title; the author term breaks it cleanly. |
| `The Stand` / *(no author)* | The Stand — Stephen King | 0.65 | 0.00 | **review** | Same title, two different books, nothing to separate them. Both offered as options. Never guessed. |
| `Dune` / `Frank Herbert` | Dune (Chilton 1965) | 1.00 | 0.00 | **review** | Both editions tie exactly. Perfect score, zero margin — the user picks the edition. |
| `Harry Potter and the Philosopher's Stone` / `J.K. Rowling` | Sorcerer's Stone (US) | 1.00 | 0.00 | **review** | The UK title matches the US entry via `alt_titles` **and** matches the UK entry directly, so both hit 1.00. Correct outcome: the same book under two titles is a decision for the human, not for the scorer. |
| `SNAP` / *(no author)* | Snap — Belinda Bauer | 0.65 | 0.36 | **review** | Case-folded, so the title matches perfectly; no author read, so it correctly stays below `high`. |
| `Overkill` / `Vanda Symon` | — | 0.47 | — | **unmatched** | Genuinely not in my catalog. Correctly refuses to invent a match. |

### 9.4 A bug the measurement found

Worth documenting because it's the clearest example in this repo of measurement paying for itself.

Running the full pipeline on real photos, the spine printed **`SNAP`** came back `unmatched` at score
0.26 — while a different copy of the same book, read as `Snap`, matched at 1.00. The cause:
`rapidfuzz`'s `token_set_ratio` is **case-sensitive by default**. Measured directly:

```
token_set_ratio("SNAP", "Snap")            → 25.0
token_set_ratio("DUNE", "Dune")            → 25.0
token_set_ratio("THE STAND", "The Stand")  → 33.3
```

Look back at the [detection image](#4-what-the-spine-detector-actually-sees): `SNAP`, `OVERKILL`,
`THE SECOND RIDER`, `DEATH OF A TRAITOR` — all caps. This wasn't an edge case, it was most of a
shelf silently failing to match.

**The fix** is `processor=default_process` on both `token_set_ratio` calls in `matcher.py`, which
normalises case and punctuation before comparison. On the 26-spine benchmark it moved one book from
`unmatched` to `high` and would move far more on an all-caps shelf. Three regression tests cover it:
`test_all_caps_title_still_matches`, `test_all_caps_author_still_matches`,
`test_punctuation_differences_do_not_break_match`.

The lesson I'd repeat: **the unit tests all passed before this fix**, because I'd written them with
title-case fixtures — the way titles appear in a catalog, not the way they appear on a spine. Only
running the real pipeline over real photographs surfaced it.

---

## 10. Human in the loop

The brief is explicit that low-confidence results must not be silently accepted *or* silently
dropped. Here is every path a detected spine can take, and none of them ends in the void:

| Case | Where it surfaces | Can the user act on it? |
|---|---|---|
| Confident match | Row, green, **pre-ticked** | Yes — untick to reject |
| Low-confidence match | Row **unticked**, status line in amber (`review · 0.65`), plus an `also matched: …` line naming the alternates | Yes — tick to accept |
| No catalog match, but text was read | Row **unticked**, status line in red (`unmatched`), displaying the raw VLM title/author | Yes — tick to save it as a free-text book with `catalog_id = ""` |
| VLM couldn't read the spine | Row reading **"Unreadable spine"** | Yes — still tickable |
| Zero books detected in the photo | Explicit message: *"No books found. Try a straighter, closer photo."* | Retake the photo |
| Network / server failure | Error text in red at the top of the screen | Retry |

Design decisions in that table:

* **The review step is the same screen as the results.** I deliberately did not build a separate
  "review queue" the user has to remember to visit. Everything the model found is on one screen with
  its confidence visible, and the only difference between a high-confidence row and a low-confidence
  one is whether it starts ticked. A separate screen makes uncertain results easy to abandon; one
  screen makes them impossible to miss.
* **Nothing is written to the library without an explicit tap.** The confirm button says
  `Add N to library` with the live count, and is disabled at N = 0. There is no auto-save path in the
  code at all.
* **The score is shown on every row**, to two decimals, next to the status. If the model is wrong,
  the interface is honest about how sure it was.
* **Unmatched books are still savable.** Confirming a book the catalog has never heard of is a normal
  action, not an error — `catalog_id` is simply blank.
* **The stage timings are visible in the app.** The raw `timings_ms` are printed at the bottom of the
  result. That's more debug-flavoured than the rest of the UI, and in a real product it'd go — but
  for a task that asks about latency, it belongs on screen.

---

## 11. Graceful failure

Every one of these was considered and has an explicit code path. None of them crashes the app or
leaves a blank screen.

| Failure | Where it's handled | Behaviour |
|---|---|---|
| **No image in the POST** | `views.py` `ScanView.post` | `400` with `{"detail": "No image supplied."}` |
| **Zero books detected** | `run.py` | Returns early with a structured error. **No API calls made, nothing billed.** App shows "No books found. Try a straighter, closer photo." |
| **Unreadable image file** | `detector.py` | `cv2.imread` returning `None` raises `ValueError`, caught by the blanket handler in `ScanView` |
| **Malformed JSON from the model** | `vlm.py` `read_spine` | `json.JSONDecodeError` caught → that spine becomes `{title: None, author: None}` + a structured error. **Observed 2 of 26 times (7.7 %) in the benchmark — this is a live path, not a theoretical one.** |
| **Model timeout** | `vlm.py` | 15-second `timeout` on the call; `APITimeoutError` caught per spine. One slow spine doesn't sink the scan. |
| **Rate limiting** | `vlm.py` | Up to 3 retries with exponential backoff (1.0 s, 1.5 s, 2.25 s), then a structured error for that spine only |
| **Any other API exception** | `vlm.py` | Blanket `except Exception` → logged with traceback, spine degrades to unreadable |
| **VLM read a title but nothing matches** | `matcher.py` | `unmatched` status with **null identity fields**, surfaced to the user with the raw text |
| **Anything unexpected in the pipeline** | `views.py` | Whole `run_pipeline` call is wrapped; returns **HTTP 200** with `detections: []` and the error in `errors[]` |
| **Backend unreachable / non-2xx** | `mobile/api.js` + `App.js` | Each helper throws on `!res.ok`; `App.js` catches into an error banner and always clears the spinner in `finally` |
| **Camera permission denied** | `App.js` | Explicit message: *"Camera permission denied. Pick from library instead."* |

The load-bearing decision: **`read_spine()` never raises.** Its contract is to always return a
`(read, error)` tuple. A 30-spine shelf where 3 spines fail returns 27 books and 3 error entries — a
partial result is far more useful than an exception.

The one deliberate rough edge: `ScanView` returns **HTTP 200 even on total pipeline failure**, with
the reason in `errors[]`. That's unconventional — a purist would return 5xx. I chose it so the app has
exactly one response shape to render and the user always sees a specific reason rather than a generic
failure. I'd revisit it if this API had other consumers.

---

## 12. Tests

```bash
cd backend
pytest -q                          # 22 tests
pytest scans/tests/test_matcher.py -v   # named, one line each
```

Runtime is about 0.13 s — no network, no database, no model. The tests import
[`matcher.py`](backend/scans/pipeline/matcher.py) directly, which is possible only because the
pipeline modules are plain functions over plain dicts.

> **Use `pytest`, not `python manage.py test`.** The Django test runner reports "Ran 0 tests" here —
> `scans/tests.py` (an empty `startapp` stub) and the `scans/tests/` package collide, so Django's
> discovery finds nothing. Deleting the stub is on the next-day list.

The suite is aimed squarely at the matcher, because that's the part the brief says it will look at,
and it's the only part whose behaviour is deterministic enough to assert on. The fixture catalog is a
deliberately nasty 11-entry miniature of `catalog.csv` — every trap from
[section 8.3](#83-the-ambiguity-i-put-in-deliberately) in a form you can read in one screen.

| Group | Tests | What it proves |
|---|---|---|
| Substring traps | `test_substring_trap_does_not_false_match`, `test_short_title_does_not_match_longer_unrelated_title` | *It* doesn't match inside *Atomic Habits* — the test that rules out `partial_ratio` |
| Editions | `test_ambiguous_editions_score_high_but_low_margin_forces_review` | Two *Dune*s score 1.00 → margin forces `review`, and alternates are offered |
| UK/US titles | `test_uk_title_matches_via_alt_titles` | *Philosopher's Stone* resolves to the *Sorcerer's Stone* entry via `alt_titles` |
| Shared titles | `test_shared_title_resolved_by_author`, `test_shared_title_no_author_stays_review_not_arbitrary_pick` | Author breaks the tie; **absence of an author never produces a guess** |
| Omnibus | `test_omnibus_and_individual_volume_stay_distinct`, `test_omnibus_entry_tracks_its_contained_volumes` | Collected edition and volume 1 don't collapse into each other |
| Author variants | `test_author_unaccented_variant_matches_accented_catalog_entry`, `test_author_variant_list_is_actually_used` | `Gabriel Garcia Marquez` ≡ `Gabriel García Márquez`; variants are genuinely consulted |
| **Case / punctuation** | `test_all_caps_title_still_matches`, `test_all_caps_author_still_matches`, `test_punctuation_differences_do_not_break_match` | Regressions for the [live bug in 9.4](#94-a-bug-the-measurement-found) |
| Unmatched | `test_completely_unrelated_title_is_unmatched`, `test_unmatched_never_leaks_a_real_catalog_id` | Nonsense stays unmatched, and never leaks a real `catalog_id` |
| Thresholds | `test_classify_boundaries` (5 parametrised cases) | Every branch of the score/margin/ambiguity classifier |
| Real catalog | `test_real_catalog_loads_and_has_required_columns`, `test_real_catalog_path_resolves_from_repo_root` | The shipped `catalog.csv` parses, has ≥ 100 entries, and resolves from a clean clone |

**Not tested, and I'd rather say so:** the detector, the VLM client, the DRF views, and the React
Native app have no automated tests. The first two need either network mocks or real API calls, and
with limited hours I put the time into the logic that decides what the user sees.

---

## 13. Known issues and what I'd do with another day

**Known issues — real, reproducible, and none of them hidden:**

1. **Duplicate detections of the same physical book.** YOLO emits overlapping boxes, so one spine can
   be cropped and read 2–3 times, and the same title appears repeatedly in the results. Visible in
   the [detection image](#4-what-the-spine-detector-actually-sees) and in the benchmark ("Sugar and
   Spite" ×3). It costs real API calls, too. *Fix:* class-agnostic NMS with a tighter IoU threshold
   on the boxes, plus a de-dup pass on `(catalog_id)` after matching. **This is the highest-value
   fix in the repo after concurrency.**
2. **The first scan after server start takes ~13 s longer** (model warm-up). *Fix:* one dummy
   inference in an `AppConfig.ready()` hook.
3. **The backend won't boot without `OPENAI_API_KEY`**, because the OpenAI client is built at import
   time. Awkward for anyone who just wants to run the tests. *Fix:* lazy `get_client()`, same shape
   as `get_model()` in the detector.
4. **The backend URL is hardcoded** in `mobile/api.js` and must be edited by hand. *Fix:* read it
   from an Expo env var / `app.config.js`.
5. **`python manage.py test` finds 0 tests** — `scans/tests.py` collides with the `scans/tests/`
   package. *Fix:* delete the stub file.
6. **YOLOv8n on COCO class 73 is not a spine detector.** It's a book detector being used for spines,
   and its confidences are low (0.26–0.78). It works well enough on straight-on, well-lit shelves and
   degrades on angled or dim ones.
7. **Catalog coverage is genre-skewed** toward mystery/thriller, for the reason in
   [8.1](#81-where-the-data-came-from). Books outside it will land in `unmatched` more often — which
   the UI handles correctly, but the hit rate on a very different shelf will be lower.
8. **No pinned versions** for `ultralytics`, `opencv-python`, `openai`, `rapidfuzz`, `pytest` in
   `requirements.txt`. The versions I ran are listed in [section 1](#1-what-you-need-before-you-start)
   and 7.1. A fresh `pip install` could pull a newer, differently-behaved release.

**With another day, in priority order:**

1. **Parallelise the VLM calls.** A `ThreadPoolExecutor(max_workers=8)` over the spines turns a
   47-second scan into roughly 6 seconds. Same cost, same accuracy. Highest impact per line of code
   in the whole project.
2. **De-duplicate boxes** (issue 1). Cuts cost *and* cleans up the result list.
3. **Use the catalog columns I already ship.** `year` and `edition` in the review UI would turn
   "which of these two identical *Dune* rows?" into an answerable question, and `series`/`volume`
   would let a run of Jack Reacher spines reinforce each other's matches — a shelf is context, and
   right now each spine is matched in isolation.
4. **Persist scans and their detections**, so review can be resumed rather than lost on app restart.
5. **A labelled ground-truth set.** I have 23 photos and no per-spine labels, so I can report
   latency, token counts and match-status distribution — but not precision/recall. Half a day of
   labelling would let every threshold in `matcher.py` be tuned against a number instead of judgement.
6. **Tests for the view layer** with a mocked pipeline, covering the 400 path and the
   partial-failure-with-200 path.

---

## 14. API reference

Base URL `http://<host>:8000/api/`.

### `GET /api/` — health check
Returns service status and the endpoint URLs. Useful for confirming the phone can reach the backend.

### `POST /api/scans/` — scan a photo
`multipart/form-data`, one field: `image`.

```jsonc
{
  "scan_id": 12,
  "detections": [
    {
      "box": [412, 233, 468, 951],           // x1, y1, x2, y2 in the original image
      "detection_confidence": 0.68,          // YOLO's confidence (local model)
      "raw_read": { "title": "Dune", "author": "Frank Herbert" },  // exactly what the VLM said
      "match": {
        "catalog_id": "bk_305",
        "title": "Dune",                     // the CANONICAL title, not the read
        "author": "Frank Herbert",
        "score": 1.0,                        // 0..1 combined title+author score
        "margin": 0.0,                       // score gap to the runner-up
        "status": "review"                   // "high" | "review" | "unmatched"
      },
      "alternates": [                        // up to 3, only if they scored >= 0.60
        { "catalog_id": "bk_306", "title": "Dune", "score": 1.0 }   // the other edition
      ]
    }
  ],
  "errors": [                                // per-stage, non-fatal; results still present
    { "stage": "vlm", "detail": "Malformed response for spine: .../spine_12.jpg" }
  ],
  "timings_ms": { "detect": 166.7, "vlm": 46492.3, "match": 164.0 }
}
```

`raw_read` and `match` are both returned on purpose: the app can show what the model *read* next to
what it was *matched to*, which is the information a human needs to judge a low-confidence row.

Returns `400` only when no image is supplied. Every other failure returns `200` with the detail in
`errors[]` — see [section 11](#11-graceful-failure).

### `POST /api/library/` — confirm books
```json
{ "scan_id": 12,
  "books": [ { "catalog_id": "bk_203", "title": "Snap", "author": "Belinda Bauer" } ] }
```
`catalog_id` may be `null`/`""` for a book with no catalog match. Returns `201` with the created rows.

### `GET /api/library/` — list the library
Returns all confirmed entries, newest first.

---

## 15. Repository map

```
shelfie/
├── catalog.csv                    ★ the catalog — 320 entries (section 8)
├── catalog1.csv                     first-draft LLM catalog, NOT loaded (section 8.4)
├── photos/                        ★ the 23 TPL shelf photos everything was tested on
├── docs/
│   └── spine_detection_example.jpg  YOLO output shown in section 4
├── AI_USAGE.md                    ★ how AI was used, stage by stage
├── README.md                        this file
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env-example                 copy to .env and add your key
│   ├── yolov8n.pt                   committed weights (6.5 MB) — no download needed
│   ├── config/
│   │   ├── settings.py              DEBUG, MEDIA_ROOT, 20 MB upload cap, SQLite
│   │   └── urls.py                  /api/ + /media/ in DEBUG
│   ├── spine_test_yolo.py           throwaway: visualise YOLO on one photo
│   ├── spine_test_opencv.py         throwaway: the classical edge-detection segmenter I tried first
│   └── scans/
│       ├── models.py                Scan, LibraryEntry
│       ├── views.py                 IndexView, ScanView, LibraryView
│       ├── serializers.py
│       ├── urls.py
│       ├── tests/test_matcher.py  ★ 22 tests (section 12)
│       └── pipeline/
│           ├── run.py             ★ the orchestrator — read this first
│           ├── detector.py          YOLOv8n spine detection + cropping (local)
│           ├── vlm.py               hosted VLM spine reading + all its failure paths
│           ├── matcher.py         ★ scoring, margin, confidence classification
│           ├── catalog.py           catalog.csv → list of dicts
│           └── timing.py            the per-stage timing context manager
│
└── mobile/
    ├── App.js                     ★ the entire UI: capture, results, review, library
    ├── api.js                     ★ the three fetch calls — EDIT `BASE` HERE
    └── app.json                     Expo config + photo permission strings
```

★ = the files worth reading first.

---

## A note on scope

Eight hours went roughly: 1 h on the catalog and photographing shelves, 2 h on the detect → read →
match pipeline, 1.5 h on matching and confidence, 1 h on the app, 1 h on failure handling, and the
rest on measuring and writing this up.

What I cut, and why:

* **No authentication, no deployment, no visual polish** — explicitly not graded.
* **No async task queue.** A 47-second synchronous request is bad practice, and Celery + Redis is the
  textbook answer. It's also an hour of infrastructure that adds no signal about matching, cost or
  failure handling. Concurrency inside the request (next-day item 1) gets most of the win for ten
  lines.
* **No fine-tuning of anything** — forbidden by the brief, and correctly so.
* **Depth over breadth on tests.** 22 tests, all on the matcher and catalog loader, because that's
  where the judgement is.

The thing I'd most want you to look at is [section 9](#9-matching-and-confidence-the-core-of-the-task) —
the margin rule, and the bug in 9.4 that only real photographs could have found.
