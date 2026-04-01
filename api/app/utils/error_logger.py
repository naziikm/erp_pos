import logging
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.models import PosErrorLog

logger = logging.getLogger("pos_error_logger")

# Setup rotating file handler
_log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)
_file_handler = RotatingFileHandler(
    _log_dir / "pos_errors.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
)
logger.addHandler(_file_handler)
logger.setLevel(logging.DEBUG)


def log_error(
    db: Session,
    error_category: str,
    severity: str,
    message: str,
    invoice_id: int | None = None,
    exc: Exception | None = None,
) -> None:
    """Write an error to both the pos_error_log table and the rotating file log.

    Parameters
    ----------
    db : SQLAlchemy Session
    error_category : e.g. 'transaction', 'sync', 'license', 'auth', 'erp_push', 'stock', 'network', 'system'
    severity : 'debug', 'info', 'warning', 'error', 'critical'
    message : human-readable description
    invoice_id : optional FK to pos_invoice
    exc : optional exception to capture traceback from
    """
    stack_trace = None
    if exc is not None:
        stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Write to DB
    try:
        error_entry = PosErrorLog(
            error_message=f"{message}\n{stack_trace}" if stack_trace else message,
            error_category=error_category,
            severity=severity,
            invoice_id=invoice_id,
            created_at=datetime.utcnow(),
        )
        db.add(error_entry)
        db.commit()
    except Exception as db_err:
        # If DB write fails, at least log to file
        logger.error("Failed to write error to DB: %s", db_err)
        db.rollback()

    # Write to file log
    log_line = f"[{error_category}] [{severity}] {message}"
    if stack_trace:
        log_line += f"\n{stack_trace}"

    level = getattr(logging, severity.upper(), logging.ERROR)
    logger.log(level, log_line)

    # Critical severity also goes to stdout
    if severity == "critical":
        print(f"CRITICAL: {log_line}")
