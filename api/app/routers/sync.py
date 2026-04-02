from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import SyncStatusResponse, SyncStatusItem, InvoiceQueueResponse, InvoiceResponse, SuccessResponse
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import get_current_user
from app.models.models import ERPUser, SyncLog, InvoiceSyncQueue, PosInvoice

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("/erp")
def trigger_incremental_sync(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Trigger incremental ERP sync."""
    from app.services.frappe_sync_service import FrappeSyncService
    svc = FrappeSyncService()
    results = svc.run_incremental_sync(db)
    return {"success": True, "message": "Incremental sync completed", "results": results}


@router.post("/erp/full")
def trigger_full_sync(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Trigger full ERP re-sync."""
    from app.services.frappe_sync_service import FrappeSyncService
    svc = FrappeSyncService()
    results = svc.run_full_sync(db)
    return {"success": True, "message": "Full sync completed", "results": results}


@router.post("/invoice-push")
def trigger_invoice_push(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Trigger an immediate invoice push batch."""
    from app.services.invoice_push_service import InvoicePushService

    svc = InvoicePushService()
    results = svc.run_invoice_push_job(db)
    return {"success": True, "message": "Invoice push completed", "results": results}


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Get per-table sync status and timestamps."""
    rows = db.query(SyncLog).all()
    items = [
        SyncStatusItem(
            table_name=r.table_name,
            last_synced_at=r.last_synced_at,
            total_records=r.total_records,
            status=r.status,
            error_message=r.error_message,
        )
        for r in rows
    ]
    return SyncStatusResponse(tables=items)


@router.get("/invoice-queue", response_model=InvoiceQueueResponse)
def get_invoice_queue(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Get pending, synced, and failed invoice counts."""
    pending = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "pending").count()
    synced = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "synced").count()
    failed = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "failed").count()
    return InvoiceQueueResponse(pending=pending, synced=synced, failed=failed)


@router.get("/failed-invoices")
def get_failed_invoices(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """List failed invoices with error details."""
    queue_items = (
        db.query(InvoiceSyncQueue)
        .filter(InvoiceSyncQueue.status == "failed")
        .all()
    )
    result = []
    for qi in queue_items:
        invoice = db.query(PosInvoice).filter(PosInvoice.id == qi.invoice_id).first()
        result.append({
            "queue_id": qi.id,
            "invoice_id": qi.invoice_id,
            "invoice_number": invoice.invoice_number if invoice else None,
            "attempts": qi.attempts,
            "last_attempt_at": qi.last_attempt_at,
            "error_response": qi.error_response,
        })
    return result


@router.post("/retry-invoice/{invoice_id}", response_model=SuccessResponse)
def retry_invoice(
    invoice_id: int,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Retry pushing a failed invoice to ERP."""
    queue_item = (
        db.query(InvoiceSyncQueue)
        .filter(InvoiceSyncQueue.invoice_id == invoice_id, InvoiceSyncQueue.status == "failed")
        .first()
    )
    if not queue_item:
        raise HTTPException(status_code=404, detail="Failed invoice not found in queue")

    queue_item.status = "pending"
    queue_item.attempts = 0
    queue_item.error_response = None
    db.commit()

    # Also reset invoice status
    invoice = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
    if invoice and invoice.status == "failed":
        invoice.status = "submitted"
        db.commit()

    return SuccessResponse(success=True, message="Invoice re-queued for sync")


@router.post("/retry-invoice/{invoice_id}/push", response_model=SuccessResponse)
def retry_invoice_now(
    invoice_id: int,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Re-queue and immediately attempt to push a failed invoice."""
    from app.services.invoice_push_service import InvoicePushService

    queue_item = (
        db.query(InvoiceSyncQueue)
        .filter(InvoiceSyncQueue.invoice_id == invoice_id)
        .first()
    )
    if not queue_item:
        raise HTTPException(status_code=404, detail="Invoice not found in queue")

    queue_item.status = "pending"
    queue_item.error_response = None
    db.commit()

    invoice = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
    if invoice and invoice.status == "failed":
        invoice.status = "submitted"
        db.commit()

    svc = InvoicePushService()
    try:
        svc.push_invoice_now(db, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return SuccessResponse(success=True, message="Invoice synced successfully")
