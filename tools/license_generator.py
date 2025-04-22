"""
License Key Generator for SS-Ham-Modem

This utility creates license key files for specific callsigns and tiers.
This is a separate tool from the main application to enhance security.
Only authorized personnel should have access to this tool.
"""
import os
import sys
import json
import argparse
import datetime
import hashlib
import base64
import uuid
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Ensure our script can find the ss_ham_modem package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Generate license keys for SS-Ham-Modem")
    parser.add_argument("--callsign", required=True, help="Amateur radio callsign (max 8 chars)")
    parser.add_argument("--tier", choices=["basic", "pro"], required=True, help="License tier")
    parser.add_argument("--out", help="Output file path (optional)")
    parser.add_argument("--generate-key-only", action="store_true", help="Only generate and print the license key, don't create a file")

    return parser.parse_args()

def validate_callsign(callsign):
    """Validate callsign format"""
    if not callsign:
        return False

    # Convert to uppercase for consistency
    callsign = callsign.upper()

    # Check length and character set
    if not (len(callsign) <= 8 and callsign.isalnum()):
        return False

    return callsign

def derive_key(password, salt):
    """Derive encryption key from password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100001
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def generate_validation_code(callsign, tier, salt):
    """Generate a validation code based on callsign and tier"""
    # Create a unique string based on callsign and tier
    validation_string = f"{callsign.upper()}:{tier}:{salt.decode('utf-8')}"

    # Generate hash using SHA-256
    hash_obj = hashlib.sha256(validation_string.encode())
    hash_hex = hash_obj.hexdigest()

    # Return first 8 characters as validation code
    return hash_hex[:8].upper()

def generate_signature(callsign, tier):
    """Generate a unique signature for the license

    This creates additional validation values for the license key
    """
    # Create unique components for the signature
    signature_base = f"{callsign.upper()}:{tier}:{uuid.uuid4()}"

    # Generate hash
    hash_obj = hashlib.sha256(signature_base.encode())
    hash_hex = hash_obj.hexdigest()

    # Return two parts of the signature
    return hash_hex[:6].upper(), hash_hex[-6:].upper()

def generate_license_key(callsign, tier, salt):
    """Generate a license key for the given callsign and tier"""
    # Format: TIER-CALLSIGN-VALIDATION-CODE1-CODE2

    if tier == 'basic':
        tier_code = 'BAS'
    elif tier == 'pro':
        tier_code = 'PRO'
    else:
        raise ValueError(f"Invalid tier: {tier}")

    # Generate validation code
    validation_code = generate_validation_code(callsign, tier, salt)

    # Generate additional signature codes
    code1, code2 = generate_signature(callsign, tier)

    # Assemble license key
    license_key = f"{tier_code}-{callsign}-{validation_code}-{code1}-{code2}"

    return license_key

def create_license_file(callsign, tier, output_path=None):
    """Create a license file for the specified callsign and tier"""
    # Same salt as used in the main application
    salt = b'SS-Ham-Modem-Salt-V'
    secret_key = derive_key("SS-Ham-Modem-Secret-K", salt)
    cipher = Fernet(secret_key)

    # Generate the license key
    license_key = generate_license_key(callsign, tier, salt)

    # Create license data structure
    license_data = {
        'tier': tier,
        'callsign': callsign,
        'name': f"User-{callsign}",
        'issued_date': datetime.datetime.now().isoformat(),
        # No expiration date for lifetime license
        'license_key': license_key
    }    # Encrypt the license data
    encrypted_data = cipher.encrypt(json.dumps(license_data).encode('utf-8'))

    # Add binary header and obfuscation to make it harder to open in text editors
    binary_header = os.urandom(16)  # Random 16-byte header
    obfuscated_data = bytearray()

    # Add binary header
    obfuscated_data.extend(binary_header)

    # Add file signature
    obfuscated_data.extend(b'SS-HAM-BIN')

    # Add encrypted data with XOR obfuscation
    xor_key = binary_header[:8]  # Use first 8 bytes of header as XOR key
    for i, byte in enumerate(encrypted_data):
        obfuscated_data.append(byte ^ xor_key[i % len(xor_key)])

    # Add binary footer
    binary_footer = os.urandom(32)  # Random 32-byte footer
    obfuscated_data.extend(binary_footer)

    # Determine where to save the license file
    if not output_path:
        output_path = f"license.dat"

    # Save the obfuscated binary license file
    with open(output_path, 'wb') as f:
        f.write(obfuscated_data)

    print(f"License file created: {output_path}")

    return license_key

def main():
    """Main entry point"""
    args = parse_arguments()

    # Validate callsign
    callsign = validate_callsign(args.callsign)
    if not callsign:
        print(f"Error: Invalid callsign format: {args.callsign}")
        print("Callsign must be alphanumeric and max 8 characters")
        return 1

    # Generate license key only
    if args.generate_key_only:
        salt = b'SS-Ham-Modem-Salt-Value'
        license_key = generate_license_key(callsign, args.tier, salt)
        print(f"License key for {callsign} ({args.tier} tier): {license_key}")
        return 0

    # Create license file
    try:
        create_license_file(callsign, args.tier, args.out)
        return 0
    except Exception as e:
        print(f"Error creating license file: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
