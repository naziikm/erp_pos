"""Phase 4 (Task 4.6) — Sync stock levels from ERPNext Bin API."""

import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.utils.erp_client import ERPClient, get_erp_client
from app.utils.error_logger import log_error
from app.models.models import ERPItem

logger = logging.getLogger(__name__)


class StockService:
    """Sync stock levels from ERPNext."""

    def __init__(self, erp_client: ERPClient | None = None):
        self.erp = erp_client or get_erp_client()

    def sync_stock_levels(self, db: Session, warehouse: str | None = None) -> int:
        """Pull actual_qty and projected_qty from ERPNext Bin doctype.

        The Bin doctype in ERPNext holds per-item-per-warehouse stock levels.
        We update erp_item.actual_qty, projected_qty, stock_last_updated
        for every stock item.

        Parameters
        ----------
        db : SQLAlchemy Session
        warehouse : filter Bin records to a specific warehouse (optional)

        Returns
        -------
        int : number of items updated
        """
        fields = ["item_code", "warehouse", "actual_qty", "projected_qty", "modified"]
        filters = []
        if warehouse:
            filters.append(["warehouse", "=", warehouse])

        params: dict = {
            "fields": str(fields),
            "limit_page_length": 0,
        }
        if filters:
            params["filters"] = str(filters)

        try:
            resp = self.erp.get("/api/resource/Bin", params=params)
            resp.raise_for_status()
            bins = resp.json().get("data", [])
        except Exception as e:
            logger.error("Failed to fetch Bin data from ERP: %s", e)
            log_error(db, "stock", "error", f"Stock sync failed: {e}", exc=e)
            raise

        updated = 0
        # Group by item_code — sum quantities across all warehouses if no filter
        item_stock: dict[str, dict] = {}
        for b in bins:
            code = b.get("item_code")
            if not code:
                continue
            if code not in item_stock:
                item_stock[code] = {"actual_qty": Decimal("0"), "projected_qty": Decimal("0")}
            item_stock[code]["actual_qty"] += Decimal(str(b.get("actual_qty", 0)))
            item_stock[code]["projected_qty"] += Decimal(str(b.get("projected_qty", 0)))

        for item_code, qtys in item_stock.items():
            item = db.query(ERPItem).filter(ERPItem.item_code == item_code).first()
            if not item:
                continue
            item.actual_qty = qtys["actual_qty"]
            item.projected_qty = qtys["projected_qty"]
            item.stock_last_updated = datetime.utcnow()
            updated += 1

        db.commit()
        logger.info("Stock sync completed: %d items updated from %d Bin records", updated, len(bins))
        return updated
