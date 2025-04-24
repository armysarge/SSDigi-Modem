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
import re
from pathlib import Path

from ssdigi_modem.core.modems.base_modem import BaseModem

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
        self.ptt_baud = config.get('modem', 'ptt_baud', 19200)

        # For CAT PTT
        self.key_string = config.get('modem', 'key_string', '')
        self.unkey_string = config.get('modem', 'unkey_string', '')

        # Simulation mode when ARDOP binary is not available
        self.simulation_mode = False

        # Enhanced status for ARDOP
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
            logger.debug(f"Using bandwidth: {self.bandwidth} Hz")

            # Check if we have a valid ARDOP binary
            if not self.ardop_path or not os.path.exists(self.ardop_path):
                logger.warning(f"ARDOP binary not found, falling back to simulation mode")
                self.simulation_mode = True
                return self._start_simulation()

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

    def get_available_bandwidths(self):
        """Get list of available bandwidths for ARDOP"""
        # Standard ARDOP bandwidths
        return [200, 500, 1000, 2000]

    def get_fft_data(self):
        """Get current FFT data for spectrum display"""
        if not self.connected:
            return None

        # In simulation mode or when data isn't available from ARDOP,
        # generate simulated data based on settings
        if self.simulation_mode:
            return self._generate_fft_data()
        else:
            # In a real implementation, this would come from ARDOP
            # For now, generate simulated data
            return self._generate_fft_data()

    def send_pingack(self):
        """Send PINGACK command to ARDOP - useful for testing and diagnostics

        Returns:
            bool: True if command was sent successfully, False otherwise

        The PINGACK command instructs ARDOP to send a ping acknowledgment,
        which can be useful for testing the connection and functionality.
        Responses will be processed via the command socket's reader thread.
        """
        logger.info("Sending PINGACK command to ARDOP")

        if self.simulation_mode:
            # In simulation mode, simulate a successful PINGACK
            logger.info("Simulation mode: PINGACK command simulation successful")
            # Simulate a PINGACK response after a short delay
            threading.Timer(0.5, lambda:
                self._process_ardop_response("PINGACK: SUCCESS")).start()
            return True

        if not self.connected:
            logger.warning("Cannot send PINGACK: Modem not connected")
            return False

        # Send the command via the command socket
        success = self._send_command("PINGACK")
        if success:
            # Update status to indicate PINGACK was sent
            self.status['last_command'] = "PINGACK"
            self.status['last_command_time'] = time.time()

        return success

    def send_text(self, text):
        """Send text message via ARDOP data socket"""
        if not self.connected:
            logger.warning("Cannot send text: ARDOP modem not connected")
            return False

        try:
            if self.simulation_mode:
                logger.info(f"Simulation mode - Text would be sent: {text}")
                return True

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
        if self.connected and not self.simulation_mode:
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
        # Check if we're running in a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            base_dir = sys._MEIPASS
            logger.info(f"Running from PyInstaller bundle: {base_dir}")

            # In PyInstaller bundle, binaries should be in the 'bin' directory
            if sys.platform == 'win32':
                binary_path = os.path.join(base_dir, "bin", "ardop.exe")
            elif sys.platform.startswith('linux'):
                binary_path = os.path.join(base_dir, "bin", "ardop")
            else:
                logger.error(f"Unsupported platform: {sys.platform}")
                return None
        else:
            # Running in development environment
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

            # Define expected binary locations for development
            if sys.platform == 'win32':
                binary_path = os.path.join(base_dir, "bin", "ardop", "windows", "ardop.exe")
                # Also check if ardop is in the root ardop directory (from building)
                if not os.path.exists(binary_path):
                    alt_path = os.path.join(base_dir, "ardop", "ardopcf.exe")
                    if os.path.exists(alt_path):
                        binary_path = alt_path
            elif sys.platform.startswith('linux'):
                binary_path = os.path.join(base_dir, "bin", "ardop", "linux", "ardop")
                # Also check if ardop is in the root ardop directory (from building)
                if not os.path.exists(binary_path):
                    alt_path = os.path.join(base_dir, "ardop", "ardopcf")
                    if os.path.exists(alt_path):
                        binary_path = alt_path
            else:
                logger.error(f"Unsupported platform: {sys.platform}")
                return None

        # Check if binary exists
        if os.path.exists(binary_path):
            logger.info(f"Found ARDOP binary: {binary_path}")
            return binary_path
        else:
            logger.warning(f"ARDOP binary not found at {binary_path}")

            # Try a last resort search in common locations
            if sys.platform == 'win32':
                for possible_name in ["ardop.exe", "ardopcf.exe"]:
                    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                        # Check in PyInstaller bundle root
                        possible_path = os.path.join(sys._MEIPASS, possible_name)
                        if os.path.exists(possible_path):
                            logger.info(f"Found ARDOP binary in bundle root: {possible_path}")
                            return possible_path

                    # Check in the same directory as the executable
                    possible_path = os.path.join(os.path.dirname(sys.executable), possible_name)
                    if os.path.exists(possible_path):
                        logger.info(f"Found ARDOP binary next to executable: {possible_path}")
                        return possible_path

                    # Check in current working directory
                    possible_path = os.path.join(os.getcwd(), possible_name)
                    if os.path.exists(possible_path):
                        logger.info(f"Found ARDOP binary in current directory: {possible_path}")
                        return possible_path
            elif sys.platform.startswith('linux'):
                # Check common Linux locations
                for location in ["/usr/local/bin", "/usr/bin", os.path.expanduser("~")]:
                    possible_path = os.path.join(location, "ardop")
                    if os.path.exists(possible_path):
                        logger.info(f"Found ARDOP binary at {possible_path}")
                        return possible_path

            return None

    def _start_ardop_process(self):
        """Start the ARDOP binary as a separate process with appropriate parameters"""
        try:
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
            self.cmd_port = cmd_port

            # PTT Method settings
            ptt_args = []
            ptt_method = self.config.get('modem', 'ptt_method', 'VOX').upper()

            if ptt_method == 'RTS':
                # RTS PTT via serial port
                ptt_port = self.config.get('modem', 'ptt_port', '')
                ptt_baud = self.config.get('modem', 'ptt_baud', 19200)
                if ptt_port:
                    ptt_args = ["-p", f"{ptt_port}:{ptt_baud}"]
            elif ptt_method == 'CAT':
                # CAT PTT via serial port with key/unkey strings
                ptt_port = self.config.get('modem', 'ptt_port', '')
                ptt_baud = self.config.get('modem', 'ptt_baud', 19200)
                key_string = self.config.get('modem', 'key_string', '')
                unkey_string = self.config.get('modem', 'unkey_string', '')

                if ptt_port and key_string and unkey_string:
                    ptt_args = [
                        "-c", f"{ptt_port}:{ptt_baud}",
                        "--keystring", key_string,
                        "--unkeystring", unkey_string
                    ]

            # WebGUI settings
            webgui_args = []
            webgui_enabled = self.config.get('modem', 'webgui_enabled', False)
            if webgui_enabled:
                webgui_port = self.config.get('modem', 'webgui_port', 8514)
                webgui_args = ["-G", str(webgui_port)]
                self.webgui_port = webgui_port

            # Log directory settings
            logdir_args = []
            logdir = self.config.get('modem', 'logdir', '')
            if logdir:
                logdir_args = ["--logdir", logdir]

            # Host commands (semicolon-separated commands to execute at startup)
            hostcmd_args = []
            hostcmds = self.config.get('modem', 'hostcommands', '')
            if hostcmds:
                hostcmd_args = ["--hostcommands", hostcmds]

            # Build full command line
            args = [self.ardop_path] + ptt_args + webgui_args + logdir_args + hostcmd_args + [
                str(cmd_port),     # Command port (usually 8515)
                str(input_device), # Audio input device
                str(output_device) # Audio output device
            ]

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
            # Connect to command socket (default port 8515)
            self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.cmd_socket.connect(("127.0.0.1", self.cmd_port))

            # Connect to data socket (default port 8516)
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.connect(("127.0.0.1", self.data_port))

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
            self._send_command(f"ARQBW {self.bandwidth}")

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
                    if self.ardop_process.poll() is None:
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

                # Read ARDOP output and update status
                self._update_status()

                # Generate FFT data (in a real implementation, this would come from ARDOP)
                self.fft_data = self._generate_fft_data()

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

            # In a real implementation, this would parse status from ARDOP
            # For simulation, update with simulated values

            # Simulate varying SNR
            self.status['snr'] = 12 + np.sin(time.time() * 0.2) * 3

            # Simulate varying signal level
            self.status['signal_level'] = -90 + np.sin(time.time() * 0.1) * 10

        except Exception as e:
            logger.exception(f"Error updating status: {e}")

    def _generate_fft_data(self):
        """Generate simulated FFT data"""
        # Create base noise floor
        data = -120 + np.random.normal(0, 3, self.fft_size // 2)

        # Add a signal peak near center frequency
        center_bin = int(self.center_freq * self.fft_size / self.sample_rate)
        width = int(self.bandwidth * self.fft_size / self.sample_rate / 4)

        x = np.arange(self.fft_size // 2)
        signal = 40 * np.exp(-((x - center_bin) ** 2) / (2 * width ** 2))

        # Add some modulation to the signal
        # These two lines create the pulsating effect - can be reduced or removed if desired
        mod = 5 * np.sin(time.time() * 10)
        signal = signal + signal * np.sin(x / 10 + time.time() * 5) * 0.1

        # Combine noise and signal
        data += signal + mod

        # Add to signal buffer for recording
        if len(self.signal_buffer) < 100:  # Limit buffer size
            self.signal_buffer.append(data.copy())

        return data

    def _start_simulation(self):
        """Start simulation mode when ARDOP binary is not available"""
        logger.info("Starting modem simulation mode")

        # Start communication thread for simulation
        self.comm_thread_running = True
        self.comm_thread = threading.Thread(target=self._simulation_loop)
        self.comm_thread.daemon = True
        self.comm_thread.start()

        self.connected = True
        self.status['connected'] = True
        logger.info("Modem simulation active")
        return True

    def _simulation_loop(self):
        """Thread for simulating modem activity"""
        try:
            while self.comm_thread_running and self.connected:
                # Update simulated status
                self.status['snr'] = 12 + np.sin(time.time() * 0.2) * 3
                self.status['signal_level'] = -90 + np.sin(time.time() * 0.1) * 10

                # Generate simulated FFT data
                self.fft_data = self._generate_fft_data()

                # Sleep to reduce CPU usage
                time.sleep(0.1)
        except Exception as e:
            logger.exception(f"Error in simulation loop: {e}")
            self.connected = False
            self.status['connected'] = False

    def _update_modem_settings(self):
        """Send updated settings to ARDOP modem"""
        if not self.connected or self.simulation_mode:
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
