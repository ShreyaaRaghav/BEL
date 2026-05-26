import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert industrial checksheet parsing agent.
Your task is to analyze the text extracted from a checksheet document and extract all parameters/fields that need to be measured, inspected, or verified.

For each parameter/field, extract the following:
1. "title": The name/description of the parameter. Do not include prefix numbers (like "01", "02").
2. "type": One of:
   - "numeric": if it specifies numeric tolerances or limits.
   - "categorical": if it specifies condition states/words.
   - "exact": if it specifies exact values like "zero", "nil", or a single specific target value.
3. "unit": The unit of measurement or null.
4. "min": The minimum acceptable numeric value or null.
5. "max": The maximum acceptable numeric value or null.
6. "range_type": One of:
   - "range"
   - "min_only"
   - "max_only"
   - "exact"
   - "unknown"
7. "conditions": A list of acceptable state conditions or null.

You MUST return ONLY valid JSON in this exact format:

{
  "fields": [
    {
      "title": "Baseline Voltage Stability",
      "type": "numeric",
      "unit": "V",
      "min": 4.95,
      "max": 5.05,
      "range_type": "range",
      "conditions": null
    }
  ]
}

Do not include markdown.
Do not include explanations.
Return JSON only.
"""

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def query_ollama(text: str, api_url: str = "http://localhost:11434") -> list:
    url = f"{api_url.rstrip('/')}/api/chat"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"Here is the checksheet text to parse:\n\n{text}"
            }
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode("utf-8"))

            content_text = res_data["message"]["content"]

            try:
                parsed = json.loads(content_text)

                if isinstance(parsed, dict) and "fields" in parsed:
                    return parsed["fields"]

                return parsed

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON returned by Ollama:\n{content_text}")
                return []

    except urllib.error.URLError as e:
        logger.error(f"Ollama connection failed: {e}")
        return []

    except Exception as e:
        logger.error(f"Ollama parsing failed: {e}")
        return []


def parse_with_ai(text: str) -> list:
    logger.info(f"Attempting parsing with Ollama model: {OLLAMA_MODEL}")

    return query_ollama(text)