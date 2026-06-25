import os
import re
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from database.db import get_db
from database.models import ChecksheetTemplate, CheckItem
from app.core.rbac import require_role
from app.models.user import User
from app.ai_engine.pdf_parser import parse_pdf

router = APIRouter(tags=["Upload"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}

async def _validate_upload(file: UploadFile) -> bytes:
    """Read, size-check, MIME-check, and return file bytes."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size: 20 MB.")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}. Only PDF allowed.")
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Invalid file extension. Only .pdf files are accepted.")
    # Magic byte check — PDF starts with %PDF
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="File content does not match PDF format (magic byte check failed).")
    return content

@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user: User = Depends(require_role("engineer")),
    db: Session = Depends(get_db)
):
    """Upload a checksheet blueprint PDF and match it to a template."""
    # 1. Validate and read PDF content
    content = await _validate_upload(file)
    
    # 2. Save file anchored to project root uploads/ dir
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # backend/app/api/
    _PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))  # BEL/
    UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", os.path.basename(file.filename or "upload.pdf"))
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
        
    # 3. Parse PDF text
    parsed_fields = parse_pdf(file_path)
    
    # 4. Fetch all templates from database
    templates = db.query(ChecksheetTemplate).all()
    if not templates:
        raise HTTPException(status_code=500, detail="No checksheet templates initialized in database.")
    
    best_template = None
    best_match_count = -1
    
    # Helper to normalize strings for comparison
    def norm_name(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower()) if s else ""
        
    # Normalize parsed field titles
    parsed_norms = [norm_name(f.get("title", "")) for f in parsed_fields if f.get("title")]
    
    for temp in templates:
        items = db.query(CheckItem).filter(CheckItem.template_id == temp.id).all()
        matches = 0
        for item in items:
            db_norm = norm_name(item.parameter_name)
            if db_norm in parsed_norms or any(db_norm in p or p in db_norm for p in parsed_norms):
                matches += 1
                
        if matches > best_match_count:
            best_match_count = matches
            best_template = temp
            
    # Fallback if no match or tie at 0: match based on filename or default to first
    if best_template is None or best_match_count <= 0:
        filename_lower = file.filename.lower()
        if "vehicle" in filename_lower:
            best_template = db.query(ChecksheetTemplate).filter(ChecksheetTemplate.checksheet_type == "vehicle").first()
        elif "instrument" in filename_lower or "equipment" in filename_lower:
            best_template = db.query(ChecksheetTemplate).filter(ChecksheetTemplate.checksheet_type == "instrument").first()
            
        if not best_template:
            best_template = templates[0] if templates else None
            
    if not best_template:
        raise HTTPException(status_code=404, detail="No checksheet templates found in database")
        
    # 5. Get all check items of the matched template to return
    matched_items = db.query(CheckItem).filter(CheckItem.template_id == best_template.id).order_by(CheckItem.ref_number).all()
    
    returned_fields = []
    for item in matched_items:
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
        "template_id": best_template.id,
        "template_name": best_template.template_name,
        "checksheet_type": best_template.checksheet_type,
        "fields": returned_fields
    }
