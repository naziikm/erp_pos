import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime
from app.database import get_db
from app.schemas.schemas import (
    SessionStatusResponse, SessionInfo, SuccessResponse, SessionCloseRequest,
    ClosingSummaryResponse, ClosingSummaryPaymentMode,
)
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import get_current_user
from app.models.models import (
    ERPUser, ERPPosOpeningEntry, ERPModeOfPayment,
    PosInvoice, PosPayment, InvoiceSyncQueue,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["Session"])


def get_active_session(db: Session, user_id: int):
    """Get the active POS opening entry for the user.

    First tries to find an entry assigned to the specific user.
    Falls back to any Open entry if no user-specific match is found,
    since in many POS setups the opening entry is created by a manager
    and any cashier should be able to use it.
    """
    # Try user-specific match first
    entry = (
        db.query(ERPPosOpeningEntry)
        .filter(ERPPosOpeningEntry.cashier_id == user_id, ERPPosOpeningEntry.status == "Open")
        .first()
    )
    if entry:
        logger.info("Found active session %s for user_id=%d (direct match)", entry.name, user_id)
        return entry

    # Fallback: any Open entry (common in single-device setups where
    # a manager opens the session and a different cashier bills)
    entry = (
        db.query(ERPPosOpeningEntry)
        .filter(ERPPosOpeningEntry.status == "Open")
        .first()
    )
    if entry:
        logger.info(
            "Found active session %s via fallback (entry cashier_id=%s, requesting user_id=%d)",
            entry.name, entry.cashier_id, user_id,
        )
    else:
        # Log diagnostic information
        total = db.query(ERPPosOpeningEntry).count()
        logger.warning(
            "No active session for user_id=%d. Total opening entries in DB: %d",
            user_id, total,
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
    logger.info("Session status check for user_id=%d username=%s", current_user.id, current_user.username)
    entry = get_active_session(db, current_user.id)
    if not entry:
        logger.info("Returning has_session=False for user_id=%d", current_user.id)
        return SessionStatusResponse(has_session=False, session=None)

    profile = entry.pos_profile
    price_list_name = profile.default_price_list.name if profile and profile.default_price_list else None

    # Coerce nullable flags to sensible defaults so Pydantic receives
    # valid data types even if the DB row has NULLs.
    validate_stock_flag = False
    if profile and profile.validate_stock is not None:
        validate_stock_flag = bool(profile.validate_stock)

    allowed_payment_modes = []
    if profile and profile.allowed_modes_of_payment:
        raw_modes = profile.allowed_modes_of_payment
        if not isinstance(raw_modes, list):
            raw_modes = []

        mode_names = []
        for raw_mode in raw_modes:
            if isinstance(raw_mode, str) and raw_mode.strip():
                mode_names.append(raw_mode.strip())
            elif isinstance(raw_mode, dict):
                mode_name = raw_mode.get("mode_of_payment") or raw_mode.get("name")
                if mode_name:
                    mode_names.append(str(mode_name).strip())

        if mode_names:
            mode_rows = (
                db.query(ERPModeOfPayment)
                .filter(ERPModeOfPayment.name.in_(mode_names))
                .all()
            )
            mode_lookup = {row.name: row for row in mode_rows}
            for mode_name in mode_names:
                mode_row = mode_lookup.get(mode_name)
                allowed_payment_modes.append({
                    "id": mode_row.id if mode_row else None,
                    "name": mode_name,
                    "type": mode_row.type if mode_row else None,
                })

    session_info = SessionInfo(
        opening_entry_name=entry.name,
        pos_profile_name=profile.name if profile else "",
        warehouse=profile.warehouse if profile else "",
        cashier_name=current_user.full_name or current_user.username,
        period_start_date=entry.period_start_date,
        allowed_modes_of_payment=allowed_payment_modes,
        default_price_list=price_list_name,
        validate_stock=validate_stock_flag,
        printer_type=profile.printer_type if profile else None,
    )
    return SessionStatusResponse(has_session=True, session=session_info)


@router.get("/closing-summary", response_model=ClosingSummaryResponse)
def closing_summary(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Get shift closing summary — totals by payment mode, unsynced count."""
    entry = get_active_session_required(db, current_user.id)

    # Get all completed invoices for this opening entry
    invoices = (
        db.query(PosInvoice)
        .filter(
            PosInvoice.pos_opening_entry_id == entry.id,
            PosInvoice.is_complete == True,
            PosInvoice.status.in_(["submitted", "synced"]),
        )
        .all()
    )
    invoice_ids = [inv.id for inv in invoices]

    total_invoices = len(invoices)
    total_sales = sum((inv.grand_total or Decimal("0")) for inv in invoices)

    # Group payments by mode
    payments_by_mode: list[ClosingSummaryPaymentMode] = []
    if invoice_ids:
        rows = (
            db.query(
                PosPayment.mode_of_payment_id,
                func.sum(PosPayment.amount).label("total"),
            )
            .filter(PosPayment.invoice_id.in_(invoice_ids))
            .group_by(PosPayment.mode_of_payment_id)
            .all()
        )
        for mop_id, total in rows:
            mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == mop_id).first()
            payments_by_mode.append(ClosingSummaryPaymentMode(
                mode_name=mop.name if mop else f"Mode {mop_id}",
                expected_amount=total or Decimal("0"),
            ))

    # Unsynced and failed invoices
    unsynced_count = 0
    failed_count = 0
    if invoice_ids:
        unsynced_count = (
            db.query(PosInvoice)
            .filter(PosInvoice.id.in_(invoice_ids), PosInvoice.status == "submitted")
            .count()
        )
        failed_count = (
            db.query(PosInvoice)
            .filter(PosInvoice.id.in_(invoice_ids), PosInvoice.status == "failed")
            .count()
        )

    return ClosingSummaryResponse(
        total_invoices=total_invoices,
        total_sales=total_sales,
        payments_by_mode=payments_by_mode,
        unsynced_count=unsynced_count,
        failed_count=failed_count,
    )


@router.post("/close", response_model=SuccessResponse)
def close_session(
    req: SessionCloseRequest,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Close POS session and optionally push closing entry to ERP.

    Steps:
    1. Verify all invoices are synced (or force_close is True)
    2. Mark the local opening entry as Closed
    3. Try to push POS Closing Entry to ERPNext (non-blocking)
    """
    entry = get_active_session_required(db, current_user.id)

    # Check for unsynced invoices
    unsynced = (
        db.query(PosInvoice)
        .filter(
            PosInvoice.pos_opening_entry_id == entry.id,
            PosInvoice.is_complete == True,
            PosInvoice.status.in_(["submitted", "failed"]),
        )
        .count()
    )

    if unsynced > 0 and not req.force_close:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "UNSYNCED_INVOICES",
                "message": f"{unsynced} invoice(s) not yet synced to ERP. Use force_close=true to close anyway.",
            },
        )

    # Close the entry locally
    entry.status = "Closed"
    db.commit()

    # Try to push POS Closing Entry to ERPNext (best-effort)
    erp_pushed = False
    try:
        from app.utils.erp_client import get_erp_client
        erp = get_erp_client()
        if erp.check_connectivity():
            # Build closing entry payload
            invoices = (
                db.query(PosInvoice)
                .filter(
                    PosInvoice.pos_opening_entry_id == entry.id,
                    PosInvoice.is_complete == True,
                )
                .all()
            )
            invoice_ids = [inv.id for inv in invoices]
            grand_total = sum((inv.grand_total or Decimal("0")) for inv in invoices)

            # Payment mode totals
            payment_rows = []
            if invoice_ids:
                rows = (
                    db.query(
                        PosPayment.mode_of_payment_id,
                        func.sum(PosPayment.amount).label("total"),
                    )
                    .filter(PosPayment.invoice_id.in_(invoice_ids))
                    .group_by(PosPayment.mode_of_payment_id)
                    .all()
                )
                for mop_id, total in rows:
                    mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == mop_id).first()
                    payment_rows.append({
                        "mode_of_payment": mop.name if mop else "Cash",
                        "expected_amount": float(total or 0),
                        "closing_amount": float(
                            (req.actual_closing_balance or {}).get(
                                mop.name if mop else "Cash", total or 0
                            )
                        ),
                    })

            closing_payload = {
                "doctype": "POS Closing Entry",
                "pos_profile": entry.pos_profile.name if entry.pos_profile else None,
                "user": current_user.username,
                "pos_opening_entry": entry.name,
                "period_end_date": datetime.utcnow().isoformat(),
                "posting_date": datetime.utcnow().date().isoformat(),
                "grand_total": float(grand_total),
                "net_total": float(grand_total),
                "total_quantity": len(invoices),
                "payment_reconciliation": payment_rows,
            }
            resp = erp.post("/api/resource/POS Closing Entry", json=closing_payload)
            if resp.status_code in (200, 201):
                erp_name = resp.json().get("data", {}).get("name")
                if erp_name:
                    # Submit the closing entry
                    erp.post(
                        "/api/method/frappe.client.submit",
                        json={"doc": {"doctype": "POS Closing Entry", "name": erp_name}},
                    )
                erp_pushed = True
    except Exception as e:
        from app.utils.error_logger import log_error
        log_error(db, "session", "warning", f"Failed to push closing entry to ERP: {e}", exc=e)

    message = "Session closed successfully"
    if not erp_pushed:
        message += " (ERP closing entry will be pushed later)"

    return SuccessResponse(success=True, message=message)
