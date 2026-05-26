from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_token
from app.models.user import User, get_user

bearer = HTTPBearer()

# Role levels — higher number = more access
ROLE_LEVEL = {"viewer": 0, "engineer": 1, "admin": 2}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> User:
    """Validates the Bearer token and returns the User. Raises 401 if anything is wrong."""
    payload = decode_token(credentials.credentials, expected_type="access")

    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = get_user(payload["sub"])

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    if user.is_locked():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Account locked until {user.locked_until.strftime('%H:%M UTC')}")

    return user


def require_role(min_role: str):
    """Returns a dependency that allows access only if user's role >= min_role."""
    def check(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL.get(user.role, -1) < ROLE_LEVEL[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Access denied. Required role: {min_role}")
        return user
    return check
