"""
Modem factory module for creating appropriate modem instances based on configuration
"""
import logging
from ssdigi_modem.core.modems.ardop.ardop_modem import ArdopModem

logger = logging.getLogger(__name__)

class ModemFactory:
    """Factory class for creating appropriate modem instances"""

    @staticmethod
    def create_modem(mode, config, hamlib_manager=None):
        """Create and return the appropriate modem based on mode

        Args:
            mode (str): The modem mode to create ('ARDOP', etc.)
            config: Configuration object
            hamlib_manager: Optional hamlib manager instance

        Returns:
            BaseModem: A modem instance of the appropriate type
        """
        mode = mode.upper()

        if mode == 'ARDOP':
            logger.info("Creating ARDOP modem instance")
            return ArdopModem(config, hamlib_manager)
        else:
            logger.warning(f"Unknown modem mode: {mode}, falling back to ARDOP")
            return ArdopModem(config, hamlib_manager)
