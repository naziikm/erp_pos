"""Phase 7 — Push local POS invoices to ERPNext."""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import get_settings
from app.utils.erp_client import ERPClient, get_erp_client, ERPConnectionError
from app.utils.error_logger import log_error
from app.models.models import (
    PosInvoice, PosInvoiceItem, PosPayment, InvoiceSyncQueue,
    ERPCustomer, ERPModeOfPayment, ERPPosProfile, ERPPosOpeningEntry,
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
            return {"pushed": 0, "failed": 0, "skipped": 0}

        # Quick connectivity check before processing batch
        if not self.erp.check_connectivity():
            logger.warning("Invoice push skipped — ERP unreachable")
            return {"pushed": 0, "failed": 0, "skipped": len(queue_items)}

        pushed = 0
        failed = 0

        for qi in queue_items:
            invoice = db.query(PosInvoice).filter(PosInvoice.id == qi.invoice_id).first()
            if not invoice or not invoice.is_complete:
                qi.status = "failed"
                qi.error_response = "Invoice not found or incomplete"
                qi.last_attempt_at = datetime.utcnow()
                db.commit()
                failed += 1
                continue

            try:
                self._push_single_invoice(db, invoice, qi)
                pushed += 1
            except ERPConnectionError as e:
                # ERP went down mid-batch — stop processing
                logger.warning("ERP connection lost during push: %s", e)
                qi.attempts += 1
                qi.last_attempt_at = datetime.utcnow()
                qi.error_response = str(e)
                db.commit()
                break
            except Exception as e:
                qi.attempts += 1
                qi.last_attempt_at = datetime.utcnow()
                qi.error_response = str(e)[:1000]
                if qi.attempts >= max_attempts:
                    qi.status = "failed"
                    invoice.status = "failed"
                    logger.error(
                        "Invoice %s permanently failed after %d attempts: %s",
                        invoice.invoice_number, qi.attempts, e,
                    )
                    log_error(
                        db, "erp_push", "error",
                        f"Invoice {invoice.invoice_number} push failed permanently: {e}",
                        invoice_id=invoice.id, exc=e,
                    )
                db.commit()
                failed += 1

        logger.info("Invoice push batch: pushed=%d, failed=%d", pushed, failed)
        return {"pushed": pushed, "failed": failed, "skipped": 0}

    def _push_single_invoice(self, db: Session, invoice: PosInvoice, qi: InvoiceSyncQueue):
        """Build payload, create POS Invoice in ERPNext, and submit it."""
        payload = self._build_erp_payload(db, invoice)

        # Step 1: Insert (create) the POS Invoice in ERPNext
        create_resp = self.erp.post("/api/resource/POS Invoice", json=payload)
        if create_resp.status_code not in (200, 201):
            error_text = create_resp.text[:500]
            raise RuntimeError(f"ERP create failed ({create_resp.status_code}): {error_text}")

        erp_data = create_resp.json().get("data", {})
        erp_name = erp_data.get("name")
        if not erp_name:
            raise RuntimeError("ERP returned no document name")

        # Step 2: Submit the POS Invoice
        submit_resp = self.erp.post(
            f"/api/method/frappe.client.submit",
            json={"doc": {"doctype": "POS Invoice", "name": erp_name}},
        )
        if submit_resp.status_code not in (200, 201):
            error_text = submit_resp.text[:500]
            raise RuntimeError(f"ERP submit failed ({submit_resp.status_code}): {error_text}")

        # Step 3: Update local records
        invoice.status = "synced"
        qi.status = "synced"
        qi.last_attempt_at = datetime.utcnow()
        qi.attempts += 1
        db.commit()

        logger.info("Invoice %s pushed as ERP %s", invoice.invoice_number, erp_name)

    def _build_erp_payload(self, db: Session, invoice: PosInvoice) -> dict:
        """Build the ERPNext POS Invoice JSON payload from local data."""
        # Resolve names from FK IDs
        customer = db.query(ERPCustomer).filter(ERPCustomer.id == invoice.customer_id).first()
        pos_profile = db.query(ERPPosProfile).filter(ERPPosProfile.id == invoice.pos_profile_id).first()
        opening_entry = db.query(ERPPosOpeningEntry).filter(
            ERPPosOpeningEntry.id == invoice.pos_opening_entry_id
        ).first()

        items = db.query(PosInvoiceItem).filter(PosInvoiceItem.invoice_id == invoice.id).all()
        payments = db.query(PosPayment).filter(PosPayment.invoice_id == invoice.id).all()

        # Build items child table
        erp_items = []
        for item in items:
            erp_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": float(item.qty),
                "rate": float(item.rate),
                "amount": float(item.amount),
            })

        # Build payments child table
        erp_payments = []
        for pay in payments:
            mop = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.id == pay.mode_of_payment_id).first()
            erp_payments.append({
                "mode_of_payment": mop.name if mop else "Cash",
                "amount": float(pay.amount),
            })

        payload = {
            "doctype": "POS Invoice",
            "naming_series": "ACC-PSINV-.YYYY.-",
            "pos_profile": pos_profile.name if pos_profile else None,
            "customer": customer.name if customer else None,
            "posting_date": invoice.posting_date.isoformat() if invoice.posting_date else None,
            "posting_time": invoice.posting_time.isoformat() if invoice.posting_time else None,
            "is_pos": 1,
            "update_stock": 1,
            "items": erp_items,
            "payments": erp_payments,
            "net_total": float(invoice.net_total) if invoice.net_total else 0,
            "grand_total": float(invoice.grand_total) if invoice.grand_total else 0,
            "discount_amount": float(invoice.total_discount) if invoice.total_discount else 0,
        }

        if opening_entry:
            payload["posa_pos_opening_shift"] = opening_entry.name

        return payload
