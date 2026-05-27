from fastapi import APIRouter, UploadFile, File, Depends
import os
import re
import math
from app.ai_engine.pdf_parser import parse_pdf
from app.core.rbac import require_role
from app.models.user import User

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _normalize(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _align_fields_from_template(template_items, parsed_fields=None):
    """Map DB check items to API field shape; merge parsed values when titles match."""
    parsed_fields = parsed_fields or []
    parsed_by_title = {_normalize(f.get("title")): f for f in parsed_fields if f.get("title")}

    aligned = []
    for item in template_items:
        matched = parsed_by_title.get(_normalize(item.parameter_name))
        aligned.append({
            "check_item_id": item.id,
            "title": item.parameter_name,
            "type": (
                matched.get("type")
                if matched
                else ("categorical" if item.range_type == "visual" else "numeric")
            ),
            "unit": item.unit,
            "min": item.range_min,
            "max": item.range_max,
            "range_type": "range" if item.range_type == "between" else item.range_type,
            "conditions": (
                [c.strip() for c in item.range_standard.split("/")]
                if item.range_standard and item.range_type == "visual"
                else (matched.get("conditions") if matched else None)
            ),
        })
    return aligned


def clean_data(data):
    if isinstance(data, list):
        return [clean_data(item) for item in data]
    elif isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user: User = Depends(require_role("engineer")),   # viewer cannot upload
):
    """
    Upload PDF → parse using robust rule-based/AI parsing → map to database check items → return structured aligned fields
    """
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Save file
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
    except Exception as e:
        return {
            "error": f"Failed to save file: {str(e)}",
            "fields": []
        }

    try:
        fields = parse_pdf(file_path)
        fields = clean_data(fields)
    except Exception as e:
        return {
            "error": f"Parsing failed: {str(e)}",
            "fields": []
        }

    # Auto-matching: pick best DB template and align check items (always return DB-backed fields)
    import database.crud as db_crud
    from database.db import SessionLocal

    matched_template_id = 1
    matched_template_name = "Vehicle Inspection"
    checksheet_type = "vehicle"
    aligned_fields = []

    db = SessionLocal()
    try:
        templates = db_crud.get_all_templates(db)
        if not templates:
            raise ValueError("No checksheet templates in database")

        parsed_labels = {_normalize(f.get("title")) for f in fields if f.get("title")}
        best_template = templates[0]
        best_match_count = -1

        for t in templates:
            t_items = db_crud.get_check_items(db, t.id)
            t_labels = {_normalize(item.parameter_name) for item in t_items if item.parameter_name}
            match_count = len(parsed_labels.intersection(t_labels)) if parsed_labels else 0
            if match_count > best_match_count:
                best_match_count = match_count
                best_template = t

        # Use best match, or default first template when PDF parsing returned nothing
        if best_match_count <= 0 and not parsed_labels:
            best_template = templates[0]

        template_items = db_crud.get_check_items(db, best_template.id)
        matched_template_id = best_template.id
        matched_template_name = best_template.template_name
        checksheet_type = best_template.checksheet_type
        aligned_fields = _align_fields_from_template(template_items, fields)

        # Parsed fields with no DB overlap — append as extra rows (legacy dynamic mode)
        if fields and best_match_count <= 0:
            for idx, f in enumerate(fields):
                aligned_fields.append({
                    "check_item_id": -(idx + 1),
                    "title": f.get("title"),
                    "type": f.get("type"),
                    "unit": f.get("unit"),
                    "min": f.get("min"),
                    "max": f.get("max"),
                    "range_type": f.get("range_type"),
                    "conditions": f.get("conditions"),
                })
    except Exception as e:
        print(f"Template alignment warning: {e}")
        aligned_fields = [
            {
                "check_item_id": idx + 1,
                "title": f.get("title"),
                "type": f.get("type"),
                "unit": f.get("unit"),
                "min": f.get("min"),
                "max": f.get("max"),
                "range_type": f.get("range_type"),
                "conditions": f.get("conditions"),
            }
            for idx, f in enumerate(fields)
        ]
    finally:
        db.close()

    return {
        "message": "PDF uploaded and processed successfully",
        "filename": file.filename,
        "template_id": matched_template_id,
        "template_name": matched_template_name,
        "checksheet_type": checksheet_type,
        "fields": aligned_fields
    }