import { useState } from "react";
import { apiFetch, formatApiError } from "../auth";

// ─── Severity colours ────────────────────────────────────────────────────────
const SEV_COLOR = {
  CRITICAL: { text: "hsl(350, 85%, 68%)", bg: "rgba(220,38,38,0.12)", border: "hsl(350,75%,50%)" },
  HIGH:     { text: "hsl(30,  95%, 65%)", bg: "rgba(234,88,12,0.12)",  border: "hsl(30, 85%,50%)" },
  MEDIUM:   { text: "hsl(45,  95%, 62%)", bg: "rgba(202,138,4,0.12)",  border: "hsl(45, 85%,48%)" },
  LOW:      { text: "hsl(195,85%, 60%)", bg: "rgba(6,182,212,0.10)",   border: "hsl(195,75%,45%)" },
  INFO:     { text: "var(--text-secondary)", bg: "rgba(100,116,139,0.10)", border: "var(--card-border)" },
};

const STATUS_COLOR = {
  PASS:  { text: "var(--status-pass-text)",  bg: "var(--status-pass-bg)",  border: "var(--status-pass-border)" },
  FAIL:  { text: "var(--status-fail-text)",  bg: "var(--status-fail-bg)",  border: "var(--status-fail-border)" },
  SKIP:  { text: "var(--text-secondary)",    bg: "rgba(100,116,139,0.10)", border: "var(--card-border)" },
  ERROR: { text: "hsl(30,95%,65%)",          bg: "rgba(234,88,12,0.12)",   border: "hsl(30,85%,50%)" },
};

const cardStyle = {
  background: "hsla(228, 20%, 14%, 0.55)",
  border: "1px solid var(--card-border)",
  borderRadius: "16px",
  padding: "22px 24px",
  backdropFilter: "blur(8px)",
};

const badgeStyle = (colorObj) => ({
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "6px",
  fontSize: "0.7rem",
  fontWeight: 700,
  letterSpacing: "0.4px",
  background: colorObj.bg,
  color: colorObj.text,
  border: `1px solid ${colorObj.border}`,
});

// ─── Risk score ring ─────────────────────────────────────────────────────────
function ScoreRing({ score, label, color }) {
  const r = 34;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div style={{ textAlign: "center" }}>
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="hsla(228,20%,25%,0.4)" strokeWidth="7" />
        <circle
          cx="44" cy="44" r={r} fill="none"
          stroke={color} strokeWidth="7"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 44 44)"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
        <text x="44" y="48" textAnchor="middle" fontSize="16" fontWeight="700" fill={color}>{score}</text>
      </svg>
      <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "-4px" }}>{label}</div>
    </div>
  );
}

// ─── Finding row ─────────────────────────────────────────────────────────────
function FindingRow({ f, expanded, onToggle }) {
  const c = SEV_COLOR[f.severity] || SEV_COLOR.INFO;
  return (
    <div style={{ borderBottom: "1px solid var(--card-border)", cursor: "pointer" }} onClick={onToggle}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px 12px" }}>
        <span style={badgeStyle(c)}>{f.severity}</span>
        <span style={{ flex: 1, fontSize: "0.85rem", fontWeight: 500, color: "var(--text-primary)" }}>
          [{f.id}] {f.title}
        </span>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{f.category}</span>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: 4 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div style={{ padding: "0 12px 14px 12px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.55 }}>
            {f.description}
          </div>
          {f.affected_asset && (
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
              <strong style={{ color: "var(--text-secondary)" }}>Asset:</strong> <code style={{ fontFamily: "monospace" }}>{f.affected_asset}</code>
            </div>
          )}
          {f.evidence && (
            <div style={{ fontSize: "0.78rem", fontFamily: "monospace", background: "hsla(228,20%,10%,0.6)", padding: "6px 10px", borderRadius: "6px", color: "var(--text-muted)", wordBreak: "break-all" }}>
              {f.evidence}
            </div>
          )}
          <div style={{ fontSize: "0.78rem", color: "hsl(195,85%,60%)", borderLeft: "2px solid hsl(195,75%,45%)", paddingLeft: "8px", lineHeight: 1.5 }}>
            <strong>Recommendation:</strong> {f.recommendation}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Pen test row ─────────────────────────────────────────────────────────────
function PenTestRow({ r: res }) {
  const [open, setOpen] = useState(false);
  const c = STATUS_COLOR[res.status] || STATUS_COLOR.SKIP;
  return (
    <div style={{ borderBottom: "1px solid var(--card-border)", cursor: "pointer" }} onClick={() => setOpen(!open)}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px 12px" }}>
        <span style={badgeStyle(c)}>{res.status}</span>
        <span style={{ flex: 1, fontSize: "0.85rem", fontWeight: 500, color: "var(--text-primary)" }}>
          [{res.id}] {res.name}
        </span>
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{res.duration_ms}ms</span>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: 4 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 12px 14px 12px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{res.description}</div>
          {res.evidence && (
            <div style={{ fontSize: "0.78rem", fontFamily: "monospace", background: "hsla(228,20%,10%,0.6)", padding: "6px 10px", borderRadius: "6px", color: "var(--text-muted)", wordBreak: "break-all" }}>
              {res.evidence}
            </div>
          )}
          {res.recommendation && (
            <div style={{ fontSize: "0.78rem", color: "hsl(195,85%,60%)", borderLeft: "2px solid hsl(195,75%,45%)", paddingLeft: "8px" }}>
              <strong>Recommendation:</strong> {res.recommendation}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function VaptDashboard() {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [hardening, setHardening]   = useState(false);
  const [hardenResult, setHardenResult] = useState(null);
  const [hardenError, setHardenError]   = useState(null);
  const [activeSevFilter, setActiveSevFilter] = useState("ALL");

  const runReport = () => {
    setLoading(true);
    setError(null);
    setReportData(null);
    setHardenResult(null);
    setHardenError(null);
    apiFetch("/api/vapt/report")
      .then(async (res) => {
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(json, "VAPT scan failed"));
        return json;
      })
      .then(setReportData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const runHarden = () => {
    if (!window.confirm(
      "Apply automated hardening patches to the backend source files?\n\n" +
      "This will modify main.py, upload.py, and checksheet.py in place. " +
      "A backend restart is required afterwards."
    )) return;
    setHardening(true);
    setHardenResult(null);
    setHardenError(null);
    apiFetch("/api/vapt/harden", { method: "POST" })
      .then(async (res) => {
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(json, "Hardening failed"));
        return json;
      })
      .then(setHardenResult)
      .catch((e) => setHardenError(e.message))
      .finally(() => setHardening(false));
  };

  // ── Empty / loading states ──────────────────────────────────────────────
  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "400px", gap: 16, color: "var(--text-secondary)" }}>
      <div className="spinner" style={{ width: 38, height: 38, borderWidth: 3 }} />
      Running VAPT scan and penetration tests — this may take 15-30 seconds...
    </div>
  );

  // ── Landing (no data yet) ─────────────────────────────────────────────────
  if (!reportData) return (
    <div style={{ marginTop: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
      <div>
        <h2 className="title-gradient" style={{ fontSize: "1.7rem", marginBottom: "4px" }}>
          Security Assessment
        </h2>
        <p className="subtitle" style={{ fontSize: "0.92rem", margin: 0 }}>
          Vulnerability scan + active pen tests against the running backend.
          Results are restricted to admin and never stored on disk.
        </p>
      </div>

      {error && (
        <div style={{ padding: "14px 18px", borderRadius: "12px", background: "rgba(244,63,94,0.1)", border: "1px solid rgb(244,63,94)", color: "rgb(251,113,133)", fontSize: "0.9rem" }}>
          {error}
        </div>
      )}

      <div style={{ ...cardStyle, display: "flex", flexDirection: "column", alignItems: "center", gap: "20px", padding: "48px 40px", textAlign: "center" }}>
        <div style={{ fontSize: "0.95rem", color: "var(--text-secondary)", maxWidth: 520, lineHeight: 1.6 }}>
          Runs 15 static vulnerability checks (JWT, passwords, CORS, file upload, DB permissions, CVE scan)
          and 8 active pen test scenarios (brute-force, SQL injection, JWT tampering, IDOR, path traversal, role escalation, CORS, unauth access).
        </div>
        <button
          onClick={runReport}
          className="btn btn-primary"
          style={{ padding: "10px 28px", borderRadius: "10px", fontSize: "0.9rem", fontWeight: 600 }}
        >
          Run Full VAPT Report
        </button>
      </div>
    </div>
  );

  // ── Report view ────────────────────────────────────────────────────────────
  const { executive_summary: exec, vulnerability_assessment: va, penetration_tests: pt, remediation_priority } = reportData;
  const riskColors = { CRITICAL: "hsl(350,85%,68%)", HIGH: "hsl(30,95%,65%)", MEDIUM: "hsl(45,95%,62%)", LOW: "hsl(195,85%,60%)" };
  const riskColor = riskColors[exec.overall_risk] || "var(--text-secondary)";

  const sevOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];
  const findings = va.findings || [];
  const filteredFindings = activeSevFilter === "ALL" ? findings : findings.filter(f => f.severity === activeSevFilter);
  const sevCounts = sevOrder.reduce((acc, s) => { acc[s] = findings.filter(f => f.severity === s).length; return acc; }, {});

  return (
    <div style={{ marginTop: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>

      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 className="title-gradient" style={{ fontSize: "1.7rem", marginBottom: "4px" }}>Security Assessment Report</h2>
          <p className="subtitle" style={{ fontSize: "0.85rem", margin: 0 }}>
            {new Date(reportData.timestamp).toLocaleString()} &nbsp;|&nbsp; {reportData.classification}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={runReport} className="btn btn-primary"
            style={{ padding: "7px 16px", borderRadius: "9px", fontSize: "0.82rem", background: "hsla(228,20%,25%,0.5)", border: "1px solid var(--card-border)", color: "var(--text-primary)" }}>
            Re-run Scan
          </button>
          <button onClick={runHarden} disabled={hardening} className="btn btn-primary"
            style={{ padding: "7px 16px", borderRadius: "9px", fontSize: "0.82rem", background: "hsla(350,70%,20%,0.5)", border: "1px solid hsl(350,60%,40%)", color: "hsl(350,85%,75%)" }}>
            {hardening ? "Applying..." : "Apply Hardening Patches"}
          </button>
        </div>
      </div>

      {/* Harden result banner */}
      {hardenResult && (
        <div style={{ padding: "12px 18px", borderRadius: "10px", background: "rgba(22,163,74,0.1)", border: "1px solid hsl(142,60%,40%)", fontSize: "0.85rem", color: "var(--status-pass-text)" }}>
          {hardenResult.patches_applied} patch(es) applied, {hardenResult.patches_skipped} skipped.
          {hardenResult.results.map((r, i) => (
            <div key={i} style={{ marginTop: 4, fontFamily: "monospace", fontSize: "0.78rem" }}>
              [{r.patch_id}] {r.applied ? "APPLIED" : "SKIPPED"} — {r.message}
            </div>
          ))}
          <div style={{ marginTop: 6, color: "var(--text-secondary)", fontSize: "0.78rem" }}>{hardenResult.note}</div>
        </div>
      )}
      {hardenError && (
        <div style={{ padding: "12px 18px", borderRadius: "10px", background: "rgba(244,63,94,0.1)", border: "1px solid rgb(244,63,94)", fontSize: "0.85rem", color: "rgb(251,113,133)" }}>
          Hardening error: {hardenError}
        </div>
      )}

      {/* Executive summary scores */}
      <div style={{ ...cardStyle, display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-muted)", marginBottom: 4 }}>Overall Risk</div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: riskColor }}>{exec.overall_risk}</div>
        </div>
        <ScoreRing score={exec.vulnerability_risk_score} label="Vuln Risk Score" color={riskColor} />
        <ScoreRing score={exec.pentest_security_score} label="Pentest Score" color="hsl(195,85%,60%)" />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px", fontSize: "0.82rem" }}>
          {[
            ["Critical", exec.critical_findings, "hsl(350,85%,68%)"],
            ["High",     exec.high_findings,     "hsl(30,95%,65%)"],
            ["Medium",   exec.medium_findings,   "hsl(45,95%,62%)"],
            ["Low",      exec.low_findings,      "hsl(195,85%,60%)"],
            ["PT Pass",  exec.pentest_passed,    "var(--status-pass-text)"],
            ["PT Fail",  exec.pentest_failed,    "var(--status-fail-text)"],
          ].map(([label, val, color]) => (
            <div key={label}>
              <span style={{ color: "var(--text-muted)" }}>{label}: </span>
              <strong style={{ color }}>{val}</strong>
            </div>
          ))}
        </div>
      </div>

      {/* Vulnerability findings */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
            Vulnerability Findings
            <span style={{ marginLeft: 10, fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 400 }}>
              {va.summary.total} total
            </span>
          </h3>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {["ALL", ...sevOrder].map(s => {
              const active = activeSevFilter === s;
              const c = SEV_COLOR[s] || { text: "var(--text-secondary)", bg: "transparent", border: "var(--card-border)" };
              return (
                <button key={s} onClick={() => setActiveSevFilter(s)} style={{
                  padding: "3px 10px", borderRadius: 6, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
                  background: active ? (c.bg || "hsla(228,20%,25%,0.5)") : "transparent",
                  color: active ? (c.text || "var(--text-primary)") : "var(--text-muted)",
                  border: `1px solid ${active ? (c.border || "var(--card-border)") : "transparent"}`,
                  transition: "all 0.15s ease",
                }}>
                  {s}{s !== "ALL" && sevCounts[s] !== undefined ? ` (${sevCounts[s]})` : ""}
                </button>
              );
            })}
          </div>
        </div>
        <div style={{ borderRadius: "10px", overflow: "hidden", border: "1px solid var(--card-border)" }}>
          {filteredFindings.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
              No findings for selected filter.
            </div>
          ) : (
            filteredFindings.map(f => (
              <FindingRow
                key={f.id}
                f={f}
                expanded={expandedId === f.id}
                onToggle={() => setExpandedId(expandedId === f.id ? null : f.id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Penetration test results */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 14px 0" }}>
          Penetration Test Results
          <span style={{ marginLeft: 10, fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 400 }}>
            {pt.summary.total} tests &nbsp;|&nbsp;
            <span style={{ color: "var(--status-pass-text)" }}>{pt.summary.by_status.PASS} pass</span> &nbsp;|&nbsp;
            <span style={{ color: "var(--status-fail-text)" }}>{pt.summary.by_status.FAIL} fail</span>
          </span>
        </h3>
        <div style={{ borderRadius: "10px", overflow: "hidden", border: "1px solid var(--card-border)" }}>
          {pt.results.map(r => <PenTestRow key={r.id + r.name} r={r} />)}
        </div>
      </div>

      {/* Remediation priority action plan */}
      {remediation_priority && remediation_priority.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 14px 0" }}>
            Remediation Priority Action Plan
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {remediation_priority.map(item => {
              const c = SEV_COLOR[item.severity] || SEV_COLOR.INFO;
              return (
                <div key={item.priority} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "10px 12px", borderRadius: 10, background: "hsla(228,20%,10%,0.4)", border: "1px solid var(--card-border)" }}>
                  <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", minWidth: 24, paddingTop: 2 }}>#{item.priority}</div>
                  <span style={badgeStyle(c)}>{item.severity}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>[{item.id}] {item.title}</div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 2 }}>{item.affected_asset}</div>
                    <div style={{ fontSize: "0.78rem", color: "hsl(195,85%,60%)", marginTop: 4, lineHeight: 1.5 }}>{item.recommendation}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
