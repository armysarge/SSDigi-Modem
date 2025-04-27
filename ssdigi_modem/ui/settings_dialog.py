"""
Settings dialog for SSDigi Modem
"""
import os
import sys
import logging
import sounddevice as sd
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                         QFormLayout, QLabel, QLineEdit, QPushButton, 
                         QComboBox, QSpinBox, QCheckBox, QGroupBox, 
                         QTreeWidget, QTreeWidgetItem, QScrollArea, QWidget, 
                         QMessageBox, QDialogButtonBox, QSlider, QSplitter,
                         QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from ssdigi_modem.utils.ui_helpers import get_app_icon
from ssdigi_modem.core.audio_manager import AudioManager

# Setup logging
logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """Settings dialog for SSDigi Modem application"""    
    def __init__(self, config, parent=None):
        """Initialize settings dialog"""
        super().__init__(parent)
        self.config = config
        self.initialized = False
        self.current_page = None
        self.pages = {}  # Store created setting pages
        
        # Create shared widgets that are used across pages
        self.network_group = None  
        
        # Set window properties
        self.setWindowTitle("SSDigi Modem Settings")
        self.setMinimumSize(800, 600)  # More compact size while maintaining usability
        
        # Create the UI
        self._create_ui()
        
        # Schedule initialization for after the event loop starts
        QTimer.singleShot(100, self._refresh_audio_devices)
        QTimer.singleShot(200, self._load_settings)    
        
        # Center window
        self._center_dialog()
        
        # Schedule settings initialization
        def init_settings():
            self._refresh_audio_devices()
            self._load_settings()
            
        QTimer.singleShot(100, init_settings)
    
    def _center_dialog(self):
        """Center the dialog on screen in a cross-platform compatible way"""
        try:
            # Get the desktop widget which represents the whole screen
            desktop = QApplication.desktop()
            if desktop:
                # Get the screen geometry
                screen_geometry = desktop.screenGeometry()
                # Calculate center position
                x = (screen_geometry.width() - self.width()) // 2
                y = (screen_geometry.height() - self.height()) // 2
                # Move window
                self.move(x, y)
            else:
                # Fallback for newer Qt versions
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.availableGeometry()
                    x = (screen_geometry.width() - self.width()) // 2
                    y = (screen_geometry.height() - self.height()) // 2
                    self.move(x, y)
        except Exception as e:
            logger.warning(f"Could not center window: {e}")
            # If all else fails, at least try to position near the middle
            self.move(100, 100)
            
    def _center_window(self):
        """Center the window on the screen"""
        try:
            screen = QApplication.primaryScreen()
            if screen:
                center = screen.availableGeometry().center()
                geo = self.frameGeometry()
                geo.moveCenter(center)
                self.move(geo.topLeft())
        except Exception as e:
            logger.warning(f"Could not center window: {e}")
            # Fallback position
            self.move(100, 100)

    def _create_ui(self):
        """Create and set up the UI"""
        # Create main layout
        main_layout = QVBoxLayout(self)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Create tree widget for navigation
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setMinimumWidth(200)
        self.tree_widget.setMaximumWidth(250)        
        splitter.addWidget(self.tree_widget)

        # Create scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)       
        
        self.settings_container = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_container)
        self.settings_layout.setContentsMargins(10, 10, 10, 10)
        self.settings_layout.setSpacing(10)
        scroll_area.setWidget(self.settings_container)
        splitter.addWidget(scroll_area)        # Set up tree items
        audio_item = QTreeWidgetItem(["Audio"])
        modem_item = QTreeWidgetItem(["Modem"])
        ardop_item = QTreeWidgetItem(["ARDOP"])  # Changed to match page name
        station_item = QTreeWidgetItem(["Station"])
        hamlib_item = QTreeWidgetItem(["HAMLIB"])
        display_item = QTreeWidgetItem(["Display"])       
        for item in [audio_item, modem_item, ardop_item,
                    station_item, hamlib_item, display_item]:
            item.setIcon(0, QIcon())        
        self.tree_widget.addTopLevelItem(audio_item)
        self.tree_widget.addTopLevelItem(modem_item)
        modem_item.addChild(ardop_item)  # Add ARDOP as child of Modem
        self.tree_widget.addTopLevelItem(station_item)
        self.tree_widget.addTopLevelItem(hamlib_item)
        self.tree_widget.addTopLevelItem(display_item)

        # Expand all items by default
        self.tree_widget.expandAll()

        # Connect tree selection changed
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)    
        self._create_audio_page()
        self._create_modem_page()
        self._create_ardop_page() 
        self._create_station_page()
        self._create_hamlib_page()
        self._create_display_page()# Set up dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        button_box.rejected.connect(self.reject)
        apply_button = button_box.button(QDialogButtonBox.Apply)
        apply_button.clicked.connect(self._on_apply_clicked)        
        main_layout.addWidget(button_box)

        # Select first item by default
        self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        self._on_tree_item_clicked(self.tree_widget.topLevelItem(0))

        # Set splitter sizing
        splitter.setStretchFactor(1, 1)  # Make the right side stretch more
        splitter.setSizes([250, self.width() - 250])  # Initial split position

        # Set application icon
        try:
            icon_path = get_app_icon()
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}")
        
    def _on_tree_item_clicked(self, item):
        """Handle tree item selection"""
        page_name = item.text(0)
        self._show_page(page_name)

    def _show_page(self, page_name):
        """Show the selected settings page"""
        # Hide current page if exists
        if self.current_page:
            self.current_page.hide()
            self.settings_layout.removeWidget(self.current_page)

        # Show selected page
        page = self.pages.get(page_name)
        if page:
            self.settings_layout.addWidget(page)
            page.show()
            self.current_page = page

    def _create_page(self, name):
        """Create a new page widget"""
        page = QWidget()
        page.setLayout(QVBoxLayout())
        self.pages[name] = page
        return page

    def _create_audio_page(self):
        """Create audio settings page"""
        page = self._create_page("Audio")
        layout = page.layout()

        # Audio device selection
        device_group = QGroupBox("Audio Devices")
        device_layout = QFormLayout()
        
        # Create input combo
        self.input_combo = QComboBox()
        self.input_combo.setObjectName("input_combo")
        self.input_combo.addItem("System Default", -1)
        device_layout.addRow("Input Device:", self.input_combo)
        
        # Create output combo
        self.output_combo = QComboBox()
        self.output_combo.setObjectName("output_combo")
        self.output_combo.addItem("System Default", -1)
        device_layout.addRow("Output Device:", self.output_combo)

        # Add the rest of the audio settings
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

        # Add stretch at the end
        layout.addStretch(1)

    def _create_modem_page(self):
        """Create modem settings page"""
        page = self._create_page("Modem")
        layout = page.layout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Communication settings
        comm_group = QGroupBox("Communication Settings")
        comm_layout = QFormLayout()
        comm_layout.setSpacing(8)

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
        layout.addWidget(comm_group)
          # Add stretch to fill remaining space
        layout.addStretch(1)

    def _create_ardop_page(self):
        """Create ARDOP settings page with basic and advanced settings"""
        page = self._create_page("ARDOP Settings")
        layout = page.layout()

        # Basic ARDOP settings group
        basic_group = QGroupBox("ARDOP Mode")
        basic_layout = QFormLayout()

        # Internal/External ARDOP mode
        self.run_ardop_mode_combo = QComboBox()
        self.run_ardop_mode_combo.addItem("Run ARDOP Internally", "internal")
        self.run_ardop_mode_combo.addItem("Use External ARDOP", "external")
        self.run_ardop_mode_combo.currentIndexChanged.connect(self._on_ardop_mode_changed)
        basic_layout.addRow("ARDOP Mode:", self.run_ardop_mode_combo)

        # Create network settings group
        network_layout = QFormLayout()

        # IP Address
        self.ardop_ip_edit = QLineEdit()
        self.ardop_ip_edit.setPlaceholderText("127.0.0.1")
        self.ardop_ip_edit.setToolTip("IP address of external ARDOP modem")
        network_layout.addRow("ARDOP IP:", self.ardop_ip_edit)

        # Port
        self.ardop_port_spin = QSpinBox()
        self.ardop_port_spin.setRange(1, 65535)
        self.ardop_port_spin.setValue(8515)
        network_layout.addRow("ARDOP Port:", self.ardop_port_spin)

        # Create or update network group
        if not self.network_group:
            self.network_group = QGroupBox("Network Settings")
        self.network_group.setLayout(network_layout)
        basic_layout.addWidget(self.network_group)
        basic_group.setLayout(basic_layout)
        
        layout.addWidget(basic_group)

        # ARQ Settings Group
        arq_group = QGroupBox("ARQ Settings")
        arq_layout = QFormLayout()

        # Protocol Mode
        self.protocol_mode_combo = QComboBox()
        self.protocol_mode_combo.addItem("ARQ Mode", "ARQ")
        self.protocol_mode_combo.addItem("FEC Mode", "FEC")
        self.protocol_mode_combo.addItem("Receive Only", "RXO")
        arq_layout.addRow("Protocol Mode:", self.protocol_mode_combo)

        # ARQ timeout
        self.arq_timeout_spin = QSpinBox()
        self.arq_timeout_spin.setRange(30, 240)
        self.arq_timeout_spin.setSingleStep(10)
        self.arq_timeout_spin.setSuffix(" sec")
        arq_layout.addRow("ARQ Timeout:", self.arq_timeout_spin)

        arq_group.setLayout(arq_layout)
        layout.addWidget(arq_group)

        # Timing Settings Group
        timing_group = QGroupBox("Timing Settings")
        timing_layout = QFormLayout()

        # Leader length
        self.leader_spin = QSpinBox()
        self.leader_spin.setRange(120, 2500)
        self.leader_spin.setSingleStep(10)
        self.leader_spin.setSuffix(" ms")
        timing_layout.addRow("Leader Length:", self.leader_spin)

        # Trailer length
        self.trailer_spin = QSpinBox()
        self.trailer_spin.setRange(0, 200)
        self.trailer_spin.setSingleStep(5)
        self.trailer_spin.setSuffix(" ms")
        timing_layout.addRow("Trailer Length:", self.trailer_spin)

        timing_group.setLayout(timing_layout)
        layout.addWidget(timing_group)

        # Operation Settings Group
        operation_group = QGroupBox("Operation Settings")
        operation_layout = QFormLayout()

        # Basic settings
        self.cwid_check = QCheckBox()
        operation_layout.addRow("CW ID:", self.cwid_check)

        self.fsk_only_check = QCheckBox()
        operation_layout.addRow("FSK Only:", self.fsk_only_check)

        self.use600_check = QCheckBox()
        operation_layout.addRow("Use 600 Baud:", self.use600_check)

        operation_group.setLayout(operation_layout)
        layout.addWidget(operation_group)

        # Debug Settings Group
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QFormLayout()

        self.debug_log_check = QCheckBox()
        debug_layout.addRow("Debug Log:", self.debug_log_check)

        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        layout.addStretch()
        return page

    def _create_hamlib_page(self):
        """Create HAMLIB settings page"""
        page = self._create_page("HAMLIB")
        layout = page.layout()

        # Enable HAMLIB
        hamlib_group = QGroupBox("HAMLIB Control")
        hamlib_layout = QFormLayout()

        self.hamlib_enabled_check = QCheckBox()
        hamlib_layout.addRow("Enable HAMLIB:", self.hamlib_enabled_check)

        # Rig selection
        self.rig_model_combo = QComboBox()
        hamlib_layout.addRow("Rig Model:", self.rig_model_combo)

        # Serial settings
        self.port_edit = QLineEdit()
        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_edit)
        scan_button = QPushButton("Scan")
        scan_button.clicked.connect(self._scan_serial_ports)
        port_layout.addWidget(scan_button)
        hamlib_layout.addRow("Serial Port:", port_layout)

        self.baud_combo = QComboBox()
        for baud in [4800, 9600, 19200, 38400, 57600, 115200]:
            self.baud_combo.addItem(str(baud))
        hamlib_layout.addRow("Baud Rate:", self.baud_combo)

        self.ptt_combo = QComboBox()
        self.ptt_combo.addItems(["VOX", "RTS", "DTR", "CAT"])
        hamlib_layout.addRow("PTT Control:", self.ptt_combo)

        # Add test buttons
        test_layout = QHBoxLayout()
        ptt_on = QPushButton("Test PTT On")
        ptt_on.clicked.connect(self._ptt_on)
        ptt_off = QPushButton("Test PTT Off")
        ptt_off.clicked.connect(self._ptt_off)
        test_layout.addWidget(ptt_on)
        test_layout.addWidget(ptt_off)
        hamlib_layout.addRow("Test PTT:", test_layout)

        hamlib_group.setLayout(hamlib_layout)
        layout.addWidget(hamlib_group)
        layout.addStretch()

    def _create_display_page(self):
        """Create display settings page"""
        page = self._create_page("Display")
        layout = page.layout()

        # Waterfall display
        waterfall_group = QGroupBox("Waterfall Display")
        waterfall_layout = QFormLayout()

        self.waterfall_combo = QComboBox()
        self.waterfall_combo.addItems(["Default", "Viridis", "Hot", "Blue"])
        waterfall_layout.addRow("Color Scheme:", self.waterfall_combo)

        self.update_rate_spin = QSpinBox()
        self.update_rate_spin.setRange(1, 30)
        self.update_rate_spin.setSuffix(" Hz")
        waterfall_layout.addRow("Update Rate:", self.update_rate_spin)

        waterfall_group.setLayout(waterfall_layout)
        layout.addWidget(waterfall_group)

        # Spectrum display
        spectrum_group = QGroupBox("Spectrum Display")
        spectrum_layout = QFormLayout()

        self.show_freq_check = QCheckBox()
        spectrum_layout.addRow("Show Frequency Markers:", self.show_freq_check)

        self.show_grid_check = QCheckBox()
        spectrum_layout.addRow("Show Grid:", self.show_grid_check)

        self.fft_avg_spin = QSpinBox()
        self.fft_avg_spin.setRange(1, 10)
        spectrum_layout.addRow("FFT Averaging:", self.fft_avg_spin)

        self.spectrum_ref_spin = QSpinBox()
        self.spectrum_ref_spin.setRange(-120, 0)
        self.spectrum_ref_spin.setSuffix(" dB")
        spectrum_layout.addRow("Reference Level:", self.spectrum_ref_spin)

        self.spectrum_range_spin = QSpinBox()
        self.spectrum_range_spin.setRange(30, 120)
        self.spectrum_range_spin.setSuffix(" dB")
        spectrum_layout.addRow("Display Range:", self.spectrum_range_spin)

        spectrum_group.setLayout(spectrum_layout)
        layout.addWidget(spectrum_group)

        layout.addStretch()

    def _on_mode_changed(self):
        """Handle modem mode change"""
        current_mode = self.mode_combo.currentData()

        # Show/hide ARDOP related items in the tree
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item.text(0) == "ARDOP Settings":
                item.setHidden(current_mode != "ARDOP")

        # If current page is ARDOP and mode is not ARDOP,
        # switch to Modem page
        if current_mode != "ARDOP" and self.current_page:
            current_name = [k for k, v in self.pages.items() if v == self.current_page][0]
            if "ARDOP" in current_name:
                self._show_page("Modem")

    def _on_ardop_mode_changed(self, index):
        """Handle ARDOP mode change between internal and external"""
        mode = self.run_ardop_mode_combo.currentData()
        # Show/hide network settings based on mode
        self.network_group.setVisible(mode == "external")
            
    def _reset_modem_settings(self):
        """Reset modem settings to defaults"""
        try:
            # Reset basic modem settings
            self.bandwidth_combo.setCurrentText("500 Hz")
            self.center_freq_spin.setValue(1500)

            QMessageBox.information(self, "Settings Reset", 
                                  "Modem settings have been reset to defaults.")
            
            logger.info("Modem settings reset to defaults")
        except Exception as e:
            logger.exception("Error resetting modem settings")
            QMessageBox.warning(self, "Error", 
                              f"Failed to reset settings: {str(e)}")

    def _reset_ardop_settings(self):
        """Reset ARDOP-specific settings to defaults"""
        try:
            # Reset ARDOP mode and protocol settings
            self.run_ardop_mode_combo.setCurrentIndex(0)  # Internal mode
            self.protocol_mode_combo.setCurrentIndex(0)  # ARQ Mode
            self.arq_timeout_spin.setValue(120)          # 120 seconds

            # Reset timing settings
            self.leader_spin.setValue(120)               # 120 ms
            self.trailer_spin.setValue(0)                # 0 ms

            # Reset operation settings
            self.cwid_check.setChecked(False)           # CW ID off
            self.fsk_only_check.setChecked(False)       # FSK only off
            self.use600_check.setChecked(False)         # 600 baud modes off
            self.debug_log_check.setChecked(False)      # Debug log off

            QMessageBox.information(self, "Settings Reset",
                                  "ARDOP settings have been reset to defaults.")
            
            logger.info("ARDOP settings reset to defaults")

        except Exception as e:
            logger.exception("Error resetting ARDOP settings")
            QMessageBox.warning(self, "Error",
                              "Failed to reset ARDOP settings: {str(e)}")

    def _apply_settings(self):
        """Apply settings to config"""
        try:
            # Audio settings
            self.config.set('audio', 'sample_rate', self.sample_rate_combo.currentData())
            self.config.set('audio', 'channels', self.channels_combo.currentData())
            self.config.set('audio', 'buffer_size', self.buffer_spin.value())
            self.config.set('audio', 'input_device', self.input_combo.currentData())
            self.config.set('audio', 'output_device', self.output_combo.currentData())
            self.config.set('audio', 'tx_level', self.tx_level_slider.value() / 100.0)            # Modem settings
            self.config.set('modem', 'mode', self.mode_combo.currentData())
            self.config.set('modem', 'bandwidth', self.bandwidth_combo.currentData())
            self.config.set('modem', 'center_freq', self.center_freq_spin.value())     
            self.config.set('modem', 'ardop_mode', self.run_ardop_mode_combo.currentData())
            
            # ARDOP network settings
            self.config.set('modem', 'ardop_ip', self.ardop_ip_edit.text())
            self.config.set('modem', 'ardop_port', self.ardop_port_spin.value())
              
            for attr, setting in {
                'protocol_mode_combo': 'protocol_mode',
                'arq_timeout_spin': 'arq_timeout',
                'leader_spin': 'leader',
                'trailer_spin': 'trailer',
                'cwid_check': 'cwid',
                'fsk_only_check': 'fskonly',
                'use600_check': 'use600modes',
                'debug_log_check': 'debug_log'
            }.items():
                if hasattr(self, attr):
                    value = getattr(self, attr)
                    if isinstance(value, QCheckBox):
                        self.config.set('modem', setting, value.isChecked())
                    elif isinstance(value, (QSpinBox, QComboBox)):
                        self.config.set('modem', setting, value.value() if isinstance(value, QSpinBox) else value.currentText())

            # HAMLIB settings
            self.config.set('hamlib', 'enabled', self.hamlib_enabled_check.isChecked())
            self.config.set('hamlib', 'port', self.port_edit.text())
            self.config.set('hamlib', 'baud_rate', int(self.baud_combo.currentText()))
            self.config.set('hamlib', 'ptt_control', self.ptt_combo.currentText())

            # Display settings
            self.config.set('display', 'waterfall_colors', self.waterfall_combo.currentText())
            self.config.set('display', 'show_freq_markers', self.show_freq_check.isChecked())
            self.config.set('display', 'show_grid', self.show_grid_check.isChecked())
            self.config.set('display', 'update_rate', self.update_rate_spin.value())
            self.config.set('display', 'fft_average', self.fft_avg_spin.value())
            self.config.set('display', 'ref_level', self.spectrum_ref_spin.value())
            self.config.set('display', 'range', self.spectrum_range_spin.value())

            # Station settings
            self.config.set('station', 'callsign', self.callsign_edit.text().upper())
            self.config.set('station', 'fullname', self.fullname_edit.text())
            self.config.set('station', 'email', self.email_edit.text())
            self.config.set('station', 'city', self.city_edit.text())
            self.config.set('station', 'grid_square', self.grid_square_edit.text())

            self.config.save()
            return True
        except Exception as e:
            logger.exception("Error applying settings")
            QMessageBox.warning(self, "Error", 
                              f"Failed to apply settings: {str(e)}")
            return False

    def _on_apply_clicked(self):
        """Handle Apply button click"""
        if self._apply_settings():
            QMessageBox.information(self, "Settings Saved",
                                  "Settings have been applied successfully.")

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
            QMessageBox.warning(self, "Error", f"Failed to test PTT: {str(e)}")

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
            QMessageBox.warning(self, "Error", f"Failed to test PTT: {str(e)}")    
    def showEvent(self, event):
        """Show event handler - ensure dialog is properly positioned"""
        super().showEvent(event)
        
        # Get the screen size and dialog size
        desktop = QApplication.primaryScreen()
        if desktop:
            geom = desktop.geometry()
            # Ensure dialog fits within screen bounds
            if geom.width() < self.width():
                self.resize(geom.width() * 0.9, self.height())
            if geom.height() < self.height():
                self.resize(self.width(), geom.height() * 0.9)
            # Center on screen
            frame = self.frameGeometry()
            frame.moveCenter(geom.center())
            self.move(frame.topLeft())

    def _reset_modem_settings(self):
        """Reset modem settings to defaults"""
        try:
            # Reset ARDOP specific settings
            self.bandwidth_combo.setCurrentText("500 Hz")
            self.center_freq_spin.setValue(1500)
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

    def _initialize_settings(self):
        """Initialize settings after UI is fully created"""
        # First refresh audio devices
        self._refresh_audio_devices()
        # Then load all settings
        self._load_settings()
        # Finally center the window
        self._center_window()

    def _initialize_ui(self):
        """Initialize UI components with default values"""
        try:
            if hasattr(self, 'sample_rate_combo'):
                self.sample_rate_combo.setCurrentIndex(0)
            if hasattr(self, 'channels_combo'):
                self.channels_combo.setCurrentIndex(0)
            if hasattr(self, 'input_combo'):
                self.input_combo.setCurrentIndex(0)
            if hasattr(self, 'output_combo'):
                self.output_combo.setCurrentIndex(0)
                
            # Now load the actual settings
            self._load_settings()
            
        except Exception as e:
            logger.exception("Error initializing UI")
            QMessageBox.warning(self, "Error", f"Failed to initialize settings: {str(e)}")

    def _create_station_page(self):
        """Create station settings page"""
        page = self._create_page("Station")
        layout = page.layout()
        
        # Station details group
        station_group = QGroupBox("Station Details")
        station_layout = QFormLayout()

        # Callsign
        self.callsign_edit = QLineEdit()
        self.callsign_edit.setMaxLength(10)
        station_layout.addRow("Callsign:", self.callsign_edit)

        # Full Name
        self.fullname_edit = QLineEdit()
        self.fullname_edit.setMaxLength(50)
        station_layout.addRow("Full Name:", self.fullname_edit)

        # Email
        self.email_edit = QLineEdit()
        self.email_edit.setMaxLength(100)
        station_layout.addRow("Email:", self.email_edit)

        # City
        self.city_edit = QLineEdit()
        self.city_edit.setMaxLength(50)
        station_layout.addRow("City:", self.city_edit)

        # Grid Square
        self.grid_square_edit = QLineEdit()
        self.grid_square_edit.setMaxLength(6)
        self.grid_square_edit.setToolTip("Grid square is the location of your station")
        station_layout.addRow("Grid Square:", self.grid_square_edit)

        # Set the layout
        station_group.setLayout(station_layout)
        layout.addWidget(station_group)
        layout.addStretch(1)    
    
    def _refresh_audio_devices(self):
        """Refresh available audio devices in a cross-platform compatible way"""
        try:
            # Store current selections
            current_input = self.input_combo.currentData() if self.input_combo.currentData() else -1
            current_output = self.output_combo.currentData() if self.output_combo.currentData() else -1

            # Clear existing items
            self.input_combo.clear()
            self.output_combo.clear()

            # Add system default options
            self.input_combo.addItem("System Default", -1)
            self.output_combo.addItem("System Default", -1)

            # Add some common device names as placeholders until we can properly detect
            self.input_combo.addItem("Microphone", 1)
            self.input_combo.addItem("Line In", 2)
            self.output_combo.addItem("Speakers", 1)
            self.output_combo.addItem("Headphones", 2)

            # Try to restore previous selection
            input_idx = self.input_combo.findData(current_input)
            if input_idx < 0:
                input_idx = self.input_combo.findData(self.config.get('audio', 'input_device', -1))
            if input_idx < 0:
                input_idx = 0
            self.input_combo.setCurrentIndex(input_idx)

            output_idx = self.output_combo.findData(current_output)
            if output_idx < 0:
                output_idx = self.output_combo.findData(self.config.get('audio', 'output_device', -1))
            if output_idx < 0:
                output_idx = 0
            self.output_combo.setCurrentIndex(output_idx)

            try:
                
                # Get input devices
                input_devices = []
                for i, device in enumerate(sd.query_devices()):
                    if device['max_input_channels'] > 0:
                        name = device['name']
                        if not any(x in name.lower() for x in ['virtual', 'vb-audio']):
                            input_devices.append((name, i))

                # Get output devices                
                output_devices = []
                for i, device in enumerate(sd.query_devices()):
                    if device['max_output_channels'] > 0:
                        name = device['name']
                        if not any(x in name.lower() for x in ['virtual', 'vb-audio']):
                            output_devices.append((name, i))

                # Sort devices by name
                input_devices.sort(key=lambda x: x[0])
                output_devices.sort(key=lambda x: x[0])

                # Add input devices
                for name, idx in input_devices:
                    self.input_combo.addItem(name, idx)

                # Add output devices
                for name, idx in output_devices:
                    self.output_combo.addItem(name, idx)

                # Try to restore previous selection
                input_idx = self.input_combo.findData(current_input)
                if input_idx < 0:
                    input_idx = self.input_combo.findData(self.config.get('audio', 'input_device', -1))
                if input_idx < 0:
                    input_idx = 0
                self.input_combo.setCurrentIndex(input_idx)

                output_idx = self.output_combo.findData(current_output)
                if output_idx < 0:
                    output_idx = self.output_combo.findData(self.config.get('audio', 'output_device', -1))
                if output_idx < 0:
                    output_idx = 0
                self.output_combo.setCurrentIndex(output_idx)

            except Exception as e:
                logger.error(f"Error querying audio devices: {e}")
                # Add placeholder items
                self.input_combo.addItem("No devices found", -1)
                self.output_combo.addItem("No devices found", -1)

        except Exception as e:
            logger.exception("Error refreshing audio devices")
            QMessageBox.warning(self, "Error",
                              f"Failed to refresh audio devices: {str(e)}")

    def _load_settings(self):
        """Load settings from config into UI"""
        try:
            # Load audio settings
            self.sample_rate_combo.setCurrentText(f"{self.config.get('audio', 'sample_rate', 48000)} Hz")
            self.channels_combo.setCurrentIndex(self.config.get('audio', 'channels', 1) - 1)
            self.buffer_spin.setValue(self.config.get('audio', 'buffer_size', 1024))
            
            # Load modem settings
            tx_level = int(self.config.get('modem', 'tx_level', 0.5) * 100)
            self.tx_level_slider.setValue(tx_level)

            # Set mode
            mode = self.config.get('modem', 'mode', 'ARDOP')
            mode_index = self.mode_combo.findData(mode)
            if mode_index >= 0:
                self.mode_combo.setCurrentIndex(mode_index)

            # Load ARDOP mode and network settings
            ardop_mode = self.config.get('modem', 'ardop_mode', 'internal')
            mode_index = self.run_ardop_mode_combo.findData(ardop_mode)
            if mode_index >= 0:
                self.run_ardop_mode_combo.setCurrentIndex(mode_index)
                self._on_ardop_mode_changed(mode_index)

            # Load network settings
            self.ardop_ip_edit.setText(self.config.get('modem', 'ardop_ip', '127.0.0.1'))
            self.ardop_port_spin.setValue(self.config.get('modem', 'ardop_port', 8515))

            # Set bandwidth
            bw = self.config.get('modem', 'bandwidth', 500)
            bw_index = self.bandwidth_combo.findData(bw)
            if bw_index >= 0:
                self.bandwidth_combo.setCurrentIndex(bw_index)

            # Set center frequency
            self.center_freq_spin.setValue(self.config.get('modem', 'center_freq', 1500))

            # Load ARDOP protocol settings
            if hasattr(self, 'protocol_mode_combo'):
                self.protocol_mode_combo.setCurrentText(self.config.get('modem', 'protocol_mode', 'ARQ'))
            if hasattr(self, 'arq_timeout_spin'):
                self.arq_timeout_spin.setValue(self.config.get('modem', 'arq_timeout', 120))
            if hasattr(self, 'leader_spin'):
                self.leader_spin.setValue(self.config.get('modem', 'leader', 120))
            if hasattr(self, 'trailer_spin'):
                self.trailer_spin.setValue(self.config.get('modem', 'trailer', 0))
            if hasattr(self, 'cwid_check'):
                self.cwid_check.setChecked(self.config.get('modem', 'cwid', False))
            if hasattr(self, 'fsk_only_check'):
                self.fsk_only_check.setChecked(self.config.get('modem', 'fskonly', False))
            if hasattr(self, 'use600_check'):
                self.use600_check.setChecked(self.config.get('modem', 'use600modes', False))
            if hasattr(self, 'debug_log_check'):
                self.debug_log_check.setChecked(self.config.get('modem', 'debug_log', False))

            # HAMLIB settings
            self.hamlib_enabled_check.setChecked(self.config.get('hamlib', 'enabled', False))
            self.port_edit.setText(self.config.get('hamlib', 'port', ''))
            self.baud_combo.setCurrentText(str(self.config.get('hamlib', 'baud_rate', 9600)))
            self.ptt_combo.setCurrentText(self.config.get('hamlib', 'ptt_control', 'CAT'))

            # Display settings
            self.waterfall_combo.setCurrentText(self.config.get('display', 'waterfall_colors', 'Default'))
            self.show_freq_check.setChecked(self.config.get('display', 'show_freq_markers', True))
            self.show_grid_check.setChecked(self.config.get('display', 'show_grid', True))
            self.update_rate_spin.setValue(self.config.get('display', 'update_rate', 10))
            self.fft_avg_spin.setValue(self.config.get('display', 'fft_average', 2))
            self.spectrum_ref_spin.setValue(self.config.get('display', 'ref_level', -60))
            self.spectrum_range_spin.setValue(self.config.get('display', 'range', 70))

            # Station settings
            self.callsign_edit.setText(self.config.get('station', 'callsign', '').upper())
            self.fullname_edit.setText(self.config.get('station', 'fullname', ''))
            self.email_edit.setText(self.config.get('station', 'email', ''))
            self.city_edit.setText(self.config.get('station', 'city', ''))
            self.grid_square_edit.setText(self.config.get('station', 'grid_square', ''))

        except Exception as e:
            logger.exception("Error loading settings")
            QMessageBox.warning(self, "Error", 
                              f"Failed to load settings: {str(e)}")

    def _browse_log_dir(self):
        """Browse for log directory"""
        try:
            current_dir = self.log_dir_edit.text() or os.path.expanduser("~")
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Log Directory",
                current_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if directory:
                self.log_dir_edit.setText(directory)
        except Exception as e:
            logger.exception("Error browsing for log directory")
            QMessageBox.warning(self, "Error",
                              f"Failed to browse for directory: {str(e)}")

    def _scan_serial_ports(self):
        """Scan for available serial ports"""
        try:
            ports = []
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
            
            if ports:
                self.port_edit.setText(ports[0])  # Set first port as default
                port_list = "\n".join(ports)
                QMessageBox.information(self, "Available Ports", 
                                      f"Found ports:\n{port_list}")
            else:
                QMessageBox.warning(self, "No Ports", 
                                  "No serial ports found")
        except Exception as e:
            logger.exception("Error scanning serial ports")
            QMessageBox.warning(self, "Error",
                              f"Failed to scan serial ports: {str(e)}")
