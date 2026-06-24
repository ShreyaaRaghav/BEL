from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional

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
