from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from contextlib import contextmanager
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.MYSQL_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    echo=settings.LOG_LEVEL == "DEBUG",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for use outside of FastAPI request cycle (e.g. scheduler jobs)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_with_transaction():
    """FastAPI dependency that wraps the session in an explicit transaction.
    Commits on success, rolls back on exception."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
