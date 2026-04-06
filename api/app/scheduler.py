import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.database import get_db_context
from app.utils.erp_client import get_erp_client

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = BackgroundScheduler()


def _check_erp_online() -> bool:
    """Quick connectivity check before running ERP-dependent jobs."""
    try:
        return get_erp_client().check_connectivity()
    except Exception:
        return False


def _erp_sync_job():
    """Pull master data from ERP (incremental)."""
    if not _check_erp_online():
        logger.info("ERP sync skipped — ERP unreachable (offline mode)")
        return

    logger.info("Running ERP sync job...")
    try:
        with get_db_context() as db:
            from app.services.frappe_sync_service import FrappeSyncService
            svc = FrappeSyncService()
            results = svc.run_incremental_sync(db)
            logger.info("ERP sync job completed: %s", results)
    except Exception as e:
        logger.error("ERP sync job failed: %s", e, exc_info=True)


def _invoice_push_job():
    """Push local invoices to ERP."""
    if not _check_erp_online():
        logger.info("Invoice push skipped — ERP unreachable (offline mode)")
        return

    logger.info("Running invoice push job...")
    try:
        with get_db_context() as db:
            from app.services.invoice_push_service import InvoicePushService
            svc = InvoicePushService()
            results = svc.run_invoice_push_job(db)
            logger.info("Invoice push job completed: %s", results)
    except Exception as e:
        logger.error("Invoice push job failed: %s", e, exc_info=True)


def _stock_sync_job():
    """Pull stock levels from ERP."""
    if not _check_erp_online():
        logger.info("Stock sync skipped — ERP unreachable (offline mode)")
        return

    logger.info("Running stock sync job...")
    try:
        with get_db_context() as db:
            from app.services.stock_service import StockService
            svc = StockService()
            svc.sync_stock_levels(db)
            logger.info("Stock sync job completed.")
    except Exception as e:
        logger.error("Stock sync job failed: %s", e, exc_info=True)


def _get_interval_setting(key: str, default: int) -> int:
    """Read a numeric setting from the database or fall back to default."""
    try:
        from app.models.models import SystemSetting
        with get_db_context() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting and setting.value:
                return int(setting.value)
    except Exception:
        pass
    return default


def start_scheduler():
    """Register and start all background jobs."""
    # Master Sync (minutes)
    erp_interval = _get_interval_setting("erp_sync_interval_mins", settings.ERP_SYNC_INTERVAL_MINUTES)
    scheduler.add_job(
        _erp_sync_job,
        trigger=IntervalTrigger(minutes=erp_interval),
        id="erp_sync",
        max_instances=1,
        replace_existing=True,
    )

    # Invoice Push (seconds)
    invoice_interval = _get_interval_setting("invoice_sync_interval_secs", settings.INVOICE_SYNC_INTERVAL_SECONDS)
    scheduler.add_job(
        _invoice_push_job,
        trigger=IntervalTrigger(seconds=invoice_interval),
        id="invoice_push",
        max_instances=1,
        replace_existing=True,
    )

    # Stock Sync (minutes)
    stock_interval = _get_interval_setting("stock_sync_interval_mins", settings.STOCK_SYNC_INTERVAL_MINUTES)
    scheduler.add_job(
        _stock_sync_job,
        trigger=IntervalTrigger(minutes=stock_interval),
        id="stock_sync",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs (ERP: %dm, Inv: %ds, Stock: %dm).", 
               len(scheduler.get_jobs()), erp_interval, invoice_interval, stock_interval)


def reload_scheduler_settings():
    """Reload all intervals from the database and reschedule active jobs."""
    if not scheduler.running:
        return

    logger.info("Reloading scheduler settings from database...")
    
    # Master Sync
    erp_interval = _get_interval_setting("erp_sync_interval_mins", settings.ERP_SYNC_INTERVAL_MINUTES)
    scheduler.reschedule_job("erp_sync", trigger=IntervalTrigger(minutes=erp_interval))

    # Invoice Push
    invoice_interval = _get_interval_setting("invoice_sync_interval_secs", settings.INVOICE_SYNC_INTERVAL_SECONDS)
    scheduler.reschedule_job("invoice_push", trigger=IntervalTrigger(seconds=invoice_interval))

    # Stock Sync
    stock_interval = _get_interval_setting("stock_sync_interval_mins", settings.STOCK_SYNC_INTERVAL_MINUTES)
    scheduler.reschedule_job("stock_sync", trigger=IntervalTrigger(minutes=stock_interval))

    logger.info("Scheduler jobs rescheduled (ERP: %dm, Inv: %ds, Stock: %dm).", 
               erp_interval, invoice_interval, stock_interval)


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
