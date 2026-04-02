#!/usr/bin/env python3
"""
Test script for the POS License System.
Run: python test_license.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import LicenseGenerator


def test_license_generation():
    print("Testing License System...\n")

    generator = LicenseGenerator()
    test_machine_id = "TEST-MACHINE-001"

    # 1. Generate license key
    license_key = generator.generate_license_key(test_machine_id, duration_years=1)
    assert "data" in license_key and "signature" in license_key
    assert license_key["data"]["machine_id"] == test_machine_id
    print(f"[PASS] Generated license key for {test_machine_id}")

    # 2. Format as activation string
    activation_string = generator.format_activation_key(license_key)
    assert activation_string.startswith("POS-LICENSE-")
    print(f"[PASS] Formatted activation key: {activation_string[:50]}...")

    # 3. Parse back
    parsed = generator.parse_activation_key(activation_string)
    assert parsed["data"]["machine_id"] == test_machine_id
    assert parsed["signature"] == license_key["signature"]
    print("[PASS] Parsed activation key back to dict")

    # 4. Validate signature
    assert generator.validate_license_key(parsed) is True
    print("[PASS] Signature validation passed")

    # 5. Tampered data should fail
    tampered = parsed.copy()
    tampered["data"] = dict(tampered["data"])
    tampered["data"]["machine_id"] = "WRONG-MACHINE"
    assert generator.validate_license_key(tampered) is False
    print("[PASS] Tampered key rejected")

    # 6. Wrong signature should fail
    bad_sig = dict(parsed)
    bad_sig["signature"] = "0" * 64
    assert generator.validate_license_key(bad_sig) is False
    print("[PASS] Wrong signature rejected")

    # 7. Custom expiry date
    license_key2 = generator.generate_license_key(test_machine_id, expiry_date="2030-12-31")
    assert "2030-12-31" in license_key2["data"]["expires_at"]
    assert generator.validate_license_key(license_key2) is True
    print("[PASS] Custom expiry date works")

    print("\nAll tests passed! License system is working correctly.\n")


if __name__ == "__main__":
    test_license_generation()
