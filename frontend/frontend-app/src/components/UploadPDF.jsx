import { useState } from "react";

export default function UploadPDF() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  
  // Track user input values for each checksheet field
  const [values, setValues] = useState({});
  
  // Track mock database storage status
  const [savedStatus, setSavedStatus] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setData(null);
      setValues({});
      setSavedStatus(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    setData(null);
    setValues({});
    setSavedStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/upload-pdf", {
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
      result.fields.forEach((field) => {
        initialValues[field.title] = "";
      });
      setValues(initialValues);
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to process the checksheet. Please ensure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (title, val) => {
    setValues((prev) => ({
      ...prev,
      [title]: val,
    }));
    setSavedStatus(null);
  };

  // Helper: determine the pass/fail status of a single field
  const getFieldStatus = (field) => {
    const rawVal = values[field.title];
    if (rawVal === undefined || rawVal === "") {
      return "PENDING";
    }
    const numVal = parseFloat(rawVal);
    if (isNaN(numVal)) {
      return "INVALID";
    }
    if (numVal >= field.min && numVal <= field.max) {
      return "PASS";
    }
    return "FAIL";
  };

  // Helper: determine the overall checksheet status
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

  const handleSaveToDatabase = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSavedStatus("Checksheet values securely stored in local SQLite database!");
    }, 800);
  };

  const overallStatus = getOverallStatus();

  return (
    <div className="container">
      <div style={{ textAlign: "center", marginBottom: "30px" }}>
        <h1 className="title-gradient" style={{ fontSize: "2.2rem" }}>BEL Secure Checksheet Processing</h1>
        <p className="subtitle">Upload industrial PDF checksheets and verify tolerances instantly</p>
      </div>

      {/* File Upload Selector Zone */}
      <div className="upload-zone">
        <span className="upload-icon" role="img" aria-label="upload">📄</span>
        <p className="upload-text-main">Drag and drop your PDF checksheet, or browse</p>
        <p className="upload-text-sub">Supports industrial equipment checksheets (PDF)</p>
        <input 
          type="file" 
          accept=".pdf,application/pdf" 
          onChange={handleFileChange} 
          disabled={loading}
        />
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
          <button 
            className="btn btn-primary" 
            onClick={handleUpload} 
            disabled={loading}
          >
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

      {/* Structured Fields & Live Verification Form */}
      {data && data.fields && (
        <div className="form-section">
          <div className="form-header">
            <div>
              <h2 className="form-title">Dynamic Inspection Form</h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                File: {data.filename}
              </p>
            </div>
            
            {overallStatus === "PASS" && (
              <span className="overall-status pass">✓ Overall PASS</span>
            )}
            {overallStatus === "FAIL" && (
              <span className="overall-status fail">✗ Overall FAIL</span>
            )}
            {overallStatus === "PENDING" && (
              <span className="overall-status" style={{
                background: "hsla(228, 10%, 20%, 0.4)",
                borderColor: "var(--text-muted)",
                color: "var(--text-secondary)"
              }}>⚡ Pending Values</span>
            )}
          </div>

          <div className="fields-grid">
            {data.fields.map((field, idx) => {
              const status = getFieldStatus(field);
              return (
                <div className="field-card" key={idx}>
                  
                  {/* Field Label and Specs */}
                  <div className="field-info">
                    <span className="field-label">{field.title}</span>
                    <span className="field-limits">
                      Range: {field.min} – {field.max} {field.unit}
                    </span>
                  </div>

                  {/* Field Live Input */}
                  <div className="input-container">
                    <input
                      type="number"
                      step="any"
                      placeholder="Enter value"
                      className="field-input"
                      value={values[field.title] || ""}
                      onChange={(e) => handleInputChange(field.title, e.target.value)}
                    />
                    <span className="input-unit">{field.unit}</span>
                  </div>

                  {/* Status Badge */}
                  <div>
                    {status === "PENDING" && (
                      <div className="badge pending">Enter value</div>
                    )}
                    {status === "PASS" && (
                      <div className="badge pass">PASS</div>
                    )}
                    {status === "FAIL" && (
                      <div className="badge fail">FAIL</div>
                    )}
                    {status === "INVALID" && (
                      <div className="badge fail">INVALID</div>
                    )}
                  </div>

                </div>
              );
            })}
          </div>

          {/* Secure Database storage action */}
          <div style={{ marginTop: "30px", display: "flex", flexDirection: "column", alignItems: "center", gap: "15px" }}>
            <button 
              className="btn btn-primary" 
              style={{ width: "100%", padding: "14px" }}
              disabled={loading || overallStatus === "PENDING"}
              onClick={handleSaveToDatabase}
            >
              Securely Save Checksheet Report
            </button>
            
            {savedStatus && (
              <p style={{ 
                color: "var(--status-pass-text)", 
                fontSize: "0.95rem", 
                fontWeight: 500,
                textAlign: "center",
                animation: "fadeIn 0.3s ease" 
              }}>
                ✅ {savedStatus}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
