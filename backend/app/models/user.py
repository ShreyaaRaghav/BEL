from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.security import hash_password

@dataclass
class User:
    username: str
    hashed_password: str
    role: str                        # "admin" | "engineer" | "viewer"
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until


# In-memory store — replace with a real DB table in production
_USERS: dict[str, User] = {
    "bel_admin": User(
        username="bel_admin",
        hashed_password=hash_password("Admin@BEL#2025!"),
        role="admin",
    ),
    "bel_engineer": User(
        username="bel_engineer",
        hashed_password=hash_password("Engineer@BEL#2025!"),
        role="engineer",
    ),
    "bel_viewer": User(
        username="bel_viewer",
        hashed_password=hash_password("Viewer@BEL#2025!"),
        role="viewer",
    ),
}

def get_user(username: str) -> Optional[User]:
    return _USERS.get(username)

def create_user(username: str, plain_password: str, role: str) -> User:
    if username in _USERS:
        raise ValueError(f"Username '{username}' already exists")
    if role not in ("admin", "engineer", "viewer"):
        raise ValueError("Role must be admin, engineer, or viewer")
    user = User(username=username, hashed_password=hash_password(plain_password), role=role)
    _USERS[username] = user
    return user
