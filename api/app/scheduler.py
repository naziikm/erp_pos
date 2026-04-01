import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.database import get_db_context

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = BackgroundScheduler()


def _erp_sync_job():
    """Pull master data from ERP (incremental)."""
    logger.info("Running ERP sync job...")
    try:
        with get_db_context() as db:
            from app.services.frappe_sync_service import FrappeSyncService
            svc = FrappeSyncService()
            svc.run_incremental_sync(db)
            logger.info("ERP sync job completed.")
    except NotImplementedError:
        logger.debug("ERP sync not yet implemented (Phase 4)")
    except Exception as e:
        logger.error("ERP sync job failed: %s", e, exc_info=True)


def _invoice_push_job():
    """Push local invoices to ERP."""
    logger.info("Running invoice push job...")
    try:
        with get_db_context() as db:
            from app.services.invoice_push_service import InvoicePushService
            svc = InvoicePushService()
            svc.run_invoice_push_job(db)
            logger.info("Invoice push job completed.")
    except NotImplementedError:
        logger.debug("Invoice push not yet implemented (Phase 7)")
    except Exception as e:
        logger.error("Invoice push job failed: %s", e, exc_info=True)


def _stock_sync_job():
    """Pull stock levels from ERP."""
    logger.info("Running stock sync job...")
    try:
        with get_db_context() as db:
            from app.services.stock_service import StockService
            svc = StockService()
            svc.sync_stock_levels(db, None, None)
            logger.info("Stock sync job completed.")
    except NotImplementedError:
        logger.debug("Stock sync not yet implemented (Phase 4)")
    except Exception as e:
        logger.error("Stock sync job failed: %s", e, exc_info=True)


def start_scheduler():
    """Register and start all background jobs."""
    scheduler.add_job(
        _erp_sync_job,
        trigger=IntervalTrigger(minutes=settings.ERP_SYNC_INTERVAL_MINUTES),
        id="erp_sync",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.add_job(
        _invoice_push_job,
        trigger=IntervalTrigger(seconds=settings.INVOICE_SYNC_INTERVAL_SECONDS),
        id="invoice_push",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.add_job(
        _stock_sync_job,
        trigger=IntervalTrigger(minutes=settings.STOCK_SYNC_INTERVAL_MINUTES),
        id="stock_sync",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs.", len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
