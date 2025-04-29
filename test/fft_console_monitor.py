#!/usr/bin/env python3
"""
ARDOP FFT Console Monitor
This script connects to ARDOP via UDP and prints FFT data statistics to the console
"""
import sys
import time
import logging
import argparse
import numpy as np

# Import the ArdopFFTReceiver class
sys.path.append('.')  # Add current directory to path
from ssdigi_modem.core.modems.ardop_fft_receiver import ArdopFFTReceiver

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def monitor_fft_data(host='127.0.0.1', port=8515):
    """Monitor FFT data from ARDOP and print statistics"""
    receiver = ArdopFFTReceiver(host=host, port=port)

    try:
        # Start the receiver
        if not receiver.start():
            logger.error(f"Failed to start FFT receiver on {host}:{port}")
            return

        logger.info(f"Waiting for FFT data from ARDOP on {host}:{port}...")

        # Counter for received packets
        packets_received = 0
        last_print_time = time.time()

        while True:
            # Check for FFT data
            fft_data = receiver.get_fft_data()

            if fft_data is not None and receiver.is_data_fresh():
                packets_received += 1

                # Print stats every second
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    # Calculate some basic statistics
                    min_val = np.min(fft_data)
                    max_val = np.max(fft_data)
                    mean_val = np.mean(fft_data)

                    # Print info
                    print(f"\rFFT data: size={len(fft_data)}, "
                          f"min={min_val:.6f}, max={max_val:.6f}, mean={mean_val:.6f}, "
                          f"packets={packets_received}", end='')

                    last_print_time = current_time

            # Short sleep to avoid CPU spinning
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Clean up
        receiver.stop()
        logger.info("FFT monitor stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARDOP FFT Console Monitor")
    parser.add_argument("--host", default="127.0.0.1", help="ARDOP host IP address")
    parser.add_argument("--port", type=int, default=8515, help="ARDOP UDP port for FFT data")
    args = parser.parse_args()

    monitor_fft_data(host=args.host, port=args.port)
