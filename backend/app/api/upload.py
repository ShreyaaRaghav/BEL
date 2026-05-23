from fastapi import APIRouter, UploadFile, File
import os
from app.services.pdf_service import extract_text_from_pdf

router = APIRouter()

# Use absolute or relative path safely
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint that accepts a PDF checksheet, saves it locally, extracts plain text,
    and returns a structured dummy schema for dynamic form generation.
    """
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # Save the uploaded file
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
    except Exception as e:
        return {
            "error": f"Failed to save file: {str(e)}",
            "fields": []
        }

    # Extract text from the PDF
    extracted_text = extract_text_from_pdf(file_path)

    # Return structured parameters for the checksheet
    return {
        "message": "PDF uploaded and processed successfully",
        "filename": file.filename,
        "extracted_text_preview": extracted_text[:200] if extracted_text else "",
        "fields": [
            { "title": "Tire Pressure", "min": 250.0, "max": 400.0, "unit": "kPa" },
            { "title": "Engine Temperature", "min": 75.0, "max": 105.0, "unit": "°C" },
            { "title": "Battery Voltage", "min": 12.0, "max": 14.8, "unit": "V" }
        ]
    }