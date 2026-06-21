from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.db import get_db
from database import crud
from app.core.rbac import get_current_user, require_role
from app.models.user import User

router = APIRouter(prefix="/checksheets", tags=["Checksheets"])


class ResultIn(BaseModel):
    check_item_id:    int
    measured_value:   Optional[str] = None
    measured_numeric: Optional[float] = None
    status:           Optional[str] = None
    notes:            Optional[str] = None

class SessionIn(BaseModel):
    template_id:     int
    lead_technician: Optional[str] = None
    inspection_date: Optional[str] = None
    job_card_no:     Optional[str] = None
    vehicle_model:   Optional[str] = None
    vin_chassis:     Optional[str] = None
    odometer_km:     Optional[str] = None
    instrument_name: Optional[str] = None
    model_serial:    Optional[str] = None
    location_dept:   Optional[str] = None
    next_due_date:   Optional[str] = None
    results:         list[ResultIn]


@router.post("/save-report")
def save_report(
    payload: SessionIn, 
    db: Session = Depends(get_db),
    user: User = Depends(require_role("engineer"))  # Only engineer/admin can save
):
    session_data = payload.model_dump(exclude={"results"})
    results_data = [r.model_dump() for r in payload.results]
    
    # Associate technician username if not manually entered
    if not session_data.get("lead_technician"):
        session_data["lead_technician"] = user.username
        
    session = crud.save_inspection(db, session_data, results_data)
    return {"id": session.id, "overall_status": session.overall_status}


@router.get("/reports")
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)  # Any logged in user can view
):
    sessions = crud.get_all_sessions(db)
    return [
        {
            "id": s.id,
            "template_id": s.template_id,
            "lead_technician": s.lead_technician,
            "inspection_date": s.inspection_date,
            "overall_status": s.overall_status,
            "submitted_at": str(s.submitted_at),
            
            # Context fields for frontend preview
            "vehicle_model": s.vehicle_model,
            "vin_chassis": s.vin_chassis,
            "odometer_km": s.odometer_km,
            "instrument_name": s.instrument_name,
            "model_serial": s.model_serial,
            "location_dept": s.location_dept,
            "next_due_date": s.next_due_date,
            "job_card_no": s.job_card_no,
        }
        for s in sessions
    ]

@router.get("/reports/{session_id}")
def get_report(
    session_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    s = crud.get_session_with_results(db, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Return formatted session data with results mapped
    results = []
    for r in s.results:
        results.append({
            "id": r.id,
            "check_item_id": r.check_item_id,
            "measured_value": r.measured_value,
            "measured_numeric": r.measured_numeric,
            "status": r.status,
            "notes": r.notes,
            "parameter_name": r.check_item.parameter_name,
            "unit": r.check_item.unit,
            "range_standard": r.check_item.range_standard,
            "range_min": r.check_item.range_min,
            "range_max": r.check_item.range_max,
            "range_type": r.check_item.range_type,
        })
        
    return {
        "id": s.id,
        "template_id": s.template_id,
        "template_name": s.template.template_name,
        "checksheet_type": s.template.checksheet_type,
        "lead_technician": s.lead_technician,
        "inspection_date": s.inspection_date,
        "overall_status": s.overall_status,
        "submitted_at": str(s.submitted_at),
        "vehicle_model": s.vehicle_model,
        "vin_chassis": s.vin_chassis,
        "odometer_km": s.odometer_km,
        "instrument_name": s.instrument_name,
        "model_serial": s.model_serial,
        "location_dept": s.location_dept,
        "next_due_date": s.next_due_date,
        "job_card_no": s.job_card_no,
        "results": results
    }

@router.get("/templates")
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return [
        {
            "id": t.id,
            "template_name": t.template_name,
            "form_ref": t.form_ref,
            "org_name": t.org_name,
            "checksheet_type": t.checksheet_type,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in crud.get_all_templates(db)
    ]

@router.get("/templates/{template_id}/items")
def get_template_items(
    template_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    items = crud.get_check_items(db, template_id)
    if not items:
        raise HTTPException(status_code=404, detail="Template not found")
    return [
        {
            "id": i.id,
            "template_id": i.template_id,
            "ref_number": i.ref_number,
            "parameter_name": i.parameter_name,
            "unit": i.unit,
            "range_standard": i.range_standard,
            "range_min": i.range_min,
            "range_max": i.range_max,
            "range_type": i.range_type,
        }
        for i in items
    ]


from sqlalchemy import text
from collections import defaultdict
from datetime import datetime

@router.get("/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Fetch all inspection sessions ordered chronologically
    sessions_rows = db.execute(text("""
        SELECT id, template_id, vehicle_model, vin_chassis, instrument_name, model_serial, job_card_no, overall_status, submitted_at
        FROM inspection_sessions
        ORDER BY submitted_at ASC
    """)).fetchall()

    # Group sessions by unique asset / job identifier
    groups = defaultdict(list)
    for s in sessions_rows:
        key = None
        if s.job_card_no and s.job_card_no.strip():
            key = s.job_card_no.strip()
        elif s.vin_chassis and s.vin_chassis.strip():
            key = s.vin_chassis.strip()
        elif s.model_serial and s.model_serial.strip():
            key = s.model_serial.strip()
        else:
            key = f"session_{s.id}"
        groups[key].append(s)

    unique_passed = 0
    unique_failed = 0
    unique_pending = 0
    
    failed_jobs_count = 0
    recorrected_jobs_count = 0
    ftr_passed_jobs = 0
    durations = []

    for key, job_sessions in groups.items():
        statuses = [js.overall_status for js in job_sessions]
        latest_status = job_sessions[-1].overall_status

        if latest_status == 'PASS':
            unique_passed += 1
        elif latest_status == 'FAIL':
            unique_failed += 1
        else:
            unique_pending += 1

        # First-Time Right (FTR) - Was the first attempt a PASS?
        if statuses[0] == 'PASS':
            ftr_passed_jobs += 1

        # Recovery/Correction Rate & MTTR
        if 'FAIL' in statuses:
            failed_jobs_count += 1
            first_fail_idx = statuses.index('FAIL')
            subsequent_statuses = statuses[first_fail_idx:]
            
            # Check if it was ever corrected to PASS subsequently
            if 'PASS' in subsequent_statuses:
                recorrected_jobs_count += 1
                first_pass_idx = first_fail_idx + subsequent_statuses.index('PASS')
                
                fail_time = job_sessions[first_fail_idx].submitted_at
                pass_time = job_sessions[first_pass_idx].submitted_at
                
                if fail_time and pass_time:
                    fail_dt, pass_dt = None, None
                    if isinstance(fail_time, str):
                        try:
                            fail_dt = datetime.fromisoformat(fail_time)
                        except:
                            pass
                    else:
                        fail_dt = fail_time

                    if isinstance(pass_time, str):
                        try:
                            pass_dt = datetime.fromisoformat(pass_time)
                        except:
                            pass
                    else:
                        pass_dt = pass_time

                    if fail_dt and pass_dt:
                        diff = (pass_dt - fail_dt).total_seconds() / 3600.0
                        if diff >= 0:
                            durations.append(diff)

    # Compute DA metric ratios
    recorrection_rate = round((recorrected_jobs_count / failed_jobs_count * 100), 1) if failed_jobs_count > 0 else 0.0
    ftr_rate = round((ftr_passed_jobs / len(groups) * 100), 1) if len(groups) > 0 else 0.0
    avg_mttr = round(sum(durations) / len(durations), 1) if durations else 0.0

    # 1. Total count of saved report sessions
    total_count = len(sessions_rows)
    
    # 2. Volume Trend (by month)
    trend_rows = db.execute(text("""
        SELECT substr(inspection_date, 1, 7) as month, 
               COUNT(*) as total,
               SUM(CASE WHEN overall_status = 'PASS' THEN 1 ELSE 0 END) as pass_count,
               SUM(CASE WHEN overall_status = 'FAIL' THEN 1 ELSE 0 END) as fail_count
        FROM inspection_sessions
        WHERE inspection_date IS NOT NULL AND inspection_date != ''
        GROUP BY month
        ORDER BY month ASC
    """)).fetchall()
    
    trends = []
    for r in trend_rows:
        trends.append({
            "month": r[0],
            "total": r[1],
            "pass": r[2] or 0,
            "fail": r[3] or 0
        })
 
    # 3. Template distribution
    template_rows = db.execute(text("""
        SELECT t.template_name, t.checksheet_type, COUNT(s.id) as cnt
        FROM checksheet_templates t
        LEFT JOIN inspection_sessions s ON s.template_id = t.id
        GROUP BY t.id
    """)).fetchall()
    
    templates = []
    for r in template_rows:
        templates.append({
            "template_name": r[0],
            "checksheet_type": r[1],
            "count": r[2]
        })

    # 4. Top Failing Parameters (Pareto)
    pareto_rows = db.execute(text("""
        SELECT ci.parameter_name, COUNT(r.id) as fail_cnt
        FROM inspection_results r
        JOIN check_items ci ON r.check_item_id = ci.id
        WHERE r.status = 'FAIL'
        GROUP BY ci.parameter_name
        ORDER BY fail_cnt DESC
        LIMIT 5
    """)).fetchall()
    
    pareto = []
    for r in pareto_rows:
        pareto.append({
            "parameter_name": r[0],
            "fail_count": r[1]
        })

    # 4.b Most Passed Parameters (Most frequently entered correct)
    most_passed_rows = db.execute(text("""
        SELECT ci.parameter_name, COUNT(r.id) as pass_cnt
        FROM inspection_results r
        JOIN check_items ci ON r.check_item_id = ci.id
        WHERE r.status = 'PASS'
        GROUP BY ci.parameter_name
        ORDER BY pass_cnt DESC
        LIMIT 5
    """)).fetchall()
    
    most_passed = []
    for r in most_passed_rows:
        most_passed.append({
            "parameter_name": r[0],
            "pass_count": r[1]
        })

    # 5. Technician Leaderboard
    tech_rows = db.execute(text("""
        SELECT lead_technician,
               COUNT(*) as total,
               SUM(CASE WHEN overall_status = 'PASS' THEN 1 ELSE 0 END) as pass_count,
               SUM(CASE WHEN overall_status = 'FAIL' THEN 1 ELSE 0 END) as fail_count
        FROM inspection_sessions
        GROUP BY lead_technician
    """)).fetchall()
    
    technicians_list = []
    for r in tech_rows:
        technicians_list.append({
            "technician": r[0] or "unknown",
            "total": r[1],
            "pass": r[2] or 0,
            "fail": r[3] or 0
        })

    # 6. SPC Drift Analysis for Alternator Charging Voltage (Item 4) and Baseline Voltage Stability (Item 21)
    spc_vehicle_rows = db.execute(text("""
        SELECT s.id, s.job_card_no, s.inspection_date, r.measured_numeric, r.status
        FROM inspection_results r
        JOIN inspection_sessions s ON r.session_id = s.id
        WHERE r.check_item_id = 4 AND r.measured_numeric IS NOT NULL
        ORDER BY s.inspection_date ASC
    """)).fetchall()
    
    spc_vehicle = []
    for r in spc_vehicle_rows:
        spc_vehicle.append({
            "session_id": r[0],
            "job_card_no": r[1] or f"JC-{1000+r[0]}",
            "date": r[2],
            "value": r[3],
            "status": r[4]
        })
        
    spc_instrument_rows = db.execute(text("""
        SELECT s.id, s.job_card_no, s.inspection_date, r.measured_numeric, r.status
        FROM inspection_results r
        JOIN inspection_sessions s ON r.session_id = s.id
        WHERE r.check_item_id = 21 AND r.measured_numeric IS NOT NULL
        ORDER BY s.inspection_date ASC
    """)).fetchall()
    
    spc_instrument = []
    for r in spc_instrument_rows:
        spc_instrument.append({
            "session_id": r[0],
            "job_card_no": r[1] or f"JC-{1000+r[0]}",
            "date": r[2],
            "value": r[3],
            "status": r[4]
        })

    due_soon_count = db.execute(text("""
        SELECT COUNT(*) 
        FROM inspection_sessions 
        WHERE next_due_date IS NOT NULL AND next_due_date != ''
    """)).scalar() or 0

    return {
        "overview": {
            "total_reports": total_count,
            "passed": unique_passed,
            "failed": unique_failed,
            "pass_rate": round((unique_passed / len(groups) * 100), 1) if len(groups) > 0 else 0.0,
            "due_soon": due_soon_count,
            "recorrection_rate": recorrection_rate,
            "ftr_rate": ftr_rate,
            "avg_mttr_hours": avg_mttr
        },
        "trends": trends,
        "templates": templates,
        "pareto": pareto,
        "most_passed": most_passed,
        "technicians": technicians_list,
        "spc": {
            "vehicle": {
                "parameter_name": "Alternator Charging Voltage",
                "unit": "V",
                "min": 13.8,
                "max": 14.7,
                "data": spc_vehicle
            },
            "instrument": {
                "parameter_name": "Baseline Voltage Stability",
                "unit": "V",
                "min": 4.95,
                "max": 5.05,
                "data": spc_instrument
            }
        }
    }


@router.post("/reset-demo-data")
def reset_demo_data(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("engineer"))
):
    import sqlite3
    from database.init_db import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("DELETE FROM inspection_results")
        cur.execute("DELETE FROM inspection_sessions")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")
    finally:
        conn.close()
        
    return {"message": "Database cleared successfully. All inspection records deleted."}


