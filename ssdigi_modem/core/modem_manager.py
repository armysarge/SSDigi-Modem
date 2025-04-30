"""
Modem management for SSDigi Modem
"""
import logging
import numpy as np

# Import modem factory
from ssdigi_modem.core.modems.factory import ModemFactory

# Import Spectrum receiver for ARDOP
from ssdigi_modem.core.modems.ardop.ardop_spectrum_receiver import ArdopSpectrumReceiver

logger = logging.getLogger(__name__)

class ModemManager:
    """Manager for digital modem implementations"""

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

        # Initialize spectrum receiver if ARDOP mode
        self.spectrum_receiver = None
        # use_external_spectrum is always True if mode is ARDOP
        self.use_external_spectrum = self.mode.upper() == 'ARDOP'

        if self.use_external_spectrum:
            host = config.get('modem', 'ardop_host', '127.0.0.1')
            port = config.get('modem', 'ardop_spectrum_port', 8515)
            self.spectrum_receiver = ArdopSpectrumReceiver(host=host, port=port)
            # Spectrum receiver will be started when connecting to modem

    def connect(self):
        """Connect to the modem - delegates to active modem implementation"""
        result = self.active_modem.connect()
        # Update local properties after connection
        self.connected = self.active_modem.connected
        self.status = self.active_modem.status

        # Start spectrum receiver if available
        if self.spectrum_receiver and self.connected:
            self.spectrum_receiver.start()

        return result

    def disconnect(self):
        """Disconnect from the modem - delegates to active modem implementation"""
        # Stop spectrum receiver if running
        if self.spectrum_receiver:
            self.spectrum_receiver.stop()

        result = self.active_modem.disconnect()
        # Update local properties after disconnection
        self.connected = self.active_modem.connected
        self.status = self.active_modem.status
        return result

    def send_message(self, message, suppress_newline=False, mode_specific_params=None):
        """Transmit a message - delegates to active modem implementation"""
        return self.active_modem.send_message(message, suppress_newline, mode_specific_params)

    def get_status(self):
        """Get modem status - delegates to active modem implementation"""
        self.status = self.active_modem.get_status()
        return self.status

    def is_connected(self):
        """Check if modem is connected - delegates to active modem implementation"""
        self.connected = self.active_modem.is_connected()
        return self.connected

    def get_spectrum_data(self):
        """Get current spectrum data for spectrum display"""
        # If external spectrum data is enabled and available, use it
        if self.mode.upper() == 'ARDOP' and self.spectrum_receiver:
            external_spectrum = self.spectrum_receiver.get_spectrum_data()
            if external_spectrum is not None and self.spectrum_receiver.is_data_fresh():
                return external_spectrum

        # Fall back to modem's internal spectrum if external not available
        return self.active_modem.get_spectrum_data()

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

            # Update spectrum receiver
            if self.spectrum_receiver:
                self.spectrum_receiver.stop()
                self.spectrum_receiver = None

            # use_external_spectrum is always True if mode is ARDOP
            self.use_external_spectrum = self.mode.upper() == 'ARDOP'

            # Initialize spectrum receiver if in ARDOP mode
            if self.use_external_spectrum:
                host = self.config.get('modem', 'ardop_host', '127.0.0.1')
                port = self.config.get('modem', 'ardop_spectrum_port', 8515)
                self.spectrum_receiver = ArdopSpectrumReceiver(host=host, port=port)
                if self.connected:
                    self.spectrum_receiver.start()
        else:
            # Mode is the same, just update settings
            self.active_modem.update_from_config()

            # Update local properties
            self.bandwidth = self.active_modem.bandwidth
            self.center_freq = self.active_modem.center_freq
            self.callsign = self.active_modem.callsign

            # Check if external spectrum setting should be updated (based on mode)
            should_use_external_spectrum = self.mode.upper() == 'ARDOP'

            if should_use_external_spectrum != self.use_external_spectrum:
                self.use_external_spectrum = should_use_external_spectrum

                if should_use_external_spectrum:
                    # Create and start the spectrum receiver for ARDOP
                    host = self.config.get('modem', 'ardop_host', '127.0.0.1')
                    port = self.config.get('modem', 'ardop_spectrum_port', 8515)
                    self.spectrum_receiver = ArdopSpectrumReceiver(host=host, port=port)
                    if self.connected:
                        self.spectrum_receiver.start()
                else:
                    # Stop and remove the spectrum receiver
                    if self.spectrum_receiver:
                        self.spectrum_receiver.stop()
                        self.spectrum_receiver = None

        return True

    def get_connection_info(self):
        """Get modem connection info - delegates to active modem implementation"""
        return self.active_modem.get_connection_info()

    def get_modem_type(self):
        """Get the type of the active modem"""
        return self.mode
