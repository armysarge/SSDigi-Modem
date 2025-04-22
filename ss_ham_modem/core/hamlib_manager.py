"""
HAMLIB rig control integration for SS-Ham-Modem
"""
import logging
import socket
import threading
import time
import re
import subprocess
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

class HamlibManager:
    """HAMLIB rig control for SS-Ham-Modem"""

    def __init__(self, config):
        """Initialize HAMLIB manager"""
        self.config = config
        self.connected = False
        self.rigctld_process = None
        self.socket = None

        # Communication settings
        self.rig_model = config.get('hamlib', 'rig_model')
        self.port = config.get('hamlib', 'port')
        self.baud_rate = config.get('hamlib', 'baud_rate')
        self.ptt_control = config.get('hamlib', 'ptt_control')

        # Status
        self.status = {
            'connected': False,
            'rig_model': self.rig_model,
            'ptt_status': 'OFF',
            'frequency': 0,
            'mode': None,
            'signal_strength': 0,
        }

        # Lock for thread safety
        self.lock = threading.Lock()

        # Communication thread
        self.comm_thread = None
        self.comm_thread_running = False

        # Find hamlib binary path
        self.rigctld_path = self._get_rigctld_path()

    def _get_rigctld_path(self):
        """Find rigctld binary"""
        # In a real implementation, this would point to embedded binaries
        # For now, we'll assume rigctld is in PATH or use a default location

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        if sys.platform == 'win32':
            # Check for embedded binary first
            embedded_path = os.path.join(base_dir, "bin", "hamlib", "rigctld.exe")
            if os.path.exists(embedded_path):
                return embedded_path

            # Check common Windows installation paths
            potential_paths = [
                r"C:\Program Files\hamlib\bin\rigctld.exe",
                r"C:\Program Files (x86)\hamlib\bin\rigctld.exe"
            ]

            for path in potential_paths:
                if os.path.exists(path):
                    return path

            # Fall back to assuming it's in PATH
            return "rigctld.exe"
        else:
            # Check for embedded binary first
            embedded_path = os.path.join(base_dir, "bin", "hamlib", "rigctld")
            if os.path.exists(embedded_path):
                return embedded_path

            # Fall back to assuming it's in PATH
            return "rigctld"

    def connect(self):
        """Connect to rig control"""
        if self.connected:
            logger.warning("HAMLIB already connected")
            return True

        try:
            # Update config
            self.rig_model = self.config.get('hamlib', 'rig_model')
            self.port = self.config.get('hamlib', 'port')
            self.baud_rate = self.config.get('hamlib', 'baud_rate')
            self.ptt_control = self.config.get('hamlib', 'ptt_control')

            # Start rigctld process
            if not self._start_rigctld():
                return False

            # Connect to rigctld via socket
            if not self._connect_socket():
                self._stop_rigctld()
                return False

            # Start communication thread
            self.comm_thread_running = True
            self.comm_thread = threading.Thread(target=self._communication_loop)
            self.comm_thread.daemon = True
            self.comm_thread.start()

            # Enable HAMLIB in config
            self.config.set('hamlib', 'enabled', True)
            self.config.save()

            self.connected = True
            self.status['connected'] = True
            logger.info("HAMLIB connected")
            return True

        except Exception as e:
            logger.exception(f"Error connecting to HAMLIB: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Disconnect from rig control"""
        if not self.connected:
            return True

        try:
            # Stop communication thread
            self.comm_thread_running = False
            if self.comm_thread:
                self.comm_thread.join(timeout=1.0)

            # Disconnect socket
            self._disconnect_socket()

            # Stop rigctld process
            self._stop_rigctld()

            # Update config
            self.config.set('hamlib', 'enabled', False)
            self.config.save()

            self.connected = False
            self.status['connected'] = False
            logger.info("HAMLIB disconnected")
            return True

        except Exception as e:
            logger.exception(f"Error disconnecting from HAMLIB: {e}")
            return False

    def is_connected(self):
        """Check if connected to rig control"""
        return self.connected

    def get_status(self):
        """Get current rig status"""
        return self.status

    def set_frequency(self, freq):
        """Set rig frequency"""
        if not self.connected:
            logger.warning("Cannot set frequency: HAMLIB not connected")
            return False

        try:
            with self.lock:
                if not self.socket:
                    return False

                # Send frequency command
                cmd = f"F {freq}\n"
                self.socket.sendall(cmd.encode('utf-8'))

                # Read response
                response = self._read_response()
                if response and "RPRT 0" in response:
                    self.status['frequency'] = freq
                    logger.info(f"Set frequency to {freq} Hz")
                    return True
                else:
                    logger.error(f"Failed to set frequency: {response}")
                    return False

        except Exception as e:
            logger.exception(f"Error setting frequency: {e}")
            return False

    def get_frequency(self):
        """Get current rig frequency"""
        if not self.connected:
            logger.warning("Cannot get frequency: HAMLIB not connected")
            return 0

        try:
            with self.lock:
                if not self.socket:
                    return 0

                # Send frequency query command
                cmd = "f\n"
                self.socket.sendall(cmd.encode('utf-8'))

                # Read response
                response = self._read_response()
                if response:
                    match = re.search(r'Frequency: (\d+)', response)
                    if match:
                        freq = int(match.group(1))
                        self.status['frequency'] = freq
                        return freq

            logger.error(f"Failed to get frequency: {response}")
            return 0

        except Exception as e:
            logger.exception(f"Error getting frequency: {e}")
            return 0

    def set_ptt(self, enabled):
        """Set PTT state"""
        if not self.connected:
            logger.warning("Cannot set PTT: HAMLIB not connected")
            return False

        try:
            with self.lock:
                if not self.socket:
                    return False

                # Send PTT command
                cmd = f"T {1 if enabled else 0}\n"
                self.socket.sendall(cmd.encode('utf-8'))

                # Read response
                response = self._read_response()
                if response and "RPRT 0" in response:
                    self.status['ptt_status'] = 'ON' if enabled else 'OFF'
                    logger.info(f"PTT set to {'ON' if enabled else 'OFF'}")
                    return True
                else:
                    logger.error(f"Failed to set PTT: {response}")
                    return False

        except Exception as e:
            logger.exception(f"Error setting PTT: {e}")
            return False

    def get_ptt(self):
        """Get current PTT state"""
        if not self.connected:
            logger.warning("Cannot get PTT: HAMLIB not connected")
            return False

        try:
            with self.lock:
                if not self.socket:
                    return False

                # Send PTT query command
                cmd = "t\n"
                self.socket.sendall(cmd.encode('utf-8'))

                # Read response
                response = self._read_response()
                if response:
                    match = re.search(r'PTT: (\d+)', response)
                    if match:
                        ptt_state = int(match.group(1)) == 1
                        self.status['ptt_status'] = 'ON' if ptt_state else 'OFF'
                        return ptt_state

            logger.error(f"Failed to get PTT state: {response}")
            return False

        except Exception as e:
            logger.exception(f"Error getting PTT state: {e}")
            return False

    def get_signal_strength(self):
        """Get signal strength from rig"""
        if not self.connected:
            return -54  # Default value when not connected

        try:
            with self.lock:
                if not self.socket:
                    return -54

                # Send signal strength query command
                cmd = "l STRENGTH\n"
                self.socket.sendall(cmd.encode('utf-8'))

                # Read response
                response = self._read_response()
                if response:
                    match = re.search(r'Level: ([-\d]+)', response)
                    if match:
                        level = int(match.group(1))
                        self.status['signal_strength'] = level
                        return level

            return -54

        except Exception as e:
            logger.exception(f"Error getting signal strength: {e}")
            return -54

    def get_available_rig_models(self):
        """Get list of available rig models from hamlib"""
        models = [
            (1, "Dummy"),
            (2, "NET rigctl"),
            (120, "Yaesu FT-817"),
            (122, "Yaesu FT-857"),
            (103, "Yaesu FT-100"),
            (176, "Yaesu FT-991"),
            (220, "Elecraft K3"),
            (351, "Icom IC-7300"),
            (2028, "Kenwood TS-2000"),
            (2035, "Kenwood TS-480"),
            (2045, "Kenwood TS-590S"),
        ]

        return models

    def _start_rigctld(self):
        """Start the rigctld process"""
        try:
            # Check if path exists
            if not os.path.exists(self.rigctld_path):
                logger.error(f"rigctld not found at {self.rigctld_path}")
                # Try to find in PATH
                try:
                    import shutil
                    path = shutil.which("rigctld")
                    if path:
                        self.rigctld_path = path
                    else:
                        logger.error("rigctld not found in PATH")
                        return False
                except:
                    logger.error("Could not find rigctld")
                    return False

            # Prepare rigctld arguments
            args = [
                self.rigctld_path,
                "-m", str(self.rig_model),  # Rig model
                "-r", self.port,            # Serial port
                "-s", str(self.baud_rate),  # Baud rate
                "-t", "4532"                # TCP port for control
            ]

            # For dummy rig, no need for serial port
            if self.rig_model == 1:
                args = [self.rigctld_path, "-m", "1", "-t", "4532"]

            # Start rigctld process
            logger.info(f"Starting rigctld: {' '.join(args)}")
            self.rigctld_process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Wait for startup
            time.sleep(1.0)

            # Check if process is running
            if self.rigctld_process.poll() is not None:
                stdout, stderr = self.rigctld_process.communicate()
                logger.error(f"rigctld failed to start: {stderr}")
                return False

            logger.info("rigctld process started")
            return True

        except Exception as e:
            logger.exception(f"Error starting rigctld: {e}")
            return False

    def _stop_rigctld(self):
        """Stop the rigctld process"""
        try:
            if self.rigctld_process:
                # Try to terminate gracefully
                self.rigctld_process.terminate()
                try:
                    self.rigctld_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    self.rigctld_process.kill()

                self.rigctld_process = None
                logger.info("rigctld process stopped")
        except Exception as e:
            logger.exception(f"Error stopping rigctld: {e}")

    def _connect_socket(self):
        """Connect to rigctld via socket"""
        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)

            # Connect to rigctld
            self.socket.connect(('localhost', 4532))

            logger.info("Connected to rigctld socket")
            return True

        except Exception as e:
            logger.exception(f"Error connecting to rigctld socket: {e}")
            self.socket = None
            return False

    def _disconnect_socket(self):
        """Disconnect from rigctld socket"""
        try:
            if self.socket:
                self.socket.close()
                self.socket = None
                logger.info("Disconnected from rigctld socket")
        except Exception as e:
            logger.exception(f"Error disconnecting from rigctld socket: {e}")

    def _read_response(self):
        """Read response from rigctld socket"""
        try:
            if not self.socket:
                return None

            # Set timeout to avoid blocking forever
            self.socket.settimeout(2.0)

            # Read response
            response = ""
            while True:
                chunk = self.socket.recv(4096).decode('utf-8')
                if not chunk:
                    break

                response += chunk
                if '\n' in chunk:
                    break

            return response.strip()

        except socket.timeout:
            logger.warning("Socket timeout while reading response")
            return None
        except Exception as e:
            logger.exception(f"Error reading response: {e}")
            return None

    def _communication_loop(self):
        """Thread for communicating with rigctld"""
        try:
            while self.comm_thread_running and self.connected:
                if self.rigctld_process and self.rigctld_process.poll() is not None:
                    # rigctld process has terminated unexpectedly
                    stdout, stderr = self.rigctld_process.communicate()
                    logger.error(f"rigctld process terminated: {stderr}")
                    self.connected = False
                    self.status['connected'] = False
                    break

                # Update rig status
                self._update_status()

                # Sleep to reduce CPU usage
                time.sleep(1.0)
        except Exception as e:
            logger.exception(f"Error in communication loop: {e}")
            self.connected = False
            self.status['connected'] = False

    def _update_status(self):
        """Update rig status"""
        try:
            # Get current frequency
            freq = self.get_frequency()
            if freq > 0:
                self.status['frequency'] = freq

            # Get signal strength periodically
            self.status['signal_strength'] = self.get_signal_strength()

        except Exception as e:
            logger.exception(f"Error updating status: {e}")
