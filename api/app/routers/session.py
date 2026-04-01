from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import SessionStatusResponse, SessionInfo, SuccessResponse, SessionCloseRequest
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import get_current_user
from app.models.models import ERPUser, ERPPosOpeningEntry

router = APIRouter(prefix="/session", tags=["Session"])


def get_active_session(db: Session, user_id: int):
    """Get the active POS opening entry for the user."""
    entry = (
        db.query(ERPPosOpeningEntry)
        .filter(ERPPosOpeningEntry.cashier_id == user_id, ERPPosOpeningEntry.status == "Open")
        .first()
    )
    return entry


def get_active_session_required(db: Session, user_id: int):
    """Get active session or raise 403."""
    entry = get_active_session(db, user_id)
    if not entry:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "SESSION_NO_OPENING", "message": "No active POS session found"}
        )
    return entry


def require_active_session(
    current_user: ERPUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency — blocks access if no active POS opening entry."""
    return get_active_session_required(db, current_user.id)


@router.get("/status", response_model=SessionStatusResponse)
def session_status(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Check for active POS opening entry."""
    entry = get_active_session(db, current_user.id)
    if not entry:
        return SessionStatusResponse(has_session=False, session=None)

    profile = entry.pos_profile
    price_list_name = profile.default_price_list.name if profile and profile.default_price_list else None

    session_info = SessionInfo(
        opening_entry_name=entry.name,
        pos_profile_name=profile.name if profile else "",
        warehouse=profile.warehouse if profile else "",
        cashier_name=current_user.full_name or current_user.username,
        period_start_date=entry.period_start_date,
        allowed_modes_of_payment=profile.allowed_modes_of_payment if profile else [],
        default_price_list=price_list_name,
        validate_stock=profile.validate_stock if profile else False,
        printer_type=profile.printer_type if profile else None,
    )
    return SessionStatusResponse(has_session=True, session=session_info)


@router.get("/closing-summary")
def closing_summary(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Get shift closing summary."""
    # Will be fully implemented in Phase 9
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/close", response_model=SuccessResponse)
def close_session(
    req: SessionCloseRequest,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Close POS session and push closing entry to ERP."""
    # Will be fully implemented in Phase 9
    raise HTTPException(status_code=501, detail="Not implemented yet")
