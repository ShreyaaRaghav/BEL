from sqlalchemy.orm import Session
from database.models import ChecksheetTemplate, CheckItem, InspectionSession, InspectionResult


def get_template(db: Session, template_id: int):
    return db.query(ChecksheetTemplate).filter(ChecksheetTemplate.id == template_id).first()

def get_all_templates(db: Session):
    return db.query(ChecksheetTemplate).all()

def get_check_items(db: Session, template_id: int):
    return db.query(CheckItem).filter(CheckItem.template_id == template_id).order_by(CheckItem.ref_number).all()


def compute_item_status(check_item: CheckItem, measured_numeric) -> str:
    if check_item.range_type == "visual" or measured_numeric is None:
        return "PENDING"
    if check_item.range_type == "between":
        if check_item.range_min is not None and check_item.range_max is not None:
            return "PASS" if check_item.range_min <= measured_numeric <= check_item.range_max else "FAIL"
    elif check_item.range_type == "min_only":
        if check_item.range_min is not None:
            return "PASS" if measured_numeric >= check_item.range_min else "FAIL"
    elif check_item.range_type == "max_only":
        if check_item.range_max is not None:
            return "PASS" if measured_numeric <= check_item.range_max else "FAIL"
    return "PENDING"


def save_inspection(db: Session, session_data: dict, results_data: list) -> InspectionSession:
    session = InspectionSession(**session_data)
    db.add(session)
    db.flush()

    statuses = []
    for r in results_data:
        check_item = db.query(CheckItem).filter(CheckItem.id == r["check_item_id"]).first()
        numeric = r.get("measured_numeric")
        status = compute_item_status(check_item, numeric)
        statuses.append(status)

        result = InspectionResult(
            session_id       = session.id,
            check_item_id    = r["check_item_id"],
            measured_value   = r.get("measured_value"),
            measured_numeric = numeric,
            status           = status,
            notes            = r.get("notes")
        )
        db.add(result)

    session.overall_status = "FAIL" if "FAIL" in statuses else "PASS"
    db.commit()
    db.refresh(session)
    return session


def get_all_sessions(db: Session):
    return db.query(InspectionSession).order_by(InspectionSession.submitted_at.desc()).all()

def get_session_with_results(db: Session, session_id: int):
    return db.query(InspectionSession).filter(InspectionSession.id == session_id).first()
