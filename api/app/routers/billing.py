from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import InvoiceCreateRequest, InvoiceResponse, InvoiceItemResponse, PaymentResponse
from app.dependencies.license_deps import require_valid_license
from app.dependencies.auth_deps import get_current_user
from app.routers.session import require_active_session
from app.models.models import (
    ERPUser, ERPPosOpeningEntry, ERPItem, ERPModeOfPayment,
    PosInvoice, PosInvoiceItem, PosPayment, PosTransactionLog, InvoiceSyncQueue,
)
from app.utils.invoice_number import generate_invoice_number
from app.utils.error_logger import log_error
from datetime import datetime, date, time as dt_time

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/items")
def get_items(
    pos_profile_id: int | None = None,
    session: ERPPosOpeningEntry = Depends(require_active_session),
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Get items with prices for the current POS profile."""
    from app.models.models import ERPItemPrice, ERPItemGroup

    profile = session.pos_profile
    price_list_id = profile.default_price_list_id if profile else None

    # Get all items
    items_query = db.query(ERPItem)
    items = items_query.all()

    today = date.today()
    result = []
    for item in items:
        # Find applicable price
        price_query = db.query(ERPItemPrice).filter(
            ERPItemPrice.item_id == item.id,
        )
        if price_list_id:
            price_query = price_query.filter(ERPItemPrice.price_list_id == price_list_id)

        price_query = price_query.filter(
            (ERPItemPrice.valid_from.is_(None)) | (ERPItemPrice.valid_from <= today),
            (ERPItemPrice.valid_upto.is_(None)) | (ERPItemPrice.valid_upto >= today),
        )
        price_record = price_query.first()

        group_name = None
        if item.item_group:
            group_name = item.item_group.name

        result.append({
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "item_group": group_name,
            "uom": item.uom,
            "barcode": item.barcode,
            "rate": float(price_record.rate) if price_record else None,
            "actual_qty": float(item.actual_qty) if item.actual_qty else 0,
            "projected_qty": float(item.projected_qty) if item.projected_qty else 0,
        })

    return result


@router.get("/customers")
def get_customers(
    search: str = "",
    session: ERPPosOpeningEntry = Depends(require_active_session),
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Search customers."""
    from app.models.models import ERPCustomer

    query = db.query(ERPCustomer)
    if search:
        query = query.filter(
            (ERPCustomer.customer_name.ilike(f"%{search}%"))
            | (ERPCustomer.name.ilike(f"%{search}%"))
        )
    customers = query.limit(50).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "customer_name": c.customer_name,
            "customer_group": c.customer_group,
        }
        for c in customers
    ]


@router.post("/invoice", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    req: InvoiceCreateRequest,
    session: ERPPosOpeningEntry = Depends(require_active_session),
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Create invoice with full ACID transaction safety."""

    # Step 1: Idempotency check
    existing = db.query(PosInvoice).filter(PosInvoice.transaction_id == req.transaction_id).first()
    if existing and existing.is_complete:
        # Return existing invoice
        return _build_invoice_response(db, existing)
    if existing and not existing.is_complete:
        # Previous attempt failed — clean up orphan rows
        db.query(PosPayment).filter(PosPayment.invoice_id == existing.id).delete()
        db.query(PosInvoiceItem).filter(PosInvoiceItem.invoice_id == existing.id).delete()
        db.query(PosTransactionLog).filter(PosTransactionLog.transaction_id == req.transaction_id).delete()
        db.delete(existing)
        db.flush()

    # Step 2: Validate request
    for item_req in req.items:
        item = db.query(ERPItem).filter(ERPItem.id == item_req.item_id).first()
        if not item:
            raise HTTPException(status_code=400, detail={"error_code": "INVALID_ITEM", "message": f"Item {item_req.item_id} not found"})

    for pay_req in req.payments:
        mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == pay_req.mode_of_payment_id).first()
        if not mop:
            raise HTTPException(status_code=400, detail={"error_code": "INVALID_PAYMENT_MODE", "message": f"Payment mode {pay_req.mode_of_payment_id} not found"})

    payment_total = sum(p.amount for p in req.payments)
    if payment_total != req.grand_total:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "PAYMENT_MISMATCH", "message": f"Payment total {payment_total} != grand total {req.grand_total}"},
        )

    # Step 3-12: Transactional invoice creation
    try:
        # Begin explicit transaction
        db.begin_nested()

        # Stage: started
        tx_log = PosTransactionLog(
            transaction_id=req.transaction_id,
            status="started",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(tx_log)
        db.flush()

        # Lock and generate invoice number
        invoice_number = generate_invoice_number(
            db, session.id, session.name
        )

        # Stage: invoice_created
        now = datetime.utcnow()
        invoice = PosInvoice(
            transaction_id=req.transaction_id,
            invoice_number=invoice_number,
            customer_id=req.customer_id,
            pos_opening_entry_id=session.id,
            cashier_id=current_user.id,
            pos_profile_id=session.pos_profile_id,
            posting_date=now.date(),
            posting_time=now.time(),
            status="submitted",
            is_complete=False,
            net_total=req.net_total,
            total_discount=req.total_discount,
            grand_total=req.grand_total,
        )
        db.add(invoice)
        db.flush()

        tx_log.status = "invoice_created"
        tx_log.updated_at = datetime.utcnow()
        db.flush()

        # Stage: items_written
        for item_req in req.items:
            invoice_item = PosInvoiceItem(
                invoice_id=invoice.id,
                item_id=item_req.item_id,
                item_code=item_req.item_code,
                item_name=item_req.item_name,
                qty=item_req.qty,
                rate=item_req.rate,
                amount=item_req.amount,
            )
            db.add(invoice_item)
        db.flush()

        tx_log.status = "items_written"
        tx_log.updated_at = datetime.utcnow()
        db.flush()

        # Stage: payments_written
        for pay_req in req.payments:
            payment = PosPayment(
                invoice_id=invoice.id,
                mode_of_payment_id=pay_req.mode_of_payment_id,
                amount=pay_req.amount,
                reference_number=pay_req.reference_number,
            )
            db.add(payment)
        db.flush()

        tx_log.status = "payments_written"
        tx_log.updated_at = datetime.utcnow()
        db.flush()

        # Stage: completed
        invoice.is_complete = True
        invoice.completed_at = datetime.utcnow()
        tx_log.status = "completed"
        tx_log.updated_at = datetime.utcnow()

        # Queue for ERP sync
        sync_item = InvoiceSyncQueue(
            invoice_id=invoice.id,
            status="pending",
            attempts=0,
        )
        db.add(sync_item)

        db.commit()

        return _build_invoice_response(db, invoice)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Update transaction log
        try:
            log_entry = db.query(PosTransactionLog).filter(
                PosTransactionLog.transaction_id == req.transaction_id
            ).first()
            if log_entry:
                log_entry.status = "rolled_back"
                log_entry.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

        log_error(db, "transaction", "critical", f"Invoice creation failed: {e}", exc=e)
        raise HTTPException(
            status_code=500,
            detail={"error_code": "INVOICE_TX_FAILED", "message": "Invoice creation failed. Please retry."},
        )


@router.get("/invoice/check/{transaction_id}")
def check_invoice(
    transaction_id: str,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Idempotency check — find invoice by transaction_id."""
    invoice = db.query(PosInvoice).filter(
        PosInvoice.transaction_id == transaction_id,
        PosInvoice.is_complete == True,
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _build_invoice_response(db, invoice)


@router.get("/invoice/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Fetch invoice by ID for reprint."""
    invoice = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _build_invoice_response(db, invoice)


def _build_invoice_response(db: Session, invoice: PosInvoice) -> InvoiceResponse:
    """Build the full invoice response with items and payments."""
    items = db.query(PosInvoiceItem).filter(PosInvoiceItem.invoice_id == invoice.id).all()
    payments = db.query(PosPayment).filter(PosPayment.invoice_id == invoice.id).all()
    sync_item = (
        db.query(InvoiceSyncQueue)
        .filter(InvoiceSyncQueue.invoice_id == invoice.id)
        .first()
    )

    return InvoiceResponse(
        id=invoice.id,
        transaction_id=invoice.transaction_id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        posting_date=invoice.posting_date,
        posting_time=invoice.posting_time,
        status=invoice.status,
        net_total=invoice.net_total,
        total_discount=invoice.total_discount,
        grand_total=invoice.grand_total,
        is_complete=invoice.is_complete,
        sync_status=sync_item.status if sync_item else None,
        sync_attempts=sync_item.attempts if sync_item else None,
        last_sync_attempt_at=sync_item.last_attempt_at if sync_item else None,
        sync_error=sync_item.error_response if sync_item else None,
        items=[
            InvoiceItemResponse(
                id=i.id, item_code=i.item_code, item_name=i.item_name,
                qty=i.qty, rate=i.rate, amount=i.amount,
            ) for i in items
        ],
        payments=[
            PaymentResponse(
                id=p.id, mode_of_payment_id=p.mode_of_payment_id,
                amount=p.amount, reference_number=p.reference_number,
            ) for p in payments
        ],
    )
