"""
ARDOP modem implementation for SSDigi Modem
"""
import os
import sys
import subprocess
import logging
import threading
import time
import numpy as np
import wave
import socket
import select
import re
from pathlib import Path

from ssdigi_modem.core.modems.base_modem import BaseModem
from ssdigi_modem.core.modems.ardop.ardop_modem_commands import generate_host_commands

logger = logging.getLogger(__name__)

class ArdopModem(BaseModem):
    """ARDOP modem implementation for SSDigi Modem"""

    def __init__(self, config, hamlib_manager=None):
        """Initialize ARDOP modem"""
        super().__init__(config, hamlib_manager)

        # ARDOP-specific attributes
        self.ardop_process = None
        self.ardop_path = self._get_ardop_binary_path()
        self.cmd_socket = None
        self.data_socket = None
        self.cmd_thread = None
        self.cmd_thread_running = False

        # Default ports for ARDOP
        self.cmd_port = 8515
        self.data_port = 8516
        self.webgui_port = 8514

        # Default PTT settings
        self.ptt_method = config.get('modem', 'ptt_method', 'VOX')
        self.ptt_port = config.get('modem', 'ptt_port', '')
        self.ptt_baud = config.get('modem', 'ptt_baud', 19200)        # For CAT PTT
        self.key_string = config.get('modem', 'key_string', '')
        self.unkey_string = config.get('modem', 'unkey_string', '')

        # No simulation mode - using real ARDOP implementation
        self.status.update({
            'state': 'DISCONNECTED',
            'remote_station': '',
            'channel_busy': False,
            'last_command': '',
            'last_command_time': 0,
            'last_pingack_result': '',
            'last_pingack_time': 0
        })

    def connect(self):
        """Connect to the ARDOP modem"""
        if self.connected:
            logger.warning("Modem already connected")
            return True

        # Verify that a callsign is set before connecting
        if not self.callsign or self.callsign == "":
            logger.error("Cannot connect: No callsign is set")
            return False

        try:
            logger.debug(f"Using bandwidth: {self.bandwidth} Hz")            # Check if we're using external ARDOP
            if self.config.get('modem', 'ardop_mode', 'internal') == 'external':
                logger.info("Using external ARDOP mode")
                # Skip binary check and audio device configuration
                if not self._connect_to_ardop_sockets():
                    return False
            else:
                # Check if we have a valid ARDOP binary for internal mode
                if not self.ardop_path or not os.path.exists(self.ardop_path):
                    logger.error(f"ARDOP binary not found at {self.ardop_path}")
                    return False

                # Configure using actual ARDOP audio devices before connecting
                self.configure_from_ardop_devices()

                # Start ARDOP process
                if not self._start_ardop_process():
                    return False

            # Start communication thread
            self.comm_thread_running = True
            self.comm_thread = threading.Thread(target=self._communication_loop)
            self.comm_thread.daemon = True
            self.comm_thread.start()

            self.connected = True
            self.status['connected'] = True
            logger.info("ARDOP modem connected")
            return True

        except Exception as e:
            logger.exception(f"Error connecting to ARDOP modem: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Disconnect from the ARDOP modem"""
        if not self.connected:
            return True

        try:
            # Stop communication thread
            self.comm_thread_running = False
            if self.comm_thread:
                self.comm_thread.join(timeout=1.0)

            # Stop ARDOP process
            self._stop_ardop_process()

            self.connected = False
            self.status['connected'] = False
            logger.info("ARDOP modem disconnected")
            return True

        except Exception as e:
            logger.exception(f"Error disconnecting ARDOP modem: {e}")
            return False

    def get_spectrum_data(self):
        """Get current spectrum data for display - wrapper for get_fft_data method"""
        return self.get_fft_data()

    def get_fft_data(self):
        """Get current FFT data for spectrum display"""
        if not self.connected:
            # When not connected, return a synthetic noise floor
            noise_floor = -80 + np.random.normal(0, 1, self.fft_size // 2)
            return noise_floor

        # Get actual FFT data from ARDOP
        if hasattr(self, 'fft_data') and self.fft_data is not None:
            # Check if data contains any invalid values
            if np.isnan(self.fft_data).any() or np.isinf(self.fft_data).any():
                logger.warning("Invalid FFT data detected (NaN or Inf), using synthetic data")
                return -80 + np.random.normal(0, 1, self.fft_size // 2)

            # Check for extreme values that would cause rendering issues
            min_value = np.min(self.fft_data)
            max_value = np.max(self.fft_data)

            # Log if values are out of expected range
            if min_value < -120 or max_value > 0:
                logger.debug(f"FFT data out of range: min={min_value}, max={max_value}, normalizing")

            # Ensure the FFT data is within reasonable limits to prevent display issues
            # Using a wider range to prevent all-red display
            min_val = -120  # Lower minimum value to ensure good color spread
            max_val = -20   # Maximum value in dB (strongest signal)

            # Normalize and clamp values to ensure they're in a reasonable range
            # This will give better color distribution in the waterfall
            normalized_data = np.interp(self.fft_data, [min_value, max_value], [min_val, max_val])
            clamped_data = np.clip(normalized_data, min_val, max_val)

            # Return the normalized and clamped data
            return clamped_data
        else:
            # If no data is available yet, return a reasonable noise floor
            noise_floor = -80 + np.random.normal(0, 1, self.fft_size // 2)
            return noise_floor

    def send_ping(self):
        """Send PING command to ARDOP - useful for testing and diagnostics

        Returns:
            bool: True if command was sent successfully, False otherwise

        The PING command instructs ARDOP to send a ping acknowledgment,
        which can be useful for testing the connection and functionality.
        Responses will be processed via the command socket's reader thread.
        """
        logger.info("Sending PING command to ARDOP")

        if not self.connected:
            logger.warning("Cannot send PING: Modem not connected")
            return False

        # Send the command via the command socket
        # Using the correct command format for ARDOP ping - without CMD prefix
        success = self._send_command("PING MYCALL 1")

        if success:
            # Update status to indicate PING was sent
            self.status['last_command'] = "PING"
            self.status['last_command_time'] = time.time()

        return success

    def send_text(self, text):
        """Send text message via ARDOP data socket"""
        if not self.connected:
            logger.warning("Cannot send text: ARDOP modem not connected")
            return False

        try:
            if not text:
                return False

            # Send data to ARDOP via the data socket
            return self._send_data(text.encode('utf-8'))
        except Exception as e:
            logger.exception(f"Error sending text: {e}")
            return False

    def apply_config(self):
        """Apply all settings from config"""
        logger.info("Applying configuration changes to ARDOP modem")

        # Update settings from config via base class method
        super().apply_config()

        # Apply ARDOP-specific settings
        self.ptt_method = self.config.get('modem', 'ptt_method', 'VOX')
        self.ptt_port = self.config.get('modem', 'ptt_port', '')
        self.ptt_baud = self.config.get('modem', 'ptt_baud', 19200)
        self.key_string = self.config.get('modem', 'key_string', '')
        self.unkey_string = self.config.get('modem', 'unkey_string', '')

        # If connected, apply changes immediately
        if self.connected:
            logger.info("Applying configuration changes to active ARDOP connection")
            # Send updated settings to modem
            self._update_modem_settings()

        return True

    def save_to_wav(self, file_path):
        """Save recent signal data to WAV file for testing"""
        if not self.signal_buffer:
            logger.warning("No signal data to save")
            return False

        try:
            # Convert FFT data back to time domain (this is simplified)
            # In a real implementation, we would save the actual audio
            sample_data = np.random.normal(0, 0.1, 48000 * 5)  # 5 seconds of noise

            # Add simulated signals
            t = np.arange(len(sample_data)) / 48000
            signal = 0.5 * np.sin(2 * np.pi * self.center_freq * t)

            # Apply amplitude modulation to simulate FSK
            am_freq = 20  # Hz
            am_mod = 0.5 * (1 + np.sin(2 * np.pi * am_freq * t))
            sample_data += signal * am_mod

            # Normalize
            sample_data = np.clip(sample_data, -1.0, 1.0)

            # Convert to int16 for WAV
            int_data = (sample_data * 32767).astype(np.int16)

            # Write WAV file
            with wave.open(file_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 2 bytes for int16
                wf.setframerate(48000)
                wf.writeframes(int_data.tobytes())

            logger.info(f"Saved signal data to {file_path}")
            return True
        except Exception as e:
            logger.exception(f"Error saving WAV file: {e}")
            return False

    def load_from_wav(self, file_path):
        """Load a WAV file for testing the modem"""
        try:
            with wave.open(file_path, 'rb') as wf:
                # Get WAV file parameters
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()

                # Read audio data
                wave_data = wf.readframes(n_frames)

                # Convert to numpy array
                if sample_width == 2:  # 16-bit audio
                    data = np.frombuffer(wave_data, dtype=np.int16).astype(np.float32) / 32768.0
                elif sample_width == 4:  # 32-bit audio
                    data = np.frombuffer(wave_data, dtype=np.float32)
                else:
                    logger.error(f"Unsupported sample width: {sample_width}")
                    return False

                # Process the loaded data here
                # In a real implementation, this would feed the data to ARDOP
                # For now, we'll just update the FFT data based on the WAV content

                # Clear the signal buffer
                self.signal_buffer.clear()

                # Process the audio in chunks and update FFT data
                chunk_size = self.fft_size
                for i in range(0, len(data), chunk_size // 2):
                    if i + chunk_size > len(data):
                        chunk = np.pad(data[i:], (0, chunk_size - (len(data) - i)))
                    else:
                        chunk = data[i:i+chunk_size]

                    # Compute FFT
                    fft_data = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
                    fft_data = 20 * np.log10(fft_data + 1e-10)

                    # Add to signal buffer
                    self.signal_buffer.append(fft_data)

                # Update current FFT data
                if self.signal_buffer:
                    self.fft_data = self.signal_buffer[-1]

                logger.info(f"Loaded audio from {file_path}")
                return True

        except Exception as e:
            logger.exception(f"Error loading WAV file: {e}")
            return False

    # ----- Private methods -----

    def _get_ardop_binary_path(self):
        """Get path to the appropriate ARDOP binary based on platform"""
        # Debug - log current directory and module path
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Module location: {os.path.dirname(os.path.abspath(__file__))}")

        # Check if path is explicitly specified in config
        config_path = self.config.get('modem', 'ardop_path', '')
        if config_path and os.path.exists(config_path):
            logger.info(f"Using ARDOP binary from config: {config_path}")
            return config_path

        # Check if we're running in a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            base_dir = sys._MEIPASS
            logger.info(f"Running from PyInstaller bundle: {base_dir}")

            # In PyInstaller bundle, binaries should be in the 'bin' directory
            if sys.platform == 'win32':
                binary_path = os.path.join(base_dir, "bin", "ardop.exe")
                logger.debug(f"Checking PyInstaller Windows path: {binary_path}")
            elif sys.platform.startswith('linux'):
                binary_path = os.path.join(base_dir, "bin", "ardop")
                logger.debug(f"Checking PyInstaller Linux path: {binary_path}")
            else:
                logger.error(f"Unsupported platform: {sys.platform}")
                return None
        else:
            # Running in development environment
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            logger.info(f"Base directory: {base_dir}")

            # Define expected binary locations for development
            if sys.platform == 'win32':
                # Define all possible Windows paths to check
                possible_paths = [
                    os.path.join(base_dir, "bin", "ardop", "windows", "ardop.exe"),
                    os.path.join(base_dir, "ardop", "ardopcf.exe"),
                    os.path.join(base_dir, "ardop", "ardop.exe"),
                    os.path.join(base_dir, "bin", "ardop.exe"),
                    os.path.join(base_dir, "bin", "ardopcf.exe"),
                    os.path.join(os.path.dirname(base_dir), "bin", "ardop.exe"),
                    os.path.join(os.path.dirname(base_dir), "ardop", "ardop.exe")
                ]

                # Try each path
                for path in possible_paths:
                    logger.debug(f"Checking Windows path: {path}")
                    if os.path.exists(path):
                        binary_path = path
                        break
                else:
                    # If no path is found, set a default that will be checked later
                    binary_path = os.path.join(base_dir, "bin", "ardop", "windows", "ardop.exe")

            elif sys.platform.startswith('linux'):
                # On Linux, the binary is typically named 'ardopcf'
                binary_path = os.path.join(base_dir, "bin", "ardop", "linux", "ardopcf")
                logger.debug(f"Checking Linux path: {binary_path}")

                # Check alternate locations based on USAGE_linux.md
                if not os.path.exists(binary_path):
                    # Check if built from source in ardop directory
                    alt_paths = [
                        os.path.join(base_dir, "ardop", "ardopcf"),
                        os.path.join(base_dir, "bin", "ardopcf"),
                        os.path.join(base_dir, "ardopcf")
                    ]

                    for path in alt_paths:
                        logger.debug(f"Checking alternative Linux path: {path}")
                        if os.path.exists(path):
                            binary_path = path
                            break

                # Check common Linux locations as per USAGE_linux.md
                if not os.path.exists(binary_path):
                    linux_locations = [
                        "/usr/local/bin/ardopcf",
                        "/usr/bin/ardopcf",
                        os.path.expanduser("~/bin/ardopcf"),
                        os.path.join(os.getcwd(), "ardopcf"),
                        "/usr/local/bin/ardop",
                        "/usr/bin/ardop"
                    ]

                    for location in linux_locations:
                        logger.debug(f"Checking system Linux path: {location}")
                        if os.path.exists(location):
                            logger.info(f"Found ARDOP binary at {location}")
                            binary_path = location
                            break
            else:
                logger.error(f"Unsupported platform: {sys.platform}")
                return None

        # Check if binary exists
        if os.path.exists(binary_path):
            logger.info(f"Found ARDOP binary: {binary_path}")
            return binary_path
        else:
            logger.warning(f"ARDOP binary not found at expected path: {binary_path}")

            # Try a last resort search in common locations
            if sys.platform == 'win32':
                last_resort_paths = []

                for possible_name in ["ardop.exe", "ardopcf.exe"]:
                    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                        # Check in PyInstaller bundle root
                        last_resort_paths.append(os.path.join(sys._MEIPASS, possible_name))

                    # Check in the same directory as the executable
                    last_resort_paths.append(os.path.join(os.path.dirname(sys.executable), possible_name))

                    # Check in current working directory
                    last_resort_paths.append(os.path.join(os.getcwd(), possible_name))

                    # Check one directory up from current working directory
                    last_resort_paths.append(os.path.join(os.path.dirname(os.getcwd()), possible_name))

                # Check parent directory of SSDigi-Modem
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                last_resort_paths.append(os.path.join(parent_dir, "ardop.exe"))
                last_resort_paths.append(os.path.join(parent_dir, "ardopcf.exe"))

                # Also check Desktop for development convenience
                if "Desktop" in os.environ.get("USERPROFILE", ""):
                    desktop_path = os.path.join(os.environ["USERPROFILE"], "Desktop")
                    last_resort_paths.append(os.path.join(desktop_path, "ardop.exe"))
                    last_resort_paths.append(os.path.join(desktop_path, "ardopcf.exe"))

                for possible_path in last_resort_paths:
                    logger.debug(f"Last resort check: {possible_path}")
                    if os.path.exists(possible_path):
                        logger.info(f"Found ARDOP binary at {possible_path}")
                        return possible_path

            elif sys.platform.startswith('linux'):
                # Check common Linux locations
                for location in ["/usr/local/bin", "/usr/bin", os.path.expanduser("~")]:
                    for binary_name in ["ardop", "ardopcf"]:
                        possible_path = os.path.join(location, binary_name)
                        logger.debug(f"Last resort Linux check: {possible_path}")
                        if os.path.exists(possible_path):
                            logger.info(f"Found ARDOP binary at {possible_path}")
                            return possible_path

            # If we got here, no binary was found
            logger.error("ARDOP binary not found in any location")
            return None

    def _start_ardop_process(self):
        """Start the ARDOP binary as a separate process with appropriate parameters"""
        try:
            # Check if we're using external ARDOP
            if self.config.get('modem', 'ardop_mode', 'internal') == 'external':
                logger.info("Using external ARDOP - skipping local ARDOP process start")
                return True

            # Get path to the pre-built ARDOP binary
            if not self.ardop_path or not os.path.exists(self.ardop_path):
                logger.error(f"ARDOP binary not found at {self.ardop_path}")
                return False

            # Get callsign from configuration
            callsign = self.config.get('user', 'callsign', 'NOCALL')

            # Validate callsign format
            if not (len(callsign) <= 8 and callsign.isalnum()):
                logger.warning(f"Invalid callsign format: {callsign}, using NOCALL")
                callsign = "NOCALL"

            # Store the active callsign
            self.callsign = callsign.upper()

            # Get grid square from config
            grid_square = self.config.get('user', 'grid_square', '')

            # Get audio device IDs
            input_device = self.config.get('audio', 'input_device', 0)
            output_device = self.config.get('audio', 'output_device', 0)

            # Get command port
            cmd_port = self.config.get('modem', 'command_port', 8515)
            self.cmd_port = cmd_port            # PTT Method settings
            ptt_args = []
            ptt_method = self.config.get('modem', 'ptt_method', 'VOX').upper()

            if ptt_method == 'RTS':
                # RTS PTT via serial port
                ptt_port = self.config.get('modem', 'ptt_port', '')
                ptt_baud = self.config.get('modem', 'ptt_baud', 19200)
                if ptt_port:
                    # On Linux, ensure device path has correct format (e.g., /dev/ttyUSB0)
                    if sys.platform.startswith('linux') and not ptt_port.startswith('/dev/'):
                        logger.warning(f"Serial port '{ptt_port}' may not be in proper Linux format")
                        if ptt_port.isdigit():
                            # Attempt to convert numeric port to a proper Linux device path
                            ptt_port = f"/dev/ttyUSB{ptt_port}"
                            logger.info(f"Converted port number to Linux device path: {ptt_port}")

                    ptt_args = ["-p", f"{ptt_port}:{ptt_baud}"]
                    logger.info(f"Using RTS PTT with port {ptt_port} at {ptt_baud} baud")
            elif ptt_method == 'CAT':
                # CAT PTT via serial port with key/unkey strings
                ptt_port = self.config.get('modem', 'ptt_port', '')
                ptt_baud = self.config.get('modem', 'ptt_baud', 19200)
                key_string = self.config.get('modem', 'key_string', '')
                unkey_string = self.config.get('modem', 'unkey_string', '')

                # On Linux, ensure device path has correct format (e.g., /dev/ttyUSB0)
                if sys.platform.startswith('linux') and ptt_port and not ptt_port.startswith('/dev/'):
                    logger.warning(f"Serial port '{ptt_port}' may not be in proper Linux format")
                    if ptt_port.isdigit():
                        # Attempt to convert numeric port to a proper Linux device path
                        ptt_port = f"/dev/ttyUSB{ptt_port}"
                        logger.info(f"Converted port number to Linux device path: {ptt_port}")

                # On Linux, document some known working CAT key/unkey strings based on USAGE_linux.md
                if sys.platform.startswith('linux') and not (key_string and unkey_string):
                    radio_model = self.config.get('hamlib', 'rig_model', '').lower()
                    if "kenwood" in radio_model or "elecraft" in radio_model or "tx-500" in radio_model:
                        logger.info(f"Using default CAT strings for Kenwood/Elecraft/TX-500 radio")
                        key_string = "54583B"    # 'TX;' in hex
                        unkey_string = "52583B"  # 'RX;' in hex
                    elif "xiegu" in radio_model or "g90" in radio_model:
                        logger.info(f"Using default CAT strings for Xiegu G90 radio")
                        key_string = "FEFE88E01C0001FD"
                        unkey_string = "FEFE88E01C0000FD"

                if ptt_port and key_string and unkey_string:
                    ptt_args = [
                        "-c", f"{ptt_port}:{ptt_baud}",
                        "--keystring", key_string,
                        "--unkeystring", unkey_string
                    ]
                    logger.info(f"Using CAT PTT with port {ptt_port} and key/unkey strings")
            elif ptt_method == 'GPIO' and sys.platform.startswith('linux'):
                # GPIO PTT for ARM devices like Raspberry Pi (Linux only)
                gpio_pin = self.config.get('modem', 'gpio_pin', '')
                if gpio_pin:
                    ptt_args = ["--gpio", str(gpio_pin)]
                    logger.info(f"Using GPIO PTT with pin {gpio_pin}")
            elif ptt_method == 'CM108' and sys.platform.startswith('linux'):
                # CM108 PTT for Linux using USB audio devices with PTT capability
                cm108_device = self.config.get('modem', 'cm108_device', '')
                if cm108_device:
                    ptt_args = ["--cm108", cm108_device]
                    logger.info(f"Using CM108 PTT with device {cm108_device}")
            elif ptt_method != 'VOX' and ptt_method != 'NONE':
                logger.warning(f"Unsupported PTT method: {ptt_method}, falling back to VOX")

            # Log directory settings
            logdir_args = []
            logdir = self.config.get('modem', 'logdir', '')
            if logdir:
                logdir_args = ["--logdir", logdir]

            # Host commands (semicolon-separated commands to execute at startup)
            hostcmd_args = []            # Check if there are explicit hostcommands specified in config
            hostcmds = self.config.get('modem', 'hostcommands', '')

            # If no explicit hostcommands, generate them from settings
            if not hostcmds:
                # Use the imported generator function
                hostcmds = generate_host_commands(self.config, self.bandwidth, self.callsign, self.grid_square)
                #logger.info(f"Generated host commands from settings: {hostcmds}")
            else:
                logger.info(f"Using explicit host commands from config: {hostcmds}")

            # Add host commands to arguments with platform-specific format
            if hostcmds:
                if sys.platform.startswith('linux'):
                    # Linux uses -H parameter for host commands
                    hostcmd_args = ["-H", hostcmds]
                else:
                    # Windows uses --hostcommands parameter
                    hostcmd_args = ["--hostcommands", hostcmds]

            # Get platform-specific audio device arguments
            audio_device_args = self._get_audio_device_args_for_platform(input_device, output_device)

            # Build full command line
            args = [self.ardop_path] + ptt_args + logdir_args + hostcmd_args + [
                str(cmd_port),    # Command port (usually 8515)
            ] + audio_device_args  # Platform-specific audio device arguments

            # Start ARDOP process
            logger.info(f"Starting ARDOP binary: {' '.join(args)}")
            self.ardop_process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Wait for startup
            time.sleep(1.5)

            # Check if process is running
            if self.ardop_process.poll() is not None:
                stdout, stderr = self.ardop_process.communicate()
                logger.error(f"ARDOP failed to start: {stderr}")
                return False

            # Process is running, now connect to its TCP interface
            if not self._connect_to_ardop_sockets():
                self._stop_ardop_process()
                return False

            logger.info("ARDOP process started and connected to TCP interface")
            return True

        except Exception as e:
            logger.exception(f"Error starting ARDOP process: {e}")
            return False

    def _connect_to_ardop_sockets(self):
        """Connect to ARDOP's command and data TCP sockets"""
        import socket
        try:
            # Get connection details based on mode
            ardop_mode = self.config.get('modem', 'ardop_mode', 'internal')
            if ardop_mode == 'external':
                host = self.config.get('modem', 'ardop_ip', '127.0.0.1')
                port = self.config.get('modem', 'ardop_port', 8515)
                logger.info(f"Connecting to external ARDOP at {host}:{port}")
            else:
                host = '127.0.0.1'
                port = self.cmd_port
                logger.info(f"Connecting to local ARDOP at {host}:{port}")

            # Connect to command socket
            self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.cmd_socket.connect((host, port))            # Connect to data socket (default port is command_port + 1)
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if ardop_mode == 'external':
                data_port = port + 1
            else:
                data_port = self.data_port
            self.data_socket.connect((host, data_port))

            # Start thread to read from command socket
            self.cmd_thread_running = True
            self.cmd_thread = threading.Thread(target=self._command_reader_thread)
            self.cmd_thread.daemon = True
            self.cmd_thread.start()

            # Initialize ARDOP via TCP interface
            self._send_command("INITIALIZE")
            time.sleep(0.5)

            # Set callsign
            self._send_command(f"MYCALL {self.callsign}")

            # Set grid square if available
            if self.grid_square:
                self._send_command(f"GRIDSQUARE {self.grid_square}")

            # Enable ARQ mode (as per USAGE documentation)
            self._send_command("PROTOCOLMODE ARQ")

            # Set bandwidth
            self._send_command(f"ARQBW {self.bandwidth}{self.config.get('modem', 'arqbw_mode', 'MAX')}")

            return True

        except Exception as e:
            logger.exception(f"Error connecting to ARDOP sockets: {e}")
            return False

    def _command_reader_thread(self):
        """Thread to continuously read from ARDOP command socket"""
        try:
            buffer = ""
            while self.cmd_thread_running:
                data = self.cmd_socket.recv(1024).decode('utf-8')
                if not data:
                    # Connection closed
                    logger.warning("ARDOP command socket closed")
                    break

                # Process responses (they are terminated with CR)
                buffer += data
                while '\r' in buffer:
                    line, buffer = buffer.split('\r', 1)
                    if line:
                        self._process_ardop_response(line)

            logger.info("Command reader thread ending")

        except Exception as e:
            logger.exception(f"Error in command reader thread: {e}")
            self.cmd_thread_running = False

    def _process_ardop_response(self, response):
        """Process response received from ARDOP command socket"""
        logger.debug(f"ARDOP response: {response}")

        # Update status based on ARDOP responses
        if response.startswith("STATE"):
            state = response.split()[1]
            self.status['state'] = state

        elif response.startswith("BUFFER"):
            try:
                buffer_size = int(response.split()[1])
                self.status['buffer'] = buffer_size
            except:
                pass

        elif response.startswith("CONNECTED"):
            parts = response.split()
            if len(parts) >= 3:
                remote_call = parts[1]
                bandwidth = parts[2]
                self.status['connected'] = True
                self.status['remote_station'] = remote_call
                self.status['bandwidth'] = bandwidth
                logger.info(f"Connected to {remote_call} with {bandwidth}Hz bandwidth")

        elif response.startswith("DISCONNECTED"):
            self.status['connected'] = False
            self.status['remote_station'] = ""
            logger.info("Disconnected")

        elif response.startswith("PINGACK"):
            # Process PINGACK response - important for diagnostics
            logger.info(f"PINGACK response received: {response}")
            if 'SUCCESS' in response:
                self.status['last_pingack_result'] = "Success"
                self.status['last_pingack_time'] = time.time()
            else:
                self.status['last_pingack_result'] = "Failed"

        elif response.startswith("INPUTPEAKS"):
            # Process but don't log every INPUTPEAKS message as they're very frequent
            try:
                parts = response.split()
                if len(parts) >= 2:
                    peak = float(parts[1])
                    self.status['audio_level'] = 20 * np.log10(peak + 1e-10)  # Convert to dB
            except Exception:
                pass

        elif response.startswith("BUSY"):
            # Channel busy indicator
            self.status['channel_busy'] = True
            logger.info("Channel busy detected")

        elif response.startswith("FREE"):
            # Channel free indicator
            self.status['channel_busy'] = False
            logger.info("Channel free detected")

    def _send_command(self, command):
        """Send a command to ARDOP via the command socket"""
        try:
            if self.cmd_socket:
                logger.debug(f"Sending ARDOP command: {command}")
                # Commands must end with CR
                self.cmd_socket.sendall((command + "\r").encode('utf-8'))
                return True
            return False
        except Exception as e:
            logger.exception(f"Error sending command to ARDOP: {e}")
            return False

    def _send_data(self, data):
        """Send data to ARDOP via the data socket"""
        try:
            if self.data_socket and data:
                self.data_socket.sendall(data)
                return True
            return False
        except Exception as e:
            logger.exception(f"Error sending data to ARDOP: {e}")
            return False

    def _stop_ardop_process(self):
        """Stop the ARDOP process and close sockets"""
        try:
            # Close sockets if open
            if hasattr(self, 'cmd_socket') and self.cmd_socket:
                try:
                    self._send_command("CLOSE")  # Tell ARDOP to shut down
                    time.sleep(0.5)
                    self.cmd_socket.close()
                except:
                    pass

            if hasattr(self, 'data_socket') and self.data_socket:
                try:
                    self.data_socket.close()
                except:
                    pass

            # Stop command reader thread
            self.cmd_thread_running = False

            # Terminate ARDOP process if running
            if self.ardop_process:
                try:
                    self.ardop_process.terminate()
                    self.ardop_process.wait(timeout=2)
                except:
                    # Force kill if it doesn't terminate gracefully
                    if self.ardop_process.poll() is not None:
                        self.ardop_process.kill()

            logger.info("ARDOP process stopped")
            return True

        except Exception as e:
            logger.exception(f"Error stopping ARDOP process: {e}")
            return False

    def _communication_loop(self):
        """Thread for communicating with ARDOP"""
        try:
            while self.comm_thread_running and self.connected:
                if self.ardop_process and self.ardop_process.poll() is not None:
                    # ARDOP process has terminated unexpectedly
                    stdout, stderr = self.ardop_process.communicate()
                    logger.error(f"ARDOP process terminated: {stderr}")
                    self.connected = False
                    self.status['connected'] = False
                    break

                # Process any available stdout/stderr output from ARDOP
                if self.ardop_process:
                    self._process_ardop_output()

                # Sleep to reduce CPU usage
                time.sleep(0.1)
        except Exception as e:
            logger.exception(f"Error in communication loop: {e}")
            self.connected = False
            self.status['connected'] = False

    def _update_status(self):
        """Update modem status from ARDOP"""
        try:
            if not self.ardop_process:
                return

            # Most status updates come from the command socket and _process_ardop_response
            # or from stdout processing in _parse_ardop_stdout

            # Check for buffer usage
            self._send_command("BUFFER")

            # For any metrics not updated through other channels, we can query them here
            if time.time() % 5 < 0.1:  # Query less frequent metrics every 5 seconds
                # Query CPU usage
                self._send_command("PROCESSCPU")

                # Get current state
                self._send_command("STATE")

        except Exception as e:
            logger.exception(f"Error updating status: {e}")

    def _update_modem_settings(self):
        """Send updated settings to ARDOP modem"""
        if not self.connected:
            return True

        # Update bandwidth if needed
        self._send_command(f"ARQBW {self.bandwidth}")

        # Update callsign if needed
        self._send_command(f"MYCALL {self.callsign}")

        # Update grid square if available
        if self.grid_square:
            self._send_command(f"GRIDSQUARE {self.grid_square}")

        # Set drive level based on config
        tx_level = int(self.config.get('modem', 'tx_level', 0.9) * 100)
        self._send_command(f"DRIVELEVEL {tx_level}")

        return True

    def _get_audio_device_args_for_platform(self, input_device, output_device):
        """Get platform-specific audio device arguments for ARDOP

        On Windows, this is typically device indices.
        On Linux, this could be ALSA device names like 'plughw:1,0'.
        """
        if sys.platform == 'win32':
            # On Windows, need to make sure device indices are valid
            # Based on the log, we have 0-4 capture devices and 0-5 playback devices

            # Get the number of available devices from config or set reasonable defaults
            num_input_devices = self.config.get('audio', 'num_input_devices', 5)
            num_output_devices = self.config.get('audio', 'num_output_devices', 6)

            # Validate input device index
            if int(input_device) >= num_input_devices or int(input_device) < 0:
                logger.warning(f"Input device index {input_device} is out of range (0-{num_input_devices-1}). Using device 0 instead.")
                input_device = 0

            # Validate output device index
            if int(output_device) >= num_output_devices or int(output_device) < 0:
                logger.warning(f"Output device index {output_device} is out of range (0-{num_output_devices-1}). Using device 0 instead.")
                output_device = 0

            logger.info(f"Using Windows audio devices: input={input_device}, output={output_device}")
            return [str(input_device), str(output_device)]
        elif sys.platform.startswith('linux'):
            # On Linux, handle ALSA device names
            # Check if the devices are already in ALSA format
            input_dev = str(input_device)
            output_dev = str(output_device)

            # If they're just numbers, they might be device indices - check config
            # to see if we have more specific ALSA device names
            if input_dev.isdigit():
                linux_input = self.config.get('audio', 'linux_input_device', '')
                if linux_input:
                    input_dev = linux_input
                elif self.config.get('audio', 'use_pulse', False):
                    input_dev = 'pulse'
                else:
                    # For numeric indices, convert to ALSA plug format to enable resampling
                    input_dev = f"plughw:{input_dev},0"

            if output_dev.isdigit():
                linux_output = self.config.get('audio', 'linux_output_device', '')
                if linux_output:
                    output_dev = linux_output
                elif self.config.get('audio', 'use_pulse', False):
                    output_dev = 'pulse'
                else:
                    # For numeric indices, convert to ALSA plug format to enable resampling
                    output_dev = f"plughw:{output_dev},0"

            logger.info(f"Using Linux audio devices: input={input_dev}, output={output_dev}")
            return [input_dev, output_dev]
        else:
            # Default to device indices for other platforms
            return [str(input_device), str(output_device)]

    def _process_ardop_output(self):
        """Process stdout and stderr output from the ARDOP process"""
        try:
            # Non-blocking read from stdout
            if self.ardop_process.stdout and self.ardop_process.stdout.readable():
                read_ready = select.select([self.ardop_process.stdout], [], [], 0)[0]
                if read_ready:
                    output = self.ardop_process.stdout.readline().decode('utf-8', errors='ignore').strip()
                    if output:
                        logger.debug(f"ARDOP stdout: {output}")
                        # Process important output messages here if needed
                        self._parse_ardop_stdout(output)

            # Non-blocking read from stderr
            if self.ardop_process.stderr and self.ardop_process.stderr.readable():
                read_ready = select.select([self.ardop_process.stderr], [], [], 0)[0]
                if read_ready:
                    error = self.ardop_process.stderr.readline().decode('utf-8', errors='ignore').strip()
                    if error:
                        logger.error(f"ARDOP stderr: {error}")
                        # You can process error messages here if needed

        except Exception as e:
            logger.exception(f"Error processing ARDOP output: {e}")

    def _parse_ardop_stdout(self, output):
        """Parse and process stdout from ARDOP"""
        # Extract frequency spectrum data if available (format depends on ARDOP implementation)
        if output.startswith("FFT:"):
            try:
                # Assuming ARDOP outputs FFT data in a format like "FFT: val1,val2,val3,..."
                fft_values = output[4:].strip().split(',')
                if fft_values and len(fft_values) > 1:
                    fft_data = np.array([float(val) for val in fft_values if val.strip()])

                    # Add basic validation to prevent extreme values
                    fft_data = np.clip(fft_data, -120, 0)

                    # Ensure we have the right number of data points or resize
                    if len(fft_data) != self.fft_size // 2:
                        fft_data = np.interp(
                            np.linspace(0, 1, self.fft_size // 2),
                            np.linspace(0, 1, len(fft_data)),
                            fft_data
                        )
                    # Store FFT data
                    self.fft_data = fft_data
                    # Keep a history of FFT data for waterfall
                    if len(self.signal_buffer) < 100:  # Limit buffer size
                        self.signal_buffer.append(fft_data.copy())
            except Exception as e:
                logger.exception(f"Error parsing FFT data: {e}")

        # Parse status information from ARDOP stdout
        elif output.startswith("SNR:"):
            try:
                snr_value = float(output[4:].strip())
                self.status['snr'] = snr_value
            except:
                pass

        elif output.startswith("AUDIOLVL:"):
            try:
                level = float(output[9:].strip())
                self.status['audio_level'] = level
            except:
                pass

        elif output.startswith("AFC:"):
            try:
                afc = float(output[4:].strip())
                self.status['afc_offset'] = afc
            except:
                pass

        elif output.startswith("CPU:"):
            try:
                cpu = float(output[4:].strip())
                self.status['cpu_usage'] = cpu
            except:
                pass

    def _init_fft_buffer(self):
        """Initialize FFT data buffer with sensible default values"""
        # Create a realistic noise floor for better visualization
        noise_floor = -120 + np.random.normal(0, 2, self.fft_size // 2)
        self.fft_data = noise_floor.copy()

        # Initialize waterfall buffer with copies of the noise floor
        self.signal_buffer = []
        for _ in range(10):
            self.signal_buffer.append(noise_floor.copy())

        logger.debug(f"FFT buffer initialized with size {self.fft_size // 2}")
        return True

    def list_ardop_audio_devices(self):
        """
        Run the ARDOP binary briefly to get a list of available audio devices.
        Returns a tuple of (input_devices, output_devices) where each is a list of
        device information as reported by ARDOP.

        This method can be called before connect() to ensure the correct audio
        devices are configured.
        """
        logger.info("Getting list of audio devices from ARDOP...")

        # Check if we have a valid ARDOP binary
        if not self.ardop_path or not os.path.exists(self.ardop_path):
            logger.error(f"ARDOP binary not found at {self.ardop_path}")
            return [], []

        input_devices = []
        output_devices = []

        try:
            # Start ARDOP process with just enough arguments to make it list devices
            # We want it to exit quickly, so no specific arguments are needed
            args = [self.ardop_path]

            logger.info(f"Starting ARDOP binary to list devices: {' '.join(args)}")

            ardop_process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Wait briefly for ARDOP to start and print device info
            time.sleep(1)

            # Read all output lines
            stdout_data, stderr_data = ardop_process.communicate(timeout=3)

            # Kill the process if it's still running
            if ardop_process.poll() is None:
                ardop_process.terminate()
                time.sleep(0.5)
                if ardop_process.poll() is None:
                    ardop_process.kill()

            # Process the output to find audio devices
            lines = stdout_data.splitlines() + stderr_data.splitlines()

            # Parse for input and output devices
            in_input_section = False
            in_output_section = False

            for line in lines:
                line = line.strip()                # Check for input devices section
                if "Capture Devices" in line or "Input Devices" in line:
                    in_input_section = True
                    in_output_section = False
                    continue

                # Check for output devices section
                if "Playback Devices" in line or "Output Devices" in line:
                    in_input_section = False
                    in_output_section = True
                    continue

                # Skip empty lines and lines that don't contain device information
                if not line or not line.strip() or len(line.split()) < 2:
                    continue

                # Check if we hit the end of a section
                if line.startswith("-----") or line.startswith("====="):
                    in_input_section = False
                    in_output_section = False
                    continue

                # Process device info line
                if in_input_section and ":" in line:
                    try:
                        idx = line.split(":")[0].strip()
                        if idx.isdigit():
                            device_info = line.split(":", 1)[1].strip()
                            input_devices.append((int(idx), device_info))
                    except Exception as e:
                        logger.debug(f"Error parsing input device line: {line}, {e}")

                if in_output_section and ":" in line:
                    try:
                        idx = line.split(":")[0].strip()
                        if idx.isdigit():
                            device_info = line.split(":", 1)[1].strip()
                            output_devices.append((int(idx), device_info))
                    except Exception as e:
                        logger.debug(f"Error parsing output device line: {line}, {e}")

            logger.info(f"Found {len(input_devices)} input devices and {len(output_devices)} output devices")
            for i, dev in input_devices:
                logger.info(f"Input device {i}: {dev}")
            for i, dev in output_devices:
                logger.info(f"Output device {i}: {dev}")

            # Update the config with the number of available devices
            self.config.set('audio', 'num_input_devices', len(input_devices))
            self.config.set('audio', 'num_output_devices', len(output_devices))
            self.config.save()

            return input_devices, output_devices

        except Exception as e:
            logger.exception(f"Error listing ARDOP audio devices: {e}")
            return [], []

    def configure_from_ardop_devices(self):
        """
        Run ARDOP to get audio device information and configure the app to use
        those devices. This should be called before connecting to ensure proper
        audio input/output.

        Returns:
            tuple: (input_device, output_device) - The selected device indices
        """
        input_devices, output_devices = self.list_ardop_audio_devices()

        if not input_devices or not output_devices:
            logger.warning("No audio devices found from ARDOP")
            return None, None

        # Get currently configured devices
        current_input = self.config.get('audio', 'input_device', 0)
        current_output = self.config.get('audio', 'output_device', 0)

        # Check if the currently configured devices are in range
        valid_input = False
        valid_output = False

        for idx, _ in input_devices:
            if idx == int(current_input):
                valid_input = True
                break

        for idx, _ in output_devices:
            if idx == int(current_output):
                valid_output = True
                break

        # If the configured devices are valid, keep them
        if valid_input and valid_output:
            logger.info(f"Current audio device configuration is valid: input={current_input}, output={current_output}")
            return current_input, current_output

        # Otherwise, select the first available devices
        new_input = input_devices[0][0] if input_devices else 0
        new_output = output_devices[0][0] if output_devices else 0

        logger.info(f"Updating audio device configuration: input={new_input} (was {current_input}), output={new_output} (was {current_output})")

        # Update the configuration
        self.config.set('audio', 'input_device', new_input)
        self.config.set('audio', 'output_device', new_output)
        self.config.save()

        return new_input, new_output