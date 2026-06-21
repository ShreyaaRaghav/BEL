import { useState, useEffect } from "react";
import Login from "./components/Login";
import UploadPDF from "./components/UploadPDF";
import AuditLogs from "./components/AuditLogs";
import ReportsHistory from "./components/ReportsHistory";
import Dashboard from "./components/Dashboard";
import { logout, tryRestoreSession } from "./auth";

//rbac HAPPENS HERE

const ROLE_COLOR = {
  admin:    { bg: "rgba(44, 123, 229, 0.2)", color: "#d8e8ff", border: "#2c7be5" },
  engineer: { bg: "rgba(81, 183, 255, 0.2)", color: "#d8f2ff", border: "#51b7ff" },
  viewer:   { bg: "rgba(17, 29, 47, 0.75)", color: "#d4dbe7", border: "#5f738f" },
};

const ROLE_DESC = {
  admin:    "Administrator scope — Full cryptographic audit scope, user governance, metrology reviews, and checksheet management.",
  engineer: "Metrology Engineer scope — Authorized to upload blueprint checksheets, run tolerance evaluations, and record inspections.",
  viewer:   "Auditor/Viewer scope — Read-only metrology portal access. Not authorized for uploading or data modifications.",
};

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState("home");

  const [activeChecksheet, setActiveChecksheet] = useState(null);

  useEffect(() => {
    tryRestoreSession()
      .then((u) => {
        if (u) setUser(u);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setPage("home");
  };

  if (loading) {
    return (
      <div style={{ 
        minHeight: "100vh", 
        display: "flex", 
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center", 
        background: "linear-gradient(135deg, hsl(230, 25%, 8%), hsl(235, 30%, 4%))", 
        color: "var(--text-primary)", 
        fontSize: 16,
        fontFamily: "'Outfit', sans-serif",
        gap: "15px"
      }}>
        <div className="spinner" style={{ width: "30px", height: "30px", borderWidth: "3px" }}></div>
        Establishing cryptographically secure session...
      </div>
    );
  }

  if (!user) return <Login onLogin={setUser} />;

  const roleStyle = ROLE_COLOR[user.role] || ROLE_COLOR.viewer;

  return (
    <div style={{ minHeight: "100vh", background: "transparent", fontFamily: "'Outfit', sans-serif" }}>

      {/* Navigation Bar */}
      <nav style={{ 
        background: "hsla(228, 20%, 14%, 0.4)", 
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--card-border)",
        padding: "16px 36px",
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center",
        borderRadius: "0 0 16px 16px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 30 }}>
          <span style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: "1.1rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px" }}
            onClick={() => setPage("home")}>
            BEL Metrology Portal
          </span>
          
          {/* Navigation Tabs */}
          <div style={{ display: "flex", gap: "10px" }}>
            {user.role === "admin" && (
              <button onClick={() => setPage("dashboard")}
                style={{ 
                  background: page === "dashboard" ? "hsla(228, 20%, 25%, 0.5)" : "transparent",
                  border: "1px solid " + (page === "dashboard" ? "var(--card-border)" : "transparent"), 
                  color: page === "dashboard" ? "var(--text-primary)" : "var(--text-secondary)",
                  padding: "6px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13.5, fontWeight: 500,
                  transition: "all 0.2s ease"
                }}>
                Analytics Dashboard
              </button>
            )}
            <button onClick={() => setPage("home")}
              style={{ 
                background: page === "home" ? "hsla(228, 20%, 25%, 0.5)" : "transparent",
                border: "1px solid " + (page === "home" ? "var(--card-border)" : "transparent"), 
                color: page === "home" ? "var(--text-primary)" : "var(--text-secondary)",
                padding: "6px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13.5, fontWeight: 500,
                transition: "all 0.2s ease"
              }}>
              Process Checksheet
            </button>
            <button onClick={() => setPage("history")}
              style={{ 
                background: page === "history" ? "hsla(228, 20%, 25%, 0.5)" : "transparent",
                border: "1px solid " + (page === "history" ? "var(--card-border)" : "transparent"), 
                color: page === "history" ? "var(--text-primary)" : "var(--text-secondary)",
                padding: "6px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13.5, fontWeight: 500,
                transition: "all 0.2s ease"
              }}>
              Saved Reports
            </button>
            {user.role === "admin" && (
              <button onClick={() => setPage("audit")}
                style={{ 
                  background: page === "audit" ? "hsla(228, 20%, 25%, 0.5)" : "transparent",
                  border: "1px solid " + (page === "audit" ? "var(--card-border)" : "transparent"), 
                  color: page === "audit" ? "var(--text-primary)" : "var(--text-secondary)",
                  padding: "6px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13.5, fontWeight: 500,
                  transition: "all 0.2s ease"
                }}>
                Audit Logs
              </button>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <span style={{ color: "var(--text-secondary)", fontSize: 13.5 }}>
            ID: <strong style={{ color: "var(--text-primary)" }}>{user.username}</strong> &nbsp;|&nbsp;
            <span style={{ 
              background: roleStyle.bg, 
              color: roleStyle.color, 
              border: `1px solid ${roleStyle.border}`,
              padding: "2px 8px",
              borderRadius: "6px",
              fontSize: "0.75rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.5px"
            }}>{user.role}</span>
          </span>
          <button onClick={handleLogout}
            style={{ 
              background: "transparent", 
              border: "1px solid var(--card-border)",
              color: "hsl(350, 75%, 72%)", 
              padding: "6px 16px", 
              borderRadius: 8, 
              cursor: "pointer", 
              fontSize: 13,
              fontWeight: 500,
              transition: "all 0.2s ease" 
            }}>
              Sign Out
          </button>
        </div>
      </nav>

      {/* Role description banner */}
      <div style={{ maxWidth: 800, margin: "24px auto 0", padding: "0 20px" }}>
        <div style={{ 
          padding: "12px 18px", 
          borderRadius: 12, 
          fontSize: 13,
          background: "hsla(228, 20%, 14%, 0.3)", 
          color: "var(--text-secondary)", 
          border: `1px solid var(--card-border)`
        }}>
          <strong>Privilege Context:</strong> {ROLE_DESC[user.role]}
        </div>
      </div>

      {/* Dynamic Main Workspace Content */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 20px 40px 20px" }}>
        {page === "dashboard" && user.role === "admin" && <Dashboard userRole={user.role} activeChecksheet={activeChecksheet} />}
        {page === "home"    && <UploadPDF userRole={user.role} activeChecksheet={activeChecksheet} setActiveChecksheet={setActiveChecksheet} />}
        {page === "history" && <ReportsHistory />}
        {page === "audit"   && user.role === "admin" && <AuditLogs />}
      </div>
    </div>
  );
}