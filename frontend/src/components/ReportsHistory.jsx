import { useState, useEffect } from "react";
import { apiFetch, formatApiError } from "../auth";

export default function ReportsHistory() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // State for showing detailed report in modal
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [details, setDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);
  
  // Filter states
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = () => {
    setLoading(true);
    apiFetch("/api/checksheets/reports")
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(data, "Could not fetch reports list"));
        return data;
      })
      .then(data => {
        setReports(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load saved inspection reports.");
        setLoading(false);
      });
  };

  const handleViewDetails = (reportId) => {
    setSelectedReportId(reportId);
    setDetailsLoading(true);
    setDetails(null);
    setDetailsError(null);

    apiFetch(`/api/checksheets/reports/${reportId}`)
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(data, "Could not retrieve report details"));
        return data;
      })
      .then(data => {
        setDetails(data);
        setDetailsLoading(false);
      })
      .catch((err) => {
        setDetailsError(err.message || "Failed to load report parameters.");
        setDetailsLoading(false);
      });
  };

  const closeDetails = () => {
    setSelectedReportId(null);
    setDetails(null);
  };

  // Filter logic
  const filteredReports = reports.filter(r => {
    const term = search.toLowerCase();
    const tech = (r.lead_technician || "").toLowerCase();
    const model = (r.vehicle_model || r.instrument_name || "").toLowerCase();
    const matchesSearch = tech.includes(term) || model.includes(term);
    const matchesStatus = statusFilter === "ALL" || r.overall_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    const isPass = status === "PASS";
    return (
      <span className={`overall-status ${isPass ? "pass" : "fail"}`} style={{ 
        padding: "4px 10px", fontSize: "0.75rem", borderRadius: "12px", border: "1px solid" 
      }}>
        {isPass ? "✓ PASS" : "✗ FAIL"}
      </span>
    );
  };

  return (
    <div style={{ marginTop: "20px", animation: "fadeIn 0.5s ease-out" }}>
      
      {/* Header & Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "15px", marginBottom: "24px" }}>
        <div>
          <h2 className="title-gradient" style={{ fontSize: "1.8rem", marginBottom: "6px" }}> Saved Inspection Reports</h2>
          <p className="subtitle" style={{ fontSize: "0.95rem", margin: 0 }}>
            Browse and review past PDF checksheet persistences stored in the SQLite database.
          </p>
        </div>
        
        {/* Search & Filter */}
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <input 
            type="text" 
            placeholder="Search technician or model..." 
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="field-input"
            style={{ width: "240px", fontSize: "0.85rem", padding: "8px 12px" }}
          />
          <select 
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="field-input"
            style={{ width: "120px", fontSize: "0.85rem", padding: "8px 12px", background: "hsla(228, 20%, 10%, 0.8)", cursor: "pointer" }}
          >
            <option value="ALL">All Statuses</option>
            <option value="PASS">PASS Only</option>
            <option value="FAIL">FAIL Only</option>
          </select>
        </div>
      </div>

      {loading && (
        <div style={{ display: "flex", gap: "10px", alignItems: "center", color: "var(--text-secondary)" }}>
          <div className="spinner"></div> Reading report database...
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

      {!loading && !error && filteredReports.length === 0 && (
        <div style={{ padding: "40px 20px", textAlign: "center", border: "1px dashed var(--card-border)", borderRadius: "16px", background: "hsla(228, 20%, 14%, 0.2)" }}>
          <p style={{ color: "var(--text-muted)", margin: 0 }}>No saved reports match your current filter settings.</p>
        </div>
      )}

      {/* Reports Table */}
      {!loading && filteredReports.length > 0 && (
        <div style={{ overflowX: "auto", borderRadius: "16px", border: "1px solid var(--card-border)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem", background: "hsla(228, 20%, 18%, 0.2)" }}>
            <thead>
              <tr style={{ background: "hsla(228, 20%, 10%, 0.6)", borderBottom: "1px solid var(--card-border)" }}>
                <th style={th}>Job Card</th>
                <th style={th}>Equipment / Asset Model</th>
                <th style={th}>Lead Technician</th>
                <th style={th}>Inspection Date</th>
                <th style={th}>Metrology Status</th>
                <th style={{ ...th, textAlign: "center" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredReports.map((r, idx) => {
                const modelName = r.vehicle_model || r.instrument_name || "Custom Inspection";
                const serialNum = r.vin_chassis || r.model_serial || "N/A";
                return (
                  <tr key={idx} style={{ 
                    borderBottom: "1px solid var(--card-border)", 
                    background: idx % 2 === 0 ? "hsla(228, 20%, 14%, 0.2)" : "transparent",
                    transition: "background 0.2s ease"
                  }}>
                    <td style={{ ...td, fontWeight: 600, color: "var(--accent-cyan)", fontFamily: "monospace" }}>
                      {r.job_card_no || `JC-${1000 + r.id}`}
                    </td>
                    <td style={td}>
                      <div>
                        <div style={{ fontWeight: 500 }}>{modelName}</div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>ID/Serial: {serialNum}</div>
                      </div>
                    </td>
                    <td style={{ ...td, fontWeight: 500 }}>{r.lead_technician || "system"}</td>
                    <td style={{ ...td, color: "var(--text-muted)" }}>{r.inspection_date || "N/A"}</td>
                    <td style={td}>{getStatusBadge(r.overall_status)}</td>
                    <td style={{ ...td, textAlign: "center" }}>
                      <button 
                        onClick={() => handleViewDetails(r.id)}
                        className="btn btn-primary"
                        style={{ padding: "6px 14px", borderRadius: "8px", fontSize: "0.8rem", cursor: "pointer" }}
                      >
                        Open Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Report Details Modal */}
      {selectedReportId && (
        <div style={modalOverlayStyle}>
          <div style={modalCardStyle}>
            
            {/* Modal Header */}
            <div style={modalHeaderStyle}>
              <div>
                <h3 style={{ fontSize: "1.35rem", fontWeight: 600, color: "var(--text-primary)" }}>
                   Persistence Details: Report #{selectedReportId}
                </h3>
                {details && (
                  <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Template: {details.template_name} ({details.checksheet_type})
                  </p>
                )}
              </div>
              <button onClick={closeDetails} style={closeButtonStyle}>✕</button>
            </div>

            {/* Modal Content */}
            <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "flex", flexDirection: "column", gap: "24px" }}>
              {detailsLoading && (
                <div style={{ display: "flex", gap: "10px", alignItems: "center", justifyContent: "center", height: "150px" }}>
                  <div className="spinner"></div> Fetching records from database...
                </div>
              )}

              {detailsError && (
                <div style={{ padding: "16px", borderRadius: "12px", background: "rgba(244, 63, 94, 0.15)", border: "1px solid rgb(244, 63, 94)", color: "rgb(251, 113, 133)" }}>
                   {detailsError}
                </div>
              )}

              {details && (
                <>
                  {/* Metadata Cards Grid */}
                  <div style={metaGridStyle}>
                    <div style={metaCardStyle}>
                      <span style={metaLabel}>Lead Technician</span>
                      <span style={metaVal}>{details.lead_technician || "N/A"}</span>
                    </div>
                    <div style={metaCardStyle}>
                      <span style={metaLabel}>Inspection Date</span>
                      <span style={metaVal}>{details.inspection_date || "N/A"}</span>
                    </div>
                    <div style={metaCardStyle}>
                      <span style={metaLabel}>Job Card Number</span>
                      <span style={metaVal}>{details.job_card_no || "N/A"}</span>
                    </div>
                    <div style={metaCardStyle}>
                      <span style={metaLabel}>Overall Verification Status</span>
                      <span style={{ display: "inline-block", marginTop: "4px" }}>{getStatusBadge(details.overall_status)}</span>
                    </div>
                  </div>

                  {/* Asset Details */}
                  <div style={assetPanelStyle}>
                    <h4 style={{ color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      🔍 Asset/Equipment Context Data
                    </h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                      {details.checksheet_type === "vehicle" ? (
                        <>
                          <div>
                            <span style={metaLabel}>Vehicle Model</span>
                            <span style={metaVal}>{details.vehicle_model || "N/A"}</span>
                          </div>
                          <div>
                            <span style={metaLabel}>VIN / Chassis Number</span>
                            <span style={metaVal}>{details.vin_chassis || "N/A"}</span>
                          </div>
                          <div>
                            <span style={metaLabel}>Odometer (KM)</span>
                            <span style={metaVal}>{details.odometer_km ? `${details.odometer_km} km` : "N/A"}</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <span style={metaLabel}>Instrument Name</span>
                            <span style={metaVal}>{details.instrument_name || "N/A"}</span>
                          </div>
                          <div>
                            <span style={metaLabel}>Model / Serial Number</span>
                            <span style={metaVal}>{details.model_serial || "N/A"}</span>
                          </div>
                          <div>
                            <span style={metaLabel}>Location / Department</span>
                            <span style={metaVal}>{details.location_dept || "N/A"}</span>
                          </div>
                          <div>
                            <span style={metaLabel}>Next Due Date</span>
                            <span style={metaVal}>{details.next_due_date || "N/A"}</span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Inspection Items Table */}
                  <div>
                    <h4 style={{ color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Tolerance Compliance Checklist
                    </h4>
                    <div style={{ overflowX: "auto", borderRadius: "12px", border: "1px solid var(--card-border)" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                        <thead>
                          <tr style={{ background: "hsla(228, 20%, 10%, 0.8)", borderBottom: "1px solid var(--card-border)" }}>
                            <th style={mTh}>Param</th>
                            <th style={mTh}>Target / Spec Standard</th>
                            <th style={mTh}>Measured Observation</th>
                            <th style={mTh}>Compliance</th>
                            <th style={mTh}>Inspector Notes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {details.results.map((item, idx) => {
                            const isPass = item.status === "PASS";
                            return (
                              <tr key={idx} style={{ 
                                borderBottom: "1px solid var(--card-border)", 
                                background: idx % 2 === 0 ? "hsla(228, 20%, 14%, 0.15)" : "transparent"
                              }}>
                                <td style={{ ...mTd, fontWeight: 500 }}>{item.parameter_name}</td>
                                <td style={{ ...mTd, color: "var(--text-secondary)" }}>{item.range_standard || "Manual Check"}</td>
                                <td style={{ ...mTd, fontWeight: 600 }}>{item.measured_value || "—"} {item.measured_value && item.unit ? item.unit : ""}</td>
                                <td style={mTd}>
                                  <span style={{ 
                                    padding: "3px 8px", borderRadius: "6px", fontSize: "0.7rem", fontWeight: 700,
                                    background: isPass ? "var(--status-pass-bg)" : "var(--status-fail-bg)",
                                    border: `1px solid ${isPass ? "var(--status-pass-border)" : "var(--status-fail-border)"}`,
                                    color: isPass ? "var(--status-pass-text)" : "var(--status-fail-text)"
                                  }}>
                                    {item.status}
                                  </span>
                                </td>
                                <td style={{ ...mTd, color: "var(--text-muted)", fontStyle: "italic" }}>{item.notes || "No notes"}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div style={modalFooterStyle}>
              <button onClick={closeDetails} className="btn" style={{ background: "hsla(228, 20%, 25%, 0.8)", border: "1px solid var(--card-border)", color: "#fff", cursor: "pointer" }}>
                Close Inspector
              </button>
            </div>

          </div>
        </div>
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
  color: "var(--text-primary)",
  verticalAlign: "middle"
};

const mTh = {
  padding: "12px 16px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: "0.8rem",
  color: "var(--text-secondary)",
  textTransform: "uppercase",
  letterSpacing: "0.5px"
};

const mTd = {
  padding: "10px 16px",
  color: "var(--text-primary)",
  verticalAlign: "middle"
};

// Modal UI Styles
const modalOverlayStyle = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: "rgba(0,0,0,0.6)",
  backdropFilter: "blur(8px)",
  WebkitBackdropFilter: "blur(8px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  padding: "20px",
  animation: "fadeIn 0.3s ease-out"
};

const modalCardStyle = {
  background: "hsl(230, 25%, 10%)",
  border: "1px solid var(--card-border)",
  borderRadius: "24px",
  width: "100%",
  maxWidth: "850px",
  maxHeight: "90vh",
  boxShadow: "0 25px 50px rgba(0,0,0,0.6)",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden"
};

const modalHeaderStyle = {
  padding: "24px",
  borderBottom: "1px solid var(--card-border)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  background: "hsla(228, 20%, 8%, 0.4)"
};

const closeButtonStyle = {
  background: "transparent",
  border: "none",
  color: "var(--text-secondary)",
  fontSize: "1.2rem",
  cursor: "pointer",
  padding: "4px 8px",
  borderRadius: "6px",
  transition: "all 0.2s ease"
};

const modalFooterStyle = {
  padding: "18px 24px",
  borderTop: "1px solid var(--card-border)",
  display: "flex",
  justifyContent: "flex-end",
  background: "hsla(228, 20%, 8%, 0.4)"
};

const metaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "16px"
};

const metaCardStyle = {
  background: "hsla(228, 20%, 14%, 0.4)",
  border: "1px solid var(--card-border)",
  borderRadius: "12px",
  padding: "12px 16px",
  display: "flex",
  flexDirection: "column"
};

const metaLabel = {
  fontSize: "0.75rem",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.5px"
};

const metaVal = {
  fontSize: "0.95rem",
  fontWeight: 600,
  color: "var(--text-primary)",
  marginTop: "4px"
};

const assetPanelStyle = {
  background: "hsla(228, 20%, 12%, 0.4)",
  border: "1px solid var(--card-border)",
  borderRadius: "16px",
  padding: "20px"
};
