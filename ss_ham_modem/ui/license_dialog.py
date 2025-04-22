"""
License dialog for SS Ham Modem
"""
import logging
import os
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QLineEdit, QFormLayout, QGroupBox,
                            QDialogButtonBox, QMessageBox, QTabWidget,
                            QTextEdit, QWidget, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSlot, QUrl
from PyQt5.QtGui import QDesktopServices

logger = logging.getLogger(__name__)

class LicenseDialog(QDialog):
    """License dialog for SS Ham Modem application"""

    def __init__(self, license_manager, parent=None):
        """Initialize license dialog"""
        super().__init__(parent)

        self.license_manager = license_manager

        # Create UI
        self.setWindowTitle("SS Ham Modem License")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        # Create layout
        main_layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create license tabs
        self._create_status_tab()
        self._create_activation_tab()
        self._create_features_tab()
        self._create_purchase_tab()

        # Create dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # Update license info
        self._update_license_info()

    def _create_status_tab(self):
        """Create license status tab"""
        status_tab = QWidget()
        layout = QVBoxLayout(status_tab)

        # License information
        info_group = QGroupBox("License Information")
        info_layout = QFormLayout()

        self.status_label = QLabel("Free Version")
        self.name_label = QLabel("Not licensed")
        self.expiry_label = QLabel("N/A")
        self.machine_id_label = QLabel(self.license_manager.machine_id)

        info_layout.addRow("Status:", self.status_label)
        info_layout.addRow("Licensed To:", self.name_label)
        info_layout.addRow("Expiry Date:", self.expiry_label)
        info_layout.addRow("Machine ID:", self.machine_id_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Deactivate button
        self.deactivate_button = QPushButton("Deactivate License")
        self.deactivate_button.clicked.connect(self._deactivate_license)
        layout.addWidget(self.deactivate_button)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(status_tab, "Status")

    def _create_activation_tab(self):
        """Create license activation tab"""
        activation_tab = QWidget()
        layout = QVBoxLayout(activation_tab)

        # Activation form
        activation_group = QGroupBox("License Activation")
        activation_layout = QFormLayout()

        self.license_key_edit = QLineEdit()
        self.license_key_edit.setPlaceholderText("Enter your license key here")

        activation_layout.addRow("License Key:", self.license_key_edit)

        # Activation button
        self.activate_button = QPushButton("Activate License")
        self.activate_button.clicked.connect(self._activate_license)
        activation_layout.addRow("", self.activate_button)

        activation_group.setLayout(activation_layout)
        layout.addWidget(activation_group)

        # Note about license
        note_label = QLabel(
            "Note: License is tied to this machine. If you need to transfer your "
            "license to another machine, please deactivate it first and then "
            "contact support for assistance."
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(activation_tab, "Activation")

    def _create_features_tab(self):
        """Create features tab"""
        features_tab = QWidget()
        layout = QVBoxLayout(features_tab)

        # Features explanation
        features_label = QLabel(
            "SS Ham Modem is available in different tiers with increasing capabilities. "
            "Upgrade your license to unlock more features and higher performance limits."
        )
        features_label.setWordWrap(True)
        layout.addWidget(features_label)

        # Feature comparison table
        comparison_group = QGroupBox("Feature Comparison")
        comparison_layout = QVBoxLayout()

        # Create feature comparison as text
        comparison_text = QTextEdit()
        comparison_text.setReadOnly(True)
        comparison_text.setHtml("""
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
        </style>
        <table>
            <tr>
                <th>Feature</th>
                <th>Free</th>
                <th>Basic</th>
                <th>Pro</th>
            </tr>
            <tr>
                <td>Max Bandwidth</td>
                <td>500 Hz</td>
                <td>2000 Hz</td>
                <td>5000 Hz</td>
            </tr>
            <tr>
                <td>Max Speed</td>
                <td>600 bps</td>
                <td>3600 bps</td>
                <td>9600 bps</td>
            </tr>
            <tr>
                <td>Waterfall Display</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
            </tr>
            <tr>
                <td>Advanced Filters</td>
                <td>✗</td>
                <td>✗</td>
                <td>✓</td>
            </tr>
            <tr>
                <td>WAV Import/Export</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
            </tr>
            <tr>
                <td>Batch Processing</td>
                <td>✗</td>
                <td>✗</td>
                <td>✓</td>
            </tr>
        </table>
        """)

        comparison_layout.addWidget(comparison_text)
        comparison_group.setLayout(comparison_layout)
        layout.addWidget(comparison_group)

        # Current tier
        current_tier_group = QGroupBox("Your Current Tier")
        current_tier_layout = QVBoxLayout()

        self.tier_label = QLabel("Free")
        self.tier_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.tier_label.setAlignment(Qt.AlignCenter)

        self.tier_features = QLabel(
            "Max Bandwidth: 500 Hz\nMax Speed: 600 bps"
        )
        self.tier_features.setAlignment(Qt.AlignCenter)

        current_tier_layout.addWidget(self.tier_label)
        current_tier_layout.addWidget(self.tier_features)

        current_tier_group.setLayout(current_tier_layout)
        layout.addWidget(current_tier_group)

        # Add to tab widget
        self.tab_widget.addTab(features_tab, "Features")

    def _create_purchase_tab(self):
        """Create purchase tab"""
        purchase_tab = QWidget()
        layout = QVBoxLayout(purchase_tab)

        # Purchase information
        purchase_label = QLabel(
            "Upgrade your SS Ham Modem to unlock additional features and capabilities. "
            "Choose the tier that best fits your needs."
        )
        purchase_label.setWordWrap(True)
        layout.addWidget(purchase_label)

        # Pricing table
        pricing_group = QGroupBox("Pricing")
        pricing_layout = QVBoxLayout()

        pricing_text = QTextEdit()
        pricing_text.setReadOnly(True)
        pricing_text.setHtml("""
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
        </style>
        <table>
            <tr>
                <th>Tier</th>
                <th>Price</th>
                <th>License Type</th>
            </tr>
            <tr>
                <td>Basic</td>
                <td>$19.99</td>
                <td>Perpetual, 1 year of updates</td>
            </tr>
            <tr>
                <td>Pro</td>
                <td>$39.99</td>
                <td>Perpetual, 1 year of updates</td>
            </tr>
            <tr>
                <td>Update Extension</td>
                <td>$14.99/year</td>
                <td>Extends update eligibility</td>
            </tr>
        </table>
        """)

        pricing_layout.addWidget(pricing_text)
        pricing_group.setLayout(pricing_layout)
        layout.addWidget(pricing_group)

        # Purchase buttons
        buttons_layout = QHBoxLayout()

        self.buy_basic_button = QPushButton("Buy Basic License")
        self.buy_basic_button.clicked.connect(self._open_basic_purchase)

        self.buy_pro_button = QPushButton("Buy Pro License")
        self.buy_pro_button.clicked.connect(self._open_pro_purchase)

        buttons_layout.addWidget(self.buy_basic_button)
        buttons_layout.addWidget(self.buy_pro_button)
        layout.addLayout(buttons_layout)

        # Add stretch
        layout.addStretch(1)

        # Add to tab widget
        self.tab_widget.addTab(purchase_tab, "Purchase")

    def _update_license_info(self):
        """Update license information display"""
        try:
            # Get license information
            license_info = self.license_manager.get_license_info()

            # Update status tab
            self.status_label.setText(f"{license_info['tier'].capitalize()} Version")

            if license_info['licensed_to']:
                self.name_label.setText(license_info['licensed_to'])
            else:
                self.name_label.setText("Not licensed")

            if license_info['expiration_date']:
                exp_date = datetime.datetime.fromisoformat(license_info['expiration_date'])
                self.expiry_label.setText(exp_date.strftime("%Y-%m-%d"))
            else:
                self.expiry_label.setText("N/A")

            # Update features tab
            self.tier_label.setText(license_info['tier'].capitalize())

            features = license_info['features']
            features_text = f"Max Bandwidth: {features['max_bandwidth']} Hz\n"
            features_text += f"Max Speed: {features['max_speed']} bps\n"

            for feature, enabled in features.items():
                if feature not in ['max_bandwidth', 'max_speed'] and enabled:
                    features_text += f"{feature.replace('_', ' ').capitalize()}: Enabled\n"

            self.tier_features.setText(features_text)

            # Enable/disable buttons based on license status
            if license_info['tier'] == 'free':
                self.deactivate_button.setEnabled(False)
            else:
                self.deactivate_button.setEnabled(True)

        except Exception as e:
            logger.exception(f"Error updating license info: {e}")

    @pyqtSlot()
    def _activate_license(self):
        """Activate license with entered key"""
        license_key = self.license_key_edit.text().strip()

        if not license_key:
            QMessageBox.warning(self, "Activation Error", "Please enter a license key.")
            return

        try:
            # Show progress dialog
            progress = QProgressBar(self)
            progress.setRange(0, 0)  # Indeterminate
            progress.setTextVisible(False)

            layout = self.layout()
            layout.addWidget(progress)

            # Process activation
            if self.license_manager.activate(license_key):
                # Remove progress bar
                progress.setParent(None)

                QMessageBox.information(self, "License Activated",
                                      "Your license has been activated successfully!")

                # Update license info display
                self._update_license_info()

                # Switch to status tab
                self.tab_widget.setCurrentIndex(0)

                # Clear license key field
                self.license_key_edit.clear()
            else:
                # Remove progress bar
                progress.setParent(None)

                QMessageBox.warning(self, "Activation Failed",
                                  "Failed to activate license. Please check your license key and try again.")
        except Exception as e:
            logger.exception(f"Error activating license: {e}")
            QMessageBox.critical(self, "Activation Error",
                               f"An error occurred during activation: {str(e)}")

    @pyqtSlot()
    def _deactivate_license(self):
        """Deactivate current license"""
        reply = QMessageBox.question(self, "Deactivate License",
                                    "Are you sure you want to deactivate your license? "
                                    "The application will revert to the free version.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                if self.license_manager.deactivate():
                    QMessageBox.information(self, "License Deactivated",
                                          "Your license has been deactivated successfully.")

                    # Update license info display
                    self._update_license_info()
                else:
                    QMessageBox.warning(self, "Deactivation Failed",
                                      "Failed to deactivate license.")
            except Exception as e:
                logger.exception(f"Error deactivating license: {e}")
                QMessageBox.critical(self, "Deactivation Error",
                                   f"An error occurred during deactivation: {str(e)}")

    @pyqtSlot()
    def _open_basic_purchase(self):
        """Open browser to purchase basic license"""
        url = QUrl("https://www.SS Ham Modem.com/purchase/basic")
        QDesktopServices.openUrl(url)

    @pyqtSlot()
    def _open_pro_purchase(self):
        """Open browser to purchase pro license"""
        url = QUrl("https://www.SS Ham Modem.com/purchase/pro")
        QDesktopServices.openUrl(url)
