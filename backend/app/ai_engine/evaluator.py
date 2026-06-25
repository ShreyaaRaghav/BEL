import re

def normalize_text_value(value: str) -> str:
    """
    Normalizes string values for robust comparisons (lower case, stripping space, converting underscores/dashes to spaces).
    """
    return re.sub(r"[_-]+", " ", str(value or "").strip().lower())

def evaluate_pass_fail(field: dict, value) -> str:
    """
    Evaluates whether the input observation value satisfies the spec limits for the parsed field.
    Returns: 'PASS', 'FAIL', 'PENDING' (if empty/none), or 'INVALID' (if malformed).
    """
    if value is None or str(value).strip() == "":
        return "PENDING"
        
    # Check if the field is categorical or has condition rules
    is_categorical = (
        field.get("type") == "categorical"
        or field.get("range_type") == "visual"
        or (
            field.get("conditions")
            and len(field["conditions"]) > 0
            and field.get("range_type") in ("unknown", "visual")
        )
    )
    
    if is_categorical:
        conditions = field.get("conditions")
        if not conditions:
            return "PASS"
            
        norm_val = normalize_text_value(value)
        # All conditions must be found in the normalized input text
        for cond in conditions:
            norm_cond = normalize_text_value(cond)
            if norm_cond not in norm_val:
                return "FAIL"
        return "PASS"
        
    # Numeric evaluation
    try:
        num_val = float(str(value).replace(",", "").strip())
    except ValueError:
        # Check if the value matches categorical terms since it's not a float
        # This acts as a fallback for cases where numeric fields might receive word answers
        norm_val = normalize_text_value(value)
        if field.get("conditions"):
            for cond in field["conditions"]:
                if normalize_text_value(cond) in norm_val:
                    return "PASS"
        return "INVALID"
        
    range_type = field.get("range_type")
    min_val = field.get("min")
    max_val = field.get("max")
    
    if range_type == "min_only":
        if min_val is not None:
            return "PASS" if num_val >= min_val else "FAIL"
    elif range_type == "max_only":
        if max_val is not None:
            return "PASS" if num_val <= max_val else "FAIL"
    elif range_type == "exact":
        if min_val is not None:
            return "PASS" if abs(num_val - min_val) < 1e-9 else "FAIL"
    elif range_type == "range":
        if min_val is not None and max_val is not None:
            return "PASS" if min_val <= num_val <= max_val else "FAIL"
            
    # Fallback check if min/max are present regardless of range_type
    if min_val is not None and max_val is not None:
        return "PASS" if min_val <= num_val <= max_val else "FAIL"
    elif min_val is not None:
        return "PASS" if num_val >= min_val else "FAIL"
    elif max_val is not None:
        return "PASS" if num_val <= max_val else "FAIL"
        
    return "INVALID"
