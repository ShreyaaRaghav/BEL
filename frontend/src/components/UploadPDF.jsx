import { useState } from "react";
import { apiFetch } from "../auth";

export default function UploadPDF({ userRole }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  
  // Track user input values & notes keyed by check_item_id
  const [values, setValues] = useState({});
  const [notes, setNotes] = useState({});
  
  // Metadata state for the session
  const [meta, setMeta] = useState({
    job_card_no: "",
    vehicle_model: "",
    vin_chassis: "",
    odometer_km: "",
    instrument_name: "",
    model_serial: "",
    location_dept: "",
    next_due_date: "",
    inspection_date: new Date().toISOString().substring(0, 10), // default to today
  });

  // Track database storage status
  const [savedStatus, setSavedStatus] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setData(null);
      setValues({});
      setNotes({});
      setSavedStatus(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    setData(null);
    setValues({});
    setNotes({});
    setSavedStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiFetch("http://127.0.0.1:8000/api/upload-pdf", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server returned status: ${res.status}`);
      }

      const result = await res.json();
      
      if (result.error) {
        throw new Error(result.error);
      }
      
      setData(result);
      
      // Initialize inputs with empty strings
      const initialValues = {};
      const initialNotes = {};
      result.fields.forEach((field) => {
        initialValues[field.check_item_id] = "";
        initialNotes[field.check_item_id] = "";
      });
      setValues(initialValues);
      setNotes(initialNotes);

      // Pre-fill metadata if template returned matches
      setMeta(prev => ({
        ...prev,
        vehicle_model: result.checksheet_type === "vehicle" ? (result.filename.split(".")[0]) : "",
        instrument_name: result.checksheet_type === "instrument" ? (result.filename.split(".")[0]) : "",
        job_card_no: `JC-${Math.floor(100000 + Math.random() * 900000)}`, // Seed random job card
      }));

    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to process the checksheet. Please ensure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (checkItemId, val) => {
    setValues((prev) => ({
      ...prev,
      [checkItemId]: val,
    }));
    setSavedStatus(null);
  };

  const handleNoteChange = (checkItemId, val) => {
    setNotes((prev) => ({
      ...prev,
      [checkItemId]: val,
    }));
  };

  const handleMetaChange = (key, val) => {
    setMeta(prev => ({
      ...prev,
      [key]: val
    }));
    setSavedStatus(null);
  };

  const normalizeTextValue = (value) =>
    String(value || "").trim().toLowerCase().replace(/[_-]+/g, " ");

  const isTextField = (field) =>
    field.conditions && field.conditions.length > 0 && field.range_type === "unknown";

  const getFieldStatus = (field) => {
    const rawVal = values[field.check_item_id];
    if (rawVal === undefined || rawVal === "") {
      return "PENDING";
    }

    if (isTextField(field)) {
      const normalized = normalizeTextValue(rawVal);
      const passed = field.conditions.every((condition) =>
        normalized.includes(normalizeTextValue(condition))
      );
      return passed ? "PASS" : "FAIL";
    }

    const numVal = parseFloat(rawVal);
    if (Number.isNaN(numVal)) {
      return "INVALID";
    }

    if (field.range_type === "min_only") return numVal >= field.min ? "PASS" : "FAIL";
    if (field.range_type === "max_only") return numVal <= field.max ? "PASS" : "FAIL";
    if (field.range_type === "exact") return numVal === field.min ? "PASS" : "FAIL";
    
    // Range standard
    if (field.min !== null && field.max !== null) {
      return numVal >= field.min && numVal <= field.max ? "PASS" : "FAIL";
    }

    return "INVALID";
  };

  const getFieldSpec = (field) => {
    const unit = field.unit ? ` ${field.unit}` : "";

    if (field.range_type === "min_only") return `Minimum: ${field.min}${unit}`;
    if (field.range_type === "max_only") return `Maximum: ${field.max}${unit}`;
    if (field.range_type === "exact") return `Exact: ${field.min}${unit}`;
    if (field.range_type === "range") return `Range: ${field.min} - ${field.max}${unit}`;
    if (field.conditions && field.conditions.length > 0) {
      return `Standard: ${field.conditions.map((c) => c.replace(/_/g, " ")).join(", ")}`;
    }
    return "Standard: Manual check";
  };

  const getOverallStatus = () => {
    if (!data || !data.fields) return null;

    let hasFail = false;
    let hasPending = false;

    for (const field of data.fields) {
      const status = getFieldStatus(field);
      if (status === "FAIL" || status === "INVALID") {
        hasFail = true;
      } else if (status === "PENDING") {
        hasPending = true;
      }
    }

    if (hasFail) return "FAIL";
    if (hasPending) return "PENDING";
    return "PASS";
  };

  const handleSaveToDatabase = async () => {
    if (userRole === "viewer") {
      setError("Read-only access: Viewers are not authorized to persist checksheet records.");
      return;
    }

    setLoading(true);
    setSavedStatus(null);
    setError(null);

    // Format results list according to DB Schema
    const results = data.fields.map(field => {
      const rawVal = values[field.check_item_id];
      const parsedFloat = parseFloat(rawVal);
      return {
        check_item_id: field.check_item_id,
        measured_value: rawVal,
        measured_numeric: Number.isNaN(parsedFloat) ? null : parsedFloat,
        status: getFieldStatus(field),
        notes: notes[field.check_item_id] || ""
      };
    });

    // Compile payload
    const payload = {
      template_id: data.template_id,
      job_card_no: meta.job_card_no,
      inspection_date: meta.inspection_date,
      vehicle_model: data.checksheet_type === "vehicle" ? meta.vehicle_model : null,
      vin_chassis: data.checksheet_type === "vehicle" ? meta.vin_chassis : null,
      odometer_km: data.checksheet_type === "vehicle" ? meta.odometer_km : null,
      instrument_name: data.checksheet_type === "instrument" ? meta.instrument_name : null,
      model_serial: data.checksheet_type === "instrument" ? meta.model_serial : null,
      location_dept: data.checksheet_type === "instrument" ? meta.location_dept : null,
      next_due_date: data.checksheet_type === "instrument" ? meta.next_due_date : null,
      results: results
    };

    try {
      const res = await apiFetch("http://127.0.0.1:8000/api/checksheets/save-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to persist checksheet report.");
      }

      const resJson = await res.json();
      setSavedStatus(`Checksheet persisted successfully to SQLite database! Report ID: #${resJson.id} (Overall: ${resJson.overall_status})`);
      
      // Clear selections
      setFile(null);
      setData(null);
    } catch (err) {
      console.error(err);
      setError(err.message || "Persistence failure. Make sure all metadata fields are filled correctly.");
    } finally {
      setLoading(false);
    }
  };

  const overallStatus = getOverallStatus();
  const isViewer = userRole === "viewer";

  return (
    <div className="container" style={{ animation: "fadeIn 0.5s ease-out" }}>
      
      {/* Welcome Title */}
      <div style={{ textAlign: "center", marginBottom: "30px" }}>
        <h1 className="title-gradient" style={{ fontSize: "2.2rem" }}>BEL Secure Checksheet Processing</h1>
        <p className="subtitle">Upload industrial checksheet PDF blueprints, match metrology parameters, and verify compliance.</p>
      </div>

      {/* Viewer alert notice */}
      {isViewer && (
        <div style={{
          marginBottom: "24px",
          padding: "12px 18px",
          borderRadius: "12px",
          background: "hsla(190, 90%, 55%, 0.1)",
          border: "1px solid var(--accent-cyan)",
          color: "hsl(190, 90%, 75%)",
          fontSize: "0.85rem",
          display: "flex",
          alignItems: "center",
          gap: "8px"
        }}>
          🛡️ <strong>View-Only Privilege Scope:</strong> You can view all processed checksheets and templates, but upload and persistence capabilities are restricted.
        </div>
      )}

      {/* File Upload Selector Zone */}
      <div className="upload-zone" style={{ pointerEvents: isViewer ? "none" : "auto", opacity: isViewer ? 0.5 : 1 }}>
        <span className="upload-icon" role="img" aria-label="upload">📄</span>
        <p className="upload-text-main">Drag and drop your PDF checksheet, or browse</p>
        <p className="upload-text-sub">Supports industrial metrology & calibration manuals (PDF)</p>
        {!isViewer && (
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            disabled={loading}
          />
        )}
      </div>

      {/* Selected File Details & Trigger */}
      {file && (
        <div className="file-preview">
          <div className="file-info">
            <span className="file-icon">✓</span>
            <div>
              <p className="file-name">{file.name}</p>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleUpload} disabled={loading}>
            {loading ? (
              <>
                <div className="spinner"></div>
                Analyzing...
              </>
            ) : "Analyze Checksheet"}
          </button>
        </div>
      )}

      {/* Error Message Display */}
      {error && (
        <div style={{
          marginTop: "20px",
          padding: "16px",
          borderRadius: "12px",
          background: "rgba(244, 63, 94, 0.15)",
          border: "1px solid rgb(244, 63, 94)",
          color: "rgb(251, 113, 133)",
          fontSize: "0.95rem",
          fontWeight: 500,
          animation: "slideDown 0.3s ease"
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Successful Persistent Database save notice */}
      {savedStatus && (
        <div style={{
          marginTop: "20px",
          padding: "16px",
          borderRadius: "12px",
          background: "var(--status-pass-bg)",
          border: "1px solid var(--status-pass-border)",
          color: "var(--status-pass-text)",
          fontSize: "0.95rem",
          fontWeight: 500,
          animation: "slideDown 0.3s ease"
        }}>
          ✅ {savedStatus}
        </div>
      )}

      {/* Structured Fields & Live Verification Form */}
      {data && data.fields && (
        <div className="form-section">
          
          {/* Section 1: Template Auto-Matched Context */}
          <div style={{
            background: "hsla(228, 20%, 14%, 0.4)",
            border: "1px solid var(--card-border)",
            borderRadius: "16px",
            padding: "20px",
            marginBottom: "24px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>Auto-Matched Database Template</span>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--accent-cyan)", margin: "4px 0 0 0" }}>{data.template_name}</h3>
              <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>Parsed blueprint: {data.filename}</p>
            </div>
            <div>
              {overallStatus === "PASS" && <span className="overall-status pass">Overall PASS</span>}
              {overallStatus === "FAIL" && <span className="overall-status fail">Overall FAIL</span>}
              {overallStatus === "PENDING" && (
                <span className="overall-status" style={{
                  background: "hsla(228, 10%, 20%, 0.4)",
                  borderColor: "var(--text-muted)",
                  color: "var(--text-secondary)"
                }}>Pending Inputs</span>
              )}
            </div>
          </div>

          {/* Section 2: Contextual Metadata Inputs */}
          <div style={{
            background: "hsla(228, 20%, 10%, 0.3)",
            border: "1px solid var(--card-border)",
            borderRadius: "16px",
            padding: "24px",
            marginBottom: "24px"
          }}>
            <h4 style={{ color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              🛠️ Session Metadata Parameters
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px" }}>
              
              <div>
                <label style={labelStyle}>Job Card Number</label>
                <input 
                  type="text" 
                  value={meta.job_card_no} 
                  onChange={e => handleMetaChange("job_card_no", e.target.value)}
                  className="field-input" 
                  placeholder="e.g. JC-874210"
                />
              </div>

              <div>
                <label style={labelStyle}>Inspection Date</label>
                <input 
                  type="date" 
                  value={meta.inspection_date} 
                  onChange={e => handleMetaChange("inspection_date", e.target.value)}
                  className="field-input"
                />
              </div>

              {/* Context Specific Metadata */}
              {data.checksheet_type === "vehicle" ? (
                <>
                  <div>
                    <label style={labelStyle}>Vehicle Model</label>
                    <input 
                      type="text" 
                      value={meta.vehicle_model} 
                      onChange={e => handleMetaChange("vehicle_model", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. TATA LPT 1613"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>VIN / Chassis Number</label>
                    <input 
                      type="text" 
                      value={meta.vin_chassis} 
                      onChange={e => handleMetaChange("vin_chassis", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. MAT412039W82..."
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Odometer (KM)</label>
                    <input 
                      type="number" 
                      value={meta.odometer_km} 
                      onChange={e => handleMetaChange("odometer_km", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. 45280"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label style={labelStyle}>Instrument Name</label>
                    <input 
                      type="text" 
                      value={meta.instrument_name} 
                      onChange={e => handleMetaChange("instrument_name", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. Spectrophotometer D2"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Model / Serial Number</label>
                    <input 
                      type="text" 
                      value={meta.model_serial} 
                      onChange={e => handleMetaChange("model_serial", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. BEL-CAL-892"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Location / Department</label>
                    <input 
                      type="text" 
                      value={meta.location_dept} 
                      onChange={e => handleMetaChange("location_dept", e.target.value)}
                      className="field-input" 
                      placeholder="e.g. Calibration Lab B"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Calibration Due Date</label>
                    <input 
                      type="date" 
                      value={meta.next_due_date} 
                      onChange={e => handleMetaChange("next_due_date", e.target.value)}
                      className="field-input"
                    />
                  </div>
                </>
              )}

            </div>
          </div>

          {/* Section 3: Live Verification Form Fields */}
          <h4 style={{ color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            📋 Parameter Verification Form
          </h4>
          <div className="fields-grid">
            {data.fields.map((field, idx) => {
              const status = getFieldStatus(field);
              const textField = isTextField(field);
              return (
                <div className="field-card" key={idx} style={{ gridTemplateColumns: "1.5fr 1fr 1.2fr 0.8fr", gap: "16px", padding: "16px 20px" }}>
                  
                  {/* Title and spec limits */}
                  <div className="field-info">
                    <span className="field-label" style={{ fontSize: "0.95rem", fontWeight: 600 }}>{idx + 1}. {field.title}</span>
                    <span className="field-limits" style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{getFieldSpec(field)}</span>
                  </div>

                  {/* Input value */}
                  <div className="input-container">
                    <input
                      type={textField ? "text" : "number"}
                      step="any"
                      placeholder={textField ? "Observation text" : "Value"}
                      className="field-input"
                      value={values[field.check_item_id] || ""}
                      onChange={(e) => handleInputChange(field.check_item_id, e.target.value)}
                      style={{ fontSize: "0.9rem", padding: "8px 12px" }}
                    />
                    {field.unit && <span className="input-unit" style={{ fontSize: "0.8rem", right: "12px" }}>{field.unit}</span>}
                  </div>

                  {/* Inspector Notes input */}
                  <div>
                    <input
                      type="text"
                      placeholder="Add compliance notes..."
                      className="field-input"
                      value={notes[field.check_item_id] || ""}
                      onChange={(e) => handleNoteChange(field.check_item_id, e.target.value)}
                      style={{ fontSize: "0.8rem", padding: "8px 12px", background: "hsla(228, 20%, 8%, 0.4)", borderStyle: "dashed" }}
                    />
                  </div>

                  {/* Live Verification Badge */}
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    {status === "PENDING" && <div className="badge pending" style={{ padding: "6px 12px", fontSize: "0.75rem" }}>Pending</div>}
                    {status === "PASS" && <div className="badge pass" style={{ padding: "6px 12px", fontSize: "0.75rem" }}>PASS</div>}
                    {status === "FAIL" && <div className="badge fail" style={{ padding: "6px 12px", fontSize: "0.75rem" }}>FAIL</div>}
                    {status === "INVALID" && <div className="badge fail" style={{ padding: "6px 12px", fontSize: "0.75rem" }}>INVALID</div>}
                  </div>

                </div>
              );
            })}
          </div>

          {/* Secure Database storage action */}
          <div style={{ marginTop: "30px", display: "flex", flexDirection: "column", alignItems: "center", gap: "15px" }}>
            <button
              className="btn btn-primary"
              style={{ width: "100%", padding: "14px", fontWeight: 600 }}
              disabled={loading || overallStatus === "PENDING" || isViewer}
              onClick={handleSaveToDatabase}
            >
              {loading ? (
                <>
                  <div className="spinner"></div> Persisting to Database...
                </>
              ) : "Securely Persist Inspection Report to SQLite"}
            </button>
          </div>
          
        </div>
      )}
    </div>
  );
}

const labelStyle = {
  display: "block",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "var(--text-muted)",
  marginBottom: "8px",
  textTransform: "uppercase",
  letterSpacing: "0.5px"
};
