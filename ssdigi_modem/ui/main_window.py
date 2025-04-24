"""
Main window for SSDigi Modem application
"""
import os
import logging
import datetime
import numpy as np
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QComboBox, QTabWidget, QTableWidget,
                            QStatusBar, QAction, QFileDialog, QMessageBox, QTableWidgetItem,
                            QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QCheckBox,
                            QGroupBox, QTextEdit, QListWidget, QGridLayout)
from PyQt5.QtGui import QIcon, QColor, QMovie
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QSize
from ssdigi_modem.ui.spectrum_view import SpectrumView
from ssdigi_modem.ui.waterfall_view import WaterfallView
from ssdigi_modem.ui.settings_dialog import SettingsDialog
from ssdigi_modem.core.audio_manager import AudioManager
from ssdigi_modem.core.modem_manager import ModemManager
from ssdigi_modem.core.hamlib_manager import HamlibManager
from ssdigi_modem.utils.ui_helpers import get_app_icon

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main window for SSDigi Modem application"""

    def __init__(self, config):
        """Initialize main window"""
        super().__init__()

        self.config = config

        # Initialize managers
        self.audio_manager = AudioManager(self.config)
        self.modem_manager = ModemManager(self.config)
        self.hamlib_manager = HamlibManager(self.config)

        # Initialize status labels dictionary
        self.status_labels = {}

        # Set up window properties
        self.setWindowTitle("SSDigi Modem")
        self.setFixedSize(650, 450)  # Set fixed window size

        # Prevent window resizing
        self.setWindowFlags(self.windowFlags() | Qt.MSWindowsFixedSizeDialogHint)

        # Set application icon
        icon_path = get_app_icon()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

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

        # Update status bar with basic info
        self.update_status_bar()

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

        # Settings action
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings)
        modem_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.open_about_dialog)
        help_menu.addAction(about_action)

    def setup_control_panel(self):
        """Set up the control panel with modem controls"""
        # Create main horizontal layout for the overall window
        main_control_layout = QHBoxLayout()
        # Left side panel for controls and tabs
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        # Control panel
        control_panel = QGroupBox("Modem Control")
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        control_panel.setFixedWidth(200)
        # Connect/Disconnect buttons with improved styling
        button_style = """
            QPushButton {
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:enabled {
                background-color: #2196F3;
                color: white;
                border: none;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: none;
            }
            QPushButton:hover:enabled {
                background-color: #1976D2;
            }
        """
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_modem)
        self.connect_button.setStyleSheet(button_style)

        # We'll keep this for backward compatibility but won't display it
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_modem)
        self.disconnect_button.setStyleSheet(button_style)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.hide()

        # Add buttons to control layout
        control_layout.addWidget(self.connect_button)

        # Add monitoring section
        monitoring_group = QGroupBox("Monitoring")
        monitoring_layout = QGridLayout()
        monitoring_group.setLayout(monitoring_layout)

        # Style for monitoring labels
        value_style = """
            QLabel {
                color: #2196F3;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 2px;
                border: 1px solid #404040;
                background: #1a1a1a;
                border-radius: 2px;
            }
        """

        # RX/TX Status
        self.rx_indicator = QLabel("RX")
        self.tx_indicator = QLabel("TX")
        self.rx_indicator.setStyleSheet("QLabel { color: gray; }")
        self.tx_indicator.setStyleSheet("QLabel { color: gray; }")
        monitoring_layout.addWidget(QLabel("Status:"), 0, 0)
        status_box = QHBoxLayout()
        status_box.addWidget(self.rx_indicator)
        status_box.addWidget(self.tx_indicator)
        monitoring_layout.addLayout(status_box, 0, 1)

        # Signal-to-Noise Ratio
        self.snr_label = QLabel("---")
        self.snr_label.setStyleSheet(value_style)
        monitoring_layout.addWidget(QLabel("S/N:"), 1, 0)
        monitoring_layout.addWidget(self.snr_label, 1, 1)

        # CPU Usage
        self.cpu_label = QLabel("---%")
        self.cpu_label.setStyleSheet(value_style)
        monitoring_layout.addWidget(QLabel("CPU:"), 2, 0)
        monitoring_layout.addWidget(self.cpu_label, 2, 1)

        # VU Meter (audio level)
        self.vu_label = QLabel("-∞ dB")
        self.vu_label.setStyleSheet(value_style)
        monitoring_layout.addWidget(QLabel("VU:"), 3, 0)
        monitoring_layout.addWidget(self.vu_label, 3, 1)

        # AFC (Automatic Frequency Control)
        self.afc_label = QLabel("±0 Hz")
        self.afc_label.setStyleSheet(value_style)
        monitoring_layout.addWidget(QLabel("AFC:"), 4, 0)
        monitoring_layout.addWidget(self.afc_label, 4, 1)

        # Buffer status
        self.buffer_label = QLabel("0%")
        self.buffer_label.setStyleSheet(value_style)
        monitoring_layout.addWidget(QLabel("Buffer:"), 5, 0)
        monitoring_layout.addWidget(self.buffer_label, 5, 1)

        control_layout.addWidget(monitoring_group)
        control_layout.addStretch()

        # Add control panel to left panel
        left_panel.addWidget(control_panel)

        # Add left panel to main layout
        main_control_layout.addLayout(left_panel)

        # Right side - Visualizations - FIXED LAYOUT
        vis_panel = QGroupBox("Spectrum Analysis")

        # Use a margin style that leaves room for the title
        vis_panel.setStyleSheet("""
            QGroupBox {
                margin-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding-left: 10px;
                padding-right: 10px;
                padding-top: 3px;
                padding-bottom: 3px;
            }
        """)

        # Set proper layout with more spacing at the top
        vis_layout = QVBoxLayout()
        vis_layout.setSpacing(5)
        vis_layout.setContentsMargins(5, 25, 5, 5)  # More top margin for title
        vis_panel.setLayout(vis_layout)

        # Create visualization container
        vis_container = QWidget()
        vis_container.setContentsMargins(2, 2, 2, 2)
        vis_container_layout = QVBoxLayout(vis_container)
        vis_container_layout.setSpacing(5)
        vis_container_layout.setContentsMargins(0, 5, 0, 0)  # Add some padding at top

        # Create spectrum view with proper size
        self.spectrum_view = SpectrumView(self.config)
        self.spectrum_view.setMinimumSize(400, 130)
        self.spectrum_view.setMaximumHeight(150)
        vis_container_layout.addWidget(self.spectrum_view)

        # Create waterfall view with proper size
        self.waterfall_view = WaterfallView(self.config)
        self.waterfall_view.setMinimumWidth(400)
        vis_container_layout.addWidget(self.waterfall_view)

        # Add the container to the panel layout
        vis_layout.addWidget(vis_container)

        # Add visualization panel to main layout with stretch
        main_control_layout.addWidget(vis_panel, 1)

        # Add main layout to window
        self.main_layout.addLayout(main_control_layout)

    def setup_feature_tabs(self):
        """Placeholder for future feature tabs"""
        pass

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
        """Update spectrum and waterfall with new data"""
        # Get FFT data from modem
        fft_data = self.modem_manager.get_fft_data()

        # If no FFT data, try to use latest input audio
        if fft_data is None:
            if hasattr(self, 'audio_manager') and self.audio_manager.input_buffer:
                # Get the latest audio chunk
                audio_chunk = self.audio_manager.input_buffer[-1]
                # Ensure it's the right size for FFT
                fft_size = self.config.get('ui', 'fft_size', 2048)
                if len(audio_chunk) >= fft_size:
                    audio_chunk = audio_chunk[-fft_size:]
                else:
                    # Pad with zeros if too short
                    audio_chunk = np.pad(audio_chunk, (0, fft_size - len(audio_chunk)), 'constant')
                # Compute FFT and convert to dB
                fft = np.fft.fft(audio_chunk)
                fft = np.abs(fft[:fft_size // 2])
                fft_data = 20 * np.log10(fft + 1e-6)
            else:
                return

        # Apply FFT averaging if enabled
        if self.config.get('ui', 'fft_average', True):
            avg_frames = self.config.get('ui', 'fft_average_frames', 2)
            if not hasattr(self, 'fft_avg_buffer'):
                self.fft_avg_buffer = []

            # Add current data to buffer
            self.fft_avg_buffer.append(fft_data)

            # Keep only the most recent frames for averaging
            while len(self.fft_avg_buffer) > avg_frames:
                self.fft_avg_buffer.pop(0)

            # Average the frames
            if len(self.fft_avg_buffer) > 0:
                avg_data = np.zeros_like(self.fft_avg_buffer[0])
                for frame in self.fft_avg_buffer:
                    avg_data += frame
                avg_data /= len(self.fft_avg_buffer)
                fft_data = avg_data

        self.spectrum_view.update_with_data(fft_data)
        self.waterfall_view.update_waterfall(fft_data)

    def update_status(self):
        """Update status displays"""
        if self.modem_manager.is_connected():
            # Update modem status
            status = self.modem_manager.get_status()

            # RX/TX Indicators
            rx_active = status.get('rx_active', False)
            tx_active = status.get('tx_active', False)
            self.rx_indicator.setStyleSheet(
                "QLabel { color: #00ff00; font-weight: bold; }" if rx_active else "QLabel { color: gray; }"
            )
            self.tx_indicator.setStyleSheet(
                "QLabel { color: #ff0000; font-weight: bold; }" if tx_active else "QLabel { color: gray; }"
            )

            # Signal to Noise Ratio
            snr = status.get('snr', 0)
            self.snr_label.setText(f"{snr:+.1f} dB")

            # CPU Usage
            cpu = status.get('cpu_usage', 0)
            self.cpu_label.setText(f"{cpu:.1f}%")
            if cpu > 80:
                self.cpu_label.setStyleSheet("QLabel { color: #ff0000; }")  # Red when high
            else:
                self.cpu_label.setStyleSheet("QLabel { color: #2196F3; }")

            # VU Meter (audio level)
            vu = status.get('audio_level', -60)
            self.vu_label.setText(f"{vu:.1f} dB")

            # AFC Status
            afc_offset = status.get('afc_offset', 0)
            self.afc_label.setText(f"±{abs(afc_offset):.0f} Hz")

            # Buffer Status
            buffer_used = status.get('buffer_used', 0)
            self.buffer_label.setText(f"{buffer_used:.0f}%")
            if buffer_used > 90:
                self.buffer_label.setStyleSheet("QLabel { color: #ff0000; }")  # Red when near full
            else:
                self.buffer_label.setStyleSheet("QLabel { color: #2196F3; }")

            # Update HAMLIB status if enabled
            if self.hamlib_manager.is_connected():
                hamlib_status = self.hamlib_manager.get_status()
                self.status_bar.showMessage(f"Radio: {hamlib_status.get('rig_model', 'Unknown')}")

    def update_status_bar(self):
        """Update status bar with basic information"""
        # Display a simple status message
        self.status_bar.showMessage("SSDigi Modem")

    @pyqtSlot()
    def connect_modem(self):
        """Connect to the modem"""
        try:
            # Check if we're already connected - if so, disconnect
            if self.modem_manager.is_connected():
                self.disconnect_modem()
                return

            # Show loading state in button
            self.connect_button.setText("Connecting...")
            self.connect_button.setEnabled(False)
            # Force UI update
            self.connect_button.repaint()

            # Get audio device settings from config
            input_idx = self.config.get('audio', 'input_device')
            output_idx = self.config.get('audio', 'output_device')

            if input_idx is None or output_idx is None:
                # Reset button state
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
                QMessageBox.warning(self, "Connection Error",
                                   "Please configure audio devices in Settings first")
                self.open_settings()
                return

            # Configure audio devices
            self.audio_manager.set_devices(input_idx, output_idx)

            # Check if callsign is configured
            callsign = self.config.get('user', 'callsign', '')
            if not callsign:
                # Reset button state
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
                QMessageBox.warning(self, "Missing Callsign",
                                  "A valid callsign is required to connect to the modem.\n"
                                  "Please set your callsign in Modem > Settings > Station.")
                logger.error("Connection attempt failed: No callsign configured")
                return

            # Start modem
            if self.modem_manager.connect():
                # Change button to "Disconnect"
                self.connect_button.setText("Disconnect")
                self.connect_button.setEnabled(True)
                # No longer need the separate disconnect button
                self.disconnect_button.setEnabled(False)
                self.disconnect_button.hide()
                self.status_bar.showMessage("Modem connected", 3000)
                logger.info("Modem connected successfully")
            else:
                # Reset button state
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
                QMessageBox.warning(self, "Connection Error",
                                  "Failed to connect to modem. Check settings and try again.")
                logger.error("Failed to connect to modem")
        except Exception as e:
            # Reset button state on error
            self.connect_button.setText("Connect")
            self.connect_button.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Error connecting to modem: {str(e)}")
            logger.exception("Error connecting to modem")

    @pyqtSlot()
    def disconnect_modem(self):
        """Disconnect from the modem"""
        try:
            self.modem_manager.disconnect()
            # Reset button to "Connect" state
            self.connect_button.setText("Connect")
            self.connect_button.setEnabled(True)
            # No need to modify disconnect button visibility anymore
            self.status_bar.showMessage("Modem disconnected", 3000)

            # Update status labels if they exist
            if hasattr(self, 'status_labels'):
                if 'connection' in self.status_labels:
                    self.status_labels['connection'].setText("Disconnected")
                if 'snr' in self.status_labels:
                    self.status_labels['snr'].setText("N/A")
                if 'signal' in self.status_labels:
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
            logger.exception("Error disconnecting HAMLIB")    # Removed audio device change handlers as they're now handled in the settings dialog

    @pyqtSlot(int)
    def on_bandwidth_changed(self, index):
        """Handle bandwidth selection change"""
        bandwidth = self.bandwidth_combo.currentData()

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
        """Open the settings dialog"""
        settings_dialog = SettingsDialog(self.config, self)
        if settings_dialog.exec_() == QDialog.Accepted:
            # Apply settings
            self.config.save()

            # Refresh audio devices
            settings_dialog._refresh_audio_devices()

            # Update spectrum and waterfall views with new settings
            self.spectrum_view.update_settings(self.config)
            self.waterfall_view.update_settings(self.config)

            # Update modem with new settings
            self.modem_manager.apply_config()

            # Update spectrum refresh rate
            update_rate = self.config.get('ui', 'spectrum_update_rate')
            self.spectrum_timer.start(1000 // update_rate)  # Convert Hz to ms

    @pyqtSlot()
    def open_about_dialog(self):
        """Open about dialog"""
        QMessageBox.about(self, "About SSDigi Modem",
                        "SSDigi Modem\n"
                        "Version: 0.1.0\n\n"
                        "A digital modem application for amateur radio.\n"
                        "Powered by ARDOP protocol.\n\n"
                        "Copyright © 2025")

    def update_from_config(self):
        """Update UI components when configuration changes"""
        logger.info("Updating UI from configuration")

        # Update modem with current callsign
        if hasattr(self.modem_manager, 'update_from_config'):
            self.modem_manager.update_from_config()

        # Update UI elements that depend on configuration
        current_bw = self.config.get('modem', 'bandwidth')
        index = self.bandwidth_combo.findData(current_bw)
        if index >= 0:
            self.bandwidth_combo.setCurrentIndex(index)

        # Update status labels
        self.status_labels['mode'].setText(self.config.get('modem', 'mode'))
        self.status_labels['bandwidth'].setText(f"{self.config.get('modem', 'bandwidth')} Hz")

    def _send_message(self):
        """Send a text message"""
        if self.message_input.text():
            message = self.message_input.text()
            self.message_display.append(f"TX: {message}")
            self.modem_manager.send_text(message)
            self.message_input.clear()

    def _save_log(self):
        """Save the log to a file"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Log Files (*.log)")
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.log_text.toPlainText())
                self.status_bar.showMessage(f"Log saved to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error saving log: {str(e)}")

    def add_station(self, callsign, freq, snr, mode):
        """Add or update a station in the stations list"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        freq_str = f"{freq:.0f}"
        station_color = QColor(30, 30, 30)
        highlight_color = QColor(40, 80, 120)

        # Search for existing station
        for row in range(self.stations_table.rowCount()):
            if (self.stations_table.item(row, 0).text() == callsign and
                self.stations_table.item(row, 1).text() == freq_str):
                # Update existing station
                self.stations_table.item(row, 2).setText(str(snr))
                self.stations_table.item(row, 3).setText(mode)
                self.stations_table.item(row, 4).setText(current_time)

                # Highlight row briefly to show update
                for col in range(self.stations_table.columnCount()):
                    self.stations_table.item(row, col).setBackground(highlight_color)
                QTimer.singleShot(1000, lambda r=row: self._clear_highlight(r, station_color))
                return

        # Only add new station if auto-track is enabled and frequency is in range
        if not self.auto_track.isChecked():
            return

        if not self.track_all_freqs:
            # Check if frequency is within current modem bandwidth
            center_freq = self.config.get('modem', 'center_freq')
            bandwidth = self.config.get('modem', 'bandwidth')
            if abs(freq - center_freq) > bandwidth / 2:
                return

        # Add new station
        row = self.stations_table.rowCount()
        self.stations_table.insertRow(row)

        items = [
            QTableWidgetItem(callsign),
            QTableWidgetItem(freq_str),
            QTableWidgetItem(str(snr)),
            QTableWidgetItem(mode),
            QTableWidgetItem(current_time)
        ]

        # Make frequency and SNR sort numerically
        items[1].setData(Qt.UserRole, float(freq))
        items[2].setData(Qt.UserRole, float(snr))

        # Add items to row with background color
        for col, item in enumerate(items):
            item.setBackground(station_color)
            self.stations_table.setItem(row, col, item)

        # Sort by SNR descending
        self.stations_table.sortItems(2, Qt.DescendingOrder)

    def _clear_highlight(self, row, color):
        """Clear highlighting from a row"""
        if row < self.stations_table.rowCount():
            for col in range(self.stations_table.columnCount()):
                self.stations_table.item(row, col).setBackground(color)

    def _clear_inactive_stations(self):
        """Remove stations that haven't been heard in the last 10 minutes"""
        current_time = datetime.datetime.now()
        rows_to_remove = []

        for row in range(self.stations_table.rowCount()):
            last_heard = datetime.datetime.strptime(
                self.stations_table.item(row, 4).text(),
                "%H:%M:%S"
            ).replace(
                year=current_time.year,
                month=current_time.month,
                day=current_time.day
            )

            if (current_time - last_heard).total_seconds() > 600:  # 10 minutes
                rows_to_remove.append(row)

        # Remove rows from bottom to top to avoid index issues
        for row in sorted(rows_to_remove, reverse=True):
            self.stations_table.removeRow(row)