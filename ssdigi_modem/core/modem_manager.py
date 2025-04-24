"""
Modem management for SSDigi Modem
"""
import os
import sys
import subprocess
import logging
import threading
import time
import numpy as np
import json
from pathlib import Path
import wave
import tempfile

logger = logging.getLogger(__name__)

class ModemManager:
    """ARDOP modem management for SSDigi Modem"""
    def __init__(self, config, hamlib_manager=None):
        """Initialize modem manager"""
        self.config = config
        self.hamlib_manager = hamlib_manager
        self.connected = False
        self.ardop_process = None
        self.fft_data = np.zeros(config.get('ui', 'fft_size') // 2)

        # Communication settings
        self.mode = config.get('modem', 'mode')
        self.bandwidth = int(config.get('modem', 'bandwidth'))
        self.center_freq = config.get('modem', 'center_freq')

        # Get callsign from configuration
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
        }

        # For signal processing
        self.sample_rate = config.get('audio', 'sample_rate')
        self.fft_size = config.get('ui', 'fft_size')

        # Initialize communication thread
        self.comm_thread = None
        self.comm_thread_running = False

        # Determine paths to embedded ARDOP binaries
        self.ardop_path = self._get_ardop_binary_path()

        # Signal buffer for recording
        self.signal_buffer = []

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

            return None

    def connect(self):
        """Connect to the modem"""
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
                self._start_simulation()
                return True

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
            logger.info("Modem connected")
            return True

        except Exception as e:
            logger.exception(f"Error connecting to modem: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Disconnect from the modem"""
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
            logger.info("Modem disconnected")
            return True

        except Exception as e:
            logger.exception(f"Error disconnecting modem: {e}")
            return False

    def is_connected(self):
        """Check if modem is connected"""
        return self.connected

    def get_status(self):
        """Get current modem status"""
        return self.status

    def set_bandwidth(self, bandwidth):
        """Set modem bandwidth"""
        logger.debug(f"Setting bandwidth to {bandwidth} Hz")

        # Update configuration
        self.bandwidth = bandwidth
        self.config.set('modem', 'bandwidth', bandwidth)
        self.config.save()

        # Update status
        self.status['bandwidth'] = bandwidth

        # Send command to ARDOP if connected
        if self.connected:
            # TODO: Send command to ARDOP process to change bandwidth
            pass

        return True

    def set_center_freq(self, center_freq):
        """Set center frequency"""
        self.center_freq = center_freq
        self.config.set('modem', 'center_freq', center_freq)
        self.config.save()

        # Send command to ARDOP if connected
        if self.connected:
            # TODO: Send command to ARDOP process to change center frequency
            pass

        return True

    def get_available_bandwidths(self):
        """Get list of available bandwidths - all are available now"""
        # Standard ARDOP bandwidths
        return [200, 500, 1000, 2000]  # All bandwidths available to everyone

    def get_fft_data(self):
        """Get current FFT data for spectrum display"""
        if not self.connected:
            return None

        # In a real implementation, this would come from ARDOP
        # For now, generate simulated data based on settings
        return self._generate_fft_data()

    def _start_ardop_process(self):
        """Start the ARDOP binary as a separate process"""
        try:
            # Get path to the pre-built ARDOP binary
            if not self.ardop_path or not os.path.exists(self.ardop_path):
                logger.error(f"ARDOP binary not found at {self.ardop_path}")
                return False            # Get callsign from configuration
            callsign = self.config.get('user', 'callsign', 'NOCALL')

            # Validate callsign format
            if not (len(callsign) <= 8 and callsign.isalnum()):
                logger.warning(f"Invalid callsign format: {callsign}, using NOCALL")
                callsign = "NOCALL"

            # Store the active callsign
            self.callsign = callsign.upper()

            # Get grid square from config
            grid_square = self.config.get('modem', 'grid_square', '')

            # Prepare command-line arguments for ARDOP
            args = [
                self.ardop_path,
                "-c", self.callsign,      # Callsign
                "-k", grid_square,        # Grid square
                "--hostcommands",         # TCP host interface for commands
                # Using hostcommands to set optimal parameters as shown in the documentation
                f"MYCALL {self.callsign};DRIVELEVEL 90;ARQBW {self.bandwidth}MAX;FECMODE 4FSK.500.100S;LEADER 160;TRAILER 40;PROTOCOLMODE ARQ;BUSYDET 5;CONSOLELOG 6;LOGLEVEL 6;",
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
            self.cmd_socket.connect(("127.0.0.1", 8515))

            # Connect to data socket (default port 8516)
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.connect(("127.0.0.1", 8516))

            # Start thread to read from command socket
            self.cmd_thread_running = True
            self.cmd_thread = threading.Thread(target=self._command_reader_thread)
            self.cmd_thread.daemon = True
            self.cmd_thread.start()

            # Initialize ARDOP via TCP interface
            self._send_command("INITIALIZE")
            time.sleep(0.5)

            # Enable FEC (as per your requirements)
            self._send_command("PROTOCOLMODE ARQ")

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

        # Many other responses could be handled here based on your needs

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

    def _build_ardop(self):
        """Build the ARDOP binary from source code

        This ensures we always have the latest version of ARDOP without
        requiring external dependencies. The binary is built directly
        from the source code included with the application.

        Returns:
            str: Path to the newly built ARDOP binary or None on failure
        """
        try:
            logger.info("Building ARDOP from source...")

            # Get base directory for ARDOP source
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ardop_src_dir = os.path.join(base_dir, "ardop")

            # Create build directory if it doesn't exist
            build_dir = os.path.join(base_dir, "build", "ardop")
            os.makedirs(build_dir, exist_ok=True)

            # Determine platform-specific build commands
            if sys.platform == 'win32':
                # Windows build commands
                build_cmd = ["cmake", "-S", ardop_src_dir, "-B", build_dir]
                build_cmd2 = ["cmake", "--build", build_dir, "--config", "Release"]
                ardop_bin = os.path.join(build_dir, "Release", "ardop.exe")
            else:
                # Linux/Unix build commands
                build_cmd = ["cmake", "-S", ardop_src_dir, "-B", build_dir, "-DCMAKE_BUILD_TYPE=Release"]
                build_cmd2 = ["cmake", "--build", build_dir, "-j4"]  # Use 4 threads for build
                ardop_bin = os.path.join(build_dir, "ardop")

            # Run cmake to configure
            logger.info(f"Configuring ARDOP build: {' '.join(build_cmd)}")
            result = subprocess.run(build_cmd, check=True, capture_output=True, text=True)
            logger.debug(f"CMake configure output: {result.stdout}")

            # Run cmake to build
            logger.info(f"Building ARDOP: {' '.join(build_cmd2)}")
            result = subprocess.run(build_cmd2, check=True, capture_output=True, text=True)
            logger.debug(f"CMake build output: {result.stdout}")

            # Check if build was successful
            if os.path.exists(ardop_bin):
                logger.info(f"ARDOP successfully built at: {ardop_bin}")
                return ardop_bin
            else:
                logger.error(f"Failed to find built ARDOP binary at {ardop_bin}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Build process error: {e}")
            logger.error(f"Command output: {e.stdout}")
            logger.error(f"Command error: {e.stderr}")
            return None
        except Exception as e:
            logger.exception(f"Error building ARDOP: {e}")
            return None

    def update_from_config(self):
        """Update modem settings from the configuration

        This should be called when configuration changes
        """
        # Update bandwidth and center frequency from config
        self.bandwidth = int(self.config.get('modem', 'bandwidth'))
        self.center_freq = self.config.get('modem', 'center_freq')

        # Use callsign from config
        config_callsign = self.config.get('user', 'callsign', '')
        if self.callsign != config_callsign:
            logger.info(f"ModemManager: Updating callsign from config: {config_callsign}")
            self.callsign = config_callsign

        # Update status information
        self.status.update({
            'mode': self.mode,
            'bandwidth': self.bandwidth,
        })

        # If connected, apply changes immediately
        if self.connected:
            logger.info("ModemManager: Applying configuration changes to active connection")
            # Implementation depends on your modem interface
            # This might involve sending commands to update settings

    def apply_config(self):
        """Apply all settings from config"""
        logger.info("Applying configuration changes to modem")

        # Update bandwidth and center frequency from config
        self.bandwidth = int(self.config.get('modem', 'bandwidth'))
        self.center_freq = self.config.get('modem', 'center_freq')
        self.mode = self.config.get('modem', 'mode', 'ARDOP')

        # Update user info
        self.callsign = self.config.get('user', 'callsign', '')
        self.grid_square = self.config.get('user', 'grid_square', '')
        self.fullname = self.config.get('user', 'fullname', '')
        self.email = self.config.get('user', 'email', '')
        self.city = self.config.get('user', 'city', '')

        # Update status information
        self.status.update({
            'mode': self.mode,
            'bandwidth': self.bandwidth,
            'center_freq': self.center_freq
        })

        # If connected, apply changes immediately
        if self.connected:
            logger.info("ModemManager: Applying configuration changes to active connection")
            # Send updated settings to modem
            self._update_modem_settings()

        return True

    def _update_modem_settings(self):
        """Update modem with current settings"""
        # This is called when settings change while the modem is running
        # Implementation depends on the modem interface
        try:
            # Example of sending commands to modem
            if hasattr(self, 'ardop_socket') and self.ardop_socket:
                # For example, send setting commands to ARDOP
                logger.debug(f"Sending settings update to modem: BW={self.bandwidth}, CF={self.center_freq}")
                # self._send_command(f"BANDWIDTH {self.bandwidth}")
                # self._send_command(f"CENTER {self.center_freq}")

            # In simulation mode, just update status
            if self.simulation_mode:
                logger.debug("Simulation mode: Updated settings")

            return True
        except Exception as e:
            logger.exception(f"Error updating modem settings: {e}")
            return False