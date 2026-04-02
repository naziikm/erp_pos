from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import bcrypt
from app.database import get_db
from app.config import get_settings
from app.models.models import ERPUser
from app.utils.error_logger import log_error

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(user_id: int, machine_id: str | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    if machine_id:
        payload["machine_id"] = machine_id
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> ERPUser:
    """FastAPI dependency that extracts and validates the user JWT.

    Expects a header: X-Auth-Token: <jwt>
    (Separate from the License token in Authorization header.)
    """
    token = request.headers.get("X-Auth-Token")
    if not token:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_MISSING", "message": "Authentication required"})

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_INVALID", "message": "Invalid authentication token"})

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_INVALID", "message": "Invalid token type"})

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_INVALID", "message": "Invalid token payload"})

    user = db.query(ERPUser).filter(ERPUser.id == int(user_id)).first()
    if not user or not user.is_active:
        log_error(db, "auth", "warning", f"User {user_id} not found or inactive")
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_USER_INACTIVE", "message": "User not found or inactive"})

    return user
