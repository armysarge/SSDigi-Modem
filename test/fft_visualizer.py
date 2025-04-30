#!/usr/bin/env python3
"""
ARDOP FFT Visualizer
This script connects to ARDOP via UDP and displays the FFT data as it arrives
"""
import sys
import time
import logging
import argparse
import socket
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

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
        self.host = host
        self.port = port

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

        # Set up UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.settimeout(0.05)  # 50ms timeout for animation refresh

        logger.info(f"Waiting for FFT data from ARDOP on {host}:{port}...")

        # Counter for received packets
        self.packets_received = 0
        self.last_packets_counted = 0
        self.last_count_time = time.time()

        # Current FFT data
        self.fft_data = None

    def receive_fft_data(self):
        """Receive FFT data from UDP socket"""
        try:
            data, addr = self.socket.recvfrom(16384)

            # Process the data - look for FFT type
            # Note: Using 'P' for Power spectrum data
            if data and len(data) > 3 and data[0] == ord('P'):
                data = data[1:]  # Skip the type byte

                # Extract number of samples and data
                if len(data) >= 2:
                    num_samples = (data[0] << 8) | data[1]

                    if len(data) >= 2 + num_samples * 4:  # 4 bytes per float
                        # Extract float values
                        fft_values = []
                        for i in range(num_samples):
                            offset = 2 + i * 4
                            value = struct.unpack('f', data[offset:offset+4])[0]
                            fft_values.append(value)

                        # Store the FFT data
                        self.fft_data = np.array(fft_values)
                        self.packets_received += 1

                        # Calculate packets per second every 5 seconds
                        current_time = time.time()
                        if current_time - self.last_count_time >= 5:
                            packets_per_second = (self.packets_received - self.last_packets_counted) / (current_time - self.last_count_time)
                            logger.info(f"Receiving {packets_per_second:.2f} FFT packets per second")
                            self.last_packets_counted = self.packets_received
                            self.last_count_time = current_time

        except socket.timeout:
            # This is normal, just continue
            pass
        except Exception as e:
            logger.error(f"Error receiving FFT data: {str(e)}")

    def update_plot(self, frame):
        """Update function for animation"""
        # Receive new data
        self.receive_fft_data()

        if self.fft_data is not None:
            # Normalize if needed (values should be from 0 to 1 for clean display)
            max_val = np.max(self.fft_data)
            if max_val > 0:
                normalized_data = self.fft_data / max_val
            else:
                normalized_data = self.fft_data

            # Set x-axis range on first valid data
            if len(self.line.get_xdata()) == 0:
                x = np.arange(len(normalized_data))
                self.line.set_xdata(x)
                self.ax.set_xlim(0, len(normalized_data))

            # Update y-data
            self.line.set_ydata(normalized_data)

            # Update title with status
            self.ax.set_title(f'ARDOP FFT Data - {len(normalized_data)} points - {self.packets_received} packets received')

        # Must return the artists that were updated
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
                save_count=100  # Limit cache to 100 frames
            )

            # Show the plot (this blocks until window is closed)
            plt.show()

        finally:
            # Clean up when window is closed
            self.socket.close()
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
