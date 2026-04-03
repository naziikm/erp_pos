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
import socket
import uuid
from datetime import datetime, timedelta, timezone
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

    def collect_local_server_info(self) -> dict:
        """
        Collect minimal "network identity" details from this machine.

        Note: The POS app's machine_id must match the machine_id used here
        when generating activation keys.
        """
        hostname = socket.gethostname()

        # uuid.getnode() returns the hardware address as a 48-bit integer.
        mac_int = uuid.getnode()
        mac = ":".join(f"{(mac_int >> (i * 8)) & 0xFF:02X}" for i in range(5, -1, -1))

        return {
            "hostname": hostname,
            # Support both formats: generator can consume mac_addresses or mac_address.
            "mac_addresses": [mac],
        }

    def generate_machine_id(self, server_info: dict) -> str:
        """Generate a machine ID from server information."""
        hostname = (
            server_info.get("hostname")
            or server_info.get("host")
            or server_info.get("computer_name")
            or ""
        )

        # Accept multiple possible keys for CPU/machine identity.
        cpu_id = (
            server_info.get("cpu_id")
            or server_info.get("cpu")
            or server_info.get("processor")
            or ""
        )

        # Accept both `mac_address` (string) and `mac_addresses` (list).
        mac_value = (
            server_info.get("mac_address")
            if "mac_address" in server_info
            else server_info.get("mac_addresses")
        )
        mac_list: list[str] = []
        if isinstance(mac_value, list):
            mac_list = [str(x) for x in mac_value if x]
        elif isinstance(mac_value, str):
            mac_list = [mac_value]

        # Normalize for consistent hashing regardless of ordering/casing.
        mac_list_norm = sorted({m.strip().upper() for m in mac_list if m.strip()})
        mac_joined = ",".join(mac_list_norm)

        info_string = f"{cpu_id}:{mac_joined}:{hostname}"
        return hashlib.sha256(info_string.encode()).hexdigest()[:16].upper()

    def generate_license_key(self, machine_id: str, duration_years: int, expiry_date: Optional[str] = None) -> dict:
        """Generate a license activation key."""
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date:
            expiry = datetime.fromisoformat(expiry_date)
        else:
            # Use UTC to match the API. We keep values naive (no tzinfo) since
            # the API compares with `datetime.utcnow()` and expects naive datetimes.
            expiry = now_utc + timedelta(days=duration_years * 365)

        # Create license data
        license_data = {
            "machine_id": machine_id,
            "issued_at": now_utc.isoformat(),
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
    parser.add_argument("--machine-id", help="Server machine ID")
    parser.add_argument("--years", type=int, default=1, help="License duration in years")
    parser.add_argument("--expiry-date", help="Specific expiry date (ISO format: YYYY-MM-DD)")
    parser.add_argument(
        "--auto-machine-id",
        action="store_true",
        help="Auto-detect machine ID from local network identity (hostname + MAC).",
    )
    parser.add_argument(
        "--server-info-json",
        help="Path to JSON file with server info (hostname/mac/cpu) to derive machine_id.",
    )
    parser.add_argument("--output", choices=["key", "json"], default="key", help="Output format")

    args = parser.parse_args()

    generator = LicenseGenerator()

    machine_id: Optional[str] = args.machine_id
    if not machine_id and args.auto_machine_id:
        machine_id = generator.generate_machine_id(generator.collect_local_server_info())

    if not machine_id and args.server_info_json:
        info_path = Path(args.server_info_json)
        info = json.loads(info_path.read_text(encoding="utf-8"))
        machine_id = generator.generate_machine_id(info)

    if not machine_id:
        parser.error("Provide --machine-id, or use --auto-machine-id, or --server-info-json <path>.")

    # Generate license key
    license_key = generator.generate_license_key(
        machine_id=machine_id,
        duration_years=args.years,
        expiry_date=args.expiry_date
    )

    if args.output == "key":
        activation_string = generator.format_activation_key(license_key)
        print(f"Activation Key: {activation_string}")
        print(f"Machine ID: {machine_id}")
        print(f"Expires: {license_key['data']['expires_at']}")
    else:
        print(json.dumps(license_key, indent=2))

if __name__ == "__main__":
    main()
