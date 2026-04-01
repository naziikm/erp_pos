from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.services.license_service import decode_license_token, check_license_validity
from app.utils.error_logger import log_error


def require_valid_license(request: Request, db: Session = Depends(get_db)) -> dict:
    """FastAPI dependency that validates the license JWT from the Authorization header.

    Returns the decoded license payload if valid.
    Raises HTTP 403 if license is invalid, expired, or machine mismatched.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail={"error_code": "LICENSE_MISSING", "message": "License token required"})

    token = auth_header.split(" ", 1)[1]

    try:
        payload = decode_license_token(token)
    except JWTError:
        raise HTTPException(status_code=403, detail={"error_code": "LICENSE_INVALID", "message": "Invalid license token"})

    if payload.get("type") != "license":
        raise HTTPException(status_code=403, detail={"error_code": "LICENSE_INVALID", "message": "Invalid token type"})

    machine_id = payload.get("machine_id")
    if not machine_id:
        raise HTTPException(status_code=403, detail={"error_code": "LICENSE_INVALID", "message": "No machine_id in token"})

    status = check_license_validity(db, machine_id)
    if not status["is_valid"]:
        log_error(db, "license", "critical", f"License invalid for machine {machine_id}")
        raise HTTPException(
            status_code=403,
            detail={"error_code": "LICENSE_EXPIRED", "message": "License has expired"}
        )

    return payload
