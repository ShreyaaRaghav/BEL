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
    measured_value:   str = None
    measured_numeric: float = None
    status:           str = None
    notes:            str = None

class SessionIn(BaseModel):
    template_id:     int
    lead_technician: str = None
    inspection_date: str = None
    job_card_no:     str = None
    vehicle_model:   str = None
    vin_chassis:     str = None
    odometer_km:     str = None
    instrument_name: str = None
    model_serial:    str = None
    location_dept:   str = None
    next_due_date:   str = None
    results:         list[ResultIn]


@router.post("/save-report")
def save_report(
    payload: SessionIn, 
    db: Session = Depends(get_db),
    user: User = Depends(require_role("engineer"))  # Only engineer/admin can save
):
    session_data = payload.dict(exclude={"results"})
    results_data = [r.dict() for r in payload.results]
    
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
    return crud.get_all_templates(db)

@router.get("/templates/{template_id}/items")
def get_template_items(
    template_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return crud.get_check_items(db, template_id)
