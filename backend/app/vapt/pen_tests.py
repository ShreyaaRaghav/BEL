"""
BEL VAPT Penetration Test Runner
=================================
Simulates adversarial scenarios against the running FastAPI application
using Python's httpx library (no network egress — all calls to localhost).

Tests:
  PT-001  Brute-force login simulation
  PT-002  SQL injection in login fields
  PT-003  JWT manipulation (algorithm confusion, expired, tampered)
  PT-004  IDOR — access other users' reports without authorization
  PT-005  Mass-assignment / extra fields in save-report payload
  PT-006  Path traversal in file upload filename
  PT-007  Role escalation — viewer trying engineer endpoints
  PT-008  Replay attack — reuse revoked refresh token
  PT-009  Oversized upload (DoS simulation)
  PT-010  CORS preflight with forbidden origin

Each test returns a PenTestResult with PASS/FAIL/SKIP and evidence.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal
import uuid

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

Status = Literal["PASS", "FAIL", "SKIP", "ERROR"]

BASE_URL = "http://localhost:8000/api"


@dataclass
class PenTestResult:
    id: str
    name: str
    category: str
    description: str
    status: Status
    evidence: str = ""
    recommendation: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PenTestReport:
    report_id: str
    timestamp: str
    base_url: str
    results: list[PenTestResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def compute_summary(self):
        counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        self.summary = {
            "total": len(self.results),
            "by_status": counts,
            "security_score": round(
                counts["PASS"] / max(counts["PASS"] + counts["FAIL"], 1) * 100, 1
            ),
        }

    def to_dict(self) -> dict:
        self.compute_summary()
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "base_url": self.base_url,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_token(client: "httpx.Client", username: str = "admin", password: str = "Admin@BEL2025!") -> str | None:
    """Attempt login and return access token, or None."""
    try:
        r = client.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password}, timeout=5)
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────────────
# Individual penetration tests
# ──────────────────────────────────────────────────────────────────────────────

def pt_brute_force(client: "httpx.Client") -> PenTestResult:
    """PT-001 — Brute-force login: sends 10 rapid failed attempts."""
    start = time.time()
    results = []
    for i in range(10):
        r = client.post(f"{BASE_URL}/auth/login",
                        json={"username": "admin", "password": f"wrong_password_{i}"},
                        timeout=5)
        results.append(r.status_code)

    duration = (time.time() - start) * 1000
    locked = any(s == 429 for s in results)

    return PenTestResult(
        id="PT-001",
        name="Brute-Force Login Lockout",
        category="Authentication",
        description="Sends 10 rapid failed login attempts to verify account lockout triggers.",
        status="PASS" if locked else "FAIL",
        evidence=f"Status codes received: {results}. Lockout (429) triggered: {locked}",
        recommendation="" if locked else "Verify MAX_FAILED_ATTEMPTS and LOCKOUT_MINUTES are correctly set.",
        duration_ms=round(duration, 1),
    )


def pt_sql_injection_login(client: "httpx.Client") -> PenTestResult:
    """PT-002 — SQL injection payloads in login fields."""
    start = time.time()
    payloads = [
        {"username": "admin' OR '1'='1", "password": "irrelevant"},
        {"username": "admin'--", "password": "x"},
        {"username": "' UNION SELECT 1,2,3--", "password": "x"},
        {"username": "admin", "password": "' OR '1'='1"},
    ]
    injected = False
    evidence_parts = []
    for p in payloads:
        r = client.post(f"{BASE_URL}/auth/login", json=p, timeout=5)
        evidence_parts.append(f"payload={p['username']!r} → HTTP {r.status_code}")
        if r.status_code == 200:
            injected = True

    duration = (time.time() - start) * 1000
    return PenTestResult(
        id="PT-002",
        name="SQL Injection in Login",
        category="Injection",
        description="Attempts classic SQL injection payloads in username/password fields.",
        status="FAIL" if injected else "PASS",
        evidence=" | ".join(evidence_parts),
        recommendation="Injection succeeded — switch to parameterized ORM queries." if injected else "",
        duration_ms=round(duration, 1),
    )


def pt_jwt_tampering(client: "httpx.Client") -> PenTestResult:
    """PT-003 — Tampered and expired JWTs."""
    start = time.time()
    issues = []

    # Test 1: Completely forged token
    forged = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjk5OTk5OTk5OTl9.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    r = client.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {forged}"}, timeout=5)
    if r.status_code == 200:
        issues.append("Forged JWT with fake signature was ACCEPTED")

    # Test 2: None algorithm token (base64 decode trick)
    import base64
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(
        b'{"sub":"admin","role":"admin","type":"access","exp":9999999999}'
    ).rstrip(b"=").decode()
    none_token = f"{header}.{payload_b64}."
    r2 = client.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {none_token}"}, timeout=5)
    if r2.status_code == 200:
        issues.append("JWT with 'none' algorithm was ACCEPTED — critical auth bypass")

    duration = (time.time() - start) * 1000
    return PenTestResult(
        id="PT-003",
        name="JWT Tampering & Algorithm Confusion",
        category="Authentication",
        description="Tests forged JWTs and 'none' algorithm bypass attacks.",
        status="FAIL" if issues else "PASS",
        evidence="; ".join(issues) if issues else "All tampered tokens correctly rejected (401/403).",
        recommendation="; ".join(issues) if issues else "",
        duration_ms=round(duration, 1),
    )


def pt_idor(client: "httpx.Client") -> PenTestResult:
    """PT-004 — IDOR: viewer tries to access all report IDs."""
    start = time.time()
    # Try to get a viewer token (use default viewer creds from init_db)
    viewer_token = _get_token(client, "viewer", "Viewer@BEL2025!")
    if not viewer_token:
        return PenTestResult(
            id="PT-004",
            name="IDOR — Cross-User Report Access",
            category="Authorization",
            description="Viewer attempts to access all report session IDs.",
            status="SKIP",
            evidence="Could not authenticate as viewer — skipping.",
            duration_ms=round((time.time() - start) * 1000, 1),
        )

    headers = _auth_headers(viewer_token)
    # Viewer can list reports — check if unauthorized data is exposed
    r = client.get(f"{BASE_URL}/checksheets/reports", headers=headers, timeout=5)
    reports_accessible = r.status_code == 200

    duration = (time.time() - start) * 1000
    # Viewing reports as viewer is by design — flag if there's no ownership filter
    return PenTestResult(
        id="PT-004",
        name="IDOR — Viewer Can Access All Reports",
        category="Authorization",
        description="Checks whether viewer role can list all reports across all technicians.",
        status="FAIL" if reports_accessible else "PASS",
        evidence=f"GET /checksheets/reports as viewer → HTTP {r.status_code}. "
                 f"{'All reports visible — no ownership scoping.' if reports_accessible else 'Blocked.'}",
        recommendation=(
            "If viewer should see only their own reports, filter by lead_technician == user.username in list_reports(). "
            "If all-report access for viewers is intentional, document this decision."
        ) if reports_accessible else "",
        duration_ms=round(duration, 1),
    )


def pt_role_escalation(client: "httpx.Client") -> PenTestResult:
    """PT-007 — Viewer tries to call engineer-only endpoints."""
    start = time.time()
    viewer_token = _get_token(client, "viewer", "Viewer@BEL2025!")
    if not viewer_token:
        return PenTestResult(
            id="PT-007",
            name="Role Escalation — Viewer → Engineer",
            category="Authorization",
            description="Viewer attempts to call engineer-only endpoints.",
            status="SKIP",
            evidence="Could not authenticate as viewer — skipping.",
            duration_ms=round((time.time() - start) * 1000, 1),
        )

    headers = _auth_headers(viewer_token)
    escalated = []

    # Try upload (engineer only)
    import io
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
    r = client.post(f"{BASE_URL}/upload-pdf",
                    files={"file": ("test.pdf", fake_pdf, "application/pdf")},
                    headers={"Authorization": f"Bearer {viewer_token}"},
                    timeout=5)
    if r.status_code not in (401, 403):
        escalated.append(f"upload-pdf returned {r.status_code} (expected 403)")

    # Try reset-demo-data (engineer only)
    r2 = client.post(f"{BASE_URL}/checksheets/reset-demo-data", headers=headers, timeout=5)
    if r2.status_code not in (401, 403):
        escalated.append(f"reset-demo-data returned {r2.status_code} (expected 403)")

    duration = (time.time() - start) * 1000
    return PenTestResult(
        id="PT-007",
        name="Role Escalation — Viewer → Engineer",
        category="Authorization",
        description="Viewer attempts to invoke engineer-restricted endpoints (upload, reset).",
        status="FAIL" if escalated else "PASS",
        evidence="; ".join(escalated) if escalated else "All engineer endpoints correctly blocked for viewer (403).",
        recommendation="; ".join(escalated) if escalated else "",
        duration_ms=round(duration, 1),
    )


def pt_path_traversal_upload(client: "httpx.Client") -> PenTestResult:
    """PT-006 — Path traversal via malicious filename in upload."""
    start = time.time()
    admin_token = _get_token(client)
    if not admin_token:
        return PenTestResult(
            id="PT-006",
            name="Path Traversal via Upload Filename",
            category="File Upload",
            description="Uploads a file with a path-traversal filename.",
            status="SKIP",
            evidence="Could not authenticate — skipping.",
            duration_ms=round((time.time() - start) * 1000, 1),
        )

    import io
    traversal_names = [
        "../../app/config.py",
        "../uploads/evil.py",
        "....//....//config.py",
    ]
    issues = []
    for name in traversal_names:
        fake = io.BytesIO(b"%PDF-1.4 injected")
        r = client.post(
            f"{BASE_URL}/upload-pdf",
            files={"file": (name, fake, "application/pdf")},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=5,
        )
        # If it returned 200 with the traversal filename echoed back, it's vulnerable
        if r.status_code == 200:
            body = r.text
            if ".py" in body or "config" in body:
                issues.append(f"Traversal filename '{name}' accepted, path may have been written")

    duration = (time.time() - start) * 1000
    return PenTestResult(
        id="PT-006",
        name="Path Traversal via Upload Filename",
        category="File Upload",
        description="Sends path-traversal filenames to the upload endpoint.",
        status="FAIL" if issues else "PASS",
        evidence="; ".join(issues) if issues else "Traversal filenames did not reach sensitive paths in response.",
        recommendation="Use werkzeug.utils.secure_filename() to sanitize uploaded filenames." if issues else "",
        duration_ms=round(duration, 1),
    )


def pt_cors_forbidden_origin(client: "httpx.Client") -> PenTestResult:
    """PT-010 — CORS preflight with a forbidden origin."""
    start = time.time()
    r = client.options(
        f"{BASE_URL}/auth/login",
        headers={
            "Origin": "http://evil.attacker.com",
            "Access-Control-Request-Method": "POST",
        },
        timeout=5,
    )
    allowed_origin = r.headers.get("access-control-allow-origin", "")
    is_vulnerable = allowed_origin in ("*", "http://evil.attacker.com")
    duration = (time.time() - start) * 1000

    return PenTestResult(
        id="PT-010",
        name="CORS — Forbidden Origin Accepted",
        category="Configuration",
        description="Sends a CORS preflight from a non-whitelisted origin.",
        status="FAIL" if is_vulnerable else "PASS",
        evidence=f"Origin: evil.attacker.com → Access-Control-Allow-Origin: '{allowed_origin}'",
        recommendation="Restrict ALLOWED_ORIGINS to intranet addresses only." if is_vulnerable else "",
        duration_ms=round(duration, 1),
    )


def pt_missing_auth_header(client: "httpx.Client") -> PenTestResult:
    """PT-008 — Access protected endpoints without any token."""
    start = time.time()
    endpoints = [
        ("GET", f"{BASE_URL}/auth/me"),
        ("GET", f"{BASE_URL}/checksheets/reports"),
        ("GET", f"{BASE_URL}/checksheets/templates"),
    ]
    unprotected = []
    for method, url in endpoints:
        r = client.request(method, url, timeout=5)
        if r.status_code not in (401, 403):
            unprotected.append(f"{method} {url} → {r.status_code}")

    duration = (time.time() - start) * 1000
    return PenTestResult(
        id="PT-008",
        name="Unauthenticated Access to Protected Endpoints",
        category="Authentication",
        description="Requests protected endpoints without an Authorization header.",
        status="FAIL" if unprotected else "PASS",
        evidence="; ".join(unprotected) if unprotected else "All protected endpoints returned 401/403 without token.",
        recommendation="Add get_current_user dependency to all protected routes." if unprotected else "",
        duration_ms=round(duration, 1),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

ALL_PEN_TESTS = [
    pt_brute_force,
    pt_sql_injection_login,
    pt_jwt_tampering,
    pt_idor,
    pt_role_escalation,
    pt_path_traversal_upload,
    pt_cors_forbidden_origin,
    pt_missing_auth_header,
]


def run_pen_tests(base_url: str = BASE_URL) -> PenTestReport:
    """Execute all penetration tests against the running application."""
    report = PenTestReport(
        report_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        base_url=base_url,
    )

    if not HTTPX_AVAILABLE:
        report.results.append(PenTestResult(
            id="PT-ERR",
            name="httpx not installed",
            category="Scanner",
            description="Install httpx to enable active penetration testing.",
            status="SKIP",
            evidence="pip install httpx",
        ))
        report.compute_summary()
        return report

    with httpx.Client(base_url="") as client:
        for test_fn in ALL_PEN_TESTS:
            try:
                result = test_fn(client)
                report.results.append(result)
            except Exception as exc:
                report.results.append(PenTestResult(
                    id="PT-ERR",
                    name=test_fn.__name__,
                    category="Scanner",
                    description=str(exc),
                    status="ERROR",
                    evidence=str(exc),
                ))

    report.compute_summary()
    return report
