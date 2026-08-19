# AI_USAGE.md

**Short version: I used AI at every stage** — ideation, problem understanding, coding, debugging,
testing, documentation — deliberately, to compress the work into the time available. I'm not
claiming I typed every character. I'm claiming I chose the architecture, made every judgement call
in the matcher, and can defend any line in the repo.

**Tools:** Claude Code (Opus) as the main driver; ChatGPT/Claude chat for early framing. The OpenAI
vision-language model in `backend/scans/pipeline/vlm.py` is not a dev tool — it's a runtime component
of the product.

| Stage | What AI did |
|---|---|
| **Ideation** | Explored possible approaches and where the hard parts would be, before I committed to one |
| **Problem understanding** | Worked through what each required catalog trap does to a naive matcher, which turned six bullets in the brief into a concrete list of failure modes to design and test against |
| **Coding** | Drafted most of the Django scaffold, the `pipeline/` modules, the Expo UI, and the first version of the matcher's scoring loop |
| **Debugging** | Helped read API errors and iterate on the VLM prompt, including the `max_tokens` → `max_completion_tokens` difference between model tiers |
| **Testing** | Generated the test suite and the 11-entry fixture catalog that reproduces every ambiguity class from the real one |
| **Documentation** | Wrote README.md and this file, from benchmark runs against the real code — every number in the README is measured, not described |

## The catalog

`catalog1.csv` (126 entries) is the **fully AI-generated first draft** — clean, plausible, useless:
famous titles nobody's actual shelf is made of. It's still in the repo and **not loaded by the app**.

`catalog.csv` (320 entries) is **built from my own data.** I photographed shelves at my local Toronto
Public Library branch — those are the 23 images in `photos/`, the same ones the pipeline is
benchmarked on — and transcribed titles and authors off the spines. AI filled in the derived columns
on top of that base (`Lastname, Firstname` variants, alternate/original-language titles, edition and
series metadata, omnibus → volume links); I reviewed them and chose where to plant each ambiguity
case. The point: catalog and test images come from the same real-world distribution.

