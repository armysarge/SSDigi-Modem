"""
Modem management for SSDigi Modem
"""
import logging
import numpy as np

# Import modem factory
from ssdigi_modem.core.modems.factory import ModemFactory

logger = logging.getLogger(__name__)

class ModemManager:
    """Modem management for SSDigi Modem - delegates to specific modem implementations"""

    def __init__(self, config, hamlib_manager=None):
        """Initialize modem manager"""
        self.config = config
        self.hamlib_manager = hamlib_manager

        # Create appropriate modem implementation based on configured mode
        self.mode = config.get('modem', 'mode', 'ARDOP')
        self.active_modem = ModemFactory.create_modem(self.mode, config, hamlib_manager)

        # For backwards compatibility and easy access
        self.bandwidth = self.active_modem.bandwidth
        self.center_freq = self.active_modem.center_freq
        self.callsign = self.active_modem.callsign
        self.connected = self.active_modem.connected
        self.status = self.active_modem.status

    def connect(self):
        """Connect to the modem - delegates to active modem implementation"""
        result = self.active_modem.connect()
        # Update local properties after connection
        self.connected = self.active_modem.connected
        self.status = self.active_modem.status
        return result

    def disconnect(self):
        """Disconnect from the modem - delegates to active modem implementation"""
        result = self.active_modem.disconnect()
        # Update local properties after disconnection
        self.connected = self.active_modem.connected
        self.status = self.active_modem.status
        return result

    def is_connected(self):
        """Check if modem is connected"""
        return self.active_modem.is_connected()

    def get_status(self):
        """Get current modem status"""
        # Always get the latest status from the active modem
        self.status = self.active_modem.get_status()
        return self.status

    def set_bandwidth(self, bandwidth):
        """Set modem bandwidth"""
        result = self.active_modem.set_bandwidth(bandwidth)
        self.bandwidth = self.active_modem.bandwidth
        return result

    def set_center_freq(self, center_freq):
        """Set center frequency"""
        result = self.active_modem.set_center_freq(center_freq)
        self.center_freq = self.active_modem.center_freq
        return result

    def get_available_bandwidths(self):
        """Get list of available bandwidths"""
        return self.active_modem.get_available_bandwidths()

    def get_fft_data(self):
        """Get current FFT data for spectrum display"""
        return self.active_modem.get_fft_data()

    def send_text(self, text):
        """Send text message"""
        return self.active_modem.send_text(text)

    def send_pingack(self):
        """Send PINGACK command for testing ARDOP functionality"""
        if hasattr(self.active_modem, 'send_pingack'):
            return self.active_modem.send_pingack()
        else:
            logger.warning(f"PINGACK not supported by {self.mode} modem")
            return False

    def save_to_wav(self, file_path):
        """Save recent signal data to WAV file"""
        return self.active_modem.save_to_wav(file_path)

    def load_from_wav(self, file_path):
        """Load audio from WAV file"""
        return self.active_modem.load_from_wav(file_path)

    def update_from_config(self):
        """Update modem settings from configuration"""
        # Check if the mode has changed
        new_mode = self.config.get('modem', 'mode', 'ARDOP')
        if new_mode.upper() != self.mode.upper():
            # Mode has changed, create a new modem instance
            logger.info(f"Modem mode changed from {self.mode} to {new_mode}")

            # Disconnect existing modem if connected
            if self.connected:
                self.disconnect()

            # Create new modem instance
            self.mode = new_mode
            self.active_modem = ModemFactory.create_modem(self.mode, self.config, self.hamlib_manager)

            # Update local properties
            self.bandwidth = self.active_modem.bandwidth
            self.center_freq = self.active_modem.center_freq
            self.callsign = self.active_modem.callsign
            self.connected = self.active_modem.connected
            self.status = self.active_modem.status
        else:
            # Mode is the same, just update settings
            self.active_modem.update_from_config()

            # Update local properties
            self.bandwidth = self.active_modem.bandwidth
            self.center_freq = self.active_modem.center_freq
            self.callsign = self.active_modem.callsign

        return True

    def apply_config(self):
        """Apply all settings from config"""
        result = self.active_modem.apply_config()

        # Update local properties
        self.bandwidth = self.active_modem.bandwidth
        self.center_freq = self.active_modem.center_freq
        self.callsign = self.active_modem.callsign

        return result
