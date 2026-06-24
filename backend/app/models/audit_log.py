from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from database.db import SessionLocal
from database.models import AuditLogRecord

@dataclass
class AuditLog:
    username: str
    role: str
    ip_address: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "SUCCESS"   # "SUCCESS" or "FAILED"

def add_log(username: str, role: str, ip_address: str, status: str = "SUCCESS"):
    db = SessionLocal()
    try:
        log_record = AuditLogRecord(
            username=username,
            role=role,
            ip_address=ip_address,
            status=status
        )
        db.add(log_record)
        db.commit()
    except Exception as e:
        print(f"Error saving audit log: {e}")
        db.rollback()
    finally:
        db.close()

def get_logs() -> list:
    db = SessionLocal()
    try:
        records = db.query(AuditLogRecord).order_by(AuditLogRecord.timestamp.desc()).all()
        return records
    except Exception as e:
        print(f"Error querying audit logs: {e}")
        return []
    finally:
        db.close()

