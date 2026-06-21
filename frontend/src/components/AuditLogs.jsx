import { useState, useEffect } from "react";
import { apiFetch } from "../auth";

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch("/api/auth/audit-logs")
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : "Failed to load secure audit logs."
          );
        }
        setLogs(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load secure audit logs.");
        setLoading(false);
      });
  }, []);

  const getStatusStyle = (status) => {
    if (status === "SUCCESS") {
      return {
        background: "hsla(142, 70%, 45%, 0.15)",
        borderColor: "hsl(142, 70%, 50%)",
        color: "hsl(142, 75%, 70%)"
      };
    }
    if (status === "FAILED") {
      return {
        background: "hsla(350, 70%, 50%, 0.15)",
        borderColor: "hsl(350, 70%, 55%)",
        color: "hsl(350, 75%, 72%)"
      };
    }
    return {
      background: "hsla(45, 70%, 50%, 0.15)",
      borderColor: "hsl(45, 70%, 50%)",
      color: "hsl(45, 75%, 70%)"
    };
  };

  return (
    <div style={{ marginTop: "20px", animation: "fadeIn 0.5s ease-out" }}>
      <div style={{ marginBottom: "24px" }}>
        <h2 className="title-gradient" style={{ fontSize: "1.8rem", marginBottom: "6px" }}>Login Audit Logs</h2>
        <p className="subtitle" style={{ fontSize: "0.95rem", margin: 0 }}>
          Real-time record of all system access attempts — restricted to Administrator role.
        </p>
      </div>

      {loading && (
        <div style={{ display: "flex", gap: "10px", alignItems: "center", color: "var(--text-secondary)" }}>
          <div className="spinner"></div> Loading system records...
        </div>
      )}
      
      {error && (
        <div style={{
          padding: "16px",
          borderRadius: "12px",
          background: "rgba(244, 63, 94, 0.15)",
          border: "1px solid rgb(244, 63, 94)",
          color: "rgb(251, 113, 133)",
        }}>
          {error}
        </div>
      )}

      {!loading && !error && logs.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>No login attempts recorded yet.</p>
      )}

      {!loading && logs.length > 0 && (
        <div style={{ overflowX: "auto", borderRadius: "16px", border: "1px solid var(--card-border)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem", background: "hsla(228, 20%, 18%, 0.2)" }}>
            <thead>
              <tr style={{ background: "hsla(228, 20%, 10%, 0.6)", borderBottom: "1px solid var(--card-border)" }}>
                <th style={th}>Index</th>
                <th style={th}>Username</th>
                <th style={th}>Role Scope</th>
                <th style={th}>IP Address</th>
                <th style={th}>Access Time (UTC)</th>
                <th style={th}>Audit Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => {
                const badgeStyle = getStatusStyle(log.status);
                return (
                  <tr key={idx} style={{ 
                    borderBottom: "1px solid var(--card-border)", 
                    background: idx % 2 === 0 ? "hsla(228, 20%, 14%, 0.2)" : "transparent",
                    transition: "background 0.2s ease"
                  }} className="audit-row">
                    <td style={td}>{logs.length - idx}</td>
                    <td style={{ ...td, fontWeight: 600 }}>{log.username}</td>
                    <td style={{ ...td, textTransform: "capitalize", color: "var(--text-secondary)" }}>{log.role}</td>
                    <td style={{ ...td, fontFamily: "monospace", color: "var(--accent-cyan)" }}>{log.ip_address}</td>
                    <td style={{ ...td, color: "var(--text-muted)" }}>{log.timestamp}</td>
                    <td style={td}>
                      <span style={{ 
                        padding: "4px 12px", 
                        borderRadius: "20px", 
                        fontSize: "0.75rem",
                        fontWeight: 700, 
                        letterSpacing: "0.5px",
                        background: badgeStyle.background, 
                        color: badgeStyle.color,
                        border: `1px solid ${badgeStyle.borderColor}`,
                        display: "inline-block"
                      }}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!loading && logs.length > 0 && (
        <p style={{ marginTop: "12px", fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "right" }}>
          Showing {logs.length} entries — chronologically descending
        </p>
      )}
    </div>
  );
}

const th = { 
  padding: "16px 20px", 
  textAlign: "left", 
  fontWeight: 600, 
  fontSize: "0.85rem", 
  color: "var(--text-secondary)",
  textTransform: "uppercase",
  letterSpacing: "0.5px"
};

const td = { 
  padding: "14px 20px", 
  color: "var(--text-primary)" 
};
