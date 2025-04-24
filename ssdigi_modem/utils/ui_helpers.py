"""
UI helper utilities for SSDigi Modem
"""
import os
import logging

logger = logging.getLogger(__name__)

def get_app_icon():
    """Get the application icon path"""
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "resources", "icons", "ssdigi_modem.ico")
    if os.path.exists(icon_path):
        return icon_path
    else:
        logger.warning(f"Application icon not found at {icon_path}")
        return None
