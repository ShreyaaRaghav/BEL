import re


MOJIBAKE_REPLACEMENTS = {
    "â€“": "-",
    "â€”": "-",
    "−": "-",
    "–": "-",
    "—": "-",
    "Â±": "±",
    "+/-": "±",
    "+ / -": "±",
    "â‰¤": "<=",
    "≤": "<=",
    "â‰¥": ">=",
    "≥": ">=",
    "Â°": "°",
}

UNIT_ALIASES = {
    "°c": "°C",
    "degc": "°C",
    "degree c": "°C",
    "degrees c": "°C",
    "vdc": "V",
    "vac": "V",
    "volt": "V",
    "volts": "V",
    "rpm": "RPM",
    "psi": "PSI",
    "db": "dB",
    "ma": "mA",
    "a": "A",
    "mv": "mV",
    "kv": "kV",
    "ohm": "ohm",
    "ohms": "ohm",
    "kohm": "kOhm",
    "mohm": "MOhm",
    "hz": "Hz",
    "khz": "kHz",
    "mhz": "MHz",
    "ghz": "GHz",
    "nm": "nm",
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "kg": "kg",
    "g": "g",
    "ms": "ms",
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "%": "%",
    "%t": "%T",
    "abs": "ABS",
    "kbps": "kbps",
    "mbps": "Mbps",
    "cca": "CCA",
}

UNIT_PATTERN = (
    r"(?<![A-Za-z])(?:°\s*C|deg\s*C|degrees?\s*C|%T|%|"
    r"kOhm|MOhm|ohms?|mV|kV|VDC|VAC|volts?|V|mA|A|CCA|"
    r"mm|cm|nm|kg|RPM|PSI|dB|ABS|kbps|Mbps|GHz|MHz|kHz|Hz|ms|secs?|seconds?|s|m|g)"
    r"(?![A-Za-z])"
)
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"


def normalize_text(text):
    text = text or ""
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_lines(text):
    skip_patterns = [
        r"^ref$",
        r"^parameter$",
        r"^value$",
        r"^range /$",
        r"^standard$",
        r"^(?:ref|reference)\s*parameter\b",
        r"^parameter value range\b",
        r"^standard pass / fail\b",
        r"^pass / fail\b",
        r"^form ref:",
        r"^document ref:",
        r"^page \d+ of \d+$",
        r"^technician signature",
        r"^quality assurance reviewer",
        r"^service advisor",
    ]

    lines = []
    for line in text.splitlines():
        cleaned = normalize_text(line)
        if not cleaned:
            continue
        if any(re.search(pattern, cleaned, flags=re.IGNORECASE) for pattern in skip_patterns):
            continue
        lines.append(cleaned)
    return lines


def split_embedded_rows(text):
    text = normalize_text(text)
    text = re.sub(
        r"(\]\s*(?:F|Fail)|\bFail\b)\s+(?=(?:0?[1-9]|[1-9]\d)[\).]?\s+[A-Z][A-Za-z/(&-])",
        r"\1\n",
        text,
        flags=re.IGNORECASE,
    )
    return text.splitlines()


def is_reference_start(line):
    line = normalize_text(line)
    if re.match(r"^\d{1,3}[\).]?$", line):
        return True

    match = re.match(r"^(\d{1,3})[\).]?\s+(.+)$", line)
    if not match:
        return False

    first_token = match.group(2).split()[0].strip(":,/()[]")
    return re.fullmatch(UNIT_PATTERN, first_token, flags=re.IGNORECASE) is None


def join_multiline_fields(lines):
    merged = []
    buffer = ""
    pending_ref = ""

    for line in lines:
        if re.match(r"^\d{1,3}[\).]?$", line):
            if buffer:
                merged.append(buffer.strip())
            pending_ref = line
            buffer = line
            continue

        if is_reference_start(line):
            if buffer:
                merged.append(buffer.strip())
            pending_ref = ""
            buffer = line
        elif buffer:
            buffer += " " + line
        elif pending_ref:
            buffer = f"{pending_ref} {line}"
            pending_ref = ""

    if buffer:
        merged.append(buffer.strip())

    return merged


def _to_float(value):
    return float(value.replace(",", ""))


def _canonical_unit(unit):
    if not unit:
        return None
    cleaned = re.sub(r"\s+", "", unit).replace("°c", "°C")
    return UNIT_ALIASES.get(cleaned.lower(), cleaned)


def _number_with_optional_unit():
    return rf"({NUMBER_PATTERN})\s*({UNIT_PATTERN})?"


def _extract_unit_near_match(match):
    groups = [g for g in match.groups() if isinstance(g, str)]
    for group in reversed(groups):
        canonical = _canonical_unit(group)
        if canonical and not re.fullmatch(NUMBER_PATTERN, group):
            return canonical
    return None


def extract_range(text):
    text = normalize_text(text)
    number_unit = _number_with_optional_unit()

    patterns = [
        (
            rf"\bbetween\s+{number_unit}\s+(?:and|to)\s+{number_unit}\b",
            "range",
        ),
        (
            rf"{number_unit}\s*(?:-|to|through|upto|up to)\s*{number_unit}",
            "range",
        ),
        (
            rf"{number_unit}\s*±\s*({NUMBER_PATTERN})\s*({UNIT_PATTERN})?",
            "plus_minus",
        ),
        (
            rf"(?:(?:<=|<|max(?:imum)?|not more than|up to|upto|below)|(?<!not )less than)\s*{number_unit}",
            "max_only",
        ),
        (
            rf"(?:(?:>=|>|min(?:imum)?|not less than|above|at least)|(?<!not )more than)\s*{number_unit}",
            "min_only",
        ),
        (
            rf"(?:equal to|equals?|exact(?:ly)?|target|nominal)\s*{number_unit}",
            "exact",
        ),
        (
            rf"{number_unit}\s*(?:max(?:imum)?|or less)",
            "max_only",
        ),
        (
            rf"{number_unit}\s*(?:min(?:imum)?|or more)",
            "min_only",
        ),
    ]

    for pattern, range_type in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        if range_type == "range":
            left = _to_float(match.group(1))
            right = _to_float(match.group(3))
            unit = _canonical_unit(match.group(2)) or _canonical_unit(match.group(4))
            return min(left, right), max(left, right), "range", unit

        if range_type == "plus_minus":
            center = _to_float(match.group(1))
            delta = _to_float(match.group(3))
            unit = _canonical_unit(match.group(2)) or _canonical_unit(match.group(4))
            return center - delta, center + delta, "range", unit

        value = _to_float(match.group(1))
        unit = _extract_unit_near_match(match)
        if range_type == "min_only":
            return value, None, "min_only", unit
        if range_type == "max_only":
            return None, value, "max_only", unit
        if range_type == "exact":
            return value, value, "exact", unit

    if re.search(r"\b(?:zero|nil)\b", text, flags=re.IGNORECASE):
        return 0.0, 0.0, "exact", None

    return None, None, "unknown", None


def extract_unit(text):
    text = normalize_text(text)
    match = re.search(UNIT_PATTERN, text, flags=re.IGNORECASE)
    return _canonical_unit(match.group(0)) if match else None


def detect_type(text, range_type=None):
    t = normalize_text(text).lower()

    if range_type and range_type != "unknown":
        return "numeric"

    if re.search(NUMBER_PATTERN, t) and extract_unit(t):
        return "numeric"

    if any(x in t for x in ["clean", "intact", "firm", "sealed", "dry", "streak", "crack", "leak"]):
        return "categorical"

    if any(x in t for x in ["zero", "no ", "none", "nil"]):
        return "exact"

    return "unknown"


def extract_condition(text):
    t = normalize_text(text).lower()
    condition_patterns = {
        "no_cracks": r"\bno\s+cracks?\b|\bcrack[- ]?free\b",
        "no_leaks": r"\bno\s+leaks?\b|\bleak[- ]?free\b",
        "clean": r"\bclean\b",
        "intact": r"\bintact\b",
        "dry": r"\bdry\b",
        "sealed": r"\bsealed\b",
        "firm": r"\bfirm\b",
        "zero": r"\bzero\b(?!-)|\bnil\b",
        "none": r"\bnone\b",
        "streak_free": r"\bstreak[- ]?free\b",
    }

    conditions = [
        name for name, pattern in condition_patterns.items()
        if re.search(pattern, t, flags=re.IGNORECASE)
    ]
    return conditions or None


def extract_title(text):
    text = normalize_text(text)
    text = re.sub(r"^\d{1,3}[\).]?\s*", "", text)
    if re.search(r"_{2,}", text):
        text = re.split(r"_{2,}", text, maxsplit=1)[0]
    text = re.sub(r"[_\.]{2,}", " ", text)

    spec_patterns = [
        rf"\bbetween\s+{_number_with_optional_unit()}\s+(?:and|to)\s+{_number_with_optional_unit()}.*$",
        rf"{_number_with_optional_unit()}\s*(?:-|to|through|upto|up to)\s*{_number_with_optional_unit()}.*$",
        rf"{_number_with_optional_unit()}\s*±\s*{NUMBER_PATTERN}\s*{UNIT_PATTERN}?.*$",
        rf"(?:<=|<|>=|>|max(?:imum)?|min(?:imum)?|not more than|not less than|less than|more than|up to|upto|below|above|at least|equal to|equals?|exact(?:ly)?|target|nominal)\s*{_number_with_optional_unit()}.*$",
        rf"{_number_with_optional_unit()}\s*(?:max(?:imum)?\b|min(?:imum)?\b|or less\b|or more\b).*$",
    ]

    for pattern in spec_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"\[[^\]]*\]\s*(?:P|F|Pass|Fail)?", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:P|F|Pass|Fail)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(rf"(?:\s+{UNIT_PATTERN})?\s*(?:<=|>=|<|>)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(rf"\s+{UNIT_PATTERN}$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :-")


def parse_text(raw_text: str):
    """Parse checksheet-like raw text (string) and return extracted fields.
    This shares the same logic as the PDF fallback parser but operates on a text blob.
    """
    from app.ai_engine.ai_parser import parse_with_ai

    if not raw_text:
        return []

    # Try parsing using LLM/AI first
    ai_fields = parse_with_ai(raw_text)
    if ai_fields and isinstance(ai_fields, list) and len(ai_fields) > 0:
        return ai_fields

    # Fallback to rule-based logic
    lines = clean_lines("\n".join(split_embedded_rows(raw_text)))
    merged_lines = join_multiline_fields(lines)

    fields = []

    for line in merged_lines:
        if not is_reference_start(line):
            continue

        min_val, max_val, range_type, range_unit = extract_range(line)
        unit = range_unit or extract_unit(line)
        field_type = detect_type(line, range_type)

        fields.append({
            "title": extract_title(line),
            "type": field_type,
            "unit": unit,
            "min": min_val,
            "max": max_val,
            "range_type": range_type,
            "conditions": extract_condition(line),
        })

    return fields


def parse_pdf(file_path):
    from app.services.pdf_service import extract_text_from_pdf

    raw_text = extract_text_from_pdf(file_path)
    if not raw_text:
        return []

    # Delegate to text parser (AI-first, fallback to rule-based)
    return parse_text(raw_text)
