from sqlalchemy.orm import Session
from database.models import ChecksheetTemplate, CheckItem, InspectionSession, InspectionResult
from app.ai_engine.evaluator import evaluate_pass_fail

def get_template(db: Session, template_id: int):
    return db.query(ChecksheetTemplate).filter(ChecksheetTemplate.id == template_id).first()

def get_all_templates(db: Session):
    return db.query(ChecksheetTemplate).all()

def get_check_items(db: Session, template_id: int):
    return db.query(CheckItem).filter(CheckItem.template_id == template_id).order_by(CheckItem.ref_number).all()

def save_inspection(db: Session, session_data: dict, results_data: list) -> InspectionSession:
    session = InspectionSession(**session_data)
    db.add(session)
    db.flush()

    statuses = []
    for r in results_data:
        check_item = db.query(CheckItem).filter(CheckItem.id == r["check_item_id"]).first()
        if not check_item:
            continue

        measured_val = r.get("measured_value")
        measured_num = r.get("measured_numeric")

        # Fallback to status passed by frontend, or evaluate using the backend evaluator
        status = r.get("status")
        if not status or status == "PENDING":
            # Map database model properties to the format expected by the evaluator
            # range_type: keep "visual" as-is so evaluator detects categorical correctly
            field_dict = {
                "type": "categorical" if check_item.range_type == "visual" else "numeric",
                "range_type": (
                    "range" if check_item.range_type == "between"
                    else check_item.range_type  # passes "visual", "min_only", "max_only", etc.
                ),
                "min": check_item.range_min,
                "max": check_item.range_max,
                "conditions": (
                    [c.strip() for c in check_item.range_standard.split("/")]
                    if check_item.range_standard and check_item.range_type == "visual"
                    else None
                ),
            }
            status = evaluate_pass_fail(field_dict, measured_val)

        statuses.append(status)

        result = InspectionResult(
            session_id       = session.id,
            check_item_id    = r["check_item_id"],
            measured_value   = str(measured_val) if measured_val is not None else None,
            measured_numeric = measured_num,
            status           = status,
            notes            = r.get("notes")
        )
        db.add(result)

    session.overall_status = "FAIL" if "FAIL" in statuses or "INVALID" in statuses else "PASS"
    db.commit()
    db.refresh(session)
    return session

def get_all_sessions(db: Session):
    return db.query(InspectionSession).order_by(InspectionSession.submitted_at.desc()).all()

def get_session_with_results(db: Session, session_id: int):
    return db.query(InspectionSession).filter(InspectionSession.id == session_id).first()
