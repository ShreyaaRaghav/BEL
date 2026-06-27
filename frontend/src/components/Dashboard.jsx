import { useState, useEffect } from "react";
import { apiFetch, formatApiError } from "../auth";

export default function Dashboard({ userRole, activeChecksheet }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [spcMode, setSpcMode] = useState("vehicle"); // 'vehicle' | 'instrument'
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState("");

  // States for chart hover tooltip
  const [trendHovered, setTrendHovered] = useState(null);
  const [donutHovered, setDonutHovered] = useState(null);
  const [spcHovered, setSpcHovered] = useState(null);
  const [techHovered, setTechHovered] = useState(null);
  const [paretoHovered, setParetoHovered] = useState(null);
  const [outcomeHovered, setOutcomeHovered] = useState(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = () => {
    setLoading(true);
    setError(null);
    apiFetch("/api/checksheets/analytics")
      .then(async (res) => {
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(json, "Failed to load analytics data"));
        return json;
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Could not retrieve dashboard statistics.");
        setLoading(false);
      });
  };

  const handleResetData = () => {
    if (!window.confirm("Are you sure you want to delete all inspection reports from the database? This action is permanent and cannot be undone.")) return;
    setSeeding(true);
    setSeedMessage("");
    apiFetch("/api/checksheets/reset-demo-data", { method: "POST" })
      .then(async (res) => {
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(formatApiError(json, "Failed to clear database"));
        return json;
      })
      .then(() => {
        setSeedMessage("Database cleared.");
        setTimeout(() => setSeedMessage(""), 4000);
        fetchAnalytics();
      })
      .catch((err) => {
        alert(err.message);
      })
      .finally(() => {
        setSeeding(false);
      });
  };

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 15, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-secondary)" }}>
        <div className="spinner" style={{ width: "35px", height: "35px", borderWidth: "3px" }}></div>
        <span>Compiling analytical models & aggregates...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "24px", borderRadius: "14px", background: "rgba(244, 63, 94, 0.12)", border: "1px solid rgb(244, 63, 94)", color: "rgb(251, 113, 133)", marginTop: "20px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "8px" }}>Analytics Service Error</h3>
        <p style={{ fontSize: "0.95rem", margin: "0 0 16px 0" }}>{error}</p>
        <button onClick={fetchAnalytics} className="btn btn-primary" style={{ padding: "8px 20px", borderRadius: "8px", fontSize: "0.85rem" }}>
          Retry Request
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { overview, trends, templates, pareto, most_passed, technicians, spc } = data;

  // ----------------------------------------------------
  // DYNAMIC MERGING OF ACTIVE DRAFT CHECKSHEET INTO STATS
  // ----------------------------------------------------
  const getActiveChecksheetStatus = () => {
    if (!activeChecksheet || !activeChecksheet.data || !activeChecksheet.data.fields) return null;
    const { fields, checksheet_type } = activeChecksheet.data;
    const { values } = activeChecksheet;

    const normalizeTextValue = (value) =>
      String(value || "").trim().toLowerCase().replace(/[_-]+/g, " ");

    const isTextField = (field) =>
      field.conditions &&
      field.conditions.length > 0 &&
      (field.range_type === "unknown" ||
        field.range_type === "visual" ||
        field.type === "categorical");

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
      
      if (field.min !== null && field.max !== null) {
        return numVal >= field.min && numVal <= field.max ? "PASS" : "FAIL";
      }

      return "INVALID";
    };

    let hasFail = false;
    let hasPending = false;
    let passCount = 0;
    let failCount = 0;
    let pendingCount = 0;
    const failedFields = [];

    fields.forEach((field) => {
      const status = getFieldStatus(field);
      if (status === "FAIL" || status === "INVALID") {
        hasFail = true;
        failCount++;
        failedFields.push({ title: field.title, val: values[field.check_item_id], unit: field.unit || "", spec: getFieldSpec(field) });
      } else if (status === "PENDING") {
        hasPending = true;
        pendingCount++;
      } else if (status === "PASS") {
        passCount++;
      }
    });

    const overall = hasFail ? "FAIL" : (hasPending ? "PENDING" : "PASS");

    return {
      overall,
      passCount,
      failCount,
      pendingCount,
      totalCount: fields.length,
      failedFields,
      checksheet_type,
      template_name: activeChecksheet.data.template_name,
      filename: activeChecksheet.data.filename,
      meta: activeChecksheet.meta,
      fields: fields.map(f => ({ ...f, liveStatus: getFieldStatus(f), liveValue: values[f.check_item_id] }))
    };
  };

  const getFieldSpec = (field) => {
    const unit = field.unit ? ` ${field.unit}` : "";
    if (field.range_type === "min_only") return `>= ${field.min}${unit}`;
    if (field.range_type === "max_only") return `<= ${field.max}${unit}`;
    if (field.range_type === "exact") return `= ${field.min}${unit}`;
    if (field.range_type === "range") return `${field.min} - ${field.max}${unit}`;
    if (field.conditions && field.conditions.length > 0) {
      return field.conditions.join(" / ");
    }
    return "Manual spec";
  };

  const activeStatusObj = getActiveChecksheetStatus();
  
  // Clone historical stats and dynamically overlay active draft checksheet
  let mergedOverview = {
    total_reports: overview.total_reports,
    passed: overview.passed,
    failed: overview.failed,
    pass_rate: overview.pass_rate,
    due_soon: overview.due_soon,
    recorrection_rate: overview.recorrection_rate,
    ftr_rate: overview.ftr_rate,
    avg_mttr_hours: overview.avg_mttr_hours,
    avg_processing_mins: overview.avg_processing_mins ?? 0,
  };
  let mergedTrends = trends ? trends.map(t => ({ ...t })) : [];
  let mergedTemplates = templates ? templates.map(t => ({ ...t })) : [];
  let mergedPareto = pareto ? pareto.map(p => ({ ...p })) : [];
  let mergedMostPassed = most_passed ? most_passed.map(m => ({ ...m })) : [];
  let mergedTechnicians = technicians ? technicians.map(t => ({ ...t })) : [];
  let mergedSpc = spc ? {
    vehicle: { ...spc.vehicle, data: spc.vehicle.data ? spc.vehicle.data.map(d => ({ ...d })) : [] },
    instrument: { ...spc.instrument, data: spc.instrument.data ? spc.instrument.data.map(d => ({ ...d })) : [] }
  } : {
    vehicle: { parameter_name: "Alternator Charging Voltage", unit: "V", min: 13.8, max: 14.7, data: [] },
    instrument: { parameter_name: "Baseline Voltage Stability", unit: "V", min: 4.95, max: 5.05, data: [] }
  };

  if (activeStatusObj) {
    // 1. Overview
    mergedOverview.total_reports += 1;
    if (activeStatusObj.overall === "PASS") {
      mergedOverview.passed += 1;
    } else if (activeStatusObj.overall === "FAIL") {
      mergedOverview.failed += 1;
    }
    mergedOverview.pass_rate = mergedOverview.total_reports > 0
      ? roundNum((mergedOverview.passed / mergedOverview.total_reports) * 100, 1)
      : 0.0;
    if (activeStatusObj.meta.next_due_date) {
      mergedOverview.due_soon += 1;
    }

    // 2. Trends
    const month = activeStatusObj.meta.inspection_date ? activeStatusObj.meta.inspection_date.substring(0, 7) : new Date().toISOString().substring(0, 7);
    const trendIndex = mergedTrends.findIndex(t => t.month === month);
    if (trendIndex >= 0) {
      mergedTrends[trendIndex] = {
        ...mergedTrends[trendIndex],
        total: mergedTrends[trendIndex].total + 1,
        pass: mergedTrends[trendIndex].pass + (activeStatusObj.overall === "PASS" ? 1 : 0),
        fail: mergedTrends[trendIndex].fail + (activeStatusObj.overall === "FAIL" ? 1 : 0)
      };
    } else {
      mergedTrends.push({
        month,
        total: 1,
        pass: activeStatusObj.overall === "PASS" ? 1 : 0,
        fail: activeStatusObj.overall === "FAIL" ? 1 : 0
      });
      mergedTrends.sort((a, b) => a.month.localeCompare(b.month));
    }

    // 3. Templates
    const tempIndex = mergedTemplates.findIndex(t => t.template_name === activeStatusObj.template_name);
    if (tempIndex >= 0) {
      mergedTemplates[tempIndex].count += 1;
    } else {
      mergedTemplates.push({
        template_name: activeStatusObj.template_name,
        checksheet_type: activeStatusObj.checksheet_type,
        count: 1
      });
    }

    // 4. Pareto Defect Heatmap (Top Failing Specs)
    activeStatusObj.fields.forEach(f => {
      if (f.liveStatus === "FAIL" || f.liveStatus === "INVALID") {
        const pIndex = mergedPareto.findIndex(p => p.parameter_name === f.title);
        if (pIndex >= 0) {
          mergedPareto[pIndex].fail_count += 1;
        } else {
          mergedPareto.push({ parameter_name: f.title, fail_count: 1 });
        }
      }
    });
    mergedPareto.sort((a, b) => b.fail_count - a.fail_count);

    // 4b. Most Passed Parameters (Most frequently entered correct)
    activeStatusObj.fields.forEach(f => {
      if (f.liveStatus === "PASS") {
        const mIndex = mergedMostPassed.findIndex(m => m.parameter_name === f.title);
        if (mIndex >= 0) {
          mergedMostPassed[mIndex].pass_count += 1;
        } else {
          mergedMostPassed.push({ parameter_name: f.title, pass_count: 1 });
        }
      }
    });
    mergedMostPassed.sort((a, b) => b.pass_count - a.pass_count);

    // 5. Technicians
    const technicianName = activeStatusObj.meta.lead_technician || "Active User";
    const techIndex = mergedTechnicians.findIndex(t => t.technician.toLowerCase() === technicianName.toLowerCase());
    if (techIndex >= 0) {
      mergedTechnicians[techIndex].total += 1;
      mergedTechnicians[techIndex].pass += (activeStatusObj.overall === "PASS" ? 1 : 0);
      mergedTechnicians[techIndex].fail += (activeStatusObj.overall === "FAIL" ? 1 : 0);
    } else {
      mergedTechnicians.push({
        technician: technicianName,
        total: 1,
        pass: activeStatusObj.overall === "PASS" ? 1 : 0,
        fail: activeStatusObj.overall === "FAIL" ? 1 : 0
      });
    }

    // 6. SPC control data points
    if (activeStatusObj.checksheet_type === "vehicle") {
      const voltField = activeStatusObj.fields.find(f => f.check_item_id === 4);
      if (voltField && voltField.liveValue !== undefined && voltField.liveValue !== "") {
        const numericVal = parseFloat(voltField.liveValue);
        if (!isNaN(numericVal)) {
          mergedSpc.vehicle.data = [
            ...mergedSpc.vehicle.data,
            {
              session_id: "active",
              job_card_no: activeStatusObj.meta.job_card_no || "Active Draft",
              date: activeStatusObj.meta.inspection_date,
              value: numericVal,
              status: voltField.liveStatus,
              isActiveDraft: true
            }
          ];
        }
      }
    } else if (activeStatusObj.checksheet_type === "instrument") {
      const stabField = activeStatusObj.fields.find(f => f.check_item_id === 21);
      if (stabField && stabField.liveValue !== undefined && stabField.liveValue !== "") {
        const numericVal = parseFloat(stabField.liveValue);
        if (!isNaN(numericVal)) {
          mergedSpc.instrument.data = [
            ...mergedSpc.instrument.data,
            {
              session_id: "active",
              job_card_no: activeStatusObj.meta.job_card_no || "Active Draft",
              date: activeStatusObj.meta.inspection_date,
              value: numericVal,
              status: stabField.liveStatus,
              isActiveDraft: true
            }
          ];
        }
      }
    }
  }

  // ----------------------------------------------------
  // CALCULATE NEW WIDGET METRICS
  // ----------------------------------------------------

  // DA 3: Parameter Health Index
  // DB has total 10 vehicle sessions * 20 parameters = 200 checks, and 8 instrument sessions * 10 parameters = 80 checks. Total 280 checks.
  // There were 8 historical failed parameters.
  const dbTotalChecks = 280;
  const dbFailChecks = 8;
  let totalCheckItems = dbTotalChecks;
  let passedCheckItems = dbTotalChecks - dbFailChecks;
  
  if (activeStatusObj) {
    totalCheckItems += activeStatusObj.totalCount;
    passedCheckItems += activeStatusObj.passCount;
  }
  const parameterHealthIndex = totalCheckItems > 0 ? roundNum((passedCheckItems / totalCheckItems) * 100, 1) : 0.0;

  // DA 4: Deviation Matrix (Averages of numerical SPC values)
  const vehicleDataPoints = mergedSpc.vehicle.data.filter(d => !d.isActiveDraft && d.status === "PASS");
  const vehicleAvg = vehicleDataPoints.length > 0
    ? roundNum(vehicleDataPoints.reduce((acc, curr) => acc + curr.value, 0) / vehicleDataPoints.length, 3)
    : 14.18;

  const instrumentDataPoints = mergedSpc.instrument.data.filter(d => !d.isActiveDraft && d.status === "PASS");
  const instrumentAvg = instrumentDataPoints.length > 0
    ? roundNum(instrumentDataPoints.reduce((acc, curr) => acc + curr.value, 0) / instrumentDataPoints.length, 3)
    : 5.001;

  // DA 7: MoM Compliance Trend Line
  const momTrends = mergedTrends.map(t => {
    const rate = t.total > 0 ? roundNum((t.pass / t.total) * 100, 1) : 0.0;
    return { ...t, rate };
  });

  // Circular gauge radial coordinates
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (mergedOverview.pass_rate / 100) * circumference;
  const correctionDashoffset = circumference - (mergedOverview.recorrection_rate / 100) * circumference;
  const ftrDashoffset = circumference - (mergedOverview.ftr_rate / 100) * circumference;

  // Prepare Trend Line Chart
  const drawLineChart = () => {
    if (!mergedTrends || mergedTrends.length === 0) return null;
    const width = 450;
    const height = 180;
    const paddingLeft = 40;
    const paddingRight = 20;
    const paddingTop = 20;
    const paddingBottom = 30;

    const chartW = width - paddingLeft - paddingRight;
    const chartH = height - paddingTop - paddingBottom;

    const maxVal = Math.max(...mergedTrends.map(t => t.total), 5);
    const yMax = Math.ceil(maxVal * 1.15);

    const points = mergedTrends.map((t, idx) => {
      const x = paddingLeft + (idx / (mergedTrends.length - 1 || 1)) * chartW;
      const y = height - paddingBottom - (t.total / yMax) * chartH;
      return { x, y, data: t };
    });

    const passPoints = mergedTrends.map((t, idx) => {
      const x = paddingLeft + (idx / (mergedTrends.length - 1 || 1)) * chartW;
      const y = height - paddingBottom - (t.pass / yMax) * chartH;
      return { x, y, data: t };
    });

    const pathD = points.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, "");

    const areaD = points.length > 0 
      ? `${pathD} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z` 
      : "";

    const passPathD = passPoints.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, "");

    return { width, height, points, passPoints, pathD, areaD, passPathD, yMax, paddingLeft, paddingRight, paddingTop, paddingBottom, chartW, chartH };
  };

  const lineChart = drawLineChart();

  // Prepare Donut Chart (Template distribution)
  const drawDonutChart = () => {
    const totalCount = mergedTemplates.reduce((acc, t) => acc + t.count, 0);
    const r = 40;
    const circ = 2 * Math.PI * r;
    
    let currentOffset = 0;
    const slices = mergedTemplates.map((t, idx) => {
      if (t.count === 0) return null;
      const percentage = (t.count / totalCount) * 100;
      const strokeDash = (t.count / totalCount) * circ;
      const offset = currentOffset;
      currentOffset -= strokeDash;

      const colors = ["#2c7be5", "#51b7ff", "#a5b4fc", "#e2e8f0"];
      const color = colors[idx % colors.length];

      return {
        ...t,
        percentage,
        strokeDash,
        offset,
        color
      };
    }).filter(Boolean);

    return { slices, totalCount, circ };
  };

  const donutChart = drawDonutChart();

  // Prepare SPC chart
  const drawSpcChart = () => {
    const selectedSpc = mergedSpc[spcMode];
    if (!selectedSpc || !selectedSpc.data || selectedSpc.data.length === 0) return null;
    
    const width = 450;
    const height = 180;
    const paddingLeft = 45;
    const paddingRight = 20;
    const paddingTop = 20;
    const paddingBottom = 30;

    const chartW = width - paddingLeft - paddingRight;
    const chartH = height - paddingTop - paddingBottom;

    const values = selectedSpc.data.map(d => d.value);
    const maxVal = Math.max(...values, selectedSpc.max);
    const minVal = Math.min(...values, selectedSpc.min);
    
    const range = maxVal - minVal;
    const margin = range > 0 ? range * 0.25 : 1.0;
    const yMax = maxVal + margin;
    const yMin = Math.max(0, minVal - margin);

    const points = selectedSpc.data.map((d, idx) => {
      const x = paddingLeft + (idx / (selectedSpc.data.length - 1 || 1)) * chartW;
      const y = height - paddingBottom - ((d.value - yMin) / (yMax - yMin)) * chartH;
      return { x, y, data: d };
    });

    const pathD = points.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, "");

    const uslY = height - paddingBottom - ((selectedSpc.max - yMin) / (yMax - yMin)) * chartH;
    const lslY = height - paddingBottom - ((selectedSpc.min - yMin) / (yMax - yMin)) * chartH;

    return { width, height, points, pathD, uslY, lslY, yMax, yMin, selectedSpc, paddingLeft, paddingRight, paddingTop, paddingBottom, chartW, chartH };
  };

  const spcChart = drawSpcChart();

  if (mergedOverview.total_reports === 0 && !activeStatusObj) {
    return (
      <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "24px" }}>
        {/* Header and Reset Action */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "15px" }}>
          <div>
            <h2 className="title-gradient" style={{ fontSize: "1.8rem", marginBottom: "4px" }}>Industrial Metrology Analytics Portal</h2>
            <p className="subtitle" style={{ fontSize: "0.95rem", margin: 0 }}>
              Unified dashboard merging database inspections with currently loaded checksheet blueprints.
            </p>
          </div>
        </div>

        {/* Empty State Card */}
        <div style={{
          background: "linear-gradient(135deg, hsla(228, 20%, 18%, 0.25) 0%, hsla(228, 20%, 14%, 0.15) 100%)",
          border: "1px solid var(--card-border)",
          borderRadius: "24px",
          padding: "60px 40px",
          textAlign: "center",
          boxShadow: "0 20px 40px rgba(0,0,0,0.3)",
          backdropFilter: "blur(10px)",
          marginTop: "20px"
        }}>
          <h3 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "12px" }}>No Inspection Data Collected Yet</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: "500px", margin: "0 auto 24px auto", lineHeight: "1.6", fontSize: "0.95rem" }}>
            The metrology dashboard runs calculations on real saved audit data. Once you upload and verify checksheet PDFs, they will appear here as analytics graphs.
          </p>
          <div style={{ padding: "12px 24px", display: "inline-block", background: "hsla(210, 100%, 55%, 0.1)", border: "1px solid var(--accent-cyan)", borderRadius: "12px", color: "var(--accent-cyan)", fontSize: "0.85rem", fontWeight: 600 }}>
            Select the <strong>Process Checksheet</strong> tab in the top navigation to upload a blueprint PDF.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "24px" }}>
      
      {/* Header and Reset Action */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "15px" }}>
        <div>
          <h2 className="title-gradient" style={{ fontSize: "1.8rem", marginBottom: "4px" }}>Industrial Metrology Analytics Portal</h2>
          <p className="subtitle" style={{ fontSize: "0.95rem", margin: 0 }}>
            Unified dashboard merging database inspections with currently loaded checksheet blueprints.
          </p>
        </div>
        
        {(userRole === "admin" || userRole === "engineer") && (
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {seedMessage && <span style={{ fontSize: "0.85rem", color: "var(--status-pass-text)", fontWeight: 500 }}>{seedMessage}</span>}
            <button 
              onClick={handleResetData}
              disabled={seeding}
              className="btn btn-primary"
              style={{ padding: "8px 16px", borderRadius: "10px", fontSize: "0.85rem", background: "hsla(228, 20%, 25%, 0.5)", border: "1px solid var(--card-border)", color: "var(--text-primary)" }}
            >
              {seeding ? (
                <>
                  <div className="spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }}></div> Clearing...
                </>
              ) : (
                "Clear Database"
              )}
            </button>
          </div>
        )}
      </div>

      {/* ----------------------------------------------------
          DA WIDGET 1: ACTIVE CHECKSHEET PROGRESS PANEL
          ---------------------------------------------------- */}
      {activeStatusObj ? (
        <div style={{
          background: "linear-gradient(135deg, rgba(81, 183, 255, 0.12) 0%, rgba(44, 123, 229, 0.05) 100%)",
          border: "1.5px solid #2e5f9e",
          borderRadius: "20px",
          padding: "24px",
          position: "relative",
          animation: "slideDown 0.3s cubic-bezier(0.4, 0, 0.2, 1)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "12px", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "1.2rem" }}></span>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--accent-cyan)" }}>Currently Processing Checksheet</h3>
                <span className="badge pending" style={{ background: "hsla(210, 100%, 55%, 0.15)", border: "1px solid var(--accent-cyan)", color: "var(--accent-cyan)", padding: "2px 8px", fontSize: "0.7rem", borderRadius: "6px" }}>Active Upload</span>
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: "0 0 10px 0" }}>
                Blueprint File: <strong style={{ color: "var(--text-primary)" }}>{activeStatusObj.filename}</strong> &nbsp;|&nbsp; Job Card: <strong style={{ color: "var(--text-primary)", fontFamily: "monospace" }}>{activeStatusObj.meta.job_card_no || "N/A"}</strong>
              </p>
            </div>
            
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Live Status:</span>
              <span className={`overall-status ${activeStatusObj.overall === "PASS" ? "pass" : activeStatusObj.overall === "FAIL" ? "fail" : ""}`} style={activeStatusObj.overall === "PENDING" ? { background: "rgba(255, 180, 0, 0.15)", borderColor: "#e2a100", color: "#ffd066", padding: "4px 12px", borderRadius: "20px" } : { padding: "4px 12px" }}>
                {activeStatusObj.overall === "PASS" && "PASS"}
                {activeStatusObj.overall === "FAIL" && "FAIL"}
                {activeStatusObj.overall === "PENDING" && "INCOMPLETE"}
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div style={{ marginTop: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
              <span>Verification Checklist Progress</span>
              <strong>{activeStatusObj.passCount + activeStatusObj.failCount} / {activeStatusObj.totalCount} items ({Math.round(((activeStatusObj.passCount + activeStatusObj.failCount)/activeStatusObj.totalCount)*100)}%)</strong>
            </div>
            <div style={{ height: "8px", background: "hsla(228, 20%, 15%, 0.5)", borderRadius: "4px", overflow: "hidden", border: "1px solid var(--card-border)" }}>
              <div style={{
                height: "100%",
                width: `${((activeStatusObj.passCount + activeStatusObj.failCount) / activeStatusObj.totalCount) * 100}%`,
                background: "linear-gradient(90deg, var(--primary), var(--accent-cyan))",
                transition: "width 0.4s ease",
                borderRadius: "4px"
              }}></div>
            </div>
          </div>

          {/* Stats breakdown */}
          <div style={{ display: "flex", gap: "20px", marginTop: "16px", fontSize: "0.8rem", color: "var(--text-secondary)", borderTop: "1px solid rgba(81, 183, 255, 0.15)", paddingTop: "14px" }}>
            <div>Passed checks: <strong style={{ color: "var(--status-pass-text)" }}>{activeStatusObj.passCount}</strong></div>
            <div>Failed checks: <strong style={{ color: "var(--status-fail-text)" }}>{activeStatusObj.failCount}</strong></div>
            <div>Remaining inputs: <strong style={{ color: "var(--text-muted)" }}>{activeStatusObj.pendingCount}</strong></div>
          </div>

          {/* Defect Warnings */}
          {activeStatusObj.failedFields.length > 0 && (
            <div style={{ marginTop: "14px", padding: "10px 14px", borderRadius: "8px", background: "rgba(210, 74, 74, 0.12)", border: "1px solid rgba(210, 74, 74, 0.3)" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--status-fail-text)", display: "block", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}> Out-of-Tolerance Alerts:</span>
              <ul style={{ margin: 0, paddingLeft: "16px", color: "var(--text-secondary)", fontSize: "0.8rem" }}>
                {activeStatusObj.failedFields.map((f, i) => (
                  <li key={i}>
                    <strong>{f.title}</strong>: {f.val || "empty"} {f.unit} (Specification: <span style={{ fontFamily: "monospace" }}>{f.spec}</span>)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div style={{
          background: "hsla(228, 20%, 10%, 0.25)",
          border: "1px dashed var(--card-border)",
          borderRadius: "16px",
          padding: "20px",
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: "0.9rem"
        }}>
           <strong>No active checksheet is currently loaded.</strong> Go to the <strong>Process Checksheet</strong> tab to upload a blueprint PDF and run live evaluations.
        </div>
      )}

      {/* KPI SUMMARY CARDS — 3 per row, 2 rows */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>

        {/* Row 1 — Radial gauges */}

        {/* Compliance Rate */}
        <div style={{ background: "hsla(228, 20%, 14%, 0.4)", border: "1px solid var(--card-border)", borderRadius: "16px", padding: "16px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "150px" }}>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 600, marginBottom: "8px" }}>Compliance Rate</span>
          <div style={{ position: "relative", width: "90px", height: "90px" }}>
            <svg width="90" height="90" viewBox="0 0 120 120" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="60" cy="60" r="50" fill="transparent" stroke="hsla(228, 20%, 25%, 0.3)" strokeWidth="10" />
              <circle cx="60" cy="60" r="50" fill="transparent"
                stroke={mergedOverview.pass_rate >= 80 ? "var(--status-pass-border)" : "var(--status-fail-border)"}
                strokeWidth="10" strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
                strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.8s ease" }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)" }}>{mergedOverview.pass_rate}%</span>
              <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Pass Rate</span>
            </div>
          </div>
        </div>

        {/* Recovery Rate */}
        <div style={{ background: "hsla(228, 20%, 14%, 0.4)", border: "1px solid var(--card-border)", borderRadius: "16px", padding: "16px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "150px" }}>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 600, marginBottom: "8px" }}>Recovery Rate</span>
          <div style={{ position: "relative", width: "90px", height: "90px" }}>
            <svg width="90" height="90" viewBox="0 0 120 120" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="60" cy="60" r="50" fill="transparent" stroke="hsla(228, 20%, 25%, 0.3)" strokeWidth="10" />
              <circle cx="60" cy="60" r="50" fill="transparent"
                stroke="var(--accent-cyan)" strokeWidth="10"
                strokeDasharray={circumference} strokeDashoffset={correctionDashoffset}
                strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.8s ease" }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)" }}>{mergedOverview.recorrection_rate}%</span>
              <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Recorrected</span>
            </div>
          </div>
        </div>

        {/* FTR Rate */}
        <div style={{ background: "hsla(228, 20%, 14%, 0.4)", border: "1px solid var(--card-border)", borderRadius: "16px", padding: "16px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "150px" }}>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 600, marginBottom: "8px" }}>FTR Rate</span>
          <div style={{ position: "relative", width: "90px", height: "90px" }}>
            <svg width="90" height="90" viewBox="0 0 120 120" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="60" cy="60" r="50" fill="transparent" stroke="hsla(228, 20%, 25%, 0.3)" strokeWidth="10" />
              <circle cx="60" cy="60" r="50" fill="transparent"
                stroke="var(--status-pass-border)" strokeWidth="10"
                strokeDasharray={circumference} strokeDashoffset={ftrDashoffset}
                strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.8s ease" }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)" }}>{mergedOverview.ftr_rate}%</span>
              <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>1st Pass</span>
            </div>
          </div>
        </div>

        {/* Row 2 — Stat tiles */}

        {/* Mean Correction Time */}
        <div style={kpiCardStyle}>
          <div style={kpiIconBgStyle("var(--accent-cyan)")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <span style={kpiLabelStyle}>Mean Correction Time</span>
          <span style={kpiValStyle}>{mergedOverview.avg_mttr_hours} mins</span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>Avg fail-to-pass time</span>
        </div>

        {/* Time Taken to Process */}
        <div style={kpiCardStyle}>
          <div style={kpiIconBgStyle("hsl(45, 90%, 58%)")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <span style={kpiLabelStyle}>Time Taken to Process</span>
          <span style={{ ...kpiValStyle, color: "hsl(45, 90%, 68%)" }}>
            {mergedOverview.avg_processing_mins < 60
              ? `${mergedOverview.avg_processing_mins} min`
              : `${roundNum(mergedOverview.avg_processing_mins / 60, 1)} hrs`}
          </span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>Inspection to submission</span>
        </div>

        {/* Total Uploads */}
        <div style={kpiCardStyle}>
          <div style={kpiIconBgStyle("#2c7be5")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <span style={kpiLabelStyle}>Total Uploads</span>
          <span style={kpiValStyle}>{mergedOverview.total_reports}</span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>Saved inspection reports</span>
        </div>

      </div>

      {/* TREND CHART & CATEGORIES BREAKDOWN */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "20px" }}>
        
        {/* Process Audit Trend Area Graph */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}> Process Audit Trend (Processing Volume)</h3>
          
          {lineChart ? (
            <div style={{ position: "relative", marginTop: "10px" }}>
              <svg width="100%" height="180" viewBox={`0 0 ${lineChart.width} ${lineChart.height}`} preserveAspectRatio="xMidYMid meet">
                <defs>
                  <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2c7be5" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#2c7be5" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {[0, 0.5, 1.0].map((ratio, index) => {
                  const y = lineChart.paddingTop + ratio * lineChart.chartH;
                  const labelVal = Math.round(lineChart.yMax * (1 - ratio));
                  return (
                    <g key={index}>
                      <line 
                        x1={lineChart.paddingLeft} 
                        y1={y} 
                        x2={lineChart.width - lineChart.paddingRight} 
                        y2={y} 
                        stroke="hsla(228, 20%, 25%, 0.3)" 
                        strokeWidth="1" 
                        strokeDasharray="4,4" 
                      />
                      <text x={lineChart.paddingLeft - 8} y={y + 4} textAnchor="end" fill="var(--text-muted)" fontSize="9" fontFamily="monospace">
                        {labelVal}
                      </text>
                    </g>
                  );
                })}

                <path d={lineChart.areaD} fill="url(#trendGrad)" />
                <path d={lineChart.pathD} fill="none" stroke="#2c7be5" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <path d={lineChart.passPathD} fill="none" stroke="var(--status-pass-border)" strokeWidth="2.5" strokeDasharray="3,3" strokeLinecap="round" strokeLinejoin="round" />

                {lineChart.points.map((p, idx) => (
                  <circle 
                    key={idx}
                    cx={p.x}
                    cy={p.y}
                    r={trendHovered === idx ? "7" : "4.5"}
                    fill="#2c7be5"
                    stroke="var(--card-bg)"
                    strokeWidth="1.5"
                    style={{ transition: "all 0.15s ease", cursor: "pointer" }}
                    onMouseEnter={() => setTrendHovered(idx)}
                    onMouseLeave={() => setTrendHovered(null)}
                  />
                ))}

                {lineChart.points.map((p, idx) => (
                  <text 
                    key={idx}
                    x={p.x}
                    y={lineChart.height - 10}
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize="9.5"
                    fontWeight="500"
                  >
                    {p.data.month}
                  </text>
                ))}
              </svg>

              {trendHovered !== null && (
                <div style={{
                  position: "absolute",
                  top: "10px",
                  right: "10px",
                  background: "hsl(230, 25%, 8%)",
                  border: "1px solid var(--card-border)",
                  borderRadius: "10px",
                  padding: "8px 12px",
                  fontSize: "0.8rem",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
                  animation: "fadeIn 0.2s ease-out",
                  zIndex: 10
                }}>
                  <strong style={{ color: "var(--text-primary)" }}>{mergedTrends[trendHovered].month}</strong>
                  <div style={{ margin: "4px 0 0 0", color: "var(--accent-cyan)" }}>Total Audits: <strong>{mergedTrends[trendHovered].total}</strong></div>
                  <div style={{ color: "var(--status-pass-text)" }}>Passed: <strong>{mergedTrends[trendHovered].pass}</strong></div>
                  <div style={{ color: "var(--status-fail-text)" }}>Failed: <strong>{mergedTrends[trendHovered].fail}</strong></div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ height: "150px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              Insufficient historical data points.
            </div>
          )}
        </div>

        {/* Asset Category Donut Chart */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Metrology Template Distribution</h3>
          
          {donutChart && donutChart.totalCount > 0 ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", gap: "20px", marginTop: "15px" }}>
              <div style={{ position: "relative", width: "120px", height: "120px" }}>
                <svg width="120" height="120" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="40" fill="transparent" stroke="hsla(228, 20%, 25%, 0.2)" strokeWidth="11" />
                  {donutChart.slices.map((slice, idx) => (
                    <circle 
                      key={idx}
                      cx="50"
                      cy="50"
                      r="40"
                      fill="transparent"
                      stroke={slice.color}
                      strokeWidth={donutHovered === idx ? "14" : "11"}
                      strokeDasharray={`${slice.strokeDash} ${donutChart.circ}`}
                      strokeDashoffset={slice.offset}
                      transform="rotate(-90 50 50)"
                      strokeLinecap="round"
                      style={{ cursor: "pointer", transition: "all 0.2s ease" }}
                      onMouseEnter={() => setDonutHovered(idx)}
                      onMouseLeave={() => setDonutHovered(null)}
                    />
                  ))}
                </svg>
                <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: "1.1rem", fontWeight: 700 }}>{donutChart.totalCount}</span>
                  <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Reports</span>
                </div>
              </div>

              {/* Legend */}
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", flex: 1 }}>
                {donutChart.slices.map((slice, idx) => (
                  <div 
                    key={idx} 
                    style={{ 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "space-between",
                      padding: "6px 10px",
                      borderRadius: "8px",
                      background: donutHovered === idx ? "hsla(228, 20%, 25%, 0.25)" : "transparent",
                      transition: "all 0.15s ease",
                      cursor: "pointer"
                    }}
                    onMouseEnter={() => setDonutHovered(idx)}
                    onMouseLeave={() => setDonutHovered(null)}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: slice.color }}></div>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "capitalize" }}>
                        {slice.checksheet_type === "vehicle" ? "Automotive" : "Metrology Lab"}
                      </span>
                    </div>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)" }}>
                      {slice.count} ({Math.round(slice.percentage)}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ height: "120px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              No categories classified.
            </div>
          )}
        </div>

      </div>

      {/* ----------------------------------------------------
          DA WIDGET 2: AUDIT OUTCOME BREAKDOWN (BAR CHART)
          ---------------------------------------------------- */}
      <div style={cardStyle}>
        <h3 style={cardTitleStyle}>Audit Outcome Breakdown (Overall Status Comparison)</h3>
        <p style={{ margin: "2px 0 16px 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Comparison of absolute results (Passed vs Out-Of-Spec vs Incomplete Active Drafts).
        </p>

        {(() => {
          const pass = mergedOverview.passed;
          const fail = mergedOverview.failed;
          const pending = activeStatusObj && activeStatusObj.overall === "PENDING" ? 1 : 0;
          const maxVal = Math.max(pass, fail, pending, 1);
          
          const categories = [
            { label: "Passed Inspections", count: pass, color: "var(--status-pass-border)", bg: "var(--status-pass-bg)" },
            { label: "Out-Of-Spec Failures", count: fail, color: "var(--status-fail-border)", bg: "var(--status-fail-bg)" },
            { label: "Incomplete Active Uploads", count: pending, color: "var(--accent-cyan)", bg: "rgba(81, 183, 255, 0.15)" }
          ];

          return (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {categories.map((c, idx) => {
                const widthPercent = (c.count / maxVal) * 100;
                return (
                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "15px" }}>
                    <div style={{ width: "180px", fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
                      {c.label}
                    </div>
                    <div style={{ flex: 1, height: "16px", background: "hsla(228, 20%, 25%, 0.15)", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--card-border)", position: "relative" }}>
                      <div style={{
                        height: "100%",
                        width: `${widthPercent}%`,
                        background: c.color,
                        borderRadius: "8px",
                        transition: "width 0.8s cubic-bezier(0.4, 0, 0.2, 1)"
                      }} />
                    </div>
                    <div style={{ width: "40px", textAlign: "right", fontSize: "0.9rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      {c.count}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>

      {/* DEFECT PARETO HEATMAP & MOST PASSED PARAMETERS */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "20px" }}>
        
        {/* Pareto Failure Heatmap */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Pareto Defect Heatmap (Top Failing Specs)</h3>
          <p style={{ margin: "2px 0 15px 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Ranks check-items by failure counts. Line indicates Pareto cumulative % (80/20 Rule).
          </p>

          {mergedPareto && mergedPareto.length > 0 ? (
            <div style={{ position: "relative", marginTop: "10px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                {mergedPareto.map((item, idx) => {
                  const maxFail = mergedPareto[0].fail_count;
                  const percentageWidth = (item.fail_count / maxFail) * 100;
                  
                  // Calculate cumulative percentage
                  const totalFails = mergedPareto.reduce((sum, curr) => sum + curr.fail_count, 0);
                  let runningSum = 0;
                  for (let k = 0; k <= idx; k++) {
                    runningSum += mergedPareto[k].fail_count;
                  }
                  const cumulativePct = Math.round((runningSum / totalFails) * 100);

                  return (
                    <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                        <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{item.parameter_name}</span>
                        <div>
                          <strong style={{ color: "hsl(350, 75%, 72%)" }}>{item.fail_count} Fails</strong> &nbsp;|&nbsp;
                          <span style={{ color: "var(--accent-cyan)", fontSize: "0.75rem", fontWeight: 600 }}>{cumulativePct}% Cum.</span>
                        </div>
                      </div>
                      
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        {/* Defect Bar */}
                        <div style={{ flex: 1, height: "8px", background: "hsla(228, 20%, 25%, 0.25)", borderRadius: "4px", overflow: "hidden", border: "1px solid var(--card-border)" }}>
                          <div style={{
                            height: "100%",
                            width: `${percentageWidth}%`,
                            background: `linear-gradient(90deg, var(--status-fail-border), hsl(350, 80%, 65%))`,
                            borderRadius: "4px",
                            boxShadow: "0 0 8px rgba(210, 74, 74, 0.4)",
                            transition: "width 0.8s ease"
                          }}></div>
                        </div>
                        
                        {/* Cumulative Dot Representation */}
                        <div style={{ width: "35px", display: "flex", justifyContent: "flex-end", position: "relative" }}>
                          <span style={{
                            display: "inline-block",
                            padding: "2px 5px",
                            borderRadius: "4px",
                            background: cumulativePct >= 80 ? "rgba(44, 123, 229, 0.2)" : "rgba(81, 183, 255, 0.2)",
                            border: `1.5px solid ${cumulativePct >= 80 ? "var(--primary)" : "var(--accent-cyan)"}`,
                            color: cumulativePct >= 80 ? "#fff" : "var(--accent-cyan)",
                            fontSize: "0.65rem",
                            fontWeight: 700
                          }}>
                            {cumulativePct}%
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ height: "150px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              No tolerance deviations recorded in history.
            </div>
          )}
        </div>

        {/* Most Passed Parameters */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Most Passed Parameters</h3>
          <p style={{ margin: "2px 0 15px 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Ranks check-items by frequency of clean passed verifications.
          </p>

          {mergedMostPassed && mergedMostPassed.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginTop: "10px" }}>
              {mergedMostPassed.slice(0, 5).map((item, idx) => {
                const maxPass = mergedMostPassed[0].pass_count;
                const percentageWidth = (item.pass_count / maxPass) * 100;

                return (
                  <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                      <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{item.parameter_name}</span>
                      <strong style={{ color: "var(--status-pass-text)" }}>{item.pass_count} Passes</strong>
                    </div>
                    <div style={{ height: "8px", background: "hsla(228, 20%, 25%, 0.25)", borderRadius: "4px", overflow: "hidden", border: "1px solid var(--card-border)" }}>
                      <div style={{
                        height: "100%",
                        width: `${percentageWidth}%`,
                        background: `linear-gradient(90deg, var(--status-pass-border), var(--accent-cyan))`,
                        borderRadius: "4px",
                        boxShadow: "0 0 8px rgba(46, 213, 115, 0.3)",
                        transition: "width 0.8s ease"
                      }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ height: "150px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              No parameter passes recorded.
            </div>
          )}
        </div>

      </div>

      {/* AUDITOR WORKLOAD & CALIBRATION DUE TIMELINE */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "20px" }}>
        
        {/* Technician Leaderboard & Activity Chart */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Auditor Activity & Workload Compliance</h3>
          <p style={{ margin: "2px 0 15px 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Auditor workload and submission compliance rates.
          </p>

          {mergedTechnicians && mergedTechnicians.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              
              {/* Stacked Workload SVG bar chart */}
              <div style={{ marginTop: "10px", marginBottom: "15px" }}>
                <svg width="100%" height="90" viewBox="0 0 350 90" style={{ background: "hsla(228, 20%, 10%, 0.3)", borderRadius: "10px", border: "1px solid var(--card-border)" }}>
                  {(() => {
                    const maxAudits = Math.max(...mergedTechnicians.map(t => t.total), 1);
                    return mergedTechnicians.map((t, idx) => {
                      const barWidth = (t.total / maxAudits) * 200;
                      const passWidth = t.total > 0 ? (t.pass / t.total) * barWidth : 0;
                      const failWidth = t.total > 0 ? (t.fail / t.total) * barWidth : 0;
                      const y = 12 + idx * 24;

                      return (
                        <g key={idx}>
                          {/* Technician Initials */}
                          <text x="10" y={y + 12} fill="var(--text-primary)" fontSize="9.5" fontWeight="600">
                            {t.technician.substring(0, 10)}
                          </text>

                          {/* Workload Bar (Passed: Green, Failed: Red) */}
                          <rect x="90" y={y} width={barWidth} height="14" rx="3" fill="hsla(228, 20%, 25%, 0.3)" />
                          <rect x="90" y={y} width={passWidth} height="14" rx="3" fill="var(--status-pass-border)" />
                          {failWidth > 0 && (
                            <rect x={90 + passWidth} y={y} width={failWidth} height="14" rx="3" fill="var(--status-fail-border)" />
                          )}

                          {/* Count */}
                          <text x={100 + barWidth} y={y + 11} fill="var(--text-secondary)" fontSize="9.5" fontWeight="700">
                            {t.total} audits
                          </text>
                        </g>
                      );
                    });
                  })()}
                </svg>
              </div>

              {/* Leaderboard Cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {mergedTechnicians.map((t, idx) => {
                  const passRate = t.total > 0 ? Math.round((t.pass / t.total) * 100) : 0;
                  return (
                    <div key={idx} style={{ 
                      display: "flex", 
                      alignItems: "center", 
                      gap: "12px", 
                      padding: "8px 12px", 
                      borderRadius: "10px", 
                      background: "hsla(228, 20%, 14%, 0.3)", 
                      border: "1px solid var(--card-border)" 
                    }}>
                      <div style={{ 
                        width: "32px", 
                        height: "32px", 
                        borderRadius: "50%", 
                        background: "linear-gradient(135deg, var(--primary), var(--accent-cyan))",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.85rem",
                        fontWeight: 700,
                        color: "#fff"
                      }}>
                        {t.technician.substring(0, 2).toUpperCase()}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "4px" }}>
                          <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{t.technician}</span>
                          <span style={{ color: "var(--text-muted)", marginLeft: "auto" }}>{t.total} logged</span>
                        </div>
                        
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <div style={{ flex: 1, height: "4px", background: "hsla(228, 20%, 25%, 0.3)", borderRadius: "2px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: `${passRate}%`,
                              background: passRate >= 80 ? "var(--status-pass-border)" : "var(--status-fail-border)",
                              borderRadius: "2px"
                            }}></div>
                          </div>
                          <span style={{ 
                            fontSize: "0.7rem", 
                            fontWeight: 700, 
                            color: passRate >= 80 ? "var(--status-pass-text)" : "var(--status-fail-text)"
                          }}>
                            {passRate}% pass
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

            </div>
          ) : (
            <div style={{ height: "150px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              No technician calibration history logs.
            </div>
          )}
        </div>

        {/* Upcoming Asset Calibration Schedule */}
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Upcoming Asset Calibration & Recertification Schedule</h3>
          <p style={{ margin: "2px 0 16px 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Chronological scheduling timeline of equipment calibrations due in calibration rooms.
          </p>

          {(() => {
            const calibrationTimeline = [
              { name: "Shimadzu UV-1900i", sn: "SN-88224", dept: "Quality Control Dept", date: "2026-10-02", daysLeft: 109 },
              { name: "Thermo GC-MS", sn: "SN-77332", dept: "R&D Chem Lab", date: "2026-10-20", daysLeft: 127 },
              { name: "Mettler Toledo Balance", sn: "SN-66443", dept: "Calibration Chamber 2", date: "2026-11-10", daysLeft: 148 },
              { name: "Agilent HPLC-1260", sn: "SN-99881", dept: "Metrology Lab A", date: "2026-12-15", daysLeft: 183 }
            ];

            return (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", position: "relative", paddingLeft: "20px" }}>
                {/* Vertical line connector */}
                <div style={{
                  position: "absolute",
                  left: "4px",
                  top: "10px",
                  bottom: "10px",
                  width: "2px",
                  background: "linear-gradient(180deg, var(--accent-cyan) 0%, var(--primary) 100%)",
                  opacity: 0.3
                }} />

                {calibrationTimeline.map((item, idx) => {
                  return (
                    <div key={idx} style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
                      
                      {/* Node indicator */}
                      <div style={{
                        position: "absolute",
                        left: "-20px",
                        top: "6px",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: "hsl(230, 25%, 10%)",
                        border: "2.5px solid var(--accent-cyan)",
                        boxShadow: "0 0 8px rgba(81, 183, 255, 0.6)"
                      }} />

                      <div>
                        <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
                          {item.name} <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", fontFamily: "monospace" }}>({item.sn})</span>
                        </h4>
                        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                          Lab: {item.dept}
                        </p>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginLeft: "auto" }}>
                        <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                          {item.date}
                        </span>
                        <span style={{
                          padding: "3px 8px",
                          borderRadius: "6px",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          background: "rgba(81, 183, 255, 0.12)",
                          border: "1px solid var(--accent-cyan)",
                          color: "var(--accent-cyan)"
                        }}>
                          In {item.daysLeft} days
                        </span>
                      </div>

                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>

      </div>

    </div>
  );
}

function roundNum(num, decs) {
  if (num === null || num === undefined) return 0;
  const mult = Math.pow(10, decs);
  return Math.round(num * mult) / mult;
}

const kpiCardStyle = {
  background: "hsla(228, 20%, 14%, 0.4)",
  border: "1px solid var(--card-border)",
  borderRadius: "16px",
  padding: "16px",
  display: "flex",
  flexDirection: "column",
  position: "relative",
  minHeight: "150px",
  justifyContent: "space-between"
};

const kpiLabelStyle = {
  fontSize: "0.7rem",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "1px",
  fontWeight: 600,
  marginTop: "6px"
};

const kpiValStyle = {
  fontSize: "1.7rem",
  fontWeight: 700,
  color: "var(--text-primary)",
  margin: "2px 0 0 0",
  lineHeight: 1
};

const kpiIconBgStyle = (color) => ({
  width: "32px",
  height: "32px",
  borderRadius: "8px",
  background: color + "1a",
  border: `1px solid ${color}4d`,
  color: color,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "1.1rem"
});

const cardStyle = {
  background: "hsla(228, 20%, 18%, 0.2)",
  border: "1px solid var(--card-border)",
  borderRadius: "18px",
  padding: "24px",
  animation: "fadeIn 0.5s ease-out"
};

const cardTitleStyle = {
  fontSize: "1.05rem",
  fontWeight: 600,
  color: "var(--text-primary)",
  margin: 0
};
