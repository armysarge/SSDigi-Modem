"""
License management system for SS Ham Modem
"""
import os
import json
import uuid
import logging
import datetime
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)

class LicenseManager:
    """License manager for SS Ham Modem premium features"""

    # Feature tiers
    TIERS = {
        "free": {
            "max_bandwidth": 500,  # Hz
            "max_speed": 600,      # bps
            "waterfall": True,
            "export_wav": True,
            "import_wav": True,
        },
        "basic": {
            "max_bandwidth": 2000,  # Hz
            "max_speed": 3600,      # bps
            "waterfall": True,
            "export_wav": True,
            "import_wav": True,
        },
        "pro": {
            "max_bandwidth": 5000,  # Hz
            "max_speed": 9600,      # bps
            "waterfall": True,
            "advanced_filters": True,
            "export_wav": True,
            "import_wav": True,
            "batch_processing": True,
        }
    }

    def __init__(self):
        """Initialize license manager"""
        self.config_dir = Path.home() / ".ss_ham_modem"
        self.license_file = self.config_dir / "license.dat"
        # Not using machine_id for validation anymore, but keep for backward compatibility
        self.machine_id = self._get_machine_id()
        self.current_tier = "free"
        self.licensed_to = ""
        self.expiration_date = None
        self.callsign = ""  # Store callsign from license - this is now the primary identifier

        # Cryptographic key - in production you would not hardcode this
        self._salt = b'SS-Ham-Modem-Salt-V'
        self._secret_key = self._derive_key("SS-Ham-Modem-Secret-K")
        self._cipher = Fernet(self._secret_key)

    def _get_machine_id(self):
        """Get a unique machine identifier for license binding"""
        try:
            # Try to get consistent hardware identifier
            # On Windows, you might use wmic to get motherboard serial
            if os.name == 'nt':  # Windows
                try:
                    import subprocess
                    output = subprocess.check_output('wmic csproduct get uuid').decode()
                    return output.split('\n')[1].strip()
                except:
                    pass

            # Fallback to getting a unique ID from the system
            machine_id_file = self.config_dir / "machine_id"
            self.config_dir.mkdir(parents=True, exist_ok=True)

            if machine_id_file.exists():
                with open(machine_id_file, 'r') as f:
                    return f.read().strip()
            else:
                # Generate a new machine ID
                machine_id = str(uuid.uuid4())
                with open(machine_id_file, 'w') as f:
                    f.write(machine_id)
                return machine_id

        except Exception as e:
            logger.error(f"Failed to get machine ID: {e}")
            # Return a fallback machine ID
            return str(uuid.uuid4())

    def _derive_key(self, password):
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100001
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def _generate_validation_code(self, callsign, tier):
        """Generate a validation code based on callsign and tier

        This creates a secure hash that ties the license to a specific callsign,
        ensuring that licenses can't be used with different callsigns.

        Args:
            callsign: The amateur radio callsign
            tier: License tier (basic, pro)

        Returns:
            str: A validation code derived from the callsign and tier
        """
        # Create a unique string based on callsign and tier
        validation_string = f"{callsign.upper()}:{tier}:{self._salt.decode('utf-8')}"

        # Generate hash using SHA-256
        import hashlib
        hash_obj = hashlib.sha256(validation_string.encode())
        hash_hex = hash_obj.hexdigest()

        # Return first 8 characters as validation code
        return hash_hex[:8].upper()

    def check_existing_license(self):
        """Check if a valid license is already installed"""
        if not self.license_file.exists():
            logger.info("No license file found")
            return False

        try:
            with open(self.license_file, 'rb') as f:
                file_data = f.read()

            # Handle both old and new license file formats
            try:
                # Check if this is the new binary obfuscated format
                if len(file_data) > 40 and b'SS-HAM-BIN' in file_data:
                    # New binary format with obfuscation
                    logger.debug("Detected new binary license format")

                    # Extract the signature position
                    sig_pos = file_data.find(b'SS-HAM-BIN')
                    if sig_pos == -1:
                        logger.error("Invalid license format: Missing signature")
                        return False

                    # Extract header (first 16 bytes)
                    header = file_data[:16]

                    # Extract encrypted data (after signature + 10 bytes, before footer)
                    encrypted_data_start = sig_pos + 10
                    encrypted_data_end = len(file_data) - 32  # Footer is 32 bytes

                    if encrypted_data_end <= encrypted_data_start:
                        logger.error("Invalid license format: Data section too small")
                        return False

                    encrypted_data_obfuscated = file_data[encrypted_data_start:encrypted_data_end]

                    # Remove XOR obfuscation
                    xor_key = header[:8]  # First 8 bytes of header were used as XOR key
                    encrypted_data = bytearray()
                    for i, byte in enumerate(encrypted_data_obfuscated):
                        encrypted_data.append(byte ^ xor_key[i % len(xor_key)])

                else:
                    # Old format - just encrypted data without obfuscation
                    logger.debug("Using legacy license format")
                    encrypted_data = file_data

                # Now decrypt the actual data
                decrypted_data = self._cipher.decrypt(bytes(encrypted_data)).decode('utf-8')
                license_data = json.loads(decrypted_data)

                # Validate license data - check callsign instead of machine ID
                # Note: The callsign will be verified when the modem is started
                if 'callsign' not in license_data:
                    logger.warning("License does not contain a callsign")
                    return False                # Check if expiration date exists (for backward compatibility)
                # New licenses are lifetime and don't have expiration dates
                if 'expiration_date' in license_data:
                    exp_date = datetime.datetime.fromisoformat(license_data['expiration_date'])
                    if exp_date < datetime.datetime.now():
                        logger.warning("License has expired")
                        return False
                    self.expiration_date = exp_date# Set license information
                self.current_tier = license_data.get('tier', 'free')
                self.licensed_to = license_data.get('name', '')
                self.callsign = license_data.get('callsign', '')

                logger.info(f"Valid license found: {self.current_tier} tier, licensed to {self.licensed_to}, callsign {self.callsign}")
                return True

            except Exception as e:
                logger.error(f"Failed to decrypt license: {e}")
                return False

        except Exception as e:
            logger.error(f"Error reading license file: {e}")
            return False

    def activate(self, license_key=None, license_file_path=None):
        """Activate using either a license file or a license key

        This method now focuses on importing existing license files rather than generating them.
        License files are created by the separate license generator tool.
        """
        try:
            if license_file_path:
                # Import a license file directly
                if not os.path.exists(license_file_path):
                    logger.error(f"License file not found: {license_file_path}")
                    return False

                # Copy license file to the config directory
                self.config_dir.mkdir(parents=True, exist_ok=True)
                with open(license_file_path, 'rb') as src, open(self.license_file, 'wb') as dst:
                    dst.write(src.read())

                # Verify the imported license
                if self.check_existing_license():
                    logger.info(f"License file imported successfully")
                    return True
                else:
                    logger.error("Imported license file is invalid")
                    if self.license_file.exists():
                        self.license_file.unlink()
                    return False

            elif license_key:
                # License keys can only be used to look up previously generated license files
                # No direct license generation from keys - must go through the license_generator tool
                logger.error("Direct license key activation is no longer supported")
                logger.info("Please contact support to obtain a license file for your callsign")
                return False

            else:
                logger.error("No license file or key provided")
                return False
            self.current_tier = tier
            self.licensed_to = license_data['name']
            self.callsign = license_data['callsign']  # Store the callsign from license
            self.expiration_date = datetime.datetime.fromisoformat(license_data['expiration_date'])

            logger.info(f"License activated: {tier} tier")
            return True

        except Exception as e:
            logger.error(f"License activation failed: {e}")
            return False

    def deactivate(self):
        """Deactivate the current license"""
        try:
            if self.license_file.exists():
                self.license_file.unlink()

            self.current_tier = "free"
            self.licensed_to = ""
            self.callsign = ""  # Clear the callsign on deactivation
            self.expiration_date = None

            logger.info("License deactivated")
            return True
        except Exception as e:
            logger.error(f"License deactivation failed: {e}")
            return False

    def get_feature_limits(self):
        """Get the feature limits for the current license tier"""
        return self.TIERS.get(self.current_tier, self.TIERS['free'])

    def is_feature_enabled(self, feature_name):
        """Check if a specific feature is enabled in the current license tier"""
        tier_features = self.TIERS.get(self.current_tier, {})
        return tier_features.get(feature_name, False)

    def get_license_info(self):
        """Get current license information"""
        return {
            'tier': self.current_tier,
            'licensed_to': self.licensed_to,
            'callsign': self.callsign,  # Include callsign in license info
            'expiration_date': self.expiration_date.isoformat() if self.expiration_date else None,
            'features': self.get_feature_limits()
        }

    def get_callsign(self):
        """Get the callsign from the license

        Returns:
            str: The licensed callsign if a valid license exists, empty string otherwise
        """
        return self.callsign

    def _verify_license_key(self, license_key):
        """Verify a license key and extract its components

        Args:
            license_key: The license key to verify

        Returns:
            tuple: (is_valid, tier, callsign) or (False, None, None) if invalid
        """
        try:
            parts = license_key.split('-')
            if len(parts) != 5:
                logger.error("Invalid license key format")
                return False, None, None

            # Validate tier code
            tier_code = parts[0]
            if tier_code == 'BAS':
                tier = 'basic'
            elif tier_code == 'PRO':
                tier = 'pro'
            else:
                logger.error(f"Invalid tier code: {tier_code}")
                return False, None, None

            # Extract and validate callsign
            callsign = parts[1].upper()
            if not (len(callsign) <= 8 and callsign.isalnum()):
                logger.error(f"Invalid callsign format: {callsign}")
                return False, None, None

            # Verify validation code
            validation_code = self._generate_validation_code(callsign, tier)
            if validation_code != parts[2]:
                logger.error("Invalid license key: validation code mismatch")
                return False, None, None

            # In a real implementation, parts[3] and parts[4] would contain additional
            # validation information, such as expiration dates or feature flags

            return True, tier, callsign

        except Exception as e:
            logger.error(f"Error verifying license key: {e}")
            return False, None, None
