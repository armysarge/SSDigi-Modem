"""
ARDOP FFT Data Receiver
Receives FFT data from ARDOP TNC via UDP
"""
import logging
import socket
import struct
import threading
import time
import numpy as np

logger = logging.getLogger(__name__)

class ArdopFFTReceiver:
    """Receives FFT data from ARDOP TNC via UDP"""

    def __init__(self, host='127.0.0.1', port=8515, buffer_size=16384):
        """Initialize the ARDOP FFT receiver"""
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.socket = None
        self.running = False
        self.thread = None

        # FFT data storage
        self.fft_data = None
        self.fft_data_lock = threading.Lock()
        self.last_update_time = 0

    def start(self):
        """Start the FFT receiver thread"""
        if self.running:
            logger.warning("FFT receiver already running")
            return False

        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(1.0)  # 1 second timeout for clean shutdown

            # Start receiver thread
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop)
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"ARDOP FFT receiver started on {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start FFT receiver: {str(e)}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False

    def stop(self):
        """Stop the FFT receiver thread"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(2.0)  # Wait up to 2 seconds for thread to exit

        if self.socket:
            self.socket.close()
            self.socket = None

        logger.info("ARDOP FFT receiver stopped")

    def _receive_loop(self):
        """Main receive loop - runs in separate thread"""
        while self.running:
            try:
                # Wait for data
                data, addr = self.socket.recvfrom(self.buffer_size)

                # Process the data - look for FFT type
                if data and len(data) > 3 and data[0] == ord('K'):
                    self._process_fft_data(data[1:])

            except socket.timeout:
                # This is normal, just continue
                pass
            except Exception as e:
                logger.error(f"Error in FFT receiver loop: {str(e)}")
                time.sleep(1.0)  # Avoid tight loop in case of recurring errors

    def _process_fft_data(self, data):
        """Process FFT data received from ARDOP"""
        try:
            if len(data) < 2:
                return

            # Get number of samples (first 2 bytes, big endian)
            num_samples = (data[0] << 8) | data[1]

            if len(data) < 2 + num_samples * 4:  # 4 bytes per float
                logger.warning(f"Incomplete FFT data: expected {num_samples} samples")
                return

            # Extract float values
            fft_values = []
            for i in range(num_samples):
                # Assuming 4-byte floats in native format
                offset = 2 + i * 4
                value = struct.unpack('f', data[offset:offset+4])[0]
                fft_values.append(value)

            # Store the FFT data
            with self.fft_data_lock:
                self.fft_data = np.array(fft_values)
                self.last_update_time = time.time()

        except Exception as e:
            logger.error(f"Error processing FFT data: {str(e)}")

    def get_fft_data(self):
        """Get the latest FFT data"""
        with self.fft_data_lock:
            return self.fft_data.copy() if self.fft_data is not None else None

    def get_last_update_time(self):
        """Get the timestamp of the last FFT data update"""
        return self.last_update_time

    def is_data_fresh(self, max_age_seconds=2.0):
        """Check if FFT data is fresh (updated recently)"""
        return (time.time() - self.last_update_time) < max_age_seconds
