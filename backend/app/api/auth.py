from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from app.config import MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES, TOKEN_EXPIRE_MINUTES
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, hash_password
from app.core.rbac import get_current_user, require_role
from app.models.user import User, get_user, create_user, normalize_username
from app.models.audit_log import add_log, get_logs

router = APIRouter(prefix="/auth", tags=["Authentication"])

revoked_jtis: set[str] = set()
# Valid bcrypt hash used for constant-time verification when username is missing.
DUMMY_HASH = hash_password("BelDummyAuth@2026!")

class LoginRequest(BaseModel):
    username: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str


@router.post("/login")
def login(body: LoginRequest, request: Request):
    ip = request.client.host
    username = normalize_username(body.username)

    user = get_user(username)
    stored_hash = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(body.password, stored_hash)

    if user is None:
        add_log(username=username or "unknown", role="unknown", ip_address=ip, status="FAILED")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.is_locked():
        add_log(username=username, role=user.role, ip_address=ip, status="LOCKED")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Account locked until {user.locked_until.strftime('%H:%M UTC')}")

    if not password_ok:
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            add_log(username=username, role=user.role, ip_address=ip, status="LOCKED")
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.")
        add_log(username=username, role=user.role, ip_address=ip, status="FAILED")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        add_log(username=body.username, role=user.role, ip_address=ip, status="FAILED")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Successful login
    user.failed_attempts = 0
    user.locked_until = None
    add_log(username=user.username, role=user.role, ip_address=ip, status="SUCCESS")

    return {
        "access_token": create_access_token(user.username, user.role),
        "refresh_token": create_refresh_token(user.username, user.role),
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


@router.post("/refresh")
def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    jti = payload.get("jti", "")
    if jti in revoked_jtis:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already used")

    user = get_user(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    revoked_jtis.add(jti)

    return {
        "access_token": create_access_token(user.username, user.role),
        "refresh_token": create_refresh_token(user.username, user.role),
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if payload:
        revoked_jtis.add(payload.get("jti", ""))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role, "is_active": user.is_active}


@router.post("/register", status_code=201)
def register(body: UserCreate, _: User = Depends(require_role("admin"))):
    try:
        user = create_user(body.username, body.password, body.role)
        return {"username": user.username, "role": user.role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/audit-logs")
def audit_logs(_: User = Depends(require_role("admin"))):
    """Admin only — view all login attempts."""
    logs = get_logs()
    return [
        {
            "username":   log.username,
            "role":       log.role,
            "ip_address": log.ip_address,
            "timestamp":  log.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "status":     log.status,
        }
        for log in logs
    ]


@router.get("/audit-analytics")
def audit_analytics(_: User = Depends(require_role("admin"))):
    """Admin only — view analytics on system access logs."""
    logs = get_logs()
    
    total = len(logs)
    success = sum(1 for l in logs if l.status == "SUCCESS")
    failed = sum(1 for l in logs if l.status in ("FAILED", "LOCKED"))
    locked = sum(1 for l in logs if l.status == "LOCKED")
    
    user_counts = {}
    ip_counts = {}
    suspicious = {}
    
    for l in logs:
        # Normalize fields
        u = l.username or "unknown"
        ip = l.ip_address or "unknown"
        
        user_counts[u] = user_counts.get(u, 0) + 1
        ip_counts[ip] = ip_counts.get(ip, 0) + 1
        if l.status in ("FAILED", "LOCKED"):
            key = (u, ip)
            suspicious[key] = suspicious.get(key, 0) + 1
            
    top_users = [
        {"username": u, "count": c}
        for u, c in sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    top_ips = [
        {"ip_address": ip, "count": c}
        for ip, c in sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    suspicious_list = [
        {"username": k[0], "ip_address": k[1], "failed_count": c}
        for k, c in sorted(suspicious.items(), key=lambda x: x[1], reverse=True)
        if c >= 2
    ]
    
    return {
        "total_attempts": total,
        "success_count": success,
        "failed_count": failed,
        "lockout_count": locked,
        "success_rate": round((success / total * 100), 1) if total > 0 else 0.0,
        "top_users": top_users,
        "top_ips": top_ips,
        "suspicious_activity": suspicious_list
    }

