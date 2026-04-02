#!/usr/bin/env python3
"""
POS License Generator
Developer tool for generating license activation keys for POS API servers.
"""

import argparse
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def _load_secret_from_env() -> str:
    """Read LICENSE_HMAC_SECRET from the api/.env file so keys match the API."""
    env_path = Path(__file__).resolve().parent.parent / "api" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LICENSE_HMAC_SECRET="):
                return line.split("=", 1)[1].strip()
    return ""


# Secret key — auto-loaded from api/.env to stay in sync with the backend
DEVELOPER_SECRET = _load_secret_from_env()


class LicenseGenerator:
    """License key generator for POS API servers."""

    def __init__(self, secret_key: str = DEVELOPER_SECRET):
        self.secret_key = secret_key.encode()

    def generate_machine_id(self, server_info: dict) -> str:
        """Generate a machine ID from server information."""
        info_string = f"{server_info.get('cpu_id', '')}:{server_info.get('mac_address', '')}:{server_info.get('hostname', '')}"
        return hashlib.sha256(info_string.encode()).hexdigest()[:16].upper()

    def generate_license_key(self, machine_id: str, duration_years: int, expiry_date: Optional[str] = None) -> dict:
        """Generate a license activation key."""
        if expiry_date:
            expiry = datetime.fromisoformat(expiry_date)
        else:
            expiry = datetime.now() + timedelta(days=duration_years * 365)

        # Create license data
        license_data = {
            "machine_id": machine_id,
            "issued_at": datetime.now().isoformat(),
            "expires_at": expiry.isoformat(),
            "version": "1.0"
        }

        # Create signature
        data_string = json.dumps(license_data, sort_keys=True)
        signature = hmac.new(self.secret_key, data_string.encode(), hashlib.sha256).hexdigest()

        license_key = {
            "data": license_data,
            "signature": signature
        }

        return license_key

    def format_activation_key(self, license_key: dict) -> str:
        """Format license key as a string for easy copying."""
        data_b64 = json.dumps(license_key).encode('utf-8').hex()
        return f"POS-LICENSE-{data_b64}"

    def parse_activation_key(self, activation_string: str) -> dict:
        """Parse activation key string back to dictionary."""
        if not activation_string.startswith("POS-LICENSE-"):
            raise ValueError("Invalid activation key format")

        data_hex = activation_string[12:]  # Remove "POS-LICENSE-" prefix
        data_json = bytes.fromhex(data_hex).decode('utf-8')
        return json.loads(data_json)

    def validate_license_key(self, license_key: dict) -> bool:
        """Validate a license key's signature."""
        data = license_key["data"]
        signature = license_key["signature"]

        data_string = json.dumps(data, sort_keys=True)
        expected_signature = hmac.new(self.secret_key, data_string.encode(), hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected_signature)


def main():
    parser = argparse.ArgumentParser(description="POS License Generator")
    parser.add_argument("--machine-id", required=True, help="Server machine ID")
    parser.add_argument("--years", type=int, default=1, help="License duration in years")
    parser.add_argument("--expiry-date", help="Specific expiry date (ISO format: YYYY-MM-DD)")
    parser.add_argument("--output", choices=["key", "json"], default="key", help="Output format")

    args = parser.parse_args()

    generator = LicenseGenerator()

    # Generate license key
    license_key = generator.generate_license_key(
        machine_id=args.machine_id,
        duration_years=args.years,
        expiry_date=args.expiry_date
    )

    if args.output == "key":
        activation_string = generator.format_activation_key(license_key)
        print(f"Activation Key: {activation_string}")
        print(f"Machine ID: {args.machine_id}")
        print(f"Expires: {license_key['data']['expires_at']}")
    else:
        print(json.dumps(license_key, indent=2))

if __name__ == "__main__":
    main()
