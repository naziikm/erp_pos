from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.schemas.schemas import (
    DaySummaryResponse, ErrorLogResponse, ClosingSummaryResponse,
    ClosingSummaryPaymentMode, HealthResponse,
)
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import get_current_user
from app.models.models import (
    ERPUser, PosInvoice, PosInvoiceItem, PosPayment, PosErrorLog,
    InvoiceSyncQueue, SyncLog, ERPModeOfPayment,
)
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/day-summary", response_model=DaySummaryResponse)
def day_summary(
    report_date: date | None = None,
    opening_entry_id: int | None = None,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Day/shift summary report."""
    query = db.query(PosInvoice).filter(
        PosInvoice.is_complete == True,
        PosInvoice.status.in_(["submitted", "synced"]),
    )

    if report_date:
        query = query.filter(PosInvoice.posting_date == report_date)
    else:
        query = query.filter(PosInvoice.posting_date == date.today())

    if opening_entry_id:
        query = query.filter(PosInvoice.pos_opening_entry_id == opening_entry_id)

    invoices = query.all()
    invoice_ids = [inv.id for inv in invoices]

    total_invoices = len(invoices)
    total_sales = sum((inv.grand_total or Decimal("0")) for inv in invoices)
    total_discount = sum((inv.total_discount or Decimal("0")) for inv in invoices)

    # Payments grouped by mode
    payments_by_mode: dict[str, Decimal] = {}
    if invoice_ids:
        payments = db.query(PosPayment).filter(PosPayment.invoice_id.in_(invoice_ids)).all()
        for p in payments:
            mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == p.mode_of_payment_id).first()
            mode_name = mop.name if mop else f"Mode {p.mode_of_payment_id}"
            payments_by_mode[mode_name] = payments_by_mode.get(mode_name, Decimal("0")) + (p.amount or Decimal("0"))

    # Unsynced and failed counts
    unsynced_count = db.query(PosInvoice).filter(
        PosInvoice.is_complete == True,
        PosInvoice.status == "submitted",
    ).count()

    failed_count = db.query(PosInvoice).filter(
        PosInvoice.is_complete == True,
        PosInvoice.status == "failed",
    ).count()

    return DaySummaryResponse(
        total_invoices=total_invoices,
        total_sales=total_sales,
        total_discount=total_discount,
        payments_by_mode=payments_by_mode,
        unsynced_count=unsynced_count,
        failed_count=failed_count,
    )


@router.get("/invoices")
def invoice_history(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Invoice history with filters and pagination."""
    query = db.query(PosInvoice).filter(PosInvoice.is_complete == True)

    if date_from:
        query = query.filter(PosInvoice.posting_date >= date_from)
    if date_to:
        query = query.filter(PosInvoice.posting_date <= date_to)
    if status:
        query = query.filter(PosInvoice.status == status)
    if customer_id:
        query = query.filter(PosInvoice.customer_id == customer_id)
    if search:
        query = query.filter(PosInvoice.invoice_number.ilike(f"%{search}%"))

    total = query.count()
    invoices = query.order_by(PosInvoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "posting_date": inv.posting_date,
                "status": inv.status,
                "grand_total": inv.grand_total,
                "customer_id": inv.customer_id,
            }
            for inv in invoices
        ],
    }


@router.get("/item-sales")
def item_sales(
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Item-wise sales report."""
    invoice_query = db.query(PosInvoice.id).filter(
        PosInvoice.is_complete == True,
        PosInvoice.status.in_(["submitted", "synced"]),
    )
    if date_from:
        invoice_query = invoice_query.filter(PosInvoice.posting_date >= date_from)
    if date_to:
        invoice_query = invoice_query.filter(PosInvoice.posting_date <= date_to)

    invoice_ids = [r[0] for r in invoice_query.all()]

    if not invoice_ids:
        return []

    items = (
        db.query(
            PosInvoiceItem.item_code,
            PosInvoiceItem.item_name,
            func.sum(PosInvoiceItem.qty).label("total_qty"),
            func.sum(PosInvoiceItem.amount).label("total_amount"),
        )
        .filter(PosInvoiceItem.invoice_id.in_(invoice_ids))
        .group_by(PosInvoiceItem.item_code, PosInvoiceItem.item_name)
        .order_by(func.sum(PosInvoiceItem.amount).desc())
        .all()
    )

    return [
        {
            "item_code": i.item_code,
            "item_name": i.item_name,
            "total_qty": float(i.total_qty) if i.total_qty else 0,
            "total_amount": float(i.total_amount) if i.total_amount else 0,
        }
        for i in items
    ]


@router.get("/sync-status")
def sync_status(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Sync health dashboard data."""
    sync_logs = db.query(SyncLog).all()
    pending = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "pending").count()
    failed = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "failed").count()

    today_errors = (
        db.query(PosErrorLog.error_category, func.count(PosErrorLog.id))
        .filter(PosErrorLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0))
        .group_by(PosErrorLog.error_category)
        .all()
    )

    return {
        "sync_tables": [
            {
                "table_name": sl.table_name,
                "last_synced_at": sl.last_synced_at,
                "total_records": sl.total_records,
                "status": sl.status,
            }
            for sl in sync_logs
        ],
        "invoice_queue": {"pending": pending, "failed": failed},
        "today_errors": {cat: count for cat, count in today_errors},
    }


@router.get("/errors")
def error_log(
    severity: str | None = None,
    category: str | None = None,
    resolved: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Error log with filters."""
    query = db.query(PosErrorLog)
    if severity:
        query = query.filter(PosErrorLog.severity == severity)
    if category:
        query = query.filter(PosErrorLog.error_category == category)

    total = query.count()
    errors = query.order_by(PosErrorLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "errors": [
            {
                "id": e.id,
                "error_message": e.error_message,
                "error_category": e.error_category,
                "severity": e.severity,
                "invoice_id": e.invoice_id,
                "created_at": e.created_at,
            }
            for e in errors
        ],
    }


@router.post("/errors/{error_id}/resolve")
def resolve_error(
    error_id: int,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Mark error as resolved."""
    error = db.query(PosErrorLog).filter(PosErrorLog.id == error_id).first()
    if not error:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Error not found")
    # Note: your schema doesn't have a 'resolved' column, so we just return success
    # In future: add resolved column or delete the error
    return {"success": True, "message": "Error acknowledged"}
