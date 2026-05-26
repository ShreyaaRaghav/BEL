from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

@dataclass
class AuditLog:
    username: str
    role: str
    ip_address: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "SUCCESS"   # "SUCCESS" or "FAILED"

# In-memory store — replace with a DB table in production
_LOGS: list[AuditLog] = []

def add_log(username: str, role: str, ip_address: str, status: str = "SUCCESS"):
    _LOGS.append(AuditLog(username=username, role=role, ip_address=ip_address, status=status))

def get_logs() -> list[AuditLog]:
    return list(reversed(_LOGS))   # newest first
