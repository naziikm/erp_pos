#!/usr/bin/env python3
"""
POS License Generator
Developer tool for generating license activation keys for POS API servers.

Usage:
    python main.py --machine-id <MACHINE_ID> --years 1
    python main.py --machine-id <MACHINE_ID> --expiry-date 2027-12-31
    python main.py --machine-id <MACHINE_ID> --years 2 --output json
"""

import argparse
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def _load_hmac_secret() -> str:
    """Read LICENSE_HMAC_SECRET from the api/.env file."""
    env_path = Path(__file__).resolve().parent.parent / "api" / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f".env not found at {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("LICENSE_HMAC_SECRET="):
            return line.split("=", 1)[1].strip()
    raise ValueError("LICENSE_HMAC_SECRET not found in .env")


DEVELOPER_SECRET = _load_hmac_secret()


class LicenseGenerator:
    """License key generator for POS API servers."""

    def __init__(self, secret_key: str = DEVELOPER_SECRET):
        self.secret_key = secret_key.encode()

    def generate_license_key(
        self,
        machine_id: str,
        duration_years: int = 1,
        expiry_date: Optional[str] = None,
    ) -> dict:
        """Generate a license activation key for a specific machine.

        Args:
            machine_id: The device's unique machine ID (shown on the app screen).
            duration_years: License validity in years (default 1).
            expiry_date: Specific expiry date string (YYYY-MM-DD), overrides duration_years.

        Returns:
            dict with 'data' (license info) and 'signature' (HMAC-SHA256).
        """
        if expiry_date:
            expiry = datetime.fromisoformat(expiry_date)
        else:
            expiry = datetime.now(timezone.utc) + timedelta(days=duration_years * 365)

        license_data = {
            "machine_id": machine_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expiry.isoformat(),
            "version": "1.0",
        }

        data_string = json.dumps(license_data, sort_keys=True)
        signature = hmac.new(self.secret_key, data_string.encode(), hashlib.sha256).hexdigest()

        return {"data": license_data, "signature": signature}

    def format_activation_key(self, license_key: dict) -> str:
        """Encode license key dict into a portable activation string.

        Format: POS-LICENSE-<hex encoded JSON>
        """
        data_hex = json.dumps(license_key).encode("utf-8").hex()
        return f"POS-LICENSE-{data_hex}"

    def parse_activation_key(self, activation_string: str) -> dict:
        """Parse a POS-LICENSE-... string back into a license key dict."""
        prefix = "POS-LICENSE-"
        if not activation_string.startswith(prefix):
            raise ValueError("Invalid activation key format")
        data_hex = activation_string[len(prefix):]
        data_json = bytes.fromhex(data_hex).decode("utf-8")
        return json.loads(data_json)

    def validate_license_key(self, license_key: dict) -> bool:
        """Verify a license key's HMAC signature."""
        data = license_key.get("data")
        signature = license_key.get("signature")
        if not data or not signature:
            return False
        data_string = json.dumps(data, sort_keys=True)
        expected = hmac.new(self.secret_key, data_string.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


def main():
    parser = argparse.ArgumentParser(description="POS License Generator")
    parser.add_argument("--machine-id", required=True, help="Device machine ID (shown on the app)")
    parser.add_argument("--years", type=int, default=1, help="License duration in years (default: 1)")
    parser.add_argument("--expiry-date", help="Specific expiry date (ISO format: YYYY-MM-DD)")
    parser.add_argument("--output", choices=["key", "json"], default="key", help="Output format")
    args = parser.parse_args()

    generator = LicenseGenerator()

    license_key = generator.generate_license_key(
        machine_id=args.machine_id,
        duration_years=args.years,
        expiry_date=args.expiry_date,
    )

    if args.output == "json":
        print(json.dumps(license_key, indent=2))
    else:
        activation_string = generator.format_activation_key(license_key)
        print()
        print("=" * 60)
        print("  POS License Generated Successfully")
        print("=" * 60)
        print(f"  Machine ID : {args.machine_id}")
        print(f"  Expires    : {license_key['data']['expires_at'][:10]}")
        print(f"  Duration   : {args.years} year(s)")
        print("-" * 60)
        print(f"  Activation Key:")
        print(f"  {activation_string}")
        print("=" * 60)
        print()
        print("  Paste this activation key into the POS app to activate.")
        print()


if __name__ == "__main__":
    main()
