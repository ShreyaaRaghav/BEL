import os

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    print("WARNING: PyMuPDF (fitz) is not installed. PDF text extraction will run in fallback mock mode.")

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts plain text from a PDF file. Falls back gracefully if PyMuPDF is not installed.
    """
    if not os.path.exists(file_path):
        return ""

    if FITZ_AVAILABLE:
        try:
            doc = fitz.open(file_path)
            full_text = ""
            for page in doc:
                text = page.get_text()
                if text:
                    full_text += text + "\n"
            return full_text.strip()
        except Exception as e:
            print(f"Error during PDF extraction with PyMuPDF: {e}")
            return f"[Error extracting text: {e}]"
    else:
        # Fallback if fitz is not installed
        filename = os.path.basename(file_path)
        return f"[Fallback text for {filename} - PyMuPDF not available]"