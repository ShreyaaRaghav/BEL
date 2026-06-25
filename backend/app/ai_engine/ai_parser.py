import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert industrial checksheet parsing agent.
Analyze the text extracted from a checksheet document and extract every parameter that needs to be measured, inspected, or verified.

For each parameter return:
- "title"      : parameter name, no leading number prefix
- "type"       : "numeric" | "categorical" | "exact"
- "unit"       : unit string or null
- "min"        : minimum numeric value or null
- "max"        : maximum numeric value or null
- "range_type" : "range" | "min_only" | "max_only" | "exact" | "unknown"
- "conditions" : list of acceptable text conditions or null

Return ONLY valid JSON, no markdown, no explanation:
{"fields": [...]}"""

# Configurable via environment variables
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT  = int(os.environ.get("OLLAMA_TIMEOUT", "120"))


def _is_ollama_available() -> bool:
    """Quick HEAD/GET to /api/tags to confirm Ollama is reachable."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _pull_model_if_needed() -> None:
    """
    Check if the model is already available locally.
    If not, trigger a pull. Runs only when Ollama is reachable.
    """
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        available = [m.get("name", "") for m in data.get("models", [])]
        if not any(OLLAMA_MODEL in m for m in available):
            logger.warning(
                f"Model '{OLLAMA_MODEL}' not found locally. "
                f"Run: ollama pull {OLLAMA_MODEL}"
            )
    except Exception as e:
        logger.debug(f"Model check skipped: {e}")


def query_ollama(text: str) -> list:
    """Send text to Ollama /api/chat and return parsed fields list."""
    url = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Parse this checksheet:\n\n{text}"},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as response:
            res_data = json.loads(response.read().decode("utf-8"))

        content_text = res_data.get("message", {}).get("content", "")
        if not content_text:
            logger.error("Ollama returned empty content.")
            return []

        parsed = json.loads(content_text)
        if isinstance(parsed, dict) and "fields" in parsed:
            return parsed["fields"]
        if isinstance(parsed, list):
            return parsed

        logger.error(f"Unexpected Ollama response structure: {content_text[:200]}")
        return []

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Ollama HTTP {e.code}: {body[:300]}")
        return []
    except urllib.error.URLError as e:
        logger.warning(
            f"Ollama unreachable at {OLLAMA_BASE_URL} — falling back to rule-based parser. "
            f"({e.reason})"
        )
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Ollama returned invalid JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Ollama parsing failed: {e}")
        return []


def parse_with_ai(text: str) -> list:
    """
    Try Ollama first; return [] on any failure so the caller falls back
    to the rule-based parser.
    """
    if not _is_ollama_available():
        logger.info(
            f"Ollama not running at {OLLAMA_BASE_URL}. "
            "Using rule-based parser. "
            f"To enable AI parsing: ollama serve && ollama pull {OLLAMA_MODEL}"
        )
        return []

    logger.info(f"Sending checksheet to Ollama model '{OLLAMA_MODEL}'...")
    result = query_ollama(text)
    if result:
        logger.info(f"Ollama returned {len(result)} fields.")
    else:
        logger.warning("Ollama returned no fields — rule-based fallback will be used.")
    return result
