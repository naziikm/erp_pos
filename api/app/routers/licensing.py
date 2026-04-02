from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import (
    LicenseActivateRequest, LicenseActivateResponse,
    LicenseStatusResponse, SuccessResponse,
    LicenseGenerateRequest, LicenseGenerateResponse,
)
from app.services.license_service import activate_license, check_license_validity, deactivate_license, generate_activation_key
from app.dependencies.license_deps import require_valid_license

router = APIRouter(prefix="/license", tags=["License"])


@router.post("/generate", response_model=LicenseGenerateResponse)
def license_generate(req: LicenseGenerateRequest):
    """Generate a new POS license key (Admin/Developer Tool). Requires matching secret key."""
    from app.config import get_settings
    settings = get_settings()
    if req.secret_key != settings.LICENSE_HMAC_SECRET:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid secret key")
        
    activation_key = generate_activation_key(req.machine_id, req.duration_years, req.expiry_date)
    return LicenseGenerateResponse(activation_key=activation_key)


@router.post("/activate", response_model=LicenseActivateResponse)
def license_activate(req: LicenseActivateRequest, db: Session = Depends(get_db)):
    """Activate license with machine ID and activation key."""
    try:
        result = activate_license(db, req.machine_id, req.activation_key)
        return LicenseActivateResponse(**result)
    except ValueError as e:
        from fastapi import HTTPException
        error_code = str(e)
        msg = "License activation failed"
        if error_code == "LICENSE_INVALID_KEY":
            msg = "Invalid activation key"
        elif error_code == "LICENSE_MACHINE_MISMATCH":
            msg = "This key was generated for a different machine"
        elif error_code == "LICENSE_EXPIRED":
            msg = "This license has expired"
        raise HTTPException(status_code=403, detail={"error_code": error_code, "message": msg})


@router.get("/status", response_model=LicenseStatusResponse)
def license_status(license_payload: dict = Depends(require_valid_license), db: Session = Depends(get_db)):
    """Check license validity and expiry."""
    machine_id = license_payload.get("machine_id")
    result = check_license_validity(db, machine_id)
    return LicenseStatusResponse(**result)


@router.post("/deactivate", response_model=SuccessResponse)
def license_deactivate(license_payload: dict = Depends(require_valid_license), db: Session = Depends(get_db)):
    """Release license from this machine."""
    machine_id = license_payload.get("machine_id")
    deactivate_license(db, machine_id)
    return SuccessResponse(success=True, message="License deactivated")
