import re
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.config import (
    SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_MINUTES,
    PASSWORD_MIN_LENGTH, PASSWORD_NEEDS_UPPER, PASSWORD_NEEDS_LOWER,
    PASSWORD_NEEDS_DIGIT, PASSWORD_NEEDS_SPECIAL,
)

_BCRYPT_ROUNDS = 12


# ---------- Password ----------

def validate_password(password: str):
    """Raise ValueError if password doesn't meet BEL policy."""
    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if PASSWORD_NEEDS_UPPER and not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if PASSWORD_NEEDS_LOWER and not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if PASSWORD_NEEDS_DIGIT and not re.search(r"\d", password):
        errors.append("one digit")
    if PASSWORD_NEEDS_SPECIAL and not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        errors.append("one special character")
    if errors:
        raise ValueError("Password must have: " + ", ".join(errors))

def hash_password(password: str) -> str:
    validate_password(password)
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- JWT ----------

def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),   # unique ID so we can revoke it individually
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str, expected_type: str) -> dict | None:
    """Decode and validate a token. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload
    except JWTError:
        return None