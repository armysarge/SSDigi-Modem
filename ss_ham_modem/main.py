#!/usr/bin/env python3
"""
Main entry point for the SS Ham Modem application.
"""
import sys
import os
import argparse
import logging
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from ss_ham_modem.ui.main_window import MainWindow
from ss_ham_modem.core.config import Config
from ss_ham_modem.utils.licensing import LicenseManager

def setup_logging():
    """Configure application logging"""
    log_dir = Path.home() / ".ss_ham_modem" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "ss_ham_modem.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="SS Ham Modem - Digital modem for amateur radio")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--license-file", help="Path to license file for premium features")

    return parser.parse_args()

def main():
    """Main application entry point"""
    # Parse command line arguments
    args = parse_arguments()

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting SS Ham Modem")

    # Load configuration
    config = Config()
    if args.config:
        config.load_from_file(args.config)
    else:
        config.load_default()

    # Initialize license manager
    license_manager = LicenseManager()
    if args.license_file:
        license_manager.activate(args.license_file)
    else:
        license_manager.check_existing_license()

    # If a valid license is present, enforce the callsign from the license
    licensed_callsign = license_manager.get_callsign()
    if licensed_callsign:
        logger.info(f"Valid license detected with callsign: {licensed_callsign}")
        config.enforce_licensed_callsign(licensed_callsign)
        # Save the configuration with the enforced callsign
        config.save()
        logger.info("License callsign enforced in configuration")
    else:
        logger.info("No licensed callsign detected, using configuration callsign")

    # Start Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("SS Ham Modem")
    app.setOrganizationName("XenoLabs Solutions")

    # Create and show main window
    main_window = MainWindow(config, license_manager)
    main_window.show()

    # Execute application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
