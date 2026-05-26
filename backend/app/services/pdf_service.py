import os

try:
    import fitz  # PyMuPDF
    if not hasattr(fitz, "open"):
        import pymupdf as fitz
    FITZ_AVAILABLE = True
except ImportError:
    try:
        import pymupdf as fitz
        FITZ_AVAILABLE = True
    except ImportError:
        FITZ_AVAILABLE = False
        print("WARNING: PyMuPDF is not installed. PDF text extraction will run in fallback mock mode.")

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

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

    if PYPDF_AVAILABLE:
        try:
            reader = PdfReader(file_path)
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return full_text.strip()
        except Exception as e:
            print(f"Error during PDF extraction with pypdf: {e}")

    filename = os.path.basename(file_path)
    return f"[Fallback text for {filename} - PDF text extraction not available]"
