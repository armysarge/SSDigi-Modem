"""
Settings dialog for SSDigi Modem
"""
import logging
import os
from PyQt5.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QComboBox, QCheckBox,
                            QSpinBox, QDoubleSpinBox, QLineEdit, QGroupBox,
                            QFormLayout, QFileDialog, QDialogButtonBox,
                            QMessageBox, QSlider, QWidget)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QIcon
from ssdigi_modem.utils.ui_helpers import get_app_icon
from ssdigi_modem.core.audio_manager import AudioManager
import serial.tools.list_ports

logger = logging.getLogger(__name__)
from ssdigi_modem.core.audio_manager import AudioManager

class SettingsDialog(QDialog):
    """Settings dialog for SSDigi Modem application"""

    def __init__(self, config, parent=None):
        """Initialize settings dialog"""
        super().__init__(parent)

        self.config = config        # Create UI
        self.setWindowTitle("SSDigi Modem Settings")
        self.setMinimumSize(700, 500)  # Set minimum size instead of fixed

        # Prevent window resizing
        self.setWindowFlags(self.windowFlags() | Qt.MSWindowsFixedSizeDialogHint)

        # Set application icon
        try:
            icon_path = get_app_icon()
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}")

        # Create layout
        main_layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)        # Create settings tabs
        self._create_audio_tab()
        self._create_modem_tab()
        self._create_station_tab()
        self._create_hamlib_tab()
        self._create_ui_tab()
        self._create_ardop_advanced_tab()

        # Create dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply_settings)
        main_layout.addWidget(button_box)

        # Load current settings
        self._load_settings()

    def _create_audio_tab(self):
        """Create audio settings tab"""
        audio_tab = QWidget()
        layout = QVBoxLayout(audio_tab)

        # Audio device selection
        device_group = QGroupBox("Audio Devices")
        device_layout = QFormLayout()

        # Input device
        self.input_combo = QComboBox()
        device_layout.addRow("Input Device:", self.input_combo)

        # Output device
        self.output_combo = QComboBox()
        device_layout.addRow("Output Device:", self.output_combo)

        # Audio parameters
        self.sample_rate_combo = QComboBox()
        for rate in [8000, 11025, 22050, 44100, 48000]:
            self.sample_rate_combo.addItem(f"{rate} Hz", rate)
        device_layout.addRow("Sample Rate:", self.sample_rate_combo)

        self.channels_combo = QComboBox()
        self.channels_combo.addItem("Mono (1)", 1)
        self.channels_combo.addItem("Stereo (2)", 2)
        device_layout.addRow("Channels:", self.channels_combo)

        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(256, 4096)
        self.buffer_spin.setSingleStep(256)
        device_layout.addRow("Buffer Size:", self.buffer_spin)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # Audio levels
        levels_group = QGroupBox("Audio Levels")
        levels_layout = QFormLayout()

        self.tx_level_slider = QSlider(Qt.Horizontal)
        self.tx_level_slider.setRange(0, 100)
        self.tx_level_slider.setTickPosition(QSlider.TicksBelow)
        self.tx_level_slider.setTickInterval(10)
        self.tx_level_label = QLabel("50%")

        tx_level_layout = QHBoxLayout()
        tx_level_layout.addWidget(self.tx_level_slider)
        tx_level_layout.addWidget(self.tx_level_label)

        levels_layout.addRow("TX Level:", tx_level_layout)

        # Connect slider to label update
        self.tx_level_slider.valueChanged.connect(
            lambda v: self.tx_level_label.setText(f"{v}%"))

        levels_group.setLayout(levels_layout)
        layout.addWidget(levels_group)

        # Refresh button
        refresh_button = QPushButton("Refresh Audio Devices")
        refresh_button.clicked.connect(self._refresh_audio_devices)
        layout.addWidget(refresh_button)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(audio_tab, "Audio")

    def _create_modem_tab(self):
        """Create modem settings tab"""
        modem_tab = QWidget()
        layout = QVBoxLayout(modem_tab)

        # Communication settings
        comm_group = QGroupBox("Communication Settings")
        comm_layout = QFormLayout()

        # Mode selection
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("ARDOP", "ARDOP")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        comm_layout.addRow("Mode:", self.mode_combo)

        # Bandwidth selection
        self.bandwidth_combo = QComboBox()
        for bw in [200, 500, 1000, 2000]:
            self.bandwidth_combo.addItem(f"{bw} Hz", bw)
        comm_layout.addRow("Bandwidth:", self.bandwidth_combo)

        # Center frequency
        self.center_freq_spin = QSpinBox()
        self.center_freq_spin.setRange(500, 3000)
        self.center_freq_spin.setSingleStep(10)
        self.center_freq_spin.setSuffix(" Hz")
        comm_layout.addRow("Center Frequency:", self.center_freq_spin)

        comm_group.setLayout(comm_layout)
        layout.addWidget(comm_group)        # ARDOP specific settings
        self.ardop_group = QGroupBox("ARDOP Settings")
        ardop_layout = QFormLayout()

        # Internal/External ARDOP mode
        self.run_ardop_mode_combo = QComboBox()
        self.run_ardop_mode_combo.addItem("Run ARDOP Internally", "internal")
        self.run_ardop_mode_combo.addItem("Use External ARDOP", "external")
        self.run_ardop_mode_combo.currentIndexChanged.connect(self._on_ardop_mode_changed)
        ardop_layout.addRow("ARDOP Mode:", self.run_ardop_mode_combo)

        # Network settings group        self.network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout()

        # IP Address
        self.ardop_ip_edit = QLineEdit()
        self.ardop_ip_edit.setPlaceholderText("127.0.0.1")
        self.ardop_ip_edit.setToolTip("IP address of external ARDOP modem")
        network_layout.addRow("ARDOP IP:", self.ardop_ip_edit)

        # Port
        self.ardop_port_spin = QSpinBox()
        self.ardop_port_spin.setRange(1, 65535)
        self.ardop_port_spin.setValue(8515)  # Default ARDOP port
        self.ardop_port_spin.setToolTip("Port number of external ARDOP modem")
        network_layout.addRow("ARDOP Port:", self.ardop_port_spin)

        self.network_group.setLayout(network_layout)
        ardop_layout.addWidget(self.network_group)

        # Protocol Mode (ARQ, FEC, RXO)
        self.protocol_mode_combo = QComboBox()
        self.protocol_mode_combo.addItem("ARQ Mode", "ARQ")
        self.protocol_mode_combo.addItem("FEC Mode", "FEC")
        self.protocol_mode_combo.addItem("Receive Only", "RXO")
        self.protocol_mode_combo.setToolTip("ARQ: Automatic Repeat Request - Connection mode\n"
                                          "FEC: Forward Error Correction - Broadcast mode\n"
                                          "RXO: Receive Only - No transmit")
        ardop_layout.addRow("Protocol Mode:", self.protocol_mode_combo)

        # ARQ timeout
        self.arq_timeout_spin = QSpinBox()
        self.arq_timeout_spin.setRange(30, 240)
        self.arq_timeout_spin.setSingleStep(10)
        self.arq_timeout_spin.setSuffix(" sec")
        self.arq_timeout_spin.setToolTip("Time before ARQ connection times out if idle")
        ardop_layout.addRow("ARQ Timeout:", self.arq_timeout_spin)

        # FEC repeat settings
        self.fec_repeats_spin = QSpinBox()
        self.fec_repeats_spin.setRange(0, 5)
        self.fec_repeats_spin.setToolTip("Number of times to repeat FEC transmissions (0-5)")
        ardop_layout.addRow("FEC Repeats:", self.fec_repeats_spin)

        # Leader length
        self.leader_spin = QSpinBox()
        self.leader_spin.setRange(120, 2500)
        self.leader_spin.setSingleStep(10)
        self.leader_spin.setSuffix(" ms")
        self.leader_spin.setToolTip("Sync leader length in milliseconds (120-2500)")
        ardop_layout.addRow("Leader Length:", self.leader_spin)

        # Trailer length
        self.trailer_spin = QSpinBox()
        self.trailer_spin.setRange(0, 200)
        self.trailer_spin.setSingleStep(5)
        self.trailer_spin.setSuffix(" ms")
        self.trailer_spin.setToolTip("Trailer tone length in milliseconds (0-200)")
        ardop_layout.addRow("Trailer Length:", self.trailer_spin)

        # Squelch level
        self.squelch_spin = QSpinBox()
        self.squelch_spin.setRange(1, 10)
        self.squelch_spin.setToolTip("Squelch level (1-10), lower is more sensitive")
        ardop_layout.addRow("Squelch:", self.squelch_spin)

        # Busy detection
        self.busydet_spin = QSpinBox()
        self.busydet_spin.setRange(0, 9)
        self.busydet_spin.setToolTip("Busy detection sensitivity (0=most sensitive, 9=least sensitive)")
        ardop_layout.addRow("Busy Detection:", self.busydet_spin)

        # Extra delay
        self.extradelay_spin = QSpinBox()
        self.extradelay_spin.setRange(0, 1000)
        self.extradelay_spin.setSingleStep(10)
        self.extradelay_spin.setSuffix(" ms")
        self.extradelay_spin.setToolTip("Extra delay between RX and TX")
        ardop_layout.addRow("Extra Delay:", self.extradelay_spin)

        # Console log verbosity
        self.consolelog_spin = QSpinBox()
        self.consolelog_spin.setRange(1, 6)
        self.consolelog_spin.setToolTip("Console log verbosity (1-6, 1=most verbose)")
        ardop_layout.addRow("Console Log Level:", self.consolelog_spin)

        # Advanced options
        self.cwid_check = QCheckBox()
        self.cwid_check.setToolTip("Send CW ID after IDFRAME")
        ardop_layout.addRow("CW ID:", self.cwid_check)

        self.fsk_only_check = QCheckBox()
        self.fsk_only_check.setToolTip("Use only FSK modes (no PSK or QAM)")
        ardop_layout.addRow("FSK Only:", self.fsk_only_check)

        self.use600_check = QCheckBox()
        self.use600_check.setToolTip("Enable 600 baud modes for FM/2m")
        ardop_layout.addRow("Use 600 Baud:", self.use600_check)

        self.faststart_check = QCheckBox()
        self.faststart_check.setToolTip("Start ARQ with faster speed frames")
        ardop_layout.addRow("Fast Start:", self.faststart_check)

        # Custom commands
        self.custom_commands = QLineEdit()
        self.custom_commands.setToolTip("Additional semicolon-separated ARDOP commands")
        ardop_layout.addRow("Custom Commands:", self.custom_commands)

        # Add Reset to Defaults button
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_modem_settings)
        ardop_layout.addRow("", reset_button)

        self.ardop_group.setLayout(ardop_layout)
        layout.addWidget(self.ardop_group)        # Placeholder - removed spectrum settings (moved to Display tab)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(modem_tab, "Modem")

    def _create_station_tab(self):
        """Create station settings tab"""
        station_tab = QWidget()
        layout = QVBoxLayout(station_tab)
        # ARDOP advanced settings
        advanced_group = QGroupBox("Station Details")
        advanced_layout = QFormLayout()
        self.callsign_edit = QLineEdit()
        self.callsign_edit.setMaxLength(10)
        # Check if licensed callsign is present - if so, disable editing
        self.callsign_edit.setText(self.config.get('user', 'callsign', '').upper())
        self.callsign_edit.setToolTip("Callsign is locked by your license")
        advanced_layout.addRow("Callsign:", self.callsign_edit)

        self.fullname_edit = QLineEdit()
        self.fullname_edit.setMaxLength(50)
        self.fullname_edit.setText(self.config.get('user', 'fullname', ''))
        self.fullname_edit.setToolTip("Your full name")
        advanced_layout.addRow("Full Name:", self.fullname_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setMaxLength(100)
        self.email_edit.setText(self.config.get('user', 'email', ''))
        self.email_edit.setToolTip("Your email address")
        advanced_layout.addRow("Email:", self.email_edit)

        self.city_edit = QLineEdit()
        self.city_edit.setMaxLength(50)
        self.city_edit.setText(self.config.get('user', 'city', ''))
        self.city_edit.setToolTip("Your city or location")
        advanced_layout.addRow("City:", self.city_edit)

        self.grid_square_edit = QLineEdit()
        self.grid_square_edit.setMaxLength(6)
        self.grid_square_edit.setText(self.config.get('user', 'grid_square', ''))
        self.grid_square_edit.setToolTip("Grid square is the location of your station")
        advanced_layout.addRow("Grid Square:", self.grid_square_edit)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(station_tab, "Station")

    def _create_hamlib_tab(self):
        """Create HAMLIB settings tab"""
        hamlib_tab = QWidget()
        layout = QVBoxLayout(hamlib_tab)

        # Enable HAMLIB
        self.hamlib_enabled_check = QCheckBox("Enable HAMLIB Rig Control")
        layout.addWidget(self.hamlib_enabled_check)

        # HAMLIB settings
        hamlib_group = QGroupBox("HAMLIB Settings")
        hamlib_layout = QFormLayout()

        self.rig_model_combo = QComboBox()
        hamlib_layout.addRow("Rig Model:", self.rig_model_combo)

        self.port_edit = QLineEdit()
        hamlib_layout.addRow("Serial Port:", self.port_edit)

        self.baud_combo = QComboBox()
        for baud in [4800, 9600, 19200, 38400, 57600, 115200]:
            self.baud_combo.addItem(f"{baud}", baud)
        hamlib_layout.addRow("Baud Rate:", self.baud_combo)

        self.ptt_combo = QComboBox()
        self.ptt_combo.addItem("VOX", "VOX")
        self.ptt_combo.addItem("RTS", "RTS")
        self.ptt_combo.addItem("DTR", "DTR")
        self.ptt_combo.addItem("CAT", "CAT")
        hamlib_layout.addRow("PTT Control:", self.ptt_combo)

        hamlib_group.setLayout(hamlib_layout)
        layout.addWidget(hamlib_group)

        # PTT test
        ptt_group = QGroupBox("PTT Test")
        ptt_layout = QHBoxLayout()

        self.ptt_on_button = QPushButton("PTT ON")
        self.ptt_off_button = QPushButton("PTT OFF")

        self.ptt_on_button.clicked.connect(self._ptt_on)
        self.ptt_off_button.clicked.connect(self._ptt_off)

        ptt_layout.addWidget(self.ptt_on_button)
        ptt_layout.addWidget(self.ptt_off_button)

        ptt_group.setLayout(ptt_layout)
        layout.addWidget(ptt_group)

        # Port scan
        scan_button = QPushButton("Scan for Serial Ports")
        scan_button.clicked.connect(self._scan_serial_ports)
        layout.addWidget(scan_button)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(hamlib_tab, "HAMLIB")

    def _create_ui_tab(self):
        """Create UI settings tab"""
        ui_tab = QWidget()
        layout = QVBoxLayout(ui_tab)

        # UI settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Default", "default")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Minimal", "minimal")
        ui_layout.addRow("Theme:", self.theme_combo)

        self.waterfall_combo = QComboBox()
        self.waterfall_combo.addItem("Default", "default")
        self.waterfall_combo.addItem("Viridis", "viridis")
        self.waterfall_combo.addItem("Hot", "hot")
        self.waterfall_combo.addItem("Blue", "blue")
        ui_layout.addRow("Waterfall Colors:", self.waterfall_combo)

        # FFT size is now fixed - display as a label
        self.fft_size_label = QLabel("2048 points (Fixed for optimal performance)")
        ui_layout.addRow("FFT Size:", self.fft_size_label)

        self.update_rate_spin = QSpinBox()
        self.update_rate_spin.setRange(1, 30)
        self.update_rate_spin.setSuffix(" Hz")
        ui_layout.addRow("Spectrum Update Rate:", self.update_rate_spin)

        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)        # Display settings
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout()

        self.show_freq_check = QCheckBox()
        display_layout.addRow("Show Frequency Markers:", self.show_freq_check)

        self.show_grid_check = QCheckBox()
        display_layout.addRow("Show Grid:", self.show_grid_check)

        self.average_check = QCheckBox()
        display_layout.addRow("Average FFT:", self.average_check)

        self.peak_hold_check = QCheckBox()
        display_layout.addRow("Peak Hold:", self.peak_hold_check)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Spectrum and waterfall settings (moved from Modem tab)
        spectrum_group = QGroupBox("Spectrum Display")
        spectrum_layout = QFormLayout()

        # FFT averaging settings
        self.fft_avg_spin = QSpinBox()
        self.fft_avg_spin.setRange(1, 10)
        self.fft_avg_spin.setSingleStep(1)
        self.fft_avg_spin.setToolTip("Number of FFT frames to average (higher values give smoother spectrum)")
        spectrum_layout.addRow("FFT Averaging:", self.fft_avg_spin)

        # Spectrum scaling
        self.spectrum_ref_spin = QSpinBox()
        self.spectrum_ref_spin.setRange(-120, 0)
        self.spectrum_ref_spin.setSingleStep(5)
        self.spectrum_ref_spin.setSuffix(" dB")
        self.spectrum_ref_spin.setToolTip("Reference level for spectrum display")
        spectrum_layout.addRow("Reference Level:", self.spectrum_ref_spin)

        # Spectrum range
        self.spectrum_range_spin = QSpinBox()
        self.spectrum_range_spin.setRange(30, 120)
        self.spectrum_range_spin.setSingleStep(5)
        self.spectrum_range_spin.setSuffix(" dB")
        self.spectrum_range_spin.setToolTip("Range of spectrum display")
        spectrum_layout.addRow("Display Range:", self.spectrum_range_spin)

        # Waterfall settings
        self.waterfall_speed_combo = QComboBox()
        self.waterfall_speed_combo.addItem("Slow", "slow")
        self.waterfall_speed_combo.addItem("Medium", "medium")
        self.waterfall_speed_combo.addItem("Fast", "fast")
        spectrum_layout.addRow("Waterfall Speed:", self.waterfall_speed_combo)

        spectrum_group.setLayout(spectrum_layout)
        layout.addWidget(spectrum_group)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(ui_tab, "Display") 
    
    def _create_ardop_advanced_tab(self):
        """Create advanced ARDOP settings tab"""
        ardop_tab = QWidget()
        layout = QVBoxLayout(ardop_tab)

        # Add tab to widget
        self.tab_widget.addTab(ardop_tab, "ARDOP Advanced")

        # ARQ Settings Group
        arq_group = QGroupBox("ARQ Settings")
        arq_layout = QFormLayout()

        # ARQ Bandwidth Enforcement Mode
        self.arq_bw_combo = QComboBox()
        self.arq_bw_combo.addItem("Max - Try to negotiate up to max", "MAX")
        self.arq_bw_combo.addItem("Force - Only use exact bandwidth", "FORCE")
        self.arq_bw_combo.setToolTip("ARQBW enforcement mode:\nMAX - Try to negotiate up to specified bandwidth\nFORCE - Only use exactly the specified bandwidth")
        arq_layout.addRow("ARQBW Mode:", self.arq_bw_combo)

        # Call Bandwidth (CALLBW)
        self.callbw_combo = QComboBox()
        self.callbw_combo.addItem("Use ARQBW Setting", "UNDEFINED")
        self.callbw_combo.addItem("200Hz Max", "200MAX")
        self.callbw_combo.addItem("200Hz Force", "200FORCE")
        self.callbw_combo.addItem("500Hz Max", "500MAX")
        self.callbw_combo.addItem("500Hz Force", "500FORCE")
        self.callbw_combo.addItem("1000Hz Max", "1000MAX")
        self.callbw_combo.addItem("1000Hz Force", "1000FORCE")
        self.callbw_combo.addItem("2000Hz Max", "2000MAX")
        self.callbw_combo.addItem("2000Hz Force", "2000FORCE")
        self.callbw_combo.setToolTip("Bandwidth used for ARQCALL, overrides ARQBW unless set to UNDEFINED")
        arq_layout.addRow("Call Bandwidth:", self.callbw_combo)

        # Auto Break
        self.autobreak_check = QCheckBox()
        self.autobreak_check.setToolTip("Automatically handle ARQ flow control (recommended)")
        arq_layout.addRow("Auto Break:", self.autobreak_check)

        # Busy Block
        self.busyblock_check = QCheckBox()
        self.busyblock_check.setToolTip("Reject incoming connections when channel is busy")
        arq_layout.addRow("Busy Block:", self.busyblock_check)

        arq_group.setLayout(arq_layout)
        layout.addWidget(arq_group)

        # FEC Settings Group
        fec_group = QGroupBox("FEC Settings")
        fec_layout = QFormLayout()

        # FEC Mode for transmission
        self.fec_mode_combo = QComboBox()
        # Add FEC modes from the documentation
        fec_modes = [
            "4FSK.200.50S", "4PSK.200.100S", "4PSK.200.100", "8PSK.200.100", "16QAM.200.100",
            "4FSK.500.100S", "4FSK.500.100", "4PSK.500.100", "8PSK.500.100", "16QAM.500.100",
            "4PSK.1000.100", "8PSK.1000.100", "16QAM.1000.100",
            "4PSK.2000.100", "8PSK.2000.100", "16QAM.2000.100",
            "4FSK.2000.600", "4FSK.2000.600S"
        ]
        for mode in fec_modes:
            self.fec_mode_combo.addItem(mode, mode)
        self.fec_mode_combo.setToolTip("FEC frame type for data transmission")
        fec_layout.addRow("FEC Mode:", self.fec_mode_combo)

        # FEC ID
        self.fec_id_check = QCheckBox()
        self.fec_id_check.setToolTip("Automatically transmit ID frame with every FEC transmission")
        fec_layout.addRow("Send FEC ID:", self.fec_id_check)

        fec_group.setLayout(fec_layout)
        layout.addWidget(fec_group)

        # Tuning Settings Group
        tuning_group = QGroupBox("Tuning Settings")
        tuning_layout = QFormLayout()

        # Tuning Range
        self.tuning_range_spin = QSpinBox()
        self.tuning_range_spin.setRange(0, 200)
        self.tuning_range_spin.setSingleStep(10)
        self.tuning_range_spin.setSuffix(" Hz")
        self.tuning_range_spin.setToolTip("How many Hz from center frequency an incoming signal can be decoded")
        tuning_layout.addRow("Tuning Range:", self.tuning_range_spin)

        # Input Noise (for testing)
        self.input_noise_spin = QSpinBox()
        self.input_noise_spin.setRange(0, 20000)
        self.input_noise_spin.setSingleStep(1000)
        self.input_noise_spin.setToolTip("Add simulated Gaussian noise to input (diagnostic use only)")
        tuning_layout.addRow("Input Noise:", self.input_noise_spin)

        tuning_group.setLayout(tuning_layout)
        layout.addWidget(tuning_group)

        # Debug Settings Group
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QFormLayout()

        # Debug Log
        self.debug_log_check = QCheckBox()
        self.debug_log_check.setToolTip("Write debug log to disk")
        debug_layout.addRow("Debug Log:", self.debug_log_check)

        # Log Directory
        self.log_dir_edit = QLineEdit()
        self.log_dir_edit.setToolTip("Directory to write log files")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_log_dir)

        log_dir_layout = QHBoxLayout()
        log_dir_layout.addWidget(self.log_dir_edit)
        log_dir_layout.addWidget(browse_button)

        debug_layout.addRow("Log Directory:", log_dir_layout)

        # Log Level
        self.log_level_spin = QSpinBox()
        self.log_level_spin.setRange(1, 6)
        self.log_level_spin.setToolTip("Log level (1-6, 1=most verbose)")
        debug_layout.addRow("Log Level:", self.log_level_spin)

        # Command Trace
        self.cmd_trace_check = QCheckBox()
        self.cmd_trace_check.setToolTip("Record commands in log file")
        debug_layout.addRow("Command Trace:", self.cmd_trace_check)

        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(ardop_tab, "ARDOP Advanced")    
    
    def _on_ardop_mode_changed(self, *args):
        """Handle ARDOP mode change"""
        # Enable/disable network settings based on mode
        is_external = self.run_ardop_mode_combo.currentData() == "external"
        if hasattr(self, 'network_group'):
            self.network_group.setEnabled(is_external)

    def _browse_log_dir(self):
        """Browse for log directory"""
        log_dir = QFileDialog.getExistingDirectory(self, "Select Log Directory",
                                                  self.log_dir_edit.text())
        if log_dir:
            self.log_dir_edit.setText(log_dir)

    def _refresh_audio_devices(self):
        """Refresh available audio devices"""
        try:
            # Store current selections
            current_input = self.input_combo.currentData()
            current_output = self.output_combo.currentData()

            # Clear existing items
            self.input_combo.clear()
            self.output_combo.clear()

            # Create temporary AudioManager
            audio_mgr = AudioManager(self.config)

            try:
                # Add "System Default" option with special index
                self.input_combo.addItem("System Default", -1)
                self.output_combo.addItem("System Default", -1)

                # Track added device names to prevent duplicates
                added_input_names = set()
                added_output_names = set()

                # Filter and add physical input devices
                input_devices = audio_mgr.get_input_devices()
                # Sort devices by name for consistent order
                input_devices.sort(key=lambda x: x[0])

                for name, idx in input_devices:
                    # Skip devices with duplicate names or virtual devices
                    if name in added_input_names or "Virtual" in name:
                        continue
                    # Add the device
                    self.input_combo.addItem(name, idx)
                    added_input_names.add(name)

                # Filter and add physical output devices
                output_devices = audio_mgr.get_output_devices()
                # Sort devices by name for consistent order
                output_devices.sort(key=lambda x: x[0])

                for name, idx in output_devices:
                    # Skip devices with duplicate names or virtual devices
                    if name in added_output_names or "Virtual" in name:
                        continue
                    # Add the device
                    self.output_combo.addItem(name, idx)
                    added_output_names.add(name)

                # Try to restore previous selection, fall back to config, then to default
                input_idx = self.input_combo.findData(current_input)
                if input_idx < 0:
                    input_idx = self.input_combo.findData(self.config.get('audio', 'input_device'))
                if input_idx < 0:
                    input_idx = 0
                self.input_combo.setCurrentIndex(input_idx)

                output_idx = self.output_combo.findData(current_output)
                if output_idx < 0:
                    output_idx = self.output_combo.findData(self.config.get('audio', 'output_device'))
                if output_idx < 0:
                    output_idx = 0
                self.output_combo.setCurrentIndex(output_idx)

            finally:
                # Always clean up the audio manager
                audio_mgr.close()

            logger.info("Audio devices refreshed successfully")

        except Exception as e:
            logger.exception("Error refreshing audio devices")
            QMessageBox.warning(self, "Error",
                              f"Failed to refresh audio devices: {str(e)}")

    def _scan_serial_ports(self):
        """Scan for available serial ports"""
        try:
            # Get list of ports
            ports = list(serial.tools.list_ports.comports())

            # Clear current port
            current_port = self.port_edit.text()
            self.port_edit.clear()

            if ports:
                # Set text to first port
                self.port_edit.setText(ports[0].device)

                # Show list of ports
                port_text = "Available ports:\n\n"
                for port in ports:
                    port_text += f"{port.device} - {port.description}\n"

                QMessageBox.information(self, "Serial Ports", port_text)
            else:
                QMessageBox.warning(self, "Serial Ports", "No serial ports found.")
                # Restore previous value
                self.port_edit.setText(current_port)

        except Exception as e:
            logger.exception(f"Error scanning serial ports: {e}")
            QMessageBox.warning(self, "Error",
                              f"Failed to scan serial ports: {str(e)}")

    def _load_settings(self):
        """Load current settings into dialog"""
        try:
            # Load audio settings
            self.sample_rate_combo.setCurrentText(f"{self.config.get('audio', 'sample_rate')} Hz")
            self.channels_combo.setCurrentIndex(self.config.get('audio', 'channels') - 1)
            self.buffer_spin.setValue(self.config.get('audio', 'buffer_size'))
            tx_level = int(self.config.get('modem', 'tx_level') * 100)
            self.tx_level_slider.setValue(tx_level)

            # Load modem settings
            # Set mode
            mode_index = self.mode_combo.findData(self.config.get('modem', 'mode'))
            self.mode_combo.setCurrentIndex(max(0, mode_index))

            # Set bandwidth
            bw_index = self.bandwidth_combo.findData(self.config.get('modem', 'bandwidth'))
            self.bandwidth_combo.setCurrentIndex(max(0, bw_index))

            # Set center frequency
            self.center_freq_spin.setValue(self.config.get('modem', 'center_freq'))

            # Load ARDOP specific settings
            protocol_mode = self.config.get('modem', 'protocol_mode', 'ARQ')
            protocol_index = self.protocol_mode_combo.findData(protocol_mode)
            self.protocol_mode_combo.setCurrentIndex(max(0, protocol_index))

            self.arq_timeout_spin.setValue(self.config.get('modem', 'arq_timeout', 120))
            self.fec_repeats_spin.setValue(self.config.get('modem', 'fec_repeats', 0))
            self.leader_spin.setValue(self.config.get('modem', 'leader', 120))
            self.trailer_spin.setValue(self.config.get('modem', 'trailer', 0))
            self.squelch_spin.setValue(self.config.get('modem', 'squelch', 5))
            self.busydet_spin.setValue(self.config.get('modem', 'busydet', 5))
            self.extradelay_spin.setValue(self.config.get('modem', 'extradelay', 0))
            self.consolelog_spin.setValue(self.config.get('modem', 'consolelog', 6))
            self.cwid_check.setChecked(self.config.get('modem', 'cwid', False))
            self.fsk_only_check.setChecked(self.config.get('modem', 'fskonly', False))
            self.use600_check.setChecked(self.config.get('modem', 'use600modes', False))
            self.faststart_check.setChecked(self.config.get('modem', 'faststart', True))
            self.custom_commands.setText(self.config.get('modem', 'custom_commands', ''))

            # Set spectrum settings
            self.fft_avg_spin.setValue(self.config.get('ui', 'fft_average_frames', 2))
            self.spectrum_ref_spin.setValue(self.config.get('ui', 'spectrum_ref_level', -60))
            self.spectrum_range_spin.setValue(self.config.get('ui', 'spectrum_range', 70))

            # Set waterfall settings
            waterfall_speed = self.config.get('ui', 'waterfall_speed', 'medium')
            waterfall_speed_index = self.waterfall_speed_combo.findData(waterfall_speed)
            self.waterfall_speed_combo.setCurrentIndex(max(0, waterfall_speed_index))

            # Load HAMLIB settings
            self.hamlib_enabled_check.setChecked(self.config.get('hamlib', 'enabled'))

            # Populate rig models
            hamlib_manager = self.parent().hamlib_manager if self.parent() else None
            if hamlib_manager:
                rig_models = hamlib_manager.get_available_rig_models()
                self.rig_model_combo.clear()
                for model_id, name in rig_models:
                    self.rig_model_combo.addItem(name, model_id)

                # Set current model
                current_model = self.config.get('hamlib', 'rig_model')
                for i in range(self.rig_model_combo.count()):
                    if self.rig_model_combo.itemData(i) == current_model:
                        self.rig_model_combo.setCurrentIndex(i)
                        break

            # Set other HAMLIB settings
            self.port_edit.setText(self.config.get('hamlib', 'port'))
            self.baud_combo.setCurrentText(str(self.config.get('hamlib', 'baud_rate')))
            self.ptt_combo.setCurrentText(self.config.get('hamlib', 'ptt_control'))
            # Load UI settings
            self.theme_combo.setCurrentText(self.config.get('ui', 'theme').capitalize())
            self.waterfall_combo.setCurrentText(self.config.get('ui', 'waterfall_colors').capitalize())

            self.update_rate_spin.setValue(self.config.get('ui', 'spectrum_update_rate'))

            # Load display settings
            self.show_freq_check.setChecked(self.config.get('ui', 'show_freq_markers', True))
            self.show_grid_check.setChecked(self.config.get('ui', 'show_grid', True))
            self.average_check.setChecked(self.config.get('ui', 'fft_average', False))
            self.peak_hold_check.setChecked(self.config.get('ui', 'peak_hold', False))

            # Load ARDOP Advanced settings
            # ARQ Settings
            arqbw_mode = self.config.get('modem', 'arqbw_mode', 'MAX')
            if arqbw_mode == 'MAX':
                self.arq_bw_combo.setCurrentIndex(0)
            else:
                self.arq_bw_combo.setCurrentIndex(1)

            callbw = self.config.get('modem', 'callbw', 'UNDEFINED')
            for i in range(self.callbw_combo.count()):
                if self.callbw_combo.itemData(i) == callbw:
                    self.callbw_combo.setCurrentIndex(i)
                    break

            self.autobreak_check.setChecked(self.config.get('modem', 'autobreak', True))
            self.busyblock_check.setChecked(self.config.get('modem', 'busyblock', False))

            # FEC Settings
            fec_mode = self.config.get('modem', 'fec_mode', '4FSK.500.100S')
            for i in range(self.fec_mode_combo.count()):
                if self.fec_mode_combo.itemData(i) == fec_mode:
                    self.fec_mode_combo.setCurrentIndex(i)
                    break

            self.fec_id_check.setChecked(self.config.get('modem', 'fec_id', False))

            # Tuning Settings
            self.tuning_range_spin.setValue(self.config.get('modem', 'tuning_range', 100))
            self.input_noise_spin.setValue(self.config.get('modem', 'input_noise', 0))

            # Debug Settings
            self.debug_log_check.setChecked(self.config.get('modem', 'debug_log', False))
            self.log_dir_edit.setText(self.config.get('modem', 'log_dir', ''))         
            self.cmd_trace_check.setChecked(self.config.get('modem', 'cmd_trace', False))

            # Load network settings
            ardop_mode = self.config.get('modem', 'ardop_mode', 'internal')
            self.run_ardop_mode_combo.setCurrentIndex(
                0 if ardop_mode == 'internal' else 1
            )
            self.ardop_ip_edit.setText(self.config.get('modem', 'ardop_ip', '127.0.0.1'))
            self.ardop_port_spin.setValue(self.config.get('modem', 'ardop_port', 8515))
            
            # Update network settings enabled state
            self._on_ardop_mode_changed()

        except Exception as e:
            logger.exception(f"Error loading settings: {e}")
            QMessageBox.warning(self, "Error",
                              f"Failed to load settings: {str(e)}")

    def _apply_settings(self):
        """Apply current dialog settings to config"""
        try:            # Apply audio settings
            self.config.set('audio', 'sample_rate', self.sample_rate_combo.currentData())
            self.config.set('audio', 'channels', self.channels_combo.currentData())
            self.config.set('audio', 'buffer_size', self.buffer_spin.value())

            # Save audio device selections
            self.config.set('audio', 'input_device', self.input_combo.currentData())
            self.config.set('audio', 'output_device', self.output_combo.currentData())

            tx_level = self.tx_level_slider.value() / 100.0
            self.config.set('modem', 'tx_level', tx_level)

            # Apply modem settings
            self.config.set('modem', 'mode', self.mode_combo.currentData())
            self.config.set('modem', 'bandwidth', self.bandwidth_combo.currentData())
            self.config.set('modem', 'center_freq', self.center_freq_spin.value())

            # Apply ARDOP specific settings
            self.config.set('modem', 'protocol_mode', self.protocol_mode_combo.currentData())
            self.config.set('modem', 'arq_timeout', self.arq_timeout_spin.value())
            self.config.set('modem', 'fec_repeats', self.fec_repeats_spin.value())
            self.config.set('modem', 'leader', self.leader_spin.value())
            self.config.set('modem', 'trailer', self.trailer_spin.value())
            self.config.set('modem', 'squelch', self.squelch_spin.value())
            self.config.set('modem', 'busydet', self.busydet_spin.value())
            self.config.set('modem', 'extradelay', self.extradelay_spin.value())
            self.config.set('modem', 'consolelog', self.consolelog_spin.value())
            self.config.set('modem', 'cwid', self.cwid_check.isChecked())
            self.config.set('modem', 'fskonly', self.fsk_only_check.isChecked())
            self.config.set('modem', 'use600modes', self.use600_check.isChecked())
            self.config.set('modem', 'faststart', self.faststart_check.isChecked())
            self.config.set('modem', 'custom_commands', self.custom_commands.text())

            # Apply spectrum settings
            self.config.set('ui', 'fft_average_frames', self.fft_avg_spin.value())
            self.config.set('ui', 'spectrum_ref_level', self.spectrum_ref_spin.value())
            self.config.set('ui', 'spectrum_range', self.spectrum_range_spin.value())
            self.config.set('ui', 'waterfall_speed', self.waterfall_speed_combo.currentData())

            # Apply HAMLIB settings
            self.config.set('hamlib', 'enabled', self.hamlib_enabled_check.isChecked())
            self.config.set('hamlib', 'rig_model', self.rig_model_combo.currentData())
            self.config.set('hamlib', 'port', self.port_edit.text())
            self.config.set('hamlib', 'baud_rate', int(self.baud_combo.currentText()))
            self.config.set('hamlib', 'ptt_control', self.ptt_combo.currentText())

            # Apply UI settings
            self.config.set('ui', 'theme', self.theme_combo.currentData())
            self.config.set('ui', 'waterfall_colors', self.waterfall_combo.currentData())
            self.config.set('ui', 'fft_size', 2048)  # Fixed at 2048
            self.config.set('ui', 'spectrum_update_rate', self.update_rate_spin.value())

            # Apply display settings
            self.config.set('ui', 'show_freq_markers', self.show_freq_check.isChecked())
            self.config.set('ui', 'show_grid', self.show_grid_check.isChecked())
            self.config.set('ui', 'fft_average', self.average_check.isChecked())            # Apply user settings
            self.config.set('user', 'callsign', self.callsign_edit.text().upper())

            # Save new user fields
            self.config.set('user', 'fullname', self.fullname_edit.text())
            self.config.set('user', 'email', self.email_edit.text())
            self.config.set('user', 'city', self.city_edit.text())
            self.config.set('user', 'grid_square', self.grid_square_edit.text())

            # Save ARDOP network settings
            self.config.set('modem', 'ardop_mode', self.run_ardop_mode_combo.currentData())
            self.config.set('modem', 'ardop_ip', self.ardop_ip_edit.text())
            self.config.set('modem', 'ardop_port', self.ardop_port_spin.value())

            # Save config
            self.config.save()
            return True
        except Exception as e:
            logger.exception(f"Error applying settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply settings: {e}")
            return False

    @pyqtSlot()
    def accept(self):
        """Handle OK button"""
        self._apply_settings()
        super().accept()

    @pyqtSlot()
    def _ptt_on(self):
        """Test PTT ON"""
        try:
            hamlib_manager = self.parent().hamlib_manager if self.parent() else None
            if hamlib_manager and hamlib_manager.is_connected():
                if hamlib_manager.set_ptt(True):
                    QMessageBox.information(self, "PTT Test", "PTT enabled successfully.")
                else:
                    QMessageBox.warning(self, "PTT Test", "Failed to enable PTT.")
            else:
                QMessageBox.warning(self, "PTT Test", "HAMLIB not connected. Please connect first.")
        except Exception as e:
            logger.exception(f"Error testing PTT: {e}")
            QMessageBox.warning(self, "Error",
                              f"Failed to test PTT: {str(e)}")

    @pyqtSlot()
    def _ptt_off(self):
        """Test PTT OFF"""
        try:
            hamlib_manager = self.parent().hamlib_manager if self.parent() else None
            if hamlib_manager and hamlib_manager.is_connected():
                if hamlib_manager.set_ptt(False):
                    QMessageBox.information(self, "PTT Test", "PTT disabled successfully.")
                else:
                    QMessageBox.warning(self, "PTT Test", "Failed to disable PTT.")
            else:
                QMessageBox.warning(self, "PTT Test", "HAMLIB not connected. Please connect first.")
        except Exception as e:
            logger.exception(f"Error testing PTT: {e}")
            QMessageBox.warning(self, "Error",
                              f"Failed to test PTT: {str(e)}")

    def showEvent(self, event):
        """Override showEvent to refresh audio devices when dialog opens"""
        super().showEvent(event)
        # Automatically refresh audio devices when dialog is opened
        self._refresh_audio_devices()
        logger.info("Settings dialog opened, audio devices refreshed")

    def _on_mode_changed(self):
        """Handle modem mode change"""
        # Show or hide ARDOP settings based on selected mode
        current_mode = self.mode_combo.currentData()

        # Show ARDOP settings only when ARDOP is selected
        self.ardop_group.setVisible(current_mode == "ARDOP")

        # Show/hide ARDOP advanced tab
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "ARDOP Advanced":
                self.tab_widget.setTabVisible(i, current_mode == "ARDOP")
                break

    def _reset_modem_settings(self):
        """Reset modem settings to defaults"""
        try:
            # Reset ARDOP specific settings to defaults
            self.protocol_mode_combo.setCurrentIndex(0)  # ARQ Mode
            self.arq_timeout_spin.setValue(120)          # 120 seconds
            self.fec_repeats_spin.setValue(0)            # No repeats
            self.leader_spin.setValue(120)               # 120 ms
            self.trailer_spin.setValue(0)                # 0 ms
            self.squelch_spin.setValue(5)                # Squelch level 5
            self.busydet_spin.setValue(5)                # Busy detection level 5
            self.extradelay_spin.setValue(0)             # No extra delay
            self.consolelog_spin.setValue(6)             # Verbosity level 6
            self.cwid_check.setChecked(False)            # CW ID off
            self.fsk_only_check.setChecked(False)        # FSK only off
            self.use600_check.setChecked(False)          # 600 baud modes off
            self.faststart_check.setChecked(True)        # Fast start on
            self.custom_commands.clear()                  # Clear custom commands

            # Optionally, show a message box to inform the user
            QMessageBox.information(self, "Settings Reset",
                                    "Modem settings have been reset to defaults.")

            logger.info("Modem settings reset to defaults")

        except Exception as e:
            logger.exception(f"Error resetting modem settings: {e}")
            QMessageBox.warning(self, "Error",
                              f"Failed to reset modem settings: {str(e)}")
