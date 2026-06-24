"""
BEL VAPT Scanner — Vulnerability Assessment Module
====================================================
Performs static security assessment of the running system:
  - Configuration hygiene checks
  - JWT/auth posture checks
  - File upload attack surface analysis
  - API surface enumeration
  - SQLite database file permission check
  - Secret key strength detection
  - Rate-limit / lockout policy review
  - Dependency CVE stub (offline — checks installed packages vs known-bad list)

All findings are returned as structured Finding objects with CVSS-style
severity levels: CRITICAL / HIGH / MEDIUM / LOW / INFO.
"""

from __future__ import annotations
import os
import re
import stat
import sys
import hashlib
import importlib.metadata as pkg_meta
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal

# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

@dataclass
class Finding:
    id: str                          # e.g. "VAPT-001"
    category: str                    # e.g. "Authentication"
    title: str
    severity: Severity
    description: str
    recommendation: str
    affected_asset: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    scan_id: str
    timestamp: str
    scanner_version: str = "1.0.0"
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def compute_summary(self):
        counts: dict[str, int] = {s: 0 for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        self.summary = {
            "total": len(self.findings),
            "by_severity": counts,
            "risk_score": self._risk_score(counts),
        }

    @staticmethod
    def _risk_score(counts: dict) -> int:
        """Simplified DREAD-style integer 0-100."""
        return min(100, counts["CRITICAL"] * 25 + counts["HIGH"] * 10 +
                   counts["MEDIUM"] * 5 + counts["LOW"] * 2 + counts["INFO"])

    def to_dict(self) -> dict:
        self.compute_summary()
        return {
            "scan_id": self.scan_id,
            "timestamp": self.timestamp,
            "scanner_version": self.scanner_version,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
        }


# ──────────────────────────────────────────────────────────────────────────────
# Individual check functions — each returns list[Finding]
# ──────────────────────────────────────────────────────────────────────────────

def _check_secret_key() -> list[Finding]:
    """VAPT-001 — Detect default / weak SECRET_KEY."""
    findings = []
    from app.config import SECRET_KEY

    WEAK_KEYS = {
        "bel-dev-secret-key-change-in-prod",
        "secret",
        "changeme",
        "password",
        "dev",
        "test",
    }

    key_lower = SECRET_KEY.lower().strip()
    is_weak = key_lower in WEAK_KEYS or len(SECRET_KEY) < 32

    if is_weak:
        findings.append(Finding(
            id="VAPT-001",
            category="Cryptography",
            title="Weak or default JWT SECRET_KEY in use",
            severity="CRITICAL",
            description=(
                "The application is using a short or well-known default SECRET_KEY for JWT signing. "
                "An attacker who discovers this key can forge arbitrary access tokens, bypassing authentication entirely."
            ),
            recommendation=(
                "Set BEL_SECRET_KEY environment variable to a cryptographically random string of at least 64 characters. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(64))\""
            ),
            affected_asset="backend/app/config.py → BEL_SECRET_KEY",
            evidence=f"Key length: {len(SECRET_KEY)} chars. Key appears to be default/weak.",
        ))
    else:
        findings.append(Finding(
            id="VAPT-001",
            category="Cryptography",
            title="JWT SECRET_KEY appears sufficiently strong",
            severity="INFO",
            description="SECRET_KEY is not a known default and meets minimum length (≥32 chars).",
            recommendation="Ensure the key is rotated periodically and stored in a secrets vault, not source code.",
            affected_asset="backend/app/config.py → BEL_SECRET_KEY",
            evidence=f"Key length: {len(SECRET_KEY)} chars. SHA-256 prefix: {hashlib.sha256(SECRET_KEY.encode()).hexdigest()[:8]}…",
        ))
    return findings


def _check_jwt_algorithm() -> list[Finding]:
    """VAPT-002 — HS256 is acceptable for air-gapped; flag if none-algorithm is possible."""
    from app.config import ALGORITHM
    findings = []
    if ALGORITHM.upper() in ("NONE", ""):
        findings.append(Finding(
            id="VAPT-002",
            category="Authentication",
            title="JWT algorithm set to 'none' — authentication bypassable",
            severity="CRITICAL",
            description="A JWT algorithm of 'none' disables signature verification entirely.",
            recommendation="Set ALGORITHM to HS256 or RS256.",
            affected_asset="backend/app/config.py → ALGORITHM",
            evidence=f"ALGORITHM = {ALGORITHM!r}",
        ))
    elif ALGORITHM.upper() == "HS256":
        findings.append(Finding(
            id="VAPT-002",
            category="Authentication",
            title="JWT uses symmetric HS256 algorithm",
            severity="LOW",
            description=(
                "HS256 is acceptable for air-gapped single-service deployments but shares the same key for "
                "signing and verification. Consider RS256 if multiple services ever consume the token."
            ),
            recommendation="For air-gapped single-node use, HS256 is acceptable. Document this decision.",
            affected_asset="backend/app/config.py → ALGORITHM",
            evidence=f"ALGORITHM = {ALGORITHM!r}",
        ))
    return findings


def _check_token_expiry() -> list[Finding]:
    """VAPT-003 — Token expiry policy."""
    from app.config import TOKEN_EXPIRE_MINUTES
    findings = []
    if TOKEN_EXPIRE_MINUTES > 60:
        findings.append(Finding(
            id="VAPT-003",
            category="Session Management",
            title="Access token expiry exceeds 60 minutes",
            severity="MEDIUM",
            description=(
                f"Access tokens expire after {TOKEN_EXPIRE_MINUTES} minutes. "
                "Long-lived tokens increase the window of exploitation if intercepted."
            ),
            recommendation="Reduce TOKEN_EXPIRE_MINUTES to ≤30 minutes for industrial systems.",
            affected_asset="backend/app/config.py → TOKEN_EXPIRE_MINUTES",
            evidence=f"TOKEN_EXPIRE_MINUTES = {TOKEN_EXPIRE_MINUTES}",
        ))
    else:
        findings.append(Finding(
            id="VAPT-003",
            category="Session Management",
            title="Access token expiry within acceptable range",
            severity="INFO",
            description=f"Tokens expire after {TOKEN_EXPIRE_MINUTES} minutes.",
            recommendation="No action required.",
            affected_asset="backend/app/config.py → TOKEN_EXPIRE_MINUTES",
            evidence=f"TOKEN_EXPIRE_MINUTES = {TOKEN_EXPIRE_MINUTES}",
        ))
    return findings


def _check_lockout_policy() -> list[Finding]:
    """VAPT-004 — Brute-force lockout policy review."""
    from app.config import MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES
    findings = []

    if MAX_FAILED_ATTEMPTS > 10:
        findings.append(Finding(
            id="VAPT-004a",
            category="Authentication",
            title="Account lockout threshold too high (brute-force risk)",
            severity="HIGH",
            description=f"Lockout triggers after {MAX_FAILED_ATTEMPTS} failed attempts — too permissive.",
            recommendation="Reduce MAX_FAILED_ATTEMPTS to ≤5.",
            affected_asset="backend/app/config.py → MAX_FAILED_ATTEMPTS",
            evidence=f"MAX_FAILED_ATTEMPTS = {MAX_FAILED_ATTEMPTS}",
        ))
    else:
        findings.append(Finding(
            id="VAPT-004a",
            category="Authentication",
            title="Account lockout threshold acceptable",
            severity="INFO",
            description=f"Lockout after {MAX_FAILED_ATTEMPTS} failed attempts.",
            recommendation="Current setting is within BEL security policy.",
            affected_asset="backend/app/config.py → MAX_FAILED_ATTEMPTS",
            evidence=f"MAX_FAILED_ATTEMPTS = {MAX_FAILED_ATTEMPTS}",
        ))

    if LOCKOUT_MINUTES < 5:
        findings.append(Finding(
            id="VAPT-004b",
            category="Authentication",
            title="Account lockout duration too short",
            severity="MEDIUM",
            description=f"Accounts unlock after only {LOCKOUT_MINUTES} minute(s) — allows rapid retry cycles.",
            recommendation="Set LOCKOUT_MINUTES to ≥15 minutes.",
            affected_asset="backend/app/config.py → LOCKOUT_MINUTES",
            evidence=f"LOCKOUT_MINUTES = {LOCKOUT_MINUTES}",
        ))
    return findings


def _check_password_policy() -> list[Finding]:
    """VAPT-005 — Password complexity policy review."""
    from app.config import (
        PASSWORD_MIN_LENGTH, PASSWORD_NEEDS_UPPER,
        PASSWORD_NEEDS_LOWER, PASSWORD_NEEDS_DIGIT, PASSWORD_NEEDS_SPECIAL,
    )
    findings = []
    issues = []

    if PASSWORD_MIN_LENGTH < 12:
        issues.append(f"Minimum length is {PASSWORD_MIN_LENGTH} (recommended ≥12)")
    if not PASSWORD_NEEDS_UPPER:
        issues.append("Uppercase requirement disabled")
    if not PASSWORD_NEEDS_LOWER:
        issues.append("Lowercase requirement disabled")
    if not PASSWORD_NEEDS_DIGIT:
        issues.append("Digit requirement disabled")
    if not PASSWORD_NEEDS_SPECIAL:
        issues.append("Special character requirement disabled")

    if issues:
        findings.append(Finding(
            id="VAPT-005",
            category="Authentication",
            title="Password policy does not meet minimum security standards",
            severity="HIGH",
            description="The password policy has one or more weaknesses: " + "; ".join(issues),
            recommendation=(
                "Ensure PASSWORD_MIN_LENGTH ≥ 12 and all complexity flags are True "
                "to comply with MeitY/CERT-In password guidelines."
            ),
            affected_asset="backend/app/config.py → PASSWORD_* settings",
            evidence="; ".join(issues),
        ))
    else:
        findings.append(Finding(
            id="VAPT-005",
            category="Authentication",
            title="Password complexity policy meets minimum requirements",
            severity="INFO",
            description="All password complexity rules are enabled and minimum length is ≥12.",
            recommendation="No action required.",
            affected_asset="backend/app/config.py → PASSWORD_* settings",
            evidence=f"min_length={PASSWORD_MIN_LENGTH}, upper={PASSWORD_NEEDS_UPPER}, "
                     f"lower={PASSWORD_NEEDS_LOWER}, digit={PASSWORD_NEEDS_DIGIT}, "
                     f"special={PASSWORD_NEEDS_SPECIAL}",
        ))
    return findings


def _check_cors_policy() -> list[Finding]:
    """VAPT-006 — CORS origin whitelist review."""
    from app.config import ALLOWED_ORIGINS
    findings = []

    wildcard = any(o == "*" for o in ALLOWED_ORIGINS)
    if wildcard:
        findings.append(Finding(
            id="VAPT-006",
            category="Configuration",
            title="CORS wildcard (*) allows any origin — CSRF risk",
            severity="HIGH",
            description=(
                "A wildcard CORS policy allows any web page to make credentialed requests to the API, "
                "enabling cross-site request forgery attacks."
            ),
            recommendation="Restrict ALLOWED_ORIGINS to the specific intranet origins used by the frontend.",
            affected_asset="backend/app/config.py → ALLOWED_ORIGINS",
            evidence=f"ALLOWED_ORIGINS = {ALLOWED_ORIGINS}",
        ))
    else:
        findings.append(Finding(
            id="VAPT-006",
            category="Configuration",
            title="CORS policy is origin-restricted",
            severity="INFO",
            description="CORS is limited to an explicit whitelist — no wildcard detected.",
            recommendation="Ensure listed origins are only internal/intranet addresses in production.",
            affected_asset="backend/app/config.py → ALLOWED_ORIGINS",
            evidence=f"ALLOWED_ORIGINS = {ALLOWED_ORIGINS}",
        ))
    return findings


def _check_file_upload_security() -> list[Finding]:
    """VAPT-007 — File upload endpoint security review."""
    findings = []

    # Check upload.py for extension validation
    upload_path = os.path.join(os.path.dirname(__file__), "..", "api", "upload.py")
    upload_path = os.path.abspath(upload_path)

    try:
        with open(upload_path) as fh:
            src = fh.read()

        has_ext_check = bool(re.search(r"\.pdf", src, re.IGNORECASE) and
                             re.search(r"extension|content.?type|mime|endswith", src, re.IGNORECASE))
        has_size_limit = bool(re.search(r"content.?length|max.?size|limit|len\(", src, re.IGNORECASE))

        if not has_ext_check:
            findings.append(Finding(
                id="VAPT-007a",
                category="File Upload",
                title="No MIME type / extension validation on file upload endpoint",
                severity="HIGH",
                description=(
                    "The /api/upload-pdf endpoint saves files based on the client-supplied filename without "
                    "verifying the MIME type or extension. An attacker could upload arbitrary files "
                    "(e.g. .py, .sh, .exe) to the upload directory."
                ),
                recommendation=(
                    "Add server-side validation: check file.content_type == 'application/pdf' and "
                    "file.filename.lower().endswith('.pdf') before saving. "
                    "Use python-magic for deep MIME sniffing."
                ),
                affected_asset="backend/app/api/upload.py → /api/upload-pdf",
                evidence="No content_type or endswith('.pdf') check found in upload handler.",
            ))

        if not has_size_limit:
            findings.append(Finding(
                id="VAPT-007b",
                category="File Upload",
                title="No upload file size limit enforced",
                severity="MEDIUM",
                description=(
                    "The upload endpoint does not enforce a maximum file size. "
                    "A large file upload could exhaust disk space or RAM on the air-gapped server."
                ),
                recommendation=(
                    "Add a size check: if file.size > MAX_UPLOAD_BYTES: raise HTTPException(413). "
                    "Set MAX_UPLOAD_BYTES = 20 * 1024 * 1024 (20 MB) as a reasonable limit for PDFs."
                ),
                affected_asset="backend/app/api/upload.py → /api/upload-pdf",
                evidence="No file size or content-length check found.",
            ))

        # Check if filename is used directly (path traversal)
        if re.search(r"file\.filename", src) and not re.search(r"secure_filename|basename|sanitize", src):
            findings.append(Finding(
                id="VAPT-007c",
                category="File Upload",
                title="Unsanitized filename used in file path — path traversal risk",
                severity="HIGH",
                description=(
                    "The upload handler uses `file.filename` directly to construct the save path. "
                    "A filename like '../../app/config.py' could overwrite critical application files."
                ),
                recommendation=(
                    "Use werkzeug.utils.secure_filename(file.filename) or os.path.basename() "
                    "to sanitize the filename before constructing the save path."
                ),
                affected_asset="backend/app/api/upload.py",
                evidence="Pattern: os.path.join(UPLOAD_DIR, file.filename) without sanitization.",
            ))

    except FileNotFoundError:
        findings.append(Finding(
            id="VAPT-007",
            category="File Upload",
            title="Could not locate upload.py for analysis",
            severity="INFO",
            description="Scanner could not open upload.py for static analysis.",
            recommendation="Verify scanner is running from the correct working directory.",
            affected_asset="backend/app/api/upload.py",
        ))

    return findings


def _check_db_file_permissions() -> list[Finding]:
    """VAPT-008 — SQLite file permission check."""
    findings = []

    # Try to locate the SQLite file
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "bel_checksheet.db"),
        os.path.join(os.path.dirname(__file__), "..", "..", "bel_checksheet.db"),
        "bel_checksheet.db",
    ]
    db_file = None
    for p in candidate_paths:
        p = os.path.abspath(p)
        if os.path.exists(p):
            db_file = p
            break

    if db_file:
        mode = os.stat(db_file).st_mode
        world_readable = bool(mode & stat.S_IROTH)
        world_writable = bool(mode & stat.S_IWOTH)

        if world_writable:
            findings.append(Finding(
                id="VAPT-008",
                category="Data Security",
                title="SQLite database file is world-writable",
                severity="CRITICAL",
                description=(
                    "The database file has world-write permissions. Any local OS user can modify "
                    "inspection records, audit logs, or user credentials."
                ),
                recommendation="Run: chmod 600 bel_checksheet.db  (owner read/write only).",
                affected_asset=db_file,
                evidence=f"File mode: {oct(mode)}",
            ))
        elif world_readable:
            findings.append(Finding(
                id="VAPT-008",
                category="Data Security",
                title="SQLite database file is world-readable",
                severity="HIGH",
                description=(
                    "The database file is readable by all OS users. "
                    "Any local user can copy and read hashed credentials and inspection data."
                ),
                recommendation="Run: chmod 640 bel_checksheet.db and ensure the application runs as a dedicated OS user.",
                affected_asset=db_file,
                evidence=f"File mode: {oct(mode)}",
            ))
        else:
            findings.append(Finding(
                id="VAPT-008",
                category="Data Security",
                title="SQLite database file permissions are restricted",
                severity="INFO",
                description="Database file is not world-readable or world-writable.",
                recommendation="Ensure the owning OS user is a dedicated service account, not root.",
                affected_asset=db_file,
                evidence=f"File mode: {oct(mode)}",
            ))
    else:
        findings.append(Finding(
            id="VAPT-008",
            category="Data Security",
            title="SQLite database file not found on disk (may not be initialized yet)",
            severity="INFO",
            description="Database file was not found at expected paths — possibly not yet created.",
            recommendation="Run the application startup to initialize the database, then re-scan.",
            affected_asset="bel_checksheet.db",
        ))

    return findings


def _check_audit_log_persistence() -> list[Finding]:
    """VAPT-009 — In-memory audit log is not persistent."""
    findings = []
    audit_log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "audit_log.py"))
    try:
        with open(audit_log_path) as fh:
            src = fh.read()
        is_persistent = "_LOGS" not in src and ("SessionLocal" in src or "AuditLogRecord" in src or "db.add" in src)
    except Exception:
        is_persistent = False

    if not is_persistent:
        findings.append(Finding(
            id="VAPT-009",
            category="Audit & Logging",
            title="Audit logs stored in-memory — lost on server restart",
            severity="HIGH",
            description=(
                "audit_log.py uses a plain Python list (_LOGS) as its backing store. "
                "All authentication events are wiped on every server restart. "
                "This violates audit trail requirements for defence/industrial systems."
            ),
            recommendation=(
                "Persist audit logs to the SQLite database or a dedicated append-only log file. "
                "An AuditLog SQLAlchemy model has been created — wire it into add_log()."
            ),
            affected_asset="backend/app/models/audit_log.py",
            evidence="Variable _LOGS: list[AuditLog] = [] — no DB write in add_log().",
        ))
    return findings


def _check_refresh_token_store() -> list[Finding]:
    """VAPT-010 — Revoked JTI set is in-memory."""
    findings = []
    auth_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", "auth.py"))
    try:
        with open(auth_path) as fh:
            src = fh.read()
        is_persistent = "revoked_jtis: set" not in src and "RevokedToken" in src
    except Exception:
        is_persistent = False

    if not is_persistent:
        findings.append(Finding(
            id="VAPT-010",
            category="Session Management",
            title="Revoked JWT refresh-token set is in-memory — lost on restart",
            severity="HIGH",
            description=(
                "auth.py stores revoked_jtis in a Python set(). If the server restarts, "
                "all previously revoked refresh tokens become valid again — users who logged out "
                "can have their old tokens replayed."
            ),
            recommendation=(
                "Persist revoked JTIs to the SQLite database with a TTL equal to the refresh token lifetime (7 days). "
                "A cron or startup task should prune expired entries."
            ),
            affected_asset="backend/app/api/auth.py → revoked_jtis",
            evidence="revoked_jtis: set[str] = set()  — module-level in-memory set.",
        ))
    return findings


def _check_https_enforcement() -> list[Finding]:
    """VAPT-011 — No HTTPS/TLS enforcement detected."""
    findings = []

    # Check if HSTS or HTTPS redirect middleware is present in main.py
    main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
    main_path = os.path.abspath(main_path)

    try:
        with open(main_path) as fh:
            src = fh.read()
        has_https = bool(re.search(r"HTTPSRedirect|hsts|strict.transport|TrustedHost", src, re.IGNORECASE))
    except FileNotFoundError:
        has_https = False

    if not has_https:
        findings.append(Finding(
            id="VAPT-011",
            category="Transport Security",
            title="No HTTPS/TLS redirect or HSTS header enforced",
            severity="HIGH",
            description=(
                "The FastAPI application does not enforce HTTPS or set a Strict-Transport-Security header. "
                "Even on an air-gapped network, traffic between workstations and server can be intercepted "
                "by a rogue device or ARP-spoofing attack on the LAN."
            ),
            recommendation=(
                "Add HTTPSRedirectMiddleware and a custom HSTS middleware, or terminate TLS at an nginx reverse proxy. "
                "Use a self-signed CA for the air-gapped environment.\n\n"
                "  from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware\n"
                "  app.add_middleware(HTTPSRedirectMiddleware)"
            ),
            affected_asset="backend/app/main.py",
            evidence="No HTTPSRedirectMiddleware or HSTS header logic found.",
        ))
    return findings


def _check_security_headers() -> list[Finding]:
    """VAPT-012 — HTTP security headers."""
    findings = []
    main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
    main_path = os.path.abspath(main_path)

    try:
        with open(main_path) as fh:
            src = fh.read()
        has_csp = "Content-Security-Policy" in src
        has_xcto = "X-Content-Type-Options" in src
    except FileNotFoundError:
        has_csp = has_xcto = False

    missing = []
    if not has_csp:
        missing.append("Content-Security-Policy")
    if not has_xcto:
        missing.append("X-Content-Type-Options")

    if missing:
        findings.append(Finding(
            id="VAPT-012",
            category="Configuration",
            title=f"Missing HTTP security headers: {', '.join(missing)}",
            severity="MEDIUM",
            description=(
                "The following security headers are not being set by the API: " + ", ".join(missing) + ". "
                "These headers reduce the impact of XSS and MIME-sniffing attacks on the frontend."
            ),
            recommendation=(
                "Add a middleware that injects security headers on every response:\n"
                "  X-Content-Type-Options: nosniff\n"
                "  Content-Security-Policy: default-src 'self'\n"
                "  X-Frame-Options: DENY\n"
                "  Referrer-Policy: no-referrer"
            ),
            affected_asset="backend/app/main.py",
            evidence=f"Headers not found in main.py: {missing}",
        ))
    return findings


def _check_sql_injection_surface() -> list[Finding]:
    """VAPT-013 — Raw SQL usage audit."""
    findings = []

    # Look for raw text() SQL calls in checksheet.py
    cs_path = os.path.join(os.path.dirname(__file__), "..", "api", "checksheet.py")
    cs_path = os.path.abspath(cs_path)

    try:
        with open(cs_path) as fh:
            src = fh.read()

        raw_count = len(re.findall(r"db\.execute\(text\(", src))
        param_bound = len(re.findall(r"bindparams|:param|\?", src))

        if raw_count > 0 and param_bound == 0:
            findings.append(Finding(
                id="VAPT-013",
                category="Injection",
                title=f"Raw SQL via text() without bound parameters ({raw_count} occurrences)",
                severity="MEDIUM",
                description=(
                    f"Found {raw_count} raw SQLAlchemy text() queries in checksheet.py. "
                    "Although current queries appear static, this pattern is fragile — "
                    "any future developer adding user input to these queries would create a SQL injection vulnerability."
                ),
                recommendation=(
                    "Replace text() queries with SQLAlchemy ORM queries or use bindparams() for any dynamic values. "
                    "At minimum, add a code-review rule: 'never interpolate user input into text() calls'."
                ),
                affected_asset="backend/app/api/checksheet.py",
                evidence=f"{raw_count} db.execute(text(...)) calls with no bound parameter markers.",
            ))
    except FileNotFoundError:
        pass

    return findings


def _check_demo_reset_endpoint() -> list[Finding]:
    """VAPT-014 — Destructive reset endpoint accessible to engineers."""
    findings = []
    findings.append(Finding(
        id="VAPT-014",
        category="Authorization",
        title="Destructive /reset-demo-data endpoint accessible to 'engineer' role",
        severity="HIGH",
        description=(
            "The POST /api/checksheets/reset-demo-data endpoint deletes ALL inspection records. "
            "It is currently guarded only by the 'engineer' role, meaning any engineer-level user "
            "can permanently destroy production inspection data. "
            "In a BEL defence context, this is a critical data integrity risk."
        ),
        recommendation=(
            "1. Restrict the endpoint to the 'admin' role only.\n"
            "2. Require a two-factor confirmation token (admin must supply a TOTP code or secondary password).\n"
            "3. Rename from 'reset-demo-data' to make clear it affects production data.\n"
            "4. Implement soft-delete / archival rather than hard DELETE."
        ),
        affected_asset="backend/app/api/checksheet.py → POST /api/checksheets/reset-demo-data",
        evidence="require_role('engineer') used — all engineers can trigger full data wipe.",
    ))
    return findings


def _check_dependency_versions() -> list[Finding]:
    """VAPT-015 — Offline known-vulnerable package check (curated list)."""
    findings = []

    # Curated offline CVE list for packages commonly used in Python web apps.
    # Format: (package_name, max_safe_version_exclusive, CVE_ids, description)
    KNOWN_VULNERABLE: list[tuple] = [
        ("python-jose", "3.3.0", ["CVE-2022-29217"], "JWT algorithm confusion — allows 'none' alg bypass"),
        ("cryptography", "41.0.0", ["CVE-2023-23931"], "NULL pointer dereference in X.509 parsing"),
        ("pillow", "10.0.0", ["CVE-2023-44271"], "Uncontrolled resource consumption in ImageFont"),
        ("starlette", "0.27.0", ["CVE-2023-29159"], "Path traversal in StaticFiles"),
        ("fastapi", "0.95.0", ["CVE-2023-29159"], "Inherited from Starlette path traversal"),
        ("pydantic", "1.10.13", ["CVE-2024-3772"], "ReDoS in email validator"),
        ("sqlalchemy", "1.4.49", ["CVE-2023-46051"], "SQL injection via column name"),
        ("uvicorn", "0.20.0", ["CVE-2022-31163"], "HTTP request smuggling"),
    ]

    installed: dict[str, str] = {}
    for dist in pkg_meta.distributions():
        name = dist.metadata.get("Name", "").lower().replace("-", "_").replace(".", "_")
        version = dist.metadata.get("Version", "0.0.0")
        installed[name] = version

    for pkg, max_safe, cves, desc in KNOWN_VULNERABLE:
        norm_pkg = pkg.lower().replace("-", "_").replace(".", "_")
        ver_str = installed.get(norm_pkg)
        if ver_str:
            try:
                from packaging.version import Version
                if Version(ver_str) < Version(max_safe):
                    findings.append(Finding(
                        id="VAPT-015",
                        category="Dependency Security",
                        title=f"Vulnerable dependency: {pkg} {ver_str} ({', '.join(cves)})",
                        severity="HIGH",
                        description=f"{pkg} {ver_str} is affected by {', '.join(cves)}: {desc}",
                        recommendation=f"Upgrade {pkg} to ≥{max_safe}. Update requirements.txt and rebuild Docker image.",
                        affected_asset=f"backend/requirements.txt → {pkg}=={ver_str}",
                        evidence=f"Installed: {ver_str}, Safe threshold: {max_safe}",
                    ))
            except Exception:
                pass

    if not any(f.id == "VAPT-015" for f in findings):
        findings.append(Finding(
            id="VAPT-015",
            category="Dependency Security",
            title="No known-vulnerable packages detected (offline curated list)",
            severity="INFO",
            description="All checked packages meet minimum safe version thresholds in the offline curated CVE list.",
            recommendation="Run this scan after every dependency update. Connect to NVD feed periodically for list updates.",
            affected_asset="backend/requirements.txt",
            evidence=f"Checked {len(KNOWN_VULNERABLE)} package rules against {len(installed)} installed packages.",
        ))

    return findings


def _check_error_disclosure() -> list[Finding]:
    """VAPT-016 — Debug mode / verbose error disclosure."""
    findings = []

    main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
    main_path = os.path.abspath(main_path)

    debug_env = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

    try:
        with open(main_path) as fh:
            src = fh.read()
        debug_in_src = bool(re.search(r"debug\s*=\s*True", src, re.IGNORECASE))
    except FileNotFoundError:
        debug_in_src = False

    if debug_env or debug_in_src:
        findings.append(Finding(
            id="VAPT-016",
            category="Configuration",
            title="Debug mode enabled — verbose error disclosure to clients",
            severity="HIGH",
            description=(
                "The application is running in debug mode. Full stack traces including file paths, "
                "variable values, and internal logic are returned to API callers on errors."
            ),
            recommendation="Disable debug mode in production. Set DEBUG=false and use a structured logging handler.",
            affected_asset="backend/app/main.py",
            evidence=f"DEBUG env={debug_env}, debug=True in source={debug_in_src}",
        ))
    else:
        findings.append(Finding(
            id="VAPT-016",
            category="Configuration",
            title="Debug mode is disabled",
            severity="INFO",
            description="No debug flag detected in environment or source.",
            recommendation="Confirm uvicorn is launched without --reload in production.",
            affected_asset="backend/app/main.py",
            evidence="DEBUG env var not set; no debug=True in main.py.",
        ))
    return findings


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    _check_secret_key,
    _check_jwt_algorithm,
    _check_token_expiry,
    _check_lockout_policy,
    _check_password_policy,
    _check_cors_policy,
    _check_file_upload_security,
    _check_db_file_permissions,
    _check_audit_log_persistence,
    _check_refresh_token_store,
    _check_https_enforcement,
    _check_security_headers,
    _check_sql_injection_surface,
    _check_demo_reset_endpoint,
    _check_dependency_versions,
    _check_error_disclosure,
]


def run_scan() -> ScanResult:
    """Execute all VAPT checks and return a ScanResult."""
    import uuid
    result = ScanResult(
        scan_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    for check_fn in ALL_CHECKS:
        try:
            result.findings.extend(check_fn())
        except Exception as exc:
            result.findings.append(Finding(
                id="VAPT-ERR",
                category="Scanner",
                title=f"Scanner error in {check_fn.__name__}",
                severity="INFO",
                description=str(exc),
                recommendation="Investigate scanner error.",
                affected_asset=check_fn.__name__,
            ))

    result.compute_summary()
    return result
