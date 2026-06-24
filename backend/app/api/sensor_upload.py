import hashlib
import re
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from database.db import get_db
from database.models import ChecksheetTemplate, CheckItem
from app.core.rbac import require_role
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["Upload"])


class TextIn(BaseModel):
    text: str


@router.post("/parse-text")
def parse_text_endpoint(payload: TextIn):
    """Accept raw text in JSON and return parsed fields."""
    from app.ai_engine.pdf_parser import parse_text

    fields = parse_text(payload.text)
    return {"fields": fields}


@router.post("/parse-file")
async def parse_file(file: UploadFile = File(...)):
    """Accept an uploaded text file and parse its contents."""
    try:
        raw = await file.read()
        text = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    from app.ai_engine.pdf_parser import parse_text

    fields = parse_text(text)
    return {"filename": file.filename, "fields": fields}


def verify_and_parse_sensor_content(content_str: str) -> tuple[str, dict]:
    lines = content_str.splitlines()
    data_lines = []
    provided_checksum = None
    template_name = ""
    readings = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            t_match = re.match(r"^#\s*Template:\s*(.+)$", line, re.IGNORECASE)
            if t_match:
                template_name = t_match.group(1).strip()
            continue
            
        if line.upper().startswith("CHECKSUM:"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                provided_checksum = parts[1].strip().lower()
            continue
        if line.upper().startswith("CHECKSUM"):
            parts = line.split("|")
            if len(parts) > 1:
                provided_checksum = parts[1].strip().lower()
            continue
            
        data_lines.append(line)
        
    if not provided_checksum:
        raise HTTPException(status_code=400, detail="Missing checksum. Sensor reader file integrity cannot be verified.")
        
    recomputed_content = "\n".join(data_lines).strip()
    calculated_checksum = hashlib.sha256(recomputed_content.encode('utf-8')).hexdigest().lower()
    
    if calculated_checksum != provided_checksum:
        raise HTTPException(status_code=400, detail="Integrity violation: Checksum verification failed. The file may have been altered.")
        
    for line in data_lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                name = parts[1]
                val = parts[2]
                unit = parts[3] if len(parts) > 3 else ""
                readings[name.lower().strip()] = (val, unit)
        else:
            match = re.match(r"^(\d+)\s+(.+?)\s+([^\s]+)(?:\s+([^\s]+))?$", line)
            if match:
                name = match.group(2).strip()
                val = match.group(3).strip()
                unit = match.group(4).strip() if match.group(4) else ""
                readings[name.lower().strip()] = (val, unit)
                
    return template_name, readings


@router.post("/parse-sensor-file")
async def parse_sensor_file(
    file: UploadFile = File(...),
    user: User = Depends(require_role("engineer")),
    db: Session = Depends(get_db)
):
    """Accept an uploaded checksummed sensor reader text file and parse its contents."""
    try:
        raw = await file.read()
        text = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    template_name, readings = verify_and_parse_sensor_content(text)
    
    templates = db.query(ChecksheetTemplate).all()
    if not templates:
        raise HTTPException(status_code=500, detail="No checksheet templates initialized in database.")
        
    matched_template = None
    
    if template_name:
        for temp in templates:
            if temp.template_name.lower().strip() == template_name.lower().strip():
                matched_template = temp
                break
                
    if not matched_template:
        best_match_count = -1
        for temp in templates:
            items = db.query(CheckItem).filter(CheckItem.template_id == temp.id).all()
            matches = 0
            for item in items:
                norm_item = item.parameter_name.lower().strip()
                if norm_item in readings or any(norm_item in k or k in norm_item for k in readings.keys()):
                    matches += 1
            if matches > best_match_count:
                best_match_count = matches
                matched_template = temp
                
    if not matched_template:
        matched_template = templates[0]

    matched_items = db.query(CheckItem).filter(CheckItem.template_id == matched_template.id).order_by(CheckItem.ref_number).all()
    
    returned_fields = []
    values_map = {}
    
    for item in matched_items:
        norm_item = item.parameter_name.lower().strip()
        parsed_val = ""
        
        for name, (val, unit) in readings.items():
            if name == norm_item or name in norm_item or norm_item in name:
                parsed_val = val
                break
                
        values_map[item.id] = parsed_val
        is_categorical = item.range_type == "visual"
        
        returned_fields.append({
            "check_item_id": item.id,
            "title": item.parameter_name,
            "type": "categorical" if is_categorical else "numeric",
            "unit": item.unit,
            "min": item.range_min,
            "max": item.range_max,
            "range_type": "range" if item.range_type == "between" else item.range_type,
            "conditions": [c.strip() for c in item.range_standard.split("/")] if item.range_standard and is_categorical else None
        })
        
    return {
        "filename": file.filename,
        "template_id": matched_template.id,
        "template_name": matched_template.template_name,
        "checksheet_type": matched_template.checksheet_type,
        "fields": returned_fields,
        "values": values_map
    }
