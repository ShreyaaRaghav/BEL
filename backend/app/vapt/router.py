"""
BEL VAPT API Router
====================
Exposes VAPT scan and penetration test results as secured API endpoints.

All endpoints require admin role — VAPT data is sensitive operational information.

Endpoints:
  GET  /api/vapt/scan           — Run static vulnerability assessment
  GET  /api/vapt/pentest        — Run active penetration tests (against localhost)
  POST /api/vapt/harden         — Apply automated hardening patches
  GET  /api/vapt/report         — Full combined report (scan + pentest summary)
  GET  /api/vapt/history        — Scan history (in-memory, last 20 scans)
"""

from __future__ import annotations
import os
from datetime import datetime, timezone
from collections import deque

from fastapi import APIRouter, Depends, BackgroundTasks
from app.core.rbac import require_role
from app.models.user import User
from app.vapt.scanner import run_scan, ScanResult
from app.vapt.pen_tests import run_pen_tests, PenTestReport
from app.vapt.hardening import apply_all_patches

router = APIRouter(prefix="/vapt", tags=["VAPT — Security Assessment"])

# In-memory circular history buffer (last 20 scan results)
_scan_history: deque[dict] = deque(maxlen=20)
_pentest_history: deque[dict] = deque(maxlen=10)


def _base_dir() -> str:
    """Locate the BEL project root from the vapt package location."""
    # backend/app/vapt/ → backend/app/ → backend/ → BEL-main/
    this_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(this_dir, "..", "..", ".."))


# ──────────────────────────────────────────────────────────────────────────────
# Vulnerability Assessment Scan
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/scan",
    summary="Run Vulnerability Assessment Scan",
    description=(
        "Executes the full static vulnerability assessment against the running system. "
        "Returns findings categorised by severity (CRITICAL / HIGH / MEDIUM / LOW / INFO). "
        "**Admin only.**"
    ),
)
def vulnerability_scan(_: User = Depends(require_role("admin"))):
    result: ScanResult = run_scan()
    report_dict = result.to_dict()
    _scan_history.append(report_dict)
    return report_dict


# ──────────────────────────────────────────────────────────────────────────────
# Penetration Test Runner
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/pentest",
    summary="Run Active Penetration Tests",
    description=(
        "Executes active penetration test scenarios against the locally running API "
        "(brute-force, JWT tampering, role escalation, path traversal, CORS, etc). "
        "Tests only target localhost — no external network calls. "
        "**Admin only.**"
    ),
)
def penetration_test(_: User = Depends(require_role("admin"))):
    report: PenTestReport = run_pen_tests()
    report_dict = report.to_dict()
    _pentest_history.append(report_dict)
    return report_dict


# ──────────────────────────────────────────────────────────────────────────────
# Automated Hardening
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/harden",
    summary="Apply Automated Hardening Patches",
    description=(
        "Applies automated remediation patches to the project source files: "
        "security headers middleware, upload validation, reset-endpoint role restriction, "
        "and database file permission hardening. "
        "Patches are idempotent — safe to run multiple times. "
        "A server restart is required for source-file patches to take effect. "
        "**Admin only.**"
    ),
)
def apply_hardening(_: User = Depends(require_role("admin"))):
    base = _base_dir()
    patch_results = apply_all_patches(base)
    applied = [r for r in patch_results if r.applied]
    skipped = [r for r in patch_results if not r.applied]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_directory": base,
        "patches_applied": len(applied),
        "patches_skipped": len(skipped),
        "results": [
            {
                "patch_id": r.patch_id,
                "applied": r.applied,
                "message": r.message,
            }
            for r in patch_results
        ],
        "note": "Restart the backend server for source-file patches to take effect.",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Combined VAPT Report
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/report",
    summary="Full Combined VAPT Report",
    description=(
        "Runs both the vulnerability assessment scan and the penetration test suite "
        "and returns a unified report with executive summary and risk score. "
        "This is the primary endpoint for generating the VAPT report. "
        "**Admin only.**"
    ),
)
def full_vapt_report(_: User = Depends(require_role("admin"))):
    scan: ScanResult = run_scan()
    pentest: PenTestReport = run_pen_tests()

    scan_dict = scan.to_dict()
    pentest_dict = pentest.to_dict()

    # Save to history
    _scan_history.append(scan_dict)
    _pentest_history.append(pentest_dict)

    # Executive summary
    scan_counts = scan_dict["summary"]["by_severity"]
    pentest_counts = pentest_dict["summary"]["by_status"]

    overall_risk = "LOW"
    if scan_counts.get("CRITICAL", 0) > 0 or pentest_counts.get("FAIL", 0) >= 3:
        overall_risk = "CRITICAL"
    elif scan_counts.get("HIGH", 0) > 0 or pentest_counts.get("FAIL", 0) >= 1:
        overall_risk = "HIGH"
    elif scan_counts.get("MEDIUM", 0) > 0:
        overall_risk = "MEDIUM"

    return {
        "report_type": "BEL VAPT Combined Report",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": "Secure Intelligent Digital Checksheet System",
        "classification": "RESTRICTED — BEL Internal Use Only",
        "executive_summary": {
            "overall_risk": overall_risk,
            "vulnerability_risk_score": scan_dict["summary"]["risk_score"],
            "pentest_security_score": pentest_dict["summary"]["security_score"],
            "critical_findings": scan_counts.get("CRITICAL", 0),
            "high_findings": scan_counts.get("HIGH", 0),
            "medium_findings": scan_counts.get("MEDIUM", 0),
            "low_findings": scan_counts.get("LOW", 0),
            "pentest_passed": pentest_counts.get("PASS", 0),
            "pentest_failed": pentest_counts.get("FAIL", 0),
            "pentest_skipped": pentest_counts.get("SKIP", 0),
        },
        "vulnerability_assessment": scan_dict,
        "penetration_tests": pentest_dict,
        "remediation_priority": _prioritized_remediation(scan_dict["findings"]),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Scan History
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/history",
    summary="VAPT Scan History",
    description="Returns metadata of the last 20 vulnerability assessment scans. **Admin only.**",
)
def scan_history(_: User = Depends(require_role("admin"))):
    return {
        "scan_history": [
            {
                "scan_id": s["scan_id"],
                "timestamp": s["timestamp"],
                "total_findings": s["summary"]["total"],
                "risk_score": s["summary"]["risk_score"],
                "critical": s["summary"]["by_severity"].get("CRITICAL", 0),
                "high": s["summary"]["by_severity"].get("HIGH", 0),
            }
            for s in _scan_history
        ],
        "pentest_history": [
            {
                "report_id": p["report_id"],
                "timestamp": p["timestamp"],
                "security_score": p["summary"]["security_score"],
                "failed": p["summary"]["by_status"].get("FAIL", 0),
            }
            for p in _pentest_history
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def _prioritized_remediation(findings: list[dict]) -> list[dict]:
    """Return findings sorted by severity for the remediation action plan."""
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    actionable = [f for f in findings if f["severity"] != "INFO"]
    sorted_findings = sorted(actionable, key=lambda f: severity_order.get(f["severity"], 5))
    return [
        {
            "priority": i + 1,
            "id": f["id"],
            "severity": f["severity"],
            "title": f["title"],
            "affected_asset": f["affected_asset"],
            "recommendation": f["recommendation"],
        }
        for i, f in enumerate(sorted_findings)
    ]
