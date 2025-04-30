# filepath: c:\Users\Shaun\Desktop\SSDigi-Modem\ssdigi_modem\core\modems\ardop\ardop_spectrum_receiver.py
"""
ARDOP Spectrum Receiver - Receives spectrum data from ARDOP for visualization

This module interacts with the ARDOP TNC to receive spectral data for
waterfall and spectrum display. It connects to the TNC via a UDP socket
and processes the FFT data that ARDOP sends using the 'W' packet format.
"""
import socket
import select
import logging
import threading
import time
import struct
import numpy as np
import re

logger = logging.getLogger(__name__)

class ArdopSpectrumReceiver:
    """
    Receiver for ARDOP spectrum data

    Connects to the ARDOP TNC on the specified host and port to
    receive spectrum data for visualization in the waterfall and spectrum displays.
    """

    def __init__(self, host='127.0.0.1', port=8515):
        """
        Initialize the ARDOP spectrum receiver

        Args:
            host: Host address of the ARDOP TNC (default: 127.0.0.1)
            port: Port for spectrum data (default: 8515)
        """
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.thread = None

        # Spectrum data
        self.spectrum_data = np.zeros(1024)  # Default size, will be adjusted based on actual data
        self.last_update_time = 0
        self.waterfall_data = np.zeros((256, 206), dtype=np.uint8)  # Store waterfall history
        self.waterfall_index = 0

        # Command socket
        self.cmd_socket = None
        self.cmd_port = 8515  # Default command port

        # Regex pattern for busy status from text protocol
        self.busy_pattern = re.compile(r'BUSY\s+(TRUE|FALSE)')

        # Flags for monitoring busy status
        self.busy_status = False

        # Statistics
        self.packets_received = 0
        self.last_packet_time = 0

        # Callbacks
        self.on_spectrum_update = None
        self.on_busy_status_change = None

    def start(self):
        """Start the spectrum receiver thread"""
        if self.running:
            logger.warning("ARDOP spectrum receiver already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._receive_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"ARDOP spectrum receiver started, listening on {self.host}:{self.port}")

    def stop(self):
        """Stop the spectrum receiver thread"""
        if not self.running:
            return

        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        if self.cmd_socket:
            try:
                self.cmd_socket.close()
            except:
                pass
            self.cmd_socket = None

        if self.thread:
            self.thread.join(1.0)  # Wait up to 1 second for thread to exit
            self.thread = None

        logger.info("ARDOP spectrum receiver stopped")

    def _connect(self):
        """Set up UDP socket to receive spectrum data from ARDOP"""
        try:
            # Clean up any existing socket
            if self.socket:
                self.socket.close()

            # Create a UDP socket for spectrum data
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(0.1)  # Short timeout for non-blocking operation

            # Try to create a TCP socket for command data (optional)
            try:
                self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.cmd_socket.settimeout(2)
                self.cmd_socket.connect((self.host, self.cmd_port))
                self.cmd_socket.settimeout(0.1)
                logger.info(f"Connected to ARDOP command port on {self.host}:{self.cmd_port}")
            except Exception as e:
                logger.warning(f"Could not connect to ARDOP command port: {str(e)}")
                if self.cmd_socket:
                    self.cmd_socket.close()
                    self.cmd_socket = None

            logger.info(f"Listening for ARDOP spectrum data on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to set up ARDOP spectrum receiver: {str(e)}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False

    def _send_command(self, command):
        """Send a command to the ARDOP TNC"""
        if not self.cmd_socket:
            return False

        try:
            self.cmd_socket.send(f"{command}\r".encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Failed to send command to ARDOP: {str(e)}")
            return False

    def _receive_loop(self):
        """Main receiver loop"""
        reconnect_time = 0
        reconnect_interval = 5  # Seconds between reconnection attempts

        while self.running:
            # Check if we need to connect/reconnect
            if not self.socket and time.time() > reconnect_time:
                if self._connect():
                    reconnect_time = 0
                else:
                    reconnect_time = time.time() + reconnect_interval
                    continue

            # If we're not connected, wait and retry
            if not self.socket:
                time.sleep(0.1)
                continue

            try:
                # Check if there's data to read from UDP socket
                readable, _, _ = select.select([self.socket], [], [], 0.1)

                if self.socket in readable:
                    data, addr = self.socket.recvfrom(16384)
                    if data:
                        # Process the UDP packet
                        self._process_udp_packet(data)

                # Also check for command data if we have a command socket
                if self.cmd_socket:
                    try:
                        readable, _, _ = select.select([self.cmd_socket], [], [], 0)
                        if self.cmd_socket in readable:
                            cmd_data = self.cmd_socket.recv(4096)
                            if not cmd_data:  # Connection closed
                                logger.warning("ARDOP command connection closed")
                                self.cmd_socket.close()
                                self.cmd_socket = None
                            else:
                                # Process any command data (for busy status etc.)
                                self._process_command_data(cmd_data)
                    except Exception as e:
                        logger.error(f"Error reading from command socket: {str(e)}")
                        self.cmd_socket.close()
                        self.cmd_socket = None

            except socket.timeout:
                # This is normal - just continue
                pass
            except Exception as e:
                logger.error(f"Error in ARDOP spectrum receiver: {str(e)}")
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = None
                reconnect_time = time.time() + reconnect_interval

    def _process_udp_packet(self, data):
        """Process a UDP packet from ARDOP"""
        if not data or len(data) < 3:
            return

        # Check if this is a spectrum data packet (should start with 'W')
        if data[0] == ord('W'):
            # Extract number of samples
            num_samples = (data[1] << 8) | data[2]

            # Verify we have enough data
            if len(data) >= 3 + num_samples * 4:  # Header (3 bytes) + float values (4 bytes each)
                try:
                    # Extract float values
                    fft_values = []
                    for i in range(num_samples):
                        offset = 3 + i * 4
                        value = struct.unpack('f', data[offset:offset+4])[0]
                        fft_values.append(value)

                    # Convert to numpy array
                    spectrum = np.array(fft_values)

                    # Update statistics
                    self.packets_received += 1
                    self.last_packet_time = time.time()
                    self.last_update_time = self.last_packet_time

                    # Update the spectrum data
                    self.spectrum_data = spectrum

                    # Update the waterfall data
                    self.waterfall_data[self.waterfall_index] = self._spectrum_to_colors(spectrum)
                    self.waterfall_index = (self.waterfall_index + 1) % 256

                    # Notify listeners
                    if self.on_spectrum_update:
                        self.on_spectrum_update(spectrum)

                except Exception as e:
                    logger.error(f"Error processing spectrum data: {str(e)}")
        else:
            logger.debug(f"Received non-spectral UDP packet: first byte={data[0]}")

    def _process_command_data(self, data):
        """Process command data from the ARDOP TNC"""
        # Look for busy status updates in the command data
        try:
            text = data.decode('utf-8', errors='ignore')

            # Check for busy status
            match = self.busy_pattern.search(text)
            if match:
                new_status = (match.group(1) == 'TRUE')

                # Only notify if status changed
                if new_status != self.busy_status:
                    self.busy_status = new_status
                    logger.info(f"ARDOP busy status changed: {self.busy_status}")

                    if self.on_busy_status_change:
                        self.on_busy_status_change(self.busy_status)
        except Exception as e:
            logger.error(f"Error processing command data: {str(e)}")

    def _spectrum_to_colors(self, spectrum_data):
        """
        Convert spectrum data to color values for waterfall display
        """
        # Create a color mapping for the waterfall display
        colors = np.zeros(len(spectrum_data), dtype=np.uint8)

        # Log scale mapping to colors (0-255)
        if len(spectrum_data) > 0:
            # Convert to dB scale (log10)
            db_values = 10 * np.log10(spectrum_data + 1e-10)

            # Normalize to 0-255 range with reasonable min/max values
            min_db = -130  # Typical noise floor in dB
            max_db = -30   # Typical signal peak in dB

            # Clip and normalize
            db_values = np.clip(db_values, min_db, max_db)
            normalized = (db_values - min_db) / (max_db - min_db)
            colors = (normalized * 255).astype(np.uint8)

        return colors

    def get_spectrum_data(self):
        """Get the current spectrum data"""
        return self.spectrum_data.copy()

    def is_data_fresh(self):
        """Check if spectrum data is fresh (received within the last 2 seconds)"""
        if self.last_update_time == 0:
            return False
        return (time.time() - self.last_update_time) < 2.0

    def get_waterfall_data(self):
        """Get the waterfall data as a 2D numpy array"""
        # Rearrange data so the most recent data is at the bottom
        result = np.zeros_like(self.waterfall_data)
        for i in range(256):
            idx = (self.waterfall_index - i - 1) % 256
            if idx < 0:
                idx += 256
            result[i] = self.waterfall_data[idx]
        return result

    def is_busy(self):
        """Return current busy status"""
        return self.busy_status

    def set_spectrum_update_callback(self, callback):
        """
        Set callback to be called when spectrum data is updated

        Args:
            callback: Function to call with spectrum data (numpy array)
        """
        self.on_spectrum_update = callback

    def set_busy_status_callback(self, callback):
        """
        Set callback to be called when busy status changes

        Args:
            callback: Function to call with busy status (boolean)
        """
        self.on_busy_status_change = callback

    def send_command(self, command):
        """
        Send a command to the ARDOP TNC

        This method is public to allow clients to send commands for
        configuring the spectrum display or other settings

        Args:
            command: Command string to send

        Returns:
            True if command was sent successfully
        """
        return self._send_command(command)
