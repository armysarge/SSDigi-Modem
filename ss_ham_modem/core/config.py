"""
Configuration management for SS Ham Modem
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for SS Ham Modem application"""

    DEFAULT_CONFIG = {
        "audio": {
            "input_device": None,  # Default audio input device
            "output_device": None,  # Default audio output device
            "sample_rate": 48000,
            "channels": 2,
            "buffer_size": 1024,
        },
        "modem": {
            "mode": "ardop",
            "bandwidth": "500",  # Default bandwidth in Hz
            "center_freq": 1500,  # Default center frequency in Hz
            "squelch": 3,  # Default squelch level
            "tx_level": 0.5,  # Default transmit audio level (0-1.0)
        },
        "user": {
            "callsign": "",  # User's amateur radio callsign
        },
        "hamlib": {
            "enabled": False,
            "rig_model": 1,  # Default to Dummy rig
            "port": "",  # Serial port
            "baud_rate": 9600,
            "ptt_control": "VOX",  # VOX, RTS, DTR, CAT
        },
        "ui": {
            "theme": "default",
            "waterfall_colors": "default",
            "fft_size": 2048,
            "spectrum_update_rate": 10,  # Hz
        },
        "features": {
            "premium_enabled": False,
            "max_bandwidth": 500,  # Limit for free version (Hz)
            "max_speed": 600,  # Limit for free version (bps)
        }
    }

    def __init__(self):
        """Initialize configuration with default values"""
        self.config_dir = Path.home() / ".ss_ham_modem"
        self.config_file = self.config_dir / "config.json"
        self.data = self.DEFAULT_CONFIG.copy()

    def load_default(self):
        """Load default configuration or existing configuration file if available"""
        if self.config_file.exists():
            try:
                self.load_from_file(self.config_file)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                logger.info("Using default configuration")
        else:
            logger.info("No configuration file found, using defaults")
            self._save_current()

    def load_from_file(self, file_path):
        """Load configuration from specified JSON file"""
        with open(file_path, 'r') as f:
            loaded_config = json.load(f)
            # Update configuration, preserving default values for missing keys
            self._recursive_update(self.data, loaded_config)

    def save(self):
        """Save current configuration to the default location"""
        self._save_current()

    def save_as(self, file_path):
        """Save current configuration to a specified file"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get(self, section, key=None, default=None):
        """Get configuration value(s) with optional default value

        Args:
            section: Configuration section name
            key: Configuration key name (if None, returns entire section)
            default: Default value to return if section or key not found

        Returns:
            Configuration value or default if not found
        """
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key, default)

    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value

    def _save_current(self):
        """Save current configuration to the default location"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def _recursive_update(self, d, u):
        """Recursively update nested dictionaries"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._recursive_update(d[k], v)
            else:
                d[k] = v

    def get_callsign(self):
        """Get the current callsign from configuration"""
        return self.data.get("user", {}).get("callsign", "")

    def set_callsign(self, callsign, force=False):
        """Set the callsign in configuration

        Args:
            callsign: The callsign to set
            force: If True, set the callsign even if it's already set (for license enforcement)

        Returns:
            bool: True if the callsign was set, False if blocked (e.g., by license)
        """
        if not "user" in self.data:
            self.data["user"] = {}

        # Skip if the callsign is already the same
        current = self.data["user"].get("callsign", "")
        if current == callsign:
            return True

        # Only set if force=True or if we're setting for the first time
        if force or not current:
            self.data["user"]["callsign"] = callsign
            return True

        return False

    def enforce_licensed_callsign(self, licensed_callsign):
        """Enforce the licensed callsign, overriding any manually set callsign

        This should be called whenever the application starts with a valid license
        to ensure the callsign from the license is used.

        Args:
            licensed_callsign: The callsign from the valid license

        Returns:
            bool: True if the callsign was enforced or already correct
        """
        if not licensed_callsign:
            return False

        # Force-set the licensed callsign
        return self.set_callsign(licensed_callsign, force=True)
