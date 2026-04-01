import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, SessionLocal
from app.scheduler import start_scheduler, stop_scheduler
from app.routers import licensing, auth, sync, session, billing, reports
from app.utils.erp_client import ERPClient

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting POS Backend...")

    # Verify DB connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK.")
    except Exception as e:
        logger.critical("Database connection FAILED: %s", e)
        raise

    # Check ERP connectivity (non-blocking)
    erp = ERPClient()
    if erp.check_connectivity():
        logger.info("ERP connection OK.")
    else:
        logger.warning("ERP is not reachable. Sync will retry later.")

    # Start background scheduler
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    engine.dispose()
    logger.info("POS Backend stopped.")


app = FastAPI(
    title="ERP POS System",
    description="Point of Sale backend syncing with ERPNext",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to Flutter app origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug("%s %s", request.method, request.url.path)
    response = await call_next(request)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    # Write to error log DB
    try:
        db = SessionLocal()
        from app.utils.error_logger import log_error
        log_error(db, "system", "critical", f"Unhandled: {exc}", exc=exc)
        db.close()
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )


# Register routers
app.include_router(licensing.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


# Health check (no auth required)
@app.get("/api/v1/health")
def health_check():
    """Health check endpoint."""
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "disconnected"

    erp_status = "unreachable"
    try:
        erp = ERPClient()
        if erp.check_connectivity():
            erp_status = "reachable"
    except Exception:
        pass

    pending = 0
    try:
        from app.models.models import InvoiceSyncQueue
        db = SessionLocal()
        pending = db.query(InvoiceSyncQueue).filter(InvoiceSyncQueue.status == "pending").count()
        db.close()
    except Exception:
        pass

    return {
        "status": "ok",
        "db": db_status,
        "erp": erp_status,
        "pending_invoices": pending,
    }
