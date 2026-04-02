"""Phase 7 — Push local POS invoices to ERPNext."""

import logging
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import get_settings
from app.utils.erp_client import (
    ERPAuthError,
    ERPClient,
    ERPConnectionError,
    ERPServerError,
    ERPTimeoutError,
    get_erp_client,
)
from app.utils.error_logger import log_error
from app.models.models import (
    PosInvoice, PosInvoiceItem, PosPayment, InvoiceSyncQueue,
    ERPCustomer, ERPItem, ERPModeOfPayment, ERPPosProfile, ERPPosOpeningEntry,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class InvoicePushService:
    """Push local POS invoices to ERPNext."""

    def __init__(self, erp_client: ERPClient | None = None):
        self.erp = erp_client or get_erp_client()

    def run_invoice_push_job(self, db: Session) -> dict:
        """Process the invoice sync queue — push pending invoices to ERP.

        Returns a summary dict with counts of pushed/failed/skipped.
        """
        max_attempts = settings.MAX_INVOICE_PUSH_ATTEMPTS

        # Fetch pending queue items (oldest first, limited batch)
        queue_items = (
            db.query(InvoiceSyncQueue)
            .filter(
                InvoiceSyncQueue.status == "pending",
                InvoiceSyncQueue.attempts < max_attempts,
            )
            .order_by(InvoiceSyncQueue.id.asc())
            .limit(20)
            .all()
        )

        if not queue_items:
            return {
                "processed": 0,
                "pushed": 0,
                "failed": 0,
                "requeued": 0,
                "skipped": 0,
            }

        # Quick connectivity check before processing batch
        if not self.erp.check_connectivity():
            logger.warning("Invoice push skipped — ERP unreachable")
            return {
                "processed": 0,
                "pushed": 0,
                "failed": 0,
                "requeued": len(queue_items),
                "skipped": len(queue_items),
            }

        processed = 0
        pushed = 0
        failed = 0
        requeued = 0

        for qi in queue_items:
            processed += 1
            invoice = db.query(PosInvoice).filter(PosInvoice.id == qi.invoice_id).first()
            if not invoice or not invoice.is_complete:
                qi.status = "failed"
                qi.error_response = "Invoice not found or incomplete"
                qi.last_attempt_at = datetime.utcnow()
                qi.attempts += 1
                db.commit()
                failed += 1
                continue

            try:
                self._push_single_invoice(db, invoice, qi)
                pushed += 1
            except (ERPConnectionError, ERPTimeoutError) as e:
                # ERP went down mid-batch — stop processing
                logger.warning("ERP connection lost during push: %s", e)
                self._mark_for_retry(db, invoice, qi, str(e))
                requeued += 1
                break
            except ERPAuthError as e:
                self._mark_failed(db, invoice, qi, str(e), permanent=True)
                failed += 1
                logger.error("Invoice %s auth failure during ERP push: %s", invoice.invoice_number, e)
                break
            except ERPServerError as e:
                self._mark_for_retry(db, invoice, qi, str(e))
                requeued += 1
            except Exception as e:
                error_text = str(e)[:1000]
                if qi.attempts + 1 >= max_attempts:
                    self._mark_failed(db, invoice, qi, error_text, permanent=True, exc=e)
                    failed += 1
                else:
                    self._mark_for_retry(db, invoice, qi, error_text)
                    requeued += 1

        logger.info("Invoice push batch: pushed=%d, failed=%d", pushed, failed)
        return {
            "processed": processed,
            "pushed": pushed,
            "failed": failed,
            "requeued": requeued,
            "skipped": 0,
        }

    def push_invoice_now(self, db: Session, invoice_id: int) -> dict:
        """Immediately try to push a single queued invoice."""
        qi = (
            db.query(InvoiceSyncQueue)
            .filter(InvoiceSyncQueue.invoice_id == invoice_id)
            .first()
        )
        if not qi:
            raise ValueError("INVOICE_NOT_QUEUED")

        invoice = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
        if not invoice or not invoice.is_complete:
            raise ValueError("INVOICE_NOT_READY")

        if not self.erp.check_connectivity():
            raise ERPConnectionError("ERP is unreachable")

        self._push_single_invoice(db, invoice, qi)
        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "status": "synced",
        }

    def _push_single_invoice(self, db: Session, invoice: PosInvoice, qi: InvoiceSyncQueue):
        """Build payload, create POS Invoice in ERPNext, and submit it."""
        qi.last_attempt_at = datetime.utcnow()
        qi.error_response = None
        qi.attempts += 1
        invoice.status = "submitted"
        db.commit()

        payload = self._build_erp_payload(db, invoice)

        # Step 1: Insert (create) the POS Sales Invoice in ERPNext
        create_resp = self.erp.post("/api/resource/POS Sales Invoice", json=payload)
        if create_resp.status_code not in (200, 201):
            error_text = create_resp.text[:500]
            raise RuntimeError(f"ERP create failed ({create_resp.status_code}): {error_text}")

        erp_data = create_resp.json().get("data", {})
        erp_name = erp_data.get("name")
        if not erp_name:
            raise RuntimeError("ERP returned no document name")

        # Step 2: Submit the POS Sales Invoice
        # Pass the full doc data (includes `modified` timestamp) to avoid TimestampMismatchError
        submit_resp = self.erp.post(
            f"/api/method/frappe.client.submit",
            json={"doc": erp_data},
        )
        if submit_resp.status_code not in (200, 201):
            error_text = submit_resp.text[:500]
            raise RuntimeError(f"ERP submit failed ({submit_resp.status_code}): {error_text}")

        # Step 3: Update local records
        invoice.status = "synced"
        qi.status = "synced"
        qi.last_attempt_at = datetime.utcnow()
        qi.error_response = None
        db.commit()

        logger.info("Invoice %s pushed as ERP %s", invoice.invoice_number, erp_name)

    def _mark_for_retry(
        self,
        db: Session,
        invoice: PosInvoice,
        qi: InvoiceSyncQueue,
        error_text: str,
    ):
        qi.last_attempt_at = datetime.utcnow()
        qi.error_response = error_text[:1000]
        qi.status = "pending"
        invoice.status = "submitted"
        db.commit()

    def _mark_failed(
        self,
        db: Session,
        invoice: PosInvoice,
        qi: InvoiceSyncQueue,
        error_text: str,
        permanent: bool = False,
        exc: Exception | None = None,
    ):
        qi.last_attempt_at = datetime.utcnow()
        qi.error_response = error_text[:1000]
        qi.status = "failed"
        invoice.status = "failed"
        db.commit()

        if permanent:
            logger.error(
                "Invoice %s permanently failed after %d attempts: %s",
                invoice.invoice_number,
                qi.attempts,
                error_text,
            )
            log_error(
                db,
                "erp_push",
                "error",
                f"Invoice {invoice.invoice_number} push failed permanently: {error_text}",
                invoice_id=invoice.id,
                exc=exc,
            )

    def _build_erp_payload(self, db: Session, invoice: PosInvoice) -> dict:
        """Build the ERPNext POS Invoice JSON payload from local data."""
        # Resolve names from FK IDs
        customer = None
        if invoice.customer_id:
            customer = db.query(ERPCustomer).filter(ERPCustomer.id == invoice.customer_id).first()
        if not customer:
            # ERPNext requires a customer — fall back to the first available
            customer = db.query(ERPCustomer).first()
        pos_profile = db.query(ERPPosProfile).filter(ERPPosProfile.id == invoice.pos_profile_id).first()
        opening_entry = db.query(ERPPosOpeningEntry).filter(
            ERPPosOpeningEntry.id == invoice.pos_opening_entry_id
        ).first()

        items = db.query(PosInvoiceItem).filter(PosInvoiceItem.invoice_id == invoice.id).all()
        payments = db.query(PosPayment).filter(PosPayment.invoice_id == invoice.id).all()

        # Build items child table (custom doctype needs all mandatory fields)
        erp_items = []
        for item in items:
            rate = float(item.rate)
            amount = float(item.amount)
            # Look up UOM from the local ERP item cache
            erp_item = db.query(ERPItem).filter(ERPItem.item_code == item.item_code).first()
            uom = erp_item.uom if erp_item and erp_item.uom else "Nos"
            erp_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": float(item.qty),
                "rate": rate,
                "amount": amount,
                "uom": uom,
                "conversion_factor": 1,
                "base_rate": rate,
                "base_amount": amount,
                "income_account": "Sales - LB",
                "cost_center": "Main - LB",
            })

        # Build payments child table
        erp_payments = []
        for pay in payments:
            mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == pay.mode_of_payment_id).first()
            erp_payments.append({
                "mode_of_payment": mop.name if mop else "Cash",
                "amount": float(pay.amount),
                "reference_no": pay.reference_number,
            })

        taxes = self._build_erp_taxes(invoice)
        paid_amount = sum((Decimal(str(pay.amount or 0)) for pay in payments), Decimal("0"))
        change_amount = paid_amount - (Decimal(str(invoice.grand_total or 0)))
        if change_amount < 0:
            change_amount = Decimal("0")

        net_total_float = float(invoice.net_total) if invoice.net_total else 0
        grand_total_float = float(invoice.grand_total) if invoice.grand_total else 0

        payload = {
            "doctype": "POS Sales Invoice",
            "naming_series": "ACC-SINV-.YYYY.-",
            "company": "Lyseibug",
            "pos_profile": pos_profile.name if pos_profile else None,
            "customer": customer.name if customer else "naz",
            "posting_date": invoice.posting_date.isoformat() if invoice.posting_date else None,
            "posting_time": invoice.posting_time.isoformat() if invoice.posting_time else None,
            "is_pos": 1,
            "update_stock": 1,
            "currency": "INR",
            "conversion_rate": 1,
            "selling_price_list": "Standard Selling",
            "price_list_currency": "INR",
            "plc_conversion_rate": 1,
            "debit_to": "Debtors - LB",
            "items": erp_items,
            "taxes": taxes,
            "payments": erp_payments,
            "net_total": net_total_float,
            "base_net_total": net_total_float,
            "grand_total": grand_total_float,
            "base_grand_total": grand_total_float,
            "discount_amount": float(invoice.total_discount) if invoice.total_discount else 0,
            "paid_amount": float(paid_amount),
            "base_paid_amount": float(paid_amount),
            "change_amount": float(change_amount),
            "base_change_amount": float(change_amount),
            "rounded_total": grand_total_float,
            "base_rounded_total": grand_total_float,
            "outstanding_amount": 0,
            "custom_pos_invoice_number": invoice.invoice_number,
        }

        if opening_entry:
            payload["posa_pos_opening_shift"] = opening_entry.name

        return payload

    def _build_erp_taxes(self, invoice: PosInvoice) -> list[dict]:
        """Derive a minimal tax row from stored totals when tax details are not persisted locally."""
        net_total = Decimal(str(invoice.net_total or 0))
        total_discount = Decimal(str(invoice.total_discount or 0))
        grand_total = Decimal(str(invoice.grand_total or 0))
        taxable_total = net_total - total_discount
        tax_amount = grand_total - taxable_total

        if tax_amount <= 0:
            return []

        rate = Decimal("0")
        if taxable_total > 0:
            rate = (tax_amount / taxable_total) * Decimal("100")

        return [{
            "charge_type": "On Net Total",
            "description": "POS Tax",
            "account_head": "Output Tax - LB",
            "rate": float(rate.quantize(Decimal("0.0001"))),
            "tax_amount": float(tax_amount),
            "total": float(grand_total),
        }]
