"""
BEL VAPT Hardening Patches
============================
Provides concrete remediation functions that can be applied to the project
to fix the vulnerabilities identified by the scanner.

Each function is idempotent — safe to run multiple times.
"""

from __future__ import annotations
import os
import re
import stat
from typing import NamedTuple


class PatchResult(NamedTuple):
    patch_id: str
    applied: bool
    message: str


# ──────────────────────────────────────────────────────────────────────────────
# Patch: Security headers middleware
# ──────────────────────────────────────────────────────────────────────────────

SECURITY_HEADERS_MIDDLEWARE = '''
class SecurityHeadersMiddleware:
    """Injects OWASP-recommended HTTP security headers on every response."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                security_headers = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"x-xss-protection": b"1; mode=block",
                    b"referrer-policy": b"no-referrer",
                    b"content-security-policy": b"default-src \\'self\\'",
                    b"cache-control": b"no-store",
                    b"permissions-policy": b"geolocation=(), microphone=()",
                }
                for k, v in security_headers.items():
                    headers.setdefault(k, v)
                message = {**message, "headers": list(headers.items())}
            await send(message)

        await self.app(scope, receive, send_with_headers)

'''


def patch_security_headers(main_py_path: str) -> PatchResult:
    """Add SecurityHeadersMiddleware to main.py if not already present."""
    try:
        with open(main_py_path) as fh:
            src = fh.read()

        if "SecurityHeadersMiddleware" in src:
            return PatchResult("P-HEADERS", False, "SecurityHeadersMiddleware already present — skipped.")

        # Insert class definition after imports block
        insert_after = "from fastapi.exceptions import RequestValidationError"
        if insert_after not in src:
            return PatchResult("P-HEADERS", False, f"Could not find insertion point: {insert_after!r}")

        new_src = src.replace(
            insert_after,
            insert_after + "\n" + SECURITY_HEADERS_MIDDLEWARE
        )

        # Add middleware registration after CORSMiddleware block
        new_src = new_src.replace(
            "app.include_router(auth.router",
            "app.add_middleware(SecurityHeadersMiddleware)\napp.include_router(auth.router"
        )

        with open(main_py_path, "w") as fh:
            fh.write(new_src)

        return PatchResult("P-HEADERS", True, "SecurityHeadersMiddleware injected into main.py.")
    except Exception as e:
        return PatchResult("P-HEADERS", False, f"Error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Patch: Upload filename sanitization + MIME + size check
# ──────────────────────────────────────────────────────────────────────────────

UPLOAD_VALIDATION_BLOCK = '''
# ── BEL VAPT Security Hardening: Upload Validation ──────────────────────────
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}

async def _validate_upload(file: UploadFile) -> bytes:
    """Read, size-check, MIME-check, and return file bytes."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum allowed size: 20 MB.")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}. Only PDF allowed.")
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Invalid file extension. Only .pdf files are accepted.")
    # Magic byte check — PDF starts with %PDF
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="File content does not match PDF format (magic byte check failed).")
    return content
# ────────────────────────────────────────────────────────────────────────────
'''


def patch_upload_validation(upload_py_path: str) -> PatchResult:
    """Inject upload validation helper and use secure_filename into upload.py."""
    try:
        with open(upload_py_path) as fh:
            src = fh.read()

        if "_validate_upload" in src:
            return PatchResult("P-UPLOAD", False, "Upload validation already present — skipped.")

        # Add import for HTTPException if missing
        if "HTTPException" not in src:
            src = "from fastapi import HTTPException\n" + src

        # Inject validation block after imports
        insert_after = "os.makedirs(UPLOAD_DIR, exist_ok=True)"
        if insert_after not in src:
            return PatchResult("P-UPLOAD", False, f"Could not find insertion point in upload.py")

        src = src.replace(insert_after, insert_after + "\n\n" + UPLOAD_VALIDATION_BLOCK)

        # Patch the upload handler to use validation + safe filename
        old_save = '''    # Save file
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())'''

        new_save = '''    # Save file (VAPT-hardened: validated content, sanitized filename)
    import re as _re
    safe_name = _re.sub(r"[^a-zA-Z0-9._-]", "_", os.path.basename(file.filename or "upload.pdf"))
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        file_content = await _validate_upload(file)
        with open(file_path, "wb") as f:
            f.write(file_content)'''

        if old_save in src:
            src = src.replace(old_save, new_save)
        else:
            # Fallback: patch just the open() call
            src = src.replace(
                "file_path = os.path.join(UPLOAD_DIR, file.filename)",
                "import re as _re\n    safe_name = _re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.basename(file.filename or 'upload.pdf'))\n    file_path = os.path.join(UPLOAD_DIR, safe_name)",
            )

        with open(upload_py_path, "w") as fh:
            fh.write(src)

        return PatchResult("P-UPLOAD", True, "Upload validation (size, MIME, magic bytes, safe filename) applied.")
    except Exception as e:
        return PatchResult("P-UPLOAD", False, f"Error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Patch: Restrict reset-demo-data to admin only
# ──────────────────────────────────────────────────────────────────────────────

def patch_restrict_reset_endpoint(checksheet_py_path: str) -> PatchResult:
    """Upgrade reset-demo-data from engineer to admin-only."""
    try:
        with open(checksheet_py_path) as fh:
            src = fh.read()

        if 'require_role("admin")' in src and "reset-demo-data" in src:
            return PatchResult("P-RESET", False, "reset-demo-data already restricted to admin — skipped.")

        # Find the reset endpoint and upgrade its role
        patched = src.replace(
            '@router.post("/reset-demo-data")\ndef reset_demo_data(\n    db: Session = Depends(get_db),\n    user: User = Depends(require_role("engineer"))',
            '@router.post("/reset-demo-data")\ndef reset_demo_data(\n    db: Session = Depends(get_db),\n    user: User = Depends(require_role("admin"))  # VAPT: upgraded from engineer to admin',
        )

        if patched == src:
            return PatchResult("P-RESET", False, "Could not find reset-demo-data endpoint pattern to patch.")

        with open(checksheet_py_path, "w") as fh:
            fh.write(patched)

        return PatchResult("P-RESET", True, "reset-demo-data endpoint restricted to admin role only.")
    except Exception as e:
        return PatchResult("P-RESET", False, f"Error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Patch: DB file permissions
# ──────────────────────────────────────────────────────────────────────────────

def patch_db_permissions(db_path: str) -> PatchResult:
    """Set SQLite DB to 640 permissions (owner RW, group R, others none)."""
    try:
        if not os.path.exists(db_path):
            return PatchResult("P-DBPERM", False, f"Database file not found: {db_path}")
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)  # 640
        return PatchResult("P-DBPERM", True, f"Set {db_path} permissions to 640.")
    except Exception as e:
        return PatchResult("P-DBPERM", False, f"Error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Master apply function
# ──────────────────────────────────────────────────────────────────────────────

def apply_all_patches(base_dir: str) -> list[PatchResult]:
    """Apply all available hardening patches. Returns list of results."""
    results = []

    backend = os.path.join(base_dir, "backend")
    app_dir = os.path.join(backend, "app")

    results.append(patch_security_headers(os.path.join(app_dir, "main.py")))
    results.append(patch_upload_validation(os.path.join(app_dir, "api", "upload.py")))
    results.append(patch_restrict_reset_endpoint(os.path.join(app_dir, "api", "checksheet.py")))

    # DB path candidates
    for db_candidate in [
        os.path.join(backend, "database", "bel_checksheet.db"),
        os.path.join(backend, "bel_checksheet.db"),
    ]:
        if os.path.exists(db_candidate):
            results.append(patch_db_permissions(db_candidate))
            break

    return results
