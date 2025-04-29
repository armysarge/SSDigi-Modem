#!/usr/bin/env python3
"""
ARDOP FFT Visualizer
This script connects to ARDOP via UDP and displays the FFT data as it arrives
"""
import sys
import time
import logging
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Import the ArdopFFTReceiver class
sys.path.append('.')  # Add current directory to path
from ssdigi_modem.core.modems.ardop_fft_receiver import ArdopFFTReceiver

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FFTVisualizer:
    """Visualizes FFT data from ARDOP in real-time"""

    def __init__(self, host='127.0.0.1', port=8515):
        """Initialize the FFT visualizer"""
        self.receiver = ArdopFFTReceiver(host=host, port=port)

        # Create figure for visualization
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.line, = self.ax.plot([], [], lw=2)

        # Set up the plot
        self.ax.set_title(f'ARDOP FFT Data (from {host}:{port})')
        self.ax.set_xlabel('Frequency Bin')
        self.ax.set_ylabel('Magnitude')
        self.ax.grid(True)

        # X axis will be set once we know the FFT size
        self.ax.set_ylim(0, 1)  # Will auto-adjust later

        # Initialize the receiver
        self.receiver.start()
        logger.info(f"Waiting for FFT data from ARDOP on {host}:{port}...")

        # Counter for received packets
        self.packets_received = 0
        self.last_packets_counted = 0
        self.last_count_time = time.time()

    def update_plot(self, frame):
        """Update function for animation"""
        fft_data = self.receiver.get_fft_data()

        if fft_data is not None:
            # Count packets
            self.packets_received += 1

            # Calculate packets per second every 5 seconds
            current_time = time.time()
            if current_time - self.last_count_time >= 5:
                packets_per_second = (self.packets_received - self.last_packets_counted) / (current_time - self.last_count_time)
                logger.info(f"Receiving {packets_per_second:.2f} FFT packets per second")
                self.last_packets_counted = self.packets_received
                self.last_count_time = current_time

            # Normalize if needed (values should be from 0 to 1 for clean display)
            max_val = np.max(fft_data)
            if max_val > 0:
                normalized_data = fft_data / max_val
            else:
                normalized_data = fft_data

            # Set x-axis range on first valid data
            if len(self.line.get_xdata()) == 0:
                x = np.arange(len(normalized_data))
                self.line.set_xdata(x)
                self.ax.set_xlim(0, len(normalized_data))

            # Update y-data
            self.line.set_ydata(normalized_data)

            # Update title with status
            self.ax.set_title(f'ARDOP FFT Data - {len(normalized_data)} points - {self.packets_received} packets received')

            # Return the artist that was updated
            return [self.line]

        # Always return the artist, even if no update was made
        return [self.line]


    def run(self):
        """Run the visualizer with animation"""
        try:
            # Create animation that calls update_plot() every 50ms
            self.ani = FuncAnimation(
                self.fig,
                self.update_plot,
                interval=50,  # Update every 50ms
                blit=True,
                save_count=100  # Limit the cache to 100 frames
            )

            # Show the plot (this blocks until window is closed)
            plt.show()

        finally:
            # Clean up when window is closed
            self.receiver.stop()
            logger.info("FFT visualizer stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARDOP FFT Visualizer")
    parser.add_argument("--host", default="127.0.0.1", help="ARDOP host IP address")
    parser.add_argument("--port", type=int, default=8515, help="ARDOP UDP port for FFT data")
    args = parser.parse_args()

    try:
        # Start the visualizer
        visualizer = FFTVisualizer(host=args.host, port=args.port)
        visualizer.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
