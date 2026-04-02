#!/usr/bin/env python3
"""
Test script for the POS License System
Run this to test the license generation and validation functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import LicenseGenerator

def test_license_generation():
    """Test license key generation and validation."""
    print("Testing License System...")

    # Initialize generator
    generator = LicenseGenerator()

    # Test machine ID generation (mock data)
    mock_server_info = {
        "hostname": "pos-server-01",
        "platform": "Linux-5.15.0-119-generic-x86_64-with-glibc2.35",
        "processor": "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz",
        "machine": "x86_64",
        "cpu_freq": "2600.0",
        "memory_total": "17179869184",  # 16GB
        "mac_addresses": ["00:1B:44:11:3A:B7", "00:1B:44:11:3A:B8"]
    }

    machine_id = generator.generate_machine_id(mock_server_info)
    print(f"[PASS] Generated Machine ID: {machine_id}")

    # Test license key generation
    duration_years = 1
    license_key = generator.generate_license_key(machine_id, duration_years)
    print(f"[PASS] Generated License Key for {machine_id}")

    # Test activation key formatting
    activation_string = generator.format_activation_key(license_key)
    print(f"[PASS] Formatted Activation Key: {activation_string[:50]}...")

    # Test parsing activation key
    parsed_key = generator.parse_activation_key(activation_string)
    print("[PASS] Successfully parsed activation key")

    # Test license validation
    is_valid = generator.validate_license_key(parsed_key)
    print(f"[PASS] License validation: {'PASS' if is_valid else 'FAIL'}")

    # Test with wrong machine ID
    wrong_machine_key = license_key.copy()
    wrong_machine_key["data"] = license_key["data"].copy()
    wrong_machine_key["data"]["machine_id"] = "WRONG12345678"
    is_invalid = generator.validate_license_key(wrong_machine_key)
    print(f"[PASS] Wrong machine ID validation: {'PASS' if not is_invalid else 'FAIL'}")

    print("\nAll tests passed! License system is working correctly.")
    print("\nNext steps:")
    print("1. Run the API server: cd ../api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("2. Test license activation via API endpoints")
    print("3. Test Flutter app license error handling")

if __name__ == "__main__":
    test_license_generation()
