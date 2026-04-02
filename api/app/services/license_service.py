import hashlib
import hmac
import json
import re
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


def _parse_and_validate_activation_key(activation_key: str) -> dict:
    """Parse a POS-LICENSE-... activation key and verify its HMAC signature.

    Returns the license data dict if valid.
    Raises ValueError with error code if invalid.
    """
    prefix = "POS-LICENSE-"
    normalized_key = re.sub(r"\s+", "", activation_key).strip()
    if not normalized_key:
        raise ValueError("LICENSE_INVALID_KEY")

    if normalized_key.upper().startswith(prefix):
        data_hex = normalized_key[len(prefix):]
    else:
        data_hex = normalized_key

    try:
        data_json = bytes.fromhex(data_hex).decode("utf-8")
        license_key = json.loads(data_json)
    except (ValueError, json.JSONDecodeError):
        raise ValueError("LICENSE_INVALID_KEY")

    data = license_key.get("data")
    signature = license_key.get("signature")
    if not data or not signature:
        raise ValueError("LICENSE_INVALID_KEY")

    # Verify HMAC-SHA256 signature
    data_string = json.dumps(data, sort_keys=True)
    expected = hmac.new(
        settings.LICENSE_HMAC_SECRET.encode(),
        data_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise ValueError("LICENSE_INVALID_KEY")

    # Check expiry from the key itself
    expires_at_str = data.get("expires_at")
    if expires_at_str:
        try:
            exp = datetime.fromisoformat(expires_at_str)
            # Make naive for comparison if needed
            if exp.tzinfo is not None:
                from datetime import timezone
                now = datetime.now(timezone.utc)
            else:
                now = datetime.utcnow()
            if exp < now:
                raise ValueError("LICENSE_EXPIRED")
        except (ValueError, TypeError) as e:
            if "LICENSE_EXPIRED" in str(e):
                raise
            # If date parsing fails, continue without expiry check

    return data


def activate_license(db: Session, machine_id: str, activation_key: str) -> dict:
    """Activate license for this machine.

    Returns dict with token, expires_at.
    Raises ValueError on invalid key or machine mismatch.
    """
    # Parse and validate the signed activation key
    normalized_key = re.sub(r"\s+", "", activation_key).strip()
    key_data = _parse_and_validate_activation_key(normalized_key)

    # Verify the key's machine_id matches the requesting machine
    key_machine_id = key_data.get("machine_id", "")
    if key_machine_id != machine_id:
        log_error(db, "license", "critical",
                  f"Machine mismatch: key issued for {key_machine_id}, used by {machine_id}")
        raise ValueError("LICENSE_MACHINE_MISMATCH")

    # Check if already activated with this key
    existing = db.query(License).filter(License.activation_key == normalized_key).first()
    if existing and existing.machine_id == machine_id:
        if existing.expires_at and existing.expires_at < datetime.utcnow():
            raise ValueError("LICENSE_EXPIRED")
        token = _create_license_token(existing.id, machine_id)
        return {"token": token, "expires_at": existing.expires_at, "features": None}

    # Also check if this machine already has a license
    existing_machine = db.query(License).filter(License.machine_id == machine_id).first()
    if existing_machine:
        # Replace existing license with new one
        existing_machine.activation_key = normalized_key
        expires_at_str = key_data.get("expires_at")
        if expires_at_str:
            existing_machine.expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=None)
        db.commit()
        db.refresh(existing_machine)
        token = _create_license_token(existing_machine.id, machine_id)
        return {"token": token, "expires_at": existing_machine.expires_at, "features": None}

    # Create new license record
    expires_at_str = key_data.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=None)
    else:
        expires_at = datetime.utcnow() + timedelta(days=365)

    license_key = hmac.new(
        settings.LICENSE_HMAC_SECRET.encode(),
        f"{machine_id}:{normalized_key}".encode(),
        hashlib.sha256,
    ).hexdigest()

    new_license = License(
        machine_id=machine_id,
        activation_key=normalized_key,
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
