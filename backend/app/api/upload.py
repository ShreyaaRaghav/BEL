from fastapi import APIRouter, UploadFile, File, Depends
import os
import re
import math
from app.ai_engine.pdf_parser import parse_pdf
from app.core.rbac import require_role
from app.models.user import User

router = APIRouter()

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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

    # Auto-matching Engine: Find the closest checksheet template from SQLite DB
    import database.crud as db_crud
    from database.db import SessionLocal
    
    db = SessionLocal()
    try:
        templates = db_crud.get_all_templates(db)
        best_template = None
        best_match_count = -1
        
        def normalize(name):
            return re.sub(r'[^a-z0-9]', '', str(name or "").lower())
            
        parsed_labels = {normalize(f.get("title")) for f in fields if f.get("title")}
        
        for t in templates:
            t_items = db_crud.get_check_items(db, t.id)
            t_labels = {normalize(item.parameter_name) for item in t_items if item.parameter_name}
            
            # Count common parameters
            match_count = len(parsed_labels.intersection(t_labels))
            if match_count > best_match_count:
                best_match_count = match_count
                best_template = t
                
        # If we have a match, align parsed fields to the database check items
        aligned_fields = []
        if best_template and best_match_count > 0:
            template_items = db_crud.get_check_items(db, best_template.id)
            matched_template_id = best_template.id
            matched_template_name = best_template.template_name
            checksheet_type = best_template.checksheet_type
            
            for item in template_items:
                matched_field = None
                norm_item_name = normalize(item.parameter_name)
                for f in fields:
                    if normalize(f.get("title")) == norm_item_name:
                        matched_field = f
                        break
                
                # Align values
                aligned_fields.append({
                    "check_item_id": item.id,
                    "title": item.parameter_name,
                    "type": matched_field.get("type") if matched_field else ("categorical" if item.range_type == "visual" else "numeric"),
                    "unit": item.unit,
                    "min": item.range_min,
                    "max": item.range_max,
                    "range_type": "range" if item.range_type == "between" else item.range_type,
                    "conditions": [c.strip() for c in item.range_standard.split("/")] if item.range_standard and item.range_type == "visual" else None
                })
        else:
            # Fallback if no template matches
            matched_template_id = 1
            matched_template_name = "Dynamic Vehicle Inspection"
            checksheet_type = "vehicle"
            
            for idx, f in enumerate(fields):
                aligned_fields.append({
                    "check_item_id": idx + 1,
                    "title": f.get("title"),
                    "type": f.get("type"),
                    "unit": f.get("unit"),
                    "min": f.get("min"),
                    "max": f.get("max"),
                    "range_type": f.get("range_type"),
                    "conditions": f.get("conditions")
                })
    except Exception as e:
        # Graceful fallback in case of database querying failures
        matched_template_id = 1
        matched_template_name = "Dynamic Calibration Template"
        checksheet_type = "vehicle"
        aligned_fields = []
        for idx, f in enumerate(fields):
            aligned_fields.append({
                "check_item_id": idx + 1,
                "title": f.get("title"),
                "type": f.get("type"),
                "unit": f.get("unit"),
                "min": f.get("min"),
                "max": f.get("max"),
                "range_type": f.get("range_type"),
                "conditions": f.get("conditions")
            })
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