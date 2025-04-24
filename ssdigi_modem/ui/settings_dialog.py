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
        self.setFixedSize(600, 400)  # Set fixed size

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
        main_layout.addWidget(self.tab_widget)

        # Create settings tabs
        self._create_audio_tab()
        self._create_modem_tab()
        self._create_station_tab()
        self._create_hamlib_tab()
        self._create_ui_tab()

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
        layout.addWidget(comm_group)

        # Spectrum and waterfall settings
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
        layout.addWidget(ui_group)

        # Display settings
        display_group = QGroupBox("Display Settings")
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

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(ui_tab, "Display")    # Network settings tab removed - host application interface settings now hard-coded

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

            try:                # Add "System Default" option with special index
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
            self.ptt_combo.setCurrentText(self.config.get('hamlib', 'ptt_control'))            # Load UI settings
            self.theme_combo.setCurrentText(self.config.get('ui', 'theme').capitalize())
            self.waterfall_combo.setCurrentText(self.config.get('ui', 'waterfall_colors').capitalize())

            self.update_rate_spin.setValue(self.config.get('ui', 'spectrum_update_rate'))

            # Load display settings
            self.show_freq_check.setChecked(self.config.get('ui', 'show_freq_markers', True))
            self.show_grid_check.setChecked(self.config.get('ui', 'show_grid', True))
            self.average_check.setChecked(self.config.get('ui', 'fft_average', False))
            self.peak_hold_check.setChecked(self.config.get('ui', 'peak_hold', False))

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
            self.config.set('ui', 'fft_average', self.average_check.isChecked())

            # Apply user settings
            self.config.set('user', 'callsign', self.callsign_edit.text().upper())

            # Save new user fields
            self.config.set('user', 'fullname', self.fullname_edit.text())
            self.config.set('user', 'email', self.email_edit.text())
            self.config.set('user', 'city', self.city_edit.text())
            self.config.set('user', 'grid_square', self.grid_square_edit.text())

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
