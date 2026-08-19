import base64
import json
import logging
import time
from openai import OpenAI, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)
client = OpenAI()  # reads OPENAI_API_KEY from env

# VLM_MODEL = "gpt-4o-mini"  # swap to "gpt-4o" if title/author accuracy is poor
# VLM_MODEL = "gpt-4o"
# VLM_MODEL = "gpt-5.6-luna" # (7 matches)
VLM_MODEL = "gpt-5.6-sol" # (13 matches)
PROMPT = (
    "This is a cropped photo of a single book spine. "
    "Read the title and author printed on it. "
    "Respond with ONLY raw JSON, no markdown, no explanation: "
    '{"title": "...", "author": "..."} '
    "If you cannot confidently read the title, use null for that field. "
    "Never guess or hallucinate a title you cannot actually see."
)


def read_spine(crop_path, timeout=15, max_retries=3):
    """
    Returns (raw_read: dict, error: dict or None)
    raw_read is always {"title": ..., "author": ...} — never raises.
    Retries on rate limits with exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            with open(crop_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            response = client.chat.completions.create(
                model=VLM_MODEL,
                # max_tokens=150, # use this for gpt-4o-mini, gpt-4o
                max_completion_tokens=150, # use this for gpt-5.6-luna/gpt-5.6-sol
                timeout=timeout,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }},
                    ],
                }],
            )

            text = response.choices[0].message.content.strip()
            parsed = json.loads(text)
            return {
                "title": parsed.get("title"),
                "author": parsed.get("author"),
            }, None

        except RateLimitError:
            wait = 1.5 ** attempt  # 1s, 1.5s, 2.25s
            logger.warning(
                f"Rate limited on {crop_path}, retry {attempt + 1}/{max_retries} in {wait:.1f}s"
            )
            time.sleep(wait)
            continue

        except json.JSONDecodeError as e:
            logger.warning(f"VLM returned malformed JSON for {crop_path}: {e}")
            return {"title": None, "author": None}, \
                   {"stage": "vlm", "detail": f"Malformed response for spine: {crop_path}"}

        except APITimeoutError:
            logger.warning(f"VLM timeout for {crop_path}")
            return {"title": None, "author": None}, \
                   {"stage": "vlm", "detail": f"Timed out reading spine: {crop_path}"}

        except Exception as e:
            logger.exception(f"VLM read failed for {crop_path}")
            return {"title": None, "author": None}, \
                   {"stage": "vlm", "detail": str(e)}

    # exhausted all retries on rate limits
    logger.error(f"Rate limited after {max_retries} retries: {crop_path}")
    return {"title": None, "author": None}, \
           {"stage": "vlm", "detail": f"Rate limited after {max_retries} retries: {crop_path}"}


def read_spines(spines):
    """
    spines: list of {"box": ..., "detection_confidence": ..., "crop_path": ...}
    Returns: (reads: list of dicts with raw_read attached, errors: list, timing_ms: int)
    """
    start = time.time()
    reads = []
    errors = []

    for spine in spines:
        raw_read, error = read_spine(spine["crop_path"])
        reads.append({**spine, "raw_read": raw_read})
        if error:
            errors.append(error)

    timing_ms = round((time.time() - start) * 1000)
    return reads, errors, timing_ms