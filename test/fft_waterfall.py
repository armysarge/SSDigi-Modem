#!/usr/bin/env python3
"""
ARDOP FFT Waterfall Visualizer
This script connects to ARDOP via UDP and displays the FFT data as a waterfall plot
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

class WaterfallVisualizer:
    """Visualizes FFT data from ARDOP as a waterfall plot"""

    def __init__(self, host='127.0.0.1', port=8515, history_length=100):
        """Initialize the FFT waterfall visualizer"""
        self.host = host
        self.port = port
        self.history_length = history_length
        self.waterfall_data = None

        # Create figure for visualization
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                                      gridspec_kw={'height_ratios': [1, 3]})

        # Line plot for current FFT
        self.line, = self.ax1.plot([], [], lw=2)
        self.ax1.set_title(f'ARDOP FFT Data (from {host}:{port})')
        self.ax1.set_xlabel('Frequency Bin')
        self.ax1.set_ylabel('Magnitude')
        self.ax1.grid(True)

        # Waterfall plot
        self.waterfall_img = self.ax2.imshow(
            np.zeros((history_length, 10)),  # Will be resized when we get real data
            aspect='auto',
            origin='upper',
            interpolation='none',
            cmap='viridis'
        )
        self.ax2.set_title('FFT History (Waterfall)')
        self.ax2.set_xlabel('Frequency Bin')
        self.ax2.set_ylabel('Time (newest at top)')

        # Add colorbar
        self.fig.colorbar(self.waterfall_img, ax=self.ax2, label='Magnitude')

        # Adjust layout
        plt.tight_layout()

        # Set up UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.settimeout(0.05)  # 50ms timeout for animation refresh

        logger.info(f"Waiting for FFT data from ARDOP on {host}:{port}...")

        # Counter for received packets
        self.packets_received = 0

    def receive_fft_data(self):
        """Receive FFT data from UDP socket"""
        try:
            data, addr = self.socket.recvfrom(16384)

            # Process the data - look for FFT type
            # Note: Using 'P' for Power spectrum data
            if data and len(data) > 3 and data[0] == ord('W'):
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
                        self.current_fft = np.array(fft_values)
                        self.packets_received += 1
                        return True

        except socket.timeout:
            # This is normal, just continue
            pass
        except Exception as e:
            logger.error(f"Error receiving FFT data: {str(e)}")

        return False

    def update_plot(self, frame):
        """Update function for animation"""
        # Receive new data
        if self.receive_fft_data():
            # Normalize FFT data (values from 0 to 1)
            max_val = np.max(self.current_fft)
            if max_val > 0:
                normalized_data = self.current_fft / max_val
            else:
                normalized_data = self.current_fft

            # Initialize waterfall data if this is the first packet
            if self.waterfall_data is None:
                self.waterfall_data = np.zeros((self.history_length, len(normalized_data)))

            # Update line plot
            if len(self.line.get_xdata()) == 0:
                x = np.arange(len(normalized_data))
                self.line.set_xdata(x)
                self.ax1.set_xlim(0, len(normalized_data))
                self.ax1.set_ylim(0, 1.1)  # Leave a little headroom

            self.line.set_ydata(normalized_data)

            # Update waterfall data - roll and add new data at the top
            self.waterfall_data = np.roll(self.waterfall_data, 1, axis=0)
            self.waterfall_data[0] = normalized_data

            # Update waterfall image
            self.waterfall_img.set_array(self.waterfall_data)
            self.waterfall_img.set_extent((0, len(normalized_data), self.history_length, 0))

            # Update title with status
            self.ax1.set_title(f'ARDOP FFT Data - {len(normalized_data)} points - {self.packets_received} packets received')

        # Must return the artists that were updated
        return [self.line, self.waterfall_img]

    def run(self):
        """Run the visualizer with animation"""
        try:
            # Create animation that calls update_plot() every 50ms
            self.ani = FuncAnimation(
                self.fig,
                self.update_plot,
                interval=50,
                blit=True,
                save_count=100  # Limit cache to 100 frames
            )

            # Show the plot
            plt.show()

        finally:
            # Clean up when window is closed
            self.socket.close()
            logger.info("FFT visualizer stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARDOP FFT Waterfall Visualizer")
    parser.add_argument("--host", default="127.0.0.1", help="ARDOP host IP address")
    parser.add_argument("--port", type=int, default=8515, help="ARDOP UDP port for FFT data")
    parser.add_argument("--history", type=int, default=100, help="Number of FFT frames to keep in history")
    args = parser.parse_args()

    try:
        # Start the visualizer
        visualizer = WaterfallVisualizer(host=args.host, port=args.port, history_length=args.history)
        visualizer.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
