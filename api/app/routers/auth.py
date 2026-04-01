from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import LoginRequest, LoginResponse, SuccessResponse
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import verify_password, create_access_token, get_current_user
from app.models.models import ERPUser
from app.utils.error_logger import log_error

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Login with ERP username/password. Returns a JWT access token."""
    user = db.query(ERPUser).filter(ERPUser.username == req.username).first()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_FAILED", "message": "Invalid credentials"})

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_FAILED", "message": "Invalid credentials"})

    if not user.is_active:
        log_error(db, "auth", "warning", f"Inactive user login attempt: {req.username}")
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_USER_INACTIVE", "message": "User account is inactive"})

    machine_id = license_payload.get("machine_id")
    token = create_access_token(user.id, machine_id)

    role_name = None
    if user.role_profile:
        role_name = user.role_profile.name

    return LoginResponse(
        token=token,
        user_id=user.id,
        full_name=user.full_name or user.username,
        role_profile=role_name,
    )


@router.post("/logout", response_model=SuccessResponse)
def logout(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
):
    """Invalidate JWT (client-side — discard the token)."""
    return SuccessResponse(success=True, message="Logged out successfully")
