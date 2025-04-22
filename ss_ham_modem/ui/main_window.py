"""
Main window for SS Ham Modem application
"""
import os
import logging
import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QComboBox, QTabWidget,
                            QStatusBar, QAction, QFileDialog, QMessageBox,
                            QDialog, QLineEdit, QFormLayout, QDialogButtonBox,
                            QGroupBox)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, pyqtSlot

from ss_ham_modem.ui.spectrum_view import SpectrumView
from ss_ham_modem.ui.waterfall_view import WaterfallView
from ss_ham_modem.ui.settings_dialog import SettingsDialog
from ss_ham_modem.ui.license_dialog import LicenseDialog
from ss_ham_modem.core.audio_manager import AudioManager
from ss_ham_modem.core.modem_manager import ModemManager
from ss_ham_modem.core.hamlib_manager import HamlibManager

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main window for SS Ham Modem application"""

    def __init__(self, config, license_manager):
        """Initialize main window"""
        super().__init__()

        self.config = config
        self.license_manager = license_manager

        # Initialize managers
        self.audio_manager = AudioManager(self.config)
        self.modem_manager = ModemManager(self.config, self.license_manager)
        self.hamlib_manager = HamlibManager(self.config)

        # Set up window properties
        self.setWindowTitle("SS Ham Modem")
        self.setMinimumSize(800, 600)

        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create menu bar
        self.setup_menu_bar()

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Create control panel
        self.setup_control_panel()

        # Create spectrum view and waterfall
        self.setup_visualizations()

        # Create tabs for additional features
        self.setup_feature_tabs()

        # Update status bar with license info
        self.update_license_status()

        # Start timers for UI updates
        self.start_timers()

    def setup_menu_bar(self):
        """Set up the application menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # Save/Load WAV actions
        save_wav_action = QAction("&Save Audio to WAV", self)
        save_wav_action.triggered.connect(self.save_wav_file)
        file_menu.addAction(save_wav_action)

        load_wav_action = QAction("&Load Audio from WAV", self)
        load_wav_action.triggered.connect(self.load_wav_file)
        file_menu.addAction(load_wav_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Modem menu
        modem_menu = menu_bar.addMenu("&Modem")

        # Connect action
        connect_action = QAction("&Connect", self)
        connect_action.triggered.connect(self.connect_modem)
        modem_menu.addAction(connect_action)

        # Disconnect action
        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.triggered.connect(self.disconnect_modem)
        modem_menu.addAction(disconnect_action)

        modem_menu.addSeparator()

        # Settings action
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings)
        modem_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        # License action
        license_action = QAction("&License", self)
        license_action.triggered.connect(self.open_license_dialog)
        help_menu.addAction(license_action)

        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.open_about_dialog)
        help_menu.addAction(about_action)

    def setup_control_panel(self):
        """Set up the control panel with modem controls"""
        control_panel = QGroupBox("Modem Control")
        control_layout = QHBoxLayout()
        control_panel.setLayout(control_layout)

        # Audio device selection
        self.input_device_combo = QComboBox()
        self.output_device_combo = QComboBox()

        # Populate audio device lists
        input_devices = self.audio_manager.get_input_devices()
        for name, index in input_devices:
            self.input_device_combo.addItem(name, index)

        output_devices = self.audio_manager.get_output_devices()
        for name, index in output_devices:
            self.output_device_combo.addItem(name, index)

        # Set current devices from config
        input_device = self.config.get('audio', 'input_device')
        output_device = self.config.get('audio', 'output_device')

        if input_device is not None:
            index = self.input_device_combo.findData(input_device)
            if index >= 0:
                self.input_device_combo.setCurrentIndex(index)

        if output_device is not None:
            index = self.output_device_combo.findData(output_device)
            if index >= 0:
                self.output_device_combo.setCurrentIndex(index)

        # Connect audio device change events
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)
        self.output_device_combo.currentIndexChanged.connect(self.on_output_device_changed)

        # Bandwidth selection
        self.bandwidth_combo = QComboBox()
        bandwidths = self.modem_manager.get_available_bandwidths()
        for bw in bandwidths:
            self.bandwidth_combo.addItem(f"{bw} Hz", bw)

        # Set current bandwidth from config
        current_bw = self.config.get('modem', 'bandwidth')
        index = self.bandwidth_combo.findData(current_bw)
        if index >= 0:
            self.bandwidth_combo.setCurrentIndex(index)

        self.bandwidth_combo.currentIndexChanged.connect(self.on_bandwidth_changed)

        # Center frequency control
        self.center_freq_combo = QComboBox()
        frequencies = [1000, 1500, 2000, 2500]
        for freq in frequencies:
            self.center_freq_combo.addItem(f"{freq} Hz", freq)

        # Set current center frequency from config
        current_freq = self.config.get('modem', 'center_freq')
        index = self.center_freq_combo.findData(current_freq)
        if index >= 0:
            self.center_freq_combo.setCurrentIndex(index)

        self.center_freq_combo.currentIndexChanged.connect(self.on_center_freq_changed)

        # Connect/Disconnect buttons
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_modem)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_modem)
        self.disconnect_button.setEnabled(False)

        # Add widgets to control panel layout
        device_layout = QFormLayout()
        device_layout.addRow("Input Device:", self.input_device_combo)
        device_layout.addRow("Output Device:", self.output_device_combo)

        modem_layout = QFormLayout()
        modem_layout.addRow("Bandwidth:", self.bandwidth_combo)
        modem_layout.addRow("Center Freq:", self.center_freq_combo)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.connect_button)
        buttons_layout.addWidget(self.disconnect_button)

        # Add layouts to control panel
        audio_group = QGroupBox("Audio Devices")
        audio_group.setLayout(device_layout)

        modem_group = QGroupBox("Modem Settings")
        modem_group.setLayout(modem_layout)

        control_layout.addWidget(audio_group)
        control_layout.addWidget(modem_group)
        control_layout.addLayout(buttons_layout)

        # Add control panel to main layout
        self.main_layout.addWidget(control_panel)

    def setup_visualizations(self):
        """Set up spectrum and waterfall visualizations"""
        vis_panel = QGroupBox("Spectrum & Waterfall")
        vis_layout = QVBoxLayout()
        vis_panel.setLayout(vis_layout)

        # Create spectrum view
        self.spectrum_view = SpectrumView(self.config)
        vis_layout.addWidget(self.spectrum_view, 1)

        # Create waterfall view
        self.waterfall_view = WaterfallView(self.config)
        vis_layout.addWidget(self.waterfall_view, 2)

        # Add to main layout
        self.main_layout.addWidget(vis_panel, 3)  # Larger proportion for visualizations

    def setup_feature_tabs(self):
        """Set up tabs for additional features"""
        tabs = QTabWidget()

        # Modem status tab
        self.modem_status_widget = QWidget()
        modem_status_layout = QFormLayout(self.modem_status_widget)
        self.status_labels = {
            'connection': QLabel("Disconnected"),
            'snr': QLabel("N/A"),
            'signal': QLabel("N/A"),
            'mode': QLabel(self.config.get('modem', 'mode')),
            'bandwidth': QLabel(f"{self.config.get('modem', 'bandwidth')} Hz"),
        }

        for label, widget in self.status_labels.items():
            modem_status_layout.addRow(f"{label.capitalize()}:", widget)

        tabs.addTab(self.modem_status_widget, "Status")

        # HAMLIB control tab
        self.hamlib_widget = QWidget()
        hamlib_layout = QFormLayout(self.hamlib_widget)

        self.hamlib_enabled_label = QLabel("Disabled")
        self.hamlib_rig_label = QLabel("Not connected")
        self.hamlib_ptt_label = QLabel("N/A")

        hamlib_layout.addRow("HAMLIB Status:", self.hamlib_enabled_label)
        hamlib_layout.addRow("Rig Model:", self.hamlib_rig_label)
        hamlib_layout.addRow("PTT Control:", self.hamlib_ptt_label)

        # HAMLIB control buttons
        hamlib_buttons = QHBoxLayout()
        self.hamlib_connect_btn = QPushButton("Connect Rig")
        self.hamlib_connect_btn.clicked.connect(self.connect_hamlib)

        self.hamlib_disconnect_btn = QPushButton("Disconnect Rig")
        self.hamlib_disconnect_btn.clicked.connect(self.disconnect_hamlib)
        self.hamlib_disconnect_btn.setEnabled(False)

        hamlib_buttons.addWidget(self.hamlib_connect_btn)
        hamlib_buttons.addWidget(self.hamlib_disconnect_btn)
        hamlib_layout.addRow("", hamlib_buttons)

        tabs.addTab(self.hamlib_widget, "HAMLIB")

        # Add tabs to main layout
        self.main_layout.addWidget(tabs, 1)  # Smaller proportion for tabs

    def start_timers(self):
        """Start timers for UI updates"""
        # Spectrum update timer
        self.spectrum_timer = QTimer(self)
        self.spectrum_timer.timeout.connect(self.update_spectrum)
        update_rate = self.config.get('ui', 'spectrum_update_rate')
        self.spectrum_timer.start(1000 // update_rate)  # Convert Hz to ms

        # Status update timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second

    def update_spectrum(self):
        """Update spectrum and waterfall displays"""
        if not self.modem_manager.is_connected():
            # If not connected, show dummy/demo data
            self.spectrum_view.update_with_demo_data()
            self.waterfall_view.update_with_demo_data()
        else:
            # Get real data from modem
            fft_data = self.modem_manager.get_fft_data()
            self.spectrum_view.update_with_data(fft_data)
            self.waterfall_view.append_data(fft_data)

    def update_status(self):
        """Update status displays"""
        if self.modem_manager.is_connected():
            # Update modem status
            status = self.modem_manager.get_status()
            self.status_labels['connection'].setText("Connected")
            self.status_labels['snr'].setText(f"{status.get('snr', 'N/A')} dB")
            self.status_labels['signal'].setText(f"{status.get('signal_level', 'N/A')} dBm")

            # Update HAMLIB status if enabled
            if self.hamlib_manager.is_connected():
                hamlib_status = self.hamlib_manager.get_status()
                self.hamlib_enabled_label.setText("Enabled")
                self.hamlib_rig_label.setText(hamlib_status.get('rig_model', 'Unknown'))
                self.hamlib_ptt_label.setText(hamlib_status.get('ptt_status', 'N/A'))

    def update_license_status(self):
        """Update status bar with license information"""
        license_info = self.license_manager.get_license_info()
        tier = license_info['tier'].capitalize()

        status_text = f"License: {tier}"

        if license_info['licensed_to']:
            status_text += f" | Licensed to: {license_info['licensed_to']}"

        if license_info['expiration_date']:
            exp_date = datetime.datetime.fromisoformat(license_info['expiration_date'])
            status_text += f" | Expires: {exp_date.strftime('%Y-%m-%d')}"

        self.status_bar.showMessage(status_text)

    @pyqtSlot()
    def connect_modem(self):
        """Connect to the modem"""
        try:
            # Get current audio device selections
            input_idx = self.input_device_combo.currentData()
            output_idx = self.output_device_combo.currentData()

            if input_idx is None or output_idx is None:
                QMessageBox.warning(self, "Connection Error",
                                   "Please select valid input and output audio devices")
                return

            # Configure audio devices
            self.audio_manager.set_devices(input_idx, output_idx)

            # Start modem
            if self.modem_manager.connect():
                self.connect_button.setEnabled(False)
                self.disconnect_button.setEnabled(True)
                self.status_bar.showMessage("Modem connected", 3000)
                logger.info("Modem connected successfully")
            else:
                QMessageBox.warning(self, "Connection Error",
                                  "Failed to connect to modem. Check settings and try again.")
                logger.error("Failed to connect to modem")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error connecting to modem: {str(e)}")
            logger.exception("Error connecting to modem")

    @pyqtSlot()
    def disconnect_modem(self):
        """Disconnect from the modem"""
        try:
            self.modem_manager.disconnect()
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.status_bar.showMessage("Modem disconnected", 3000)

            # Update status labels
            self.status_labels['connection'].setText("Disconnected")
            self.status_labels['snr'].setText("N/A")
            self.status_labels['signal'].setText("N/A")

            logger.info("Modem disconnected")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error disconnecting modem: {str(e)}")
            logger.exception("Error disconnecting modem")

    @pyqtSlot()
    def connect_hamlib(self):
        """Connect to HAMLIB rig"""
        try:
            if self.hamlib_manager.connect():
                self.hamlib_connect_btn.setEnabled(False)
                self.hamlib_disconnect_btn.setEnabled(True)
                self.status_bar.showMessage("HAMLIB connected", 3000)

                # Update HAMLIB status
                hamlib_status = self.hamlib_manager.get_status()
                self.hamlib_enabled_label.setText("Enabled")
                self.hamlib_rig_label.setText(hamlib_status.get('rig_model', 'Unknown'))
                self.hamlib_ptt_label.setText(hamlib_status.get('ptt_status', 'N/A'))

                logger.info("HAMLIB connected successfully")
            else:
                QMessageBox.warning(self, "HAMLIB Connection Error",
                                  "Failed to connect to HAMLIB. Check settings and try again.")
                logger.error("Failed to connect to HAMLIB")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error connecting to HAMLIB: {str(e)}")
            logger.exception("Error connecting to HAMLIB")

    @pyqtSlot()
    def disconnect_hamlib(self):
        """Disconnect from HAMLIB rig"""
        try:
            self.hamlib_manager.disconnect()
            self.hamlib_connect_btn.setEnabled(True)
            self.hamlib_disconnect_btn.setEnabled(False)

            # Update HAMLIB status
            self.hamlib_enabled_label.setText("Disabled")
            self.hamlib_rig_label.setText("Not connected")
            self.hamlib_ptt_label.setText("N/A")

            self.status_bar.showMessage("HAMLIB disconnected", 3000)
            logger.info("HAMLIB disconnected")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error disconnecting HAMLIB: {str(e)}")
            logger.exception("Error disconnecting HAMLIB")

    @pyqtSlot(int)
    def on_input_device_changed(self, index):
        """Handle input device selection change"""
        device_idx = self.input_device_combo.currentData()
        if device_idx is not None:
            self.config.set('audio', 'input_device', device_idx)
            self.config.save()

    @pyqtSlot(int)
    def on_output_device_changed(self, index):
        """Handle output device selection change"""
        device_idx = self.output_device_combo.currentData()
        if device_idx is not None:
            self.config.set('audio', 'output_device', device_idx)
            self.config.save()

    @pyqtSlot(int)
    def on_bandwidth_changed(self, index):
        """Handle bandwidth selection change"""
        bandwidth = self.bandwidth_combo.currentData()

        # Check if bandwidth is allowed with current license
        limits = self.license_manager.get_feature_limits()
        if bandwidth > limits['max_bandwidth']:
            QMessageBox.warning(self, "License Restriction",
                              f"The selected bandwidth ({bandwidth} Hz) exceeds your license limit "
                              f"({limits['max_bandwidth']} Hz). Please upgrade your license or select a lower bandwidth.")

            # Reset to highest allowed bandwidth
            allowed_bandwidths = [bw for bw in self.modem_manager.get_available_bandwidths()
                                if bw <= limits['max_bandwidth']]
            if allowed_bandwidths:
                max_allowed = max(allowed_bandwidths)
                new_index = self.bandwidth_combo.findData(max_allowed)
                if new_index >= 0:
                    self.bandwidth_combo.setCurrentIndex(new_index)
            return

        self.config.set('modem', 'bandwidth', bandwidth)
        self.config.save()
        self.status_labels['bandwidth'].setText(f"{bandwidth} Hz")

        # Update modem if connected
        if self.modem_manager.is_connected():
            self.modem_manager.set_bandwidth(bandwidth)

    @pyqtSlot(int)
    def on_center_freq_changed(self, index):
        """Handle center frequency selection change"""
        center_freq = self.center_freq_combo.currentData()
        self.config.set('modem', 'center_freq', center_freq)
        self.config.save()

        # Update modem if connected
        if self.modem_manager.is_connected():
            self.modem_manager.set_center_freq(center_freq)

    @pyqtSlot()
    def save_wav_file(self):
        """Save current audio to WAV file"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Audio", "", "WAV Files (*.wav)")
        if file_path:
            try:
                if self.modem_manager.save_to_wav(file_path):
                    self.status_bar.showMessage(f"Audio saved to {file_path}", 3000)
                else:
                    QMessageBox.warning(self, "Save Failed", "Failed to save audio to WAV file")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error saving WAV file: {str(e)}")
                logger.exception("Error saving WAV file")

    @pyqtSlot()
    def load_wav_file(self):
        """Load audio from WAV file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Audio", "", "WAV Files (*.wav)")
        if file_path:
            try:
                if self.modem_manager.load_from_wav(file_path):
                    self.status_bar.showMessage(f"Audio loaded from {file_path}", 3000)
                else:
                    QMessageBox.warning(self, "Load Failed", "Failed to load audio from WAV file")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error loading WAV file: {str(e)}")
                logger.exception("Error loading WAV file")

    @pyqtSlot()
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.config, self.license_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            # Reload configuration
            self.update_from_config()

    @pyqtSlot()
    def open_license_dialog(self):
        """Open license dialog"""
        dialog = LicenseDialog(self.license_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            # Update license status
            self.update_license_status()

    @pyqtSlot()
    def open_about_dialog(self):
        """Open about dialog"""
        QMessageBox.about(self, "About SS Ham Modem",
                        "SS Ham Modem\n"
                        "Version: 0.1.0\n\n"
                        "A digital modem application for amateur radio.\n"
                        "Based on ARDOP protocol.\n\n"
                        "Copyright © 2025")

    def update_from_config(self):
        """Update UI elements based on current configuration"""
        # Update input device
        input_device = self.config.get('audio', 'input_device')
        if input_device is not None:
            index = self.input_device_combo.findData(input_device)
            if index >= 0:
                self.input_device_combo.setCurrentIndex(index)

        # Update output device
        output_device = self.config.get('audio', 'output_device')
        if output_device is not None:
            index = self.output_device_combo.findData(output_device)
            if index >= 0:
                self.output_device_combo.setCurrentIndex(index)

        # Update bandwidth
        bandwidth = self.config.get('modem', 'bandwidth')
        index = self.bandwidth_combo.findData(bandwidth)
        if index >= 0:
            self.bandwidth_combo.setCurrentIndex(index)

        # Update center frequency
        center_freq = self.config.get('modem', 'center_freq')
        index = self.center_freq_combo.findData(center_freq)
        if index >= 0:
            self.center_freq_combo.setCurrentIndex(index)

        # Update status labels
        self.status_labels['mode'].setText(self.config.get('modem', 'mode'))
        self.status_labels['bandwidth'].setText(f"{self.config.get('modem', 'bandwidth')} Hz")

        # Update spectrum and waterfall settings
        self.spectrum_view.update_settings(self.config)
        self.waterfall_view.update_settings(self.config)

        # Update spectrum update rate
        update_rate = self.config.get('ui', 'spectrum_update_rate')
        self.spectrum_timer.setInterval(1000 // update_rate)

        # Update HAMLIB status if enabled
        hamlib_config = self.config.get('hamlib')
        if hamlib_config['enabled']:
            self.hamlib_enabled_label.setText("Enabled (not connected)")
            self.hamlib_rig_label.setText(str(hamlib_config['rig_model']))
            self.hamlib_ptt_label.setText(hamlib_config['ptt_control'])
