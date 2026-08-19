# AI_USAGE.md

An honest account of where AI was used in this project.

**Short version: everywhere.** I used AI at every stage of the development cycle — ideation, problem
understanding, coding, debugging, testing, and documentation — deliberately, to compress eight hours
of work into eight hours of *decisions*. I have not tried to make any part of this repo look
hand-crafted. What I claim is not that I typed every character, but that I understand, chose, and can
defend every line, including the ones I deleted.

## Tools

| Tool | Model | Used for |
|------|-------|----------|
| **Claude Code** | Opus | The main driver: scaffolding, refactors, catalog generation, test writing, debugging, and this documentation |
| **ChatGPT / Claude chat** | — | Ideation and problem framing before I wrote any code |
| **OpenAI vision-language API** | see `VLM_MODEL` in `backend/scans/pipeline/vlm.py` | Not a dev tool — this is a *runtime component* of the product, reading text off spine crops |

That last row is worth separating out. The VLM is not AI assistance in building the project; it is
the project. Everything else in this file is about tooling.

---

## Stage 1 — Ideation

**What I used AI for:** thinking out loud about approaches before committing to one. What a
"bookshelf → library" pipeline could look like, where the hard parts would be, which parts of the
brief were load-bearing and which were scenery.

**What came out of it:** the realisation that the interesting engineering is not detection or OCR —
both are solved-ish — but **matching a noisy read against a deliberately messy catalog, and being
honest about confidence.** That shaped where I spent my hours: the matcher is the most carefully
built and most heavily tested file in the repo, and the UI is deliberately plain.

**What I rejected:** an AI suggestion to build a separate review queue screen with its own state. I
kept review on the same screen as the results, because a separate screen is a place uncertain results
go to be forgotten. That reasoning is in README section 10.

---

## Stage 2 — Problem understanding

**What I used AI for:** interrogating the brief. I fed the task description in and worked through
what "realistically messy catalog" actually implies, and what each required trap (two editions, US/UK
titles, shared titles, omnibus editions, substring titles, author name forms) does to a naive
matcher.

**Why this mattered:** it turned six bullet points in a PDF into a concrete list of failure modes I
could then design *against*, and later write tests *for*. The mapping from each required trap to the
catalog entries that embody it and the test that covers it is in README sections 8.3 and 12 — that
table is essentially the output of this stage.

**Concrete example:** thinking through the substring case ("titles that are substrings of other
titles") is what ruled out `partial_ratio` as a scoring function before I wrote a line of the
matcher, and produced `test_substring_trap_does_not_false_match`.

---

## Stage 3 — Coding

AI wrote a large share of the first draft of nearly every file. What I did was choose the
architecture, reject the parts that were wrong, and keep the parts I could defend.

| Area | How AI was used | What I decided myself |
|------|-----------------|-----------------------|
| Django project scaffold | Generated `settings.py`, models, serializers, URL routing | The three-endpoint API shape; storing only *confirmed* books; `catalog_id` as a plain field rather than a foreign key |
| `pipeline/` package | Generated most of `detector.py`, `vlm.py`, `run.py`, `timing.py` | Splitting the pipeline into pure functions over plain dicts, with no Django imports — that's what makes the matcher unit-testable, and it was a structural choice, not an AI suggestion |
| `matcher.py` | Drafted the scoring loop and the rapidfuzz calls | The 0.65/0.35 weighting, the **margin** rule, the three-way `high`/`review`/`unmatched` classification, and the ambiguous-without-author override. These are the judgement calls the whole task turns on and they are mine |
| `catalog.py` | Generated the CSV parsing and the semicolon-splitting | The column schema |
| Expo app | Generated the components, the picker wiring, and the fetch layer | Pre-selecting only high-confidence rows; review living on the results screen; showing the score on every row |
| **`spine_test_opencv.py`** | Wrote a classical Canny-edge / column-projection spine segmenter | **I tried this first and abandoned it.** It's still in the repo as an honest record: it segments cleanly only on evenly-lit, straight-on shelves, and YOLOv8n was both more robust and less code. Keeping the dead end visible seemed better than pretending I went straight to the right answer |

**The prompt that mattered most** wasn't a coding prompt at all — it was the one inside the product.
The instruction in `vlm.py`, *"If you cannot confidently read the title, use null for that field.
Never guess or hallucinate a title you cannot actually see,"* is the difference between a `null` that
reaches a human and a confident hallucination that gets silently added to someone's library. Getting
that sentence right took several iterations of watching what the model returned on hard crops.

---

## Stage 4 — Debugging

This is where AI assistance paid off most, and also where it needed the most supervision.

**Model selection was empirical, not assumed.** `vlm.py` still carries the commented-out candidates
I benchmarked against — `gpt-4o-mini`, `gpt-4o`, and two newer tiers — with the match counts I
measured written next to them. Note the API difference recorded in the comments: the older models
take `max_tokens`, the newer ones require `max_completion_tokens`. That is not something I would have
guessed; it came out of a failing call and reading the error.

**The bug AI did not find, and the measurement did.** All 19 matcher tests passed, and the pipeline
still returned `unmatched` for a book that was plainly in the catalog. The cause was that
`rapidfuzz.fuzz.token_set_ratio` is **case-sensitive by default**, so a spine printed `SNAP` scored
25/100 against the catalog's `Snap`. The tests didn't catch it because I — and the AI that helped
write them — had used title-case fixtures, i.e. titles as they appear in a *catalog*, not as they
appear on a *spine*. Only running the real pipeline over my own photographs surfaced it.

The fix is one argument (`processor=default_process`) on two calls, plus three regression tests. The
full write-up is in README section 9.4. I'm calling it out here because it's the clearest illustration
of the limit of AI-assisted testing: **an AI will happily write you tests that share your blind
spot.** The measurement is what breaks out of it.

---

## Stage 5 — Testing

**What I used AI for:** generating the test suite in `backend/scans/tests/test_matcher.py`, including
the miniature 11-entry fixture catalog that reproduces every ambiguity class from the real one.

**What I directed:** the *list* of cases. I worked from the brief's six required traps and made sure
each one had a test that would fail if the matcher regressed — the substring trap, the two-editions
margin case, the UK/US `alt_titles` path, the shared-title-with-no-author case, the omnibus, the
accented-author variants, the threshold boundaries, and the "unmatched must not leak a real
`catalog_id`" regression.

**What I added after the fact:** the three case/punctuation tests, written *after* the live bug
above. That ordering is the point — the tests followed the measurement.

Coverage is deliberately narrow: 22 tests, all on the matcher and the catalog loader, nothing on the
views, the detector, or the app. The brief asks for tests on the matching logic, and that is where
the judgement lives.

---

## Stage 6 — Documentation

`README.md` and this file were written with Claude Code, from the actual repository contents and from
benchmark runs against the real code — not from a description of what the code was supposed to do.
Specifically:

* The **latency figures** in README section 7 come from running the detector over all 23 photos in
  `photos/` and the VLM over 26 real spine crops, capturing wall-clock timings and the token counts
  reported by the API.
* The **worked matching examples** in README section 9.3 are literal output from `match_book()`
  against the shipped `catalog.csv`.
* The **detection image** in README section 4 is real YOLOv8n output on `photos/12.jpg`, generated by
  a script, not a mock-up.
* The **known-issues list** was written from things that actually happen, including several I would
  rather not have had to write down.

Where a number could not be measured — the per-image *dollar* cost, which depends on a provider rate
rather than on my code — the README says so and reports measured token counts instead of a figure I'd
have to invent.

---

## The catalog

Worth its own section, because "generated with an LLM" would be the easy and slightly misleading
answer.

**`catalog1.csv` (126 entries) is the fully AI-generated first draft.** I asked for a list of
well-known books with the required ambiguity built in, and got a clean, plausible, useless catalog:
famous titles nobody's actual shelf is made of. It is still in the repo, and it is **not loaded by
the application**.

**`catalog.csv` (320 entries) is built from my own data.** I photographed shelves at my local Toronto
Public Library branch — those photos are the 23 images in `photos/`, and they are the same images the
pipeline is benchmarked against — and transcribed the titles and authors off the spines. AI helped
fill in the derived columns on top of that transcribed base: the `Lastname, Firstname` author
variants, the alternate and original-language titles, the edition and series metadata, and the
omnibus → volume links. I reviewed those columns and chose which ambiguity cases to plant where.

The reason this distinction matters: the catalog and the test images come from the same real-world
distribution. An LLM asked for "100 books people own" produces a list of books people have *heard
of*. A library shelf produces the mid-list mystery and thriller titles that shelves are actually full
of — which is also, honestly, the limitation of my catalog, and README section 8.1 says so.

---

## What I would tell you if you asked "did you write this?"

I directed it, I chose the architecture and every judgement call in the matcher, I threw away the
parts that were wrong (a classical CV segmenter, a synthetic catalog, a separate review screen), and
I found the one bug that mattered by measuring rather than by reading. AI made all of that faster. It
did not make any of the decisions, and it did not catch the mistake that measurement caught.

Ask me about any line in the repo.
