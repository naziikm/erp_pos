"""Phase 4 — Pull master data from ERPNext into local MySQL."""

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.utils.erp_client import ERPClient, get_erp_client, ERPConnectionError
from app.utils.error_logger import log_error
from app.models.models import (
    ERPRoleProfile, ERPUser, ERPItemGroup, ERPItem, ERPPriceList,
    ERPItemPrice, ERPCustomer, ERPModeOfPayment, ERPPosProfile,
    ERPPosOpeningEntry, SyncLog,
)

logger = logging.getLogger(__name__)


def _get_erp_list(erp: ERPClient, doctype: str, fields: list[str],
                  filters: list | None = None, limit: int = 0) -> list[dict]:
    """Fetch a Frappe doctype list via REST API.

    GET /api/resource/{doctype}?fields=[...]&filters=[...]&limit_page_length=0
    """
    params: dict = {
        "fields": json.dumps(fields),
        "limit_page_length": limit or 0,
    }
    if filters:
        params["filters"] = json.dumps(filters)

    resp = erp.get(f"/api/resource/{doctype}", params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _update_sync_log(db: Session, table_name: str, status: str,
                     total_records: int = 0, error_message: str | None = None):
    """Upsert a sync_log row for the given table."""
    log = db.query(SyncLog).filter(SyncLog.table_name == table_name).first()
    if not log:
        log = SyncLog(table_name=table_name)
        db.add(log)
    log.status = status
    log.last_synced_at = datetime.utcnow()
    log.total_records = total_records
    log.error_message = error_message
    db.flush()


# ─── Individual Doctype Sync Functions ────────────────────────────────────────


def _sync_role_profiles(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Role Profile", fields, filters)
    for row in rows:
        existing = db.query(ERPRoleProfile).filter(ERPRoleProfile.name == row["name"]).first()
        if existing:
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPRoleProfile(
                name=row["name"],
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_users(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "email", "full_name", "role_profile_name", "enabled", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "User", fields, filters)
    for row in rows:
        # Resolve role profile FK
        rp = None
        if row.get("role_profile_name"):
            rp = db.query(ERPRoleProfile).filter(ERPRoleProfile.name == row["role_profile_name"]).first()

        existing = db.query(ERPUser).filter(ERPUser.username == row["name"]).first()
        if existing:
            existing.email = row.get("email")
            existing.full_name = row.get("full_name")
            existing.role_profile_id = rp.id if rp else existing.role_profile_id
            existing.is_active = bool(row.get("enabled", 1))
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPUser(
                username=row["name"],
                email=row.get("email"),
                full_name=row.get("full_name"),
                role_profile_id=rp.id if rp else None,
                is_active=bool(row.get("enabled", 1)),
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_item_groups(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "parent_item_group", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Item Group", fields, filters)
    for row in rows:
        existing = db.query(ERPItemGroup).filter(ERPItemGroup.name == row["name"]).first()
        if existing:
            existing.parent_item_group = row.get("parent_item_group")
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPItemGroup(
                name=row["name"],
                parent_item_group=row.get("parent_item_group"),
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_items(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "item_name", "item_group", "stock_uom", "has_serial_no",
              "is_stock_item", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Item", fields, filters)
    for row in rows:
        # Resolve item group FK
        ig = None
        if row.get("item_group"):
            ig = db.query(ERPItemGroup).filter(ERPItemGroup.name == row["item_group"]).first()

        # Try to get barcode from child table
        barcode = None
        try:
            barcode_resp = erp.get(f"/api/resource/Item/{row['name']}", params={
                "fields": '["name"]',
            })
            item_data = barcode_resp.json().get("data", {})
            barcodes = item_data.get("barcodes", [])
            if barcodes:
                barcode = barcodes[0].get("barcode")
        except Exception:
            pass

        existing = db.query(ERPItem).filter(ERPItem.item_code == row["name"]).first()
        if existing:
            existing.item_name = row.get("item_name")
            existing.item_group_id = ig.id if ig else existing.item_group_id
            existing.uom = row.get("stock_uom")
            existing.has_serial_no = bool(row.get("has_serial_no"))
            existing.is_stock_item = bool(row.get("is_stock_item"))
            if barcode:
                existing.barcode = barcode
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPItem(
                item_code=row["name"],
                item_name=row.get("item_name"),
                item_group_id=ig.id if ig else None,
                uom=row.get("stock_uom"),
                has_serial_no=bool(row.get("has_serial_no")),
                is_stock_item=bool(row.get("is_stock_item")),
                barcode=barcode,
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_price_lists(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "currency", "buying", "selling", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Price List", fields, filters)
    for row in rows:
        existing = db.query(ERPPriceList).filter(ERPPriceList.name == row["name"]).first()
        if existing:
            existing.currency = row.get("currency")
            existing.is_buying = bool(row.get("buying"))
            existing.is_selling = bool(row.get("selling"))
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPPriceList(
                name=row["name"],
                currency=row.get("currency"),
                is_buying=bool(row.get("buying")),
                is_selling=bool(row.get("selling")),
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_item_prices(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "item_code", "price_list", "price_list_rate",
              "valid_from", "valid_upto", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Item Price", fields, filters)
    for row in rows:
        item = db.query(ERPItem).filter(ERPItem.item_code == row.get("item_code")).first()
        pl = db.query(ERPPriceList).filter(ERPPriceList.name == row.get("price_list")).first()
        if not item or not pl:
            continue

        existing = (
            db.query(ERPItemPrice)
            .filter(
                ERPItemPrice.item_id == item.id,
                ERPItemPrice.price_list_id == pl.id,
            )
            .first()
        )
        if existing:
            existing.rate = row.get("price_list_rate")
            existing.min_qty = row.get("min_qty")
            existing.valid_from = row.get("valid_from")
            existing.valid_upto = row.get("valid_upto")
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPItemPrice(
                item_id=item.id,
                price_list_id=pl.id,
                rate=row.get("price_list_rate"),
                min_qty=row.get("min_qty"),
                valid_from=row.get("valid_from"),
                valid_upto=row.get("valid_upto"),
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_customers(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "customer_name", "customer_group", "tax_id",
              "default_price_list", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Customer", fields, filters)
    for row in rows:
        pl = None
        if row.get("default_price_list"):
            pl = db.query(ERPPriceList).filter(ERPPriceList.name == row["default_price_list"]).first()

        existing = db.query(ERPCustomer).filter(ERPCustomer.name == row["name"]).first()
        if existing:
            existing.customer_name = row.get("customer_name")
            existing.customer_group = row.get("customer_group")
            existing.tax_id = row.get("tax_id")
            existing.default_price_list_id = pl.id if pl else existing.default_price_list_id
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPCustomer(
                name=row["name"],
                customer_name=row.get("customer_name"),
                customer_group=row.get("customer_group"),
                tax_id=row.get("tax_id"),
                default_price_list_id=pl.id if pl else None,
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_modes_of_payment(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "type", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "Mode of Payment", fields, filters)
    for row in rows:
        mop_type = row.get("type", "General")
        if mop_type not in ("Cash", "Bank", "General"):
            mop_type = "General"

        existing = db.query(ERPModeOfPayment).filter(ERPModeOfPayment.name == row["name"]).first()
        if existing:
            existing.type = mop_type
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPModeOfPayment(
                name=row["name"],
                type=mop_type,
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_pos_profiles(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "company", "warehouse", "selling_price_list", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    rows = _get_erp_list(erp, "POS Profile", fields, filters)
    for row in rows:
        pl = None
        if row.get("selling_price_list"):
            pl = db.query(ERPPriceList).filter(ERPPriceList.name == row["selling_price_list"]).first()

        # Get allowed payment methods from child table
        allowed_mops = []
        try:
            detail = erp.get(f"/api/resource/POS Profile/{row['name']}")
            profile_data = detail.json().get("data", {})
            for pm in profile_data.get("payments", []):
                allowed_mops.append(pm.get("mode_of_payment"))
        except Exception:
            pass

        existing = db.query(ERPPosProfile).filter(ERPPosProfile.name == row["name"]).first()
        if existing:
            existing.company = row.get("company")
            existing.warehouse = row.get("warehouse")
            existing.default_price_list_id = pl.id if pl else existing.default_price_list_id
            existing.allowed_modes_of_payment = allowed_mops or existing.allowed_modes_of_payment
            existing.customer_required = bool(row.get("customer_required"))
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPPosProfile(
                name=row["name"],
                company=row.get("company"),
                warehouse=row.get("warehouse"),
                default_price_list_id=pl.id if pl else None,
                allowed_modes_of_payment=allowed_mops,
                customer_required=bool(row.get("customer_required")),
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


def _sync_pos_opening_entries(db: Session, erp: ERPClient, last_synced: datetime | None):
    fields = ["name", "pos_profile", "user", "set_posting_date",
              "status", "modified"]
    filters = [["modified", ">", last_synced.isoformat()]] if last_synced else None
    # Only sync Open entries or recently modified ones
    rows = _get_erp_list(erp, "POS Opening Entry", fields, filters)
    for row in rows:
        profile = db.query(ERPPosProfile).filter(ERPPosProfile.name == row.get("pos_profile")).first()
        user = db.query(ERPUser).filter(ERPUser.username == row.get("user")).first()

        # Get opening balance from child table
        opening_balance = []
        try:
            detail = erp.get(f"/api/resource/POS Opening Entry/{row['name']}")
            entry_data = detail.json().get("data", {})
            for bal in entry_data.get("balance_details", []):
                opening_balance.append({
                    "mode_of_payment": bal.get("mode_of_payment"),
                    "opening_amount": float(bal.get("opening_amount", 0)),
                })
        except Exception:
            pass

        status = row.get("status", "Open")
        if status not in ("Open", "Closed"):
            status = "Open"

        existing = db.query(ERPPosOpeningEntry).filter(ERPPosOpeningEntry.name == row["name"]).first()
        if existing:
            existing.pos_profile_id = profile.id if profile else existing.pos_profile_id
            existing.cashier_id = user.id if user else existing.cashier_id
            existing.opening_balance = opening_balance or existing.opening_balance
            existing.period_start_date = row.get("set_posting_date")
            existing.status = status
            existing.modified = row.get("modified")
            existing.synced_at = datetime.utcnow()
        else:
            db.add(ERPPosOpeningEntry(
                name=row["name"],
                pos_profile_id=profile.id if profile else None,
                cashier_id=user.id if user else None,
                opening_balance=opening_balance,
                period_start_date=row.get("set_posting_date"),
                status=status,
                modified=row.get("modified"),
                synced_at=datetime.utcnow(),
            ))
    db.flush()
    return len(rows)


# ─── Orchestrator ─────────────────────────────────────────────────────────────


# Map of table_name → (erp_doctype_label, model_class, sync_function)
_SYNC_MAP = [
    ("erp_role_profile", "Role Profile", ERPRoleProfile, _sync_role_profiles),
    ("erp_user", "User", ERPUser, _sync_users),
    ("erp_item_group", "Item Group", ERPItemGroup, _sync_item_groups),
    ("erp_item", "Item", ERPItem, _sync_items),
    ("erp_price_list", "Price List", ERPPriceList, _sync_price_lists),
    ("erp_item_price", "Item Price", ERPItemPrice, _sync_item_prices),
    ("erp_customer", "Customer", ERPCustomer, _sync_customers),
    ("erp_mode_of_payment", "Mode of Payment", ERPModeOfPayment, _sync_modes_of_payment),
    ("erp_pos_profile", "POS Profile", ERPPosProfile, _sync_pos_profiles),
    ("erp_pos_opening_entry", "POS Opening Entry", ERPPosOpeningEntry, _sync_pos_opening_entries),
]


class FrappeSyncService:
    """Pull master data from ERPNext into local MySQL."""

    def __init__(self, erp_client: ERPClient | None = None):
        self.erp = erp_client or get_erp_client()

    def run_full_sync(self, db: Session) -> dict:
        """Full re-sync of all doctypes (ignores last_synced timestamps)."""
        return self._run_sync(db, full=True)

    def run_incremental_sync(self, db: Session) -> dict:
        """Incremental sync — only fetches records modified since last sync."""
        return self._run_sync(db, full=False)

    def _run_sync(self, db: Session, full: bool = False) -> dict:
        """Core sync loop — iterates doctypes in dependency order."""
        results = {}
        for table_name, doctype_label, model_cls, sync_fn in _SYNC_MAP:
            _update_sync_log(db, table_name, "running")
            try:
                # Get last synced time (skip for full sync)
                last_synced = None
                if not full:
                    log = db.query(SyncLog).filter(SyncLog.table_name == table_name).first()
                    if log and log.last_synced_at:
                        last_synced = log.last_synced_at

                count = sync_fn(db, self.erp, last_synced)
                total = db.query(model_cls).count()
                _update_sync_log(db, table_name, "success", total_records=total)
                db.commit()
                results[table_name] = {"status": "success", "synced": count, "total": total}
                logger.info("Synced %s: %d records (total: %d)", table_name, count, total)

            except ERPConnectionError as e:
                db.rollback()
                _update_sync_log(db, table_name, "failed", error_message=str(e))
                db.commit()
                results[table_name] = {"status": "failed", "error": str(e)}
                logger.warning("Sync %s skipped — ERP unreachable: %s", table_name, e)
                # If ERP is down, skip remaining tables
                for remaining_table, _, _, _ in _SYNC_MAP:
                    if remaining_table not in results:
                        results[remaining_table] = {"status": "skipped", "error": "ERP unreachable"}
                break

            except Exception as e:
                db.rollback()
                _update_sync_log(db, table_name, "failed", error_message=str(e))
                db.commit()
                results[table_name] = {"status": "failed", "error": str(e)}
                logger.error("Sync %s failed: %s", table_name, e, exc_info=True)
                log_error(db, "sync", "error", f"Sync {table_name} failed: {e}", exc=e)

        return results
