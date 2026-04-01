import hashlib
import hmac
from datetime import datetime, timedelta
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.models import License
from app.utils.error_logger import log_error

settings = get_settings()


def generate_machine_fingerprint(machine_id: str) -> str:
    """SHA-256 hash of machine_id with salt."""
    salt = settings.LICENSE_HMAC_SECRET[:16]
    return hashlib.sha256(f"{machine_id}{salt}".encode()).hexdigest()


def validate_license_key(machine_id: str, license_key: str) -> bool:
    """Verify the license key using HMAC-SHA256."""
    expected = hmac.new(
        settings.LICENSE_HMAC_SECRET.encode(),
        machine_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, license_key)


def activate_license(db: Session, machine_id: str, activation_key: str) -> dict:
    """Activate license for this machine.

    Returns dict with token, expires_at.
    Raises ValueError on invalid key or machine mismatch.
    """
    # Check if already activated on a different machine
    existing = db.query(License).filter(License.activation_key == activation_key).first()
    if existing and existing.machine_id != machine_id:
        log_error(db, "license", "critical", f"Machine mismatch: key already bound to {existing.machine_id}")
        raise ValueError("LICENSE_MACHINE_MISMATCH")

    # If already activated on this machine, return existing token
    if existing and existing.machine_id == machine_id:
        if existing.expires_at and existing.expires_at < datetime.utcnow():
            raise ValueError("LICENSE_EXPIRED")
        token = _create_license_token(existing.id, machine_id)
        return {"token": token, "expires_at": existing.expires_at, "features": None}

    # Validate key via HMAC
    license_key = hmac.new(
        settings.LICENSE_HMAC_SECRET.encode(),
        f"{machine_id}:{activation_key}".encode(),
        hashlib.sha256,
    ).hexdigest()

    # Default expiry: 365 days from now
    expires_at = datetime.utcnow() + timedelta(days=365)

    new_license = License(
        machine_id=machine_id,
        activation_key=activation_key,
        license_key=license_key,
        expires_at=expires_at,
    )
    db.add(new_license)
    db.commit()
    db.refresh(new_license)

    token = _create_license_token(new_license.id, machine_id)
    return {"token": token, "expires_at": expires_at, "features": None}


def check_license_validity(db: Session, machine_id: str) -> dict:
    """Check if the license is valid for this machine."""
    record = db.query(License).filter(License.machine_id == machine_id).first()
    if not record:
        return {"is_valid": False, "expires_at": None, "days_remaining": None, "features": None}

    now = datetime.utcnow()
    if record.expires_at and record.expires_at < now:
        return {"is_valid": False, "expires_at": record.expires_at, "days_remaining": 0, "features": None}

    days_remaining = (record.expires_at - now).days if record.expires_at else None
    return {
        "is_valid": True,
        "expires_at": record.expires_at,
        "days_remaining": days_remaining,
        "features": None,
    }


def deactivate_license(db: Session, machine_id: str) -> bool:
    """Remove license for this machine."""
    record = db.query(License).filter(License.machine_id == machine_id).first()
    if record:
        db.delete(record)
        db.commit()
        return True
    return False


def _create_license_token(license_id: int, machine_id: str) -> str:
    """Create a JWT token containing license info."""
    payload = {
        "license_id": license_id,
        "machine_id": machine_id,
        "type": "license",
        "exp": datetime.utcnow() + timedelta(days=365),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_license_token(token: str) -> dict:
    """Decode and validate a license JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
