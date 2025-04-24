"""
Base modem class for SSDigi Modem implementations
"""
import logging
import numpy as np
import threading
import time

logger = logging.getLogger(__name__)

class BaseModem:
    """Base class for all modem implementations"""

    def __init__(self, config, hamlib_manager=None):
        """Initialize base modem with common attributes and methods"""
        self.config = config
        self.hamlib_manager = hamlib_manager
        self.connected = False

        # Communication settings
        self.mode = config.get('modem', 'mode')
        self.bandwidth = int(config.get('modem', 'bandwidth'))
        self.center_freq = config.get('modem', 'center_freq')

        # User information
        self.callsign = config.get('user', 'callsign', '')
        self.grid_square = config.get('user', 'grid_square', '')
        self.fullname = config.get('user', 'fullname', '')
        self.email = config.get('user', 'email', '')
        self.city = config.get('user', 'city', '')

        # Status information
        self.status = {
            'connected': False,
            'snr': 0,
            'signal_level': -120,
            'mode': self.mode,
            'bandwidth': self.bandwidth,
            'center_freq': self.center_freq,
            'rx_active': False,
            'tx_active': False,
            'cpu_usage': 0,
            'audio_level': -60,
            'afc_offset': 0,
            'buffer_used': 0
        }

        # For signal processing
        self.sample_rate = config.get('audio', 'sample_rate')
        self.fft_size = config.get('ui', 'fft_size')
        self.fft_data = np.zeros(self.fft_size // 2)

        # Signal buffer for recording
        self.signal_buffer = []

        # Initialize communication thread
        self.comm_thread = None
        self.comm_thread_running = False

    def connect(self):
        """Connect to the modem - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement connect()")

    def disconnect(self):
        """Disconnect from the modem - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement disconnect()")

    def is_connected(self):
        """Check if modem is connected"""
        return self.connected

    def get_status(self):
        """Get current modem status"""
        return self.status

    def set_bandwidth(self, bandwidth):
        """Set modem bandwidth"""
        self.bandwidth = bandwidth
        self.status['bandwidth'] = bandwidth
        self.config.set('modem', 'bandwidth', bandwidth)
        self.config.save()
        return True

    def set_center_freq(self, center_freq):
        """Set center frequency"""
        self.center_freq = center_freq
        self.status['center_freq'] = center_freq
        self.config.set('modem', 'center_freq', center_freq)
        self.config.save()
        return True

    def get_available_bandwidths(self):
        """Get list of available bandwidths - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_available_bandwidths()")

    def get_fft_data(self):
        """Get current FFT data for spectrum display - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_fft_data()")

    def send_text(self, text):
        """Send text message - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement send_text()")

    def update_from_config(self):
        """Update modem settings from the configuration"""
        self.bandwidth = int(self.config.get('modem', 'bandwidth'))
        self.center_freq = self.config.get('modem', 'center_freq')
        self.callsign = self.config.get('user', 'callsign', '')

        # Update status information
        self.status.update({
            'mode': self.mode,
            'bandwidth': self.bandwidth,
            'center_freq': self.center_freq
        })

        return True

    def apply_config(self):
        """Apply all settings from config - to be implemented by subclasses if needed"""
        return self.update_from_config()

    def save_to_wav(self, file_path):
        """Save recent signal data to WAV file - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement save_to_wav()")

    def load_from_wav(self, file_path):
        """Load audio from WAV file - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement load_from_wav()")
