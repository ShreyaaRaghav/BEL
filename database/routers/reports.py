from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.db import get_db
from database import crud

router = APIRouter(prefix="/api", tags=["reports"])


class ResultIn(BaseModel):
    check_item_id:    int
    measured_value:   str = None
    measured_numeric: float = None
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
    results:         list


@router.post("/save-report")
def save_report(payload: SessionIn, db: Session = Depends(get_db)):
    session_data = payload.dict(exclude={"results"})
    results_data = [r.dict() for r in payload.results]
    session = crud.save_inspection(db, session_data, results_data)
    return {"id": session.id, "overall_status": session.overall_status}


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    sessions = crud.get_all_sessions(db)
    return [
        {
            "id": s.id,
            "template_id": s.template_id,
            "lead_technician": s.lead_technician,
            "inspection_date": s.inspection_date,
            "overall_status": s.overall_status,
            "submitted_at": str(s.submitted_at),
        }
        for s in sessions
    ]

@router.get("/reports/{session_id}")
def get_report(session_id: int, db: Session = Depends(get_db)):
    s = crud.get_session_with_results(db, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Report not found")
    return s

@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    return crud.get_all_templates(db)

@router.get("/templates/{template_id}/items")
def get_template_items(template_id: int, db: Session = Depends(get_db)):
    return crud.get_check_items(db, template_id)
