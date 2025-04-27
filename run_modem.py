#!/usr/bin/env python
"""
Launcher script for SSDigi-Modem application
"""
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now we can import from the ss_ham_modem package
from ssdigi_modem.main import main

# Run the application
if __name__ == "__main__":
    sys.exit(main())
