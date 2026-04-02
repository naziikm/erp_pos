import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import LoginRequest, LoginResponse, SuccessResponse
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import verify_password, hash_password, create_access_token, get_current_user
from app.models.models import ERPUser
from app.utils.error_logger import log_error
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _validate_with_erp(username: str, password: str) -> bool:
  """Validate ERP user credentials against ERPNext.

  This is used when a local hashed_password is missing or outdated.
  On success we can safely cache a bcrypt hash locally for offline use.
  """

  base_url = settings.ERP_BASE_URL.rstrip("/")
  try:
      # Use a bare httpx client without the integration token so that
      # we can call the standard login endpoint with username/password.
      with httpx.Client(base_url=base_url, timeout=10) as client:
          resp = client.post(
              "/api/method/login",
              data={"usr": username, "pwd": password},
          )
      # ERPNext returns 200 on successful login; anything else is a
      # failure. We don't persist cookies; this is only for validation.
      return resp.status_code == 200
  except Exception:
      # Let the caller decide what to do on connectivity errors.
      return False


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Login with ERP username/password. Returns a JWT access token.

    Password handling strategy:
    - If a local bcrypt hash exists and matches, login is immediate
      (works fully offline).
    - If the hash is missing or does not match, we call ERPNext's
      `/api/method/login` to validate the credentials. On success we
      cache a new hash locally for future offline logins.
    """
    user = db.query(ERPUser).filter(ERPUser.username == req.username).first()

    if not user:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_FAILED", "message": "Invalid credentials"})

    if not user.is_active:
        log_error(db, "auth", "warning", f"Inactive user login attempt: {req.username}")
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_USER_INACTIVE", "message": "User account is inactive"})

    password_ok = False

    # First try local hash (offline-friendly path)
    if user.hashed_password and verify_password(req.password, user.hashed_password):
        password_ok = True
    else:
        # Hash missing or outdated — try validating with ERPNext.
        erp_ok = _validate_with_erp(req.username, req.password)
        if erp_ok:
            # Cache new local hash for future offline logins
            try:
                user.hashed_password = hash_password(req.password)
                db.commit()
            except Exception as e:
                db.rollback()
                log_error(db, "auth", "warning", f"Failed to cache password hash for {req.username}: {e}", exc=e)
            password_ok = True

    if not password_ok:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_FAILED", "message": "Invalid credentials"})

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
