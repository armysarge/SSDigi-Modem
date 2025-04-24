"""
Waterfall visualization widget for SSDigi Modem
"""
import numpy as np
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPainter, QImage, QColor, QPen
from PyQt5.QtCore import Qt, QSize

class WaterfallView(QWidget):
    """Widget that displays a scrolling waterfall (spectrogram) of FFT data."""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        # Store reference to config
        self.config = config

        # Configuration values
        self.fft_size = config.get('ui', 'fft_size', 2048)
        self.sample_rate = config.get('audio', 'sample_rate', 48000)
        self.center_freq = config.get('modem', 'center_freq', 1000)
        self.bandwidth = config.get('modem', 'bandwidth', 500)
        # Frequency display range multiplier (show at least 2x the bandwidth)
        self.freq_display_multiplier = config.get('ui', 'freq_display_multiplier', 2.0)

        # Display settings
        ref_level = config.get('ui', 'spectrum_ref_level', -40)
        spectrum_range = config.get('ui', 'spectrum_range', 60)
        self.min_value = ref_level - spectrum_range
        self.max_value = ref_level

        # Left margin to align with spectrum (compensate for y-axis labels)
        self.left_margin = 40  # Adjust this value to match the spectrum's y-axis width

        # Waterfall settings
        self.bg_color = QColor(20, 20, 30)
        self.buffer_height = 200
        # Reduce buffer width by left margin to maintain total width
        self.total_width = 395 # Total desired width
        self.buffer_width = self.total_width - self.left_margin  # Actual display area width

        # Create the image with the total width
        self.waterfall_image = QImage(self.total_width, self.buffer_height, QImage.Format_RGB32)
        self.waterfall_image.fill(self.bg_color)
        self._colormap = self._create_colormap()
        self.setMinimumSize(self.total_width, self.buffer_height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Calculate frequency mapping
        self._calculate_freq_mapping()

    def _calculate_freq_mapping(self):
        """Calculate the mapping between FFT bins and display pixels."""
        # Calculate expanded frequency range based on multiplier
        display_bandwidth = self.bandwidth * self.freq_display_multiplier
        self.start_freq = self.center_freq - (display_bandwidth / 2)
        self.end_freq = self.center_freq + (display_bandwidth / 2)

        # Frequency per bin
        bin_freq = self.sample_rate / self.fft_size

        # FFT runs from 0 to sample_rate/2 across bins 0 to fft_size/2
        # Calculate exact bin indices for our frequency range
        self.start_bin = int(self.start_freq / bin_freq)
        self.end_bin = int(self.end_freq / bin_freq)

        # Clamp to valid bin range
        self.start_bin = max(0, self.start_bin)
        self.end_bin = min(self.fft_size // 2, self.end_bin)

        # Calculate how many FFT bins cover our frequency range
        bin_count = self.end_bin - self.start_bin        # Create pixel to bin mapping with interpolation weights
        self.pixel_to_bins = {}

        # For improved smoothness, we'll map each pixel to multiple nearby bins with weights
        for pixel_x in range(self.buffer_width):
            # Calculate the frequency this pixel represents        # Map pixel to frequency space - identical to how the spectrum view does it
            freq_ratio = pixel_x / self.buffer_width
            freq = self.start_freq + (self.end_freq - self.start_freq) * freq_ratio

            # Convert frequency to bin index
            bin_pos_float = freq / bin_freq

            # Make sure bin index is valid (some frequencies may map to negative bins)
            if bin_pos_float < 0:
                bin_pos_float = 0

            # Get the bin indices for interpolation (the bins that bracket our position)
            bin_floor = int(bin_pos_float)
            bin_ceil = min(bin_floor + 1, self.fft_size // 2 - 1)

            # Calculate interpolation weight
            weight_ceil = bin_pos_float - bin_floor
            weight_floor = 1.0 - weight_ceil

            # Store bins with their weights
            self.pixel_to_bins[pixel_x] = []

            # Add the primary bin
            if 0 <= bin_floor < self.fft_size // 2:
                self.pixel_to_bins[pixel_x].append((bin_floor, weight_floor))

            # Add the next bin for interpolation
            if bin_floor != bin_ceil and 0 <= bin_ceil < self.fft_size // 2:
                self.pixel_to_bins[pixel_x].append((bin_ceil, weight_ceil))

            # For additional smoothness, optionally add more neighboring bins with smaller weights
            if bin_floor > 0 and len(self.pixel_to_bins[pixel_x]) < 3:
                self.pixel_to_bins[pixel_x].append((bin_floor - 1, weight_floor * 0.3))

            if bin_ceil < self.fft_size // 2 - 1 and len(self.pixel_to_bins[pixel_x]) < 4:
                self.pixel_to_bins[pixel_x].append((bin_ceil + 1, weight_ceil * 0.3))

    def _create_colormap(self):
        """Create an enhanced colormap with better signal visualization."""
        colormap = []
        for i in range(256):
            normalized = i / 255.0
            if normalized < 0.25:  # Dark blue to blue
                r = 0
                g = int(normalized * 4 * 150)
                b = int(50 + normalized * 4 * 205)
            elif normalized < 0.5:  # Blue to cyan
                r = 0
                g = int(150 + (normalized - 0.25) * 4 * 105)
                b = 255
            elif normalized < 0.75:  # Cyan to yellow
                r = int((normalized - 0.5) * 4 * 255)
                g = 255
                b = int(255 - (normalized - 0.5) * 4 * 255)
            else:  # Yellow to red
                r = 255
                g = int(255 - (normalized - 0.75) * 4 * 255)
                b = 0
            colormap.append(QColor(r, g, b).rgb())
        return colormap

    def update_waterfall(self, fft_data):
        """Update the waterfall with a new row of FFT data (expects dB values)."""
        # Manually scroll image up by 1 row
        scrolled = self.waterfall_image.copy(0, 1, self.total_width, self.buffer_height - 1)
        self.waterfall_image.fill(self.bg_color)
        # Paste the scrolled image back (shifted up by 1)
        painter = QPainter(self.waterfall_image)
        painter.drawImage(0, 0, scrolled)
        painter.end()

        # Ensure fft_data isn't empty or invalid
        if fft_data is None or len(fft_data) == 0:
            return

        # Ensure we have enough FFT data for our frequency range
        if len(fft_data) < self.end_bin:
            print(f"Warning: FFT data length {len(fft_data)} is less than required end bin {self.end_bin}")
            return

        # Special handling for the 2000 Hz bandwidth case
        if abs(self.bandwidth - 2000) < 10:  # Check if bandwidth is approximately 2000 Hz
            # Simplify the approach - use a hardcoded range that we know works
            # This is a pragmatic workaround specific to 2000 Hz bandwidth
            self.start_bin = max(0, min(60, len(fft_data) - 100))  # Empirically chosen safe values
            self.end_bin = min(len(fft_data) - 1, self.start_bin + 100)

        # Map FFT data to color indices
        fft_data = np.clip(fft_data, self.min_value, self.max_value)
        value_range = self.max_value - self.min_value# Process data for the last row with improved interpolation
        for pixel_x in range(self.buffer_width):
            # Default to background color
            color = self.bg_color.rgb()

            if pixel_x in self.pixel_to_bins and self.pixel_to_bins[pixel_x]:
                # Get the weighted bins that contribute to this pixel
                weighted_bins = self.pixel_to_bins[pixel_x]

                # Apply weighted interpolation
                total_value = 0.0
                total_weight = 0.0

                for bin_idx, weight in weighted_bins:
                    try:
                        if 0 <= bin_idx < len(fft_data):
                            # Use weighted contribution from each bin
                            total_value += fft_data[bin_idx] * weight
                            total_weight += weight
                    except Exception as e:
                        print(f"Error at bin {bin_idx}/{len(fft_data)}: {e}")

                if total_weight > 0:
                    # Calculate weighted average
                    value = total_value / total_weight

                    # Convert to color
                    normalized = (value - self.min_value) / value_range
                    normalized = max(0.0, min(0.98, normalized))
                    color_idx = int(normalized * 255)
                    color = self._colormap[color_idx]

            # Set the pixel in the last row - offset by left margin
            self.waterfall_image.setPixel(pixel_x + self.left_margin, self.buffer_height - 1, color)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg_color)

        # Draw the waterfall - no need to shift since the image already includes the margin
        painter.drawImage(0, 0, self.waterfall_image)

        # Calculate the actual bandwidth edges for visualization
        lower_edge = self.center_freq - (self.bandwidth / 2)
        upper_edge = self.center_freq + (self.bandwidth / 2)

        # Calculate the display frequency range
        display_bandwidth = self.bandwidth * self.freq_display_multiplier
        display_start = self.center_freq - (display_bandwidth / 2)
        display_end = self.center_freq + (display_bandwidth / 2)

        # Calculate position of bandwidth indicators as a percentage of the display width
        lower_percent = (lower_edge - display_start) / display_bandwidth
        upper_percent = (upper_edge - display_start) / display_bandwidth

        # Convert to pixel positions (adding left margin since we're positioning on the full image)
        lower_pixel = int(lower_percent * self.buffer_width) + self.left_margin
        upper_pixel = int(upper_percent * self.buffer_width) + self.left_margin

        # Draw the vertical lines for bandwidth limits
        bandwidth_pen = QPen(QColor(255, 150, 0, 180))  # Orange with some transparency
        bandwidth_pen.setWidth(1)
        bandwidth_pen.setStyle(Qt.DashLine)
        painter.setPen(bandwidth_pen)

        # Draw the lines (already include left margin in pixel positions)
        painter.drawLine(lower_pixel, 0, lower_pixel, self.buffer_height)
        painter.drawLine(upper_pixel, 0, upper_pixel, self.buffer_height)

        painter.end()

    def sizeHint(self):
        return QSize(self.total_width, self.buffer_height)

    def update_settings(self, config):
        """Update waterfall settings from configuration."""
        # Store reference to config
        self.config = config

        # Update configuration values
        self.fft_size = config.get('ui', 'fft_size', 2048)
        self.sample_rate = config.get('audio', 'sample_rate', 48000)
        self.center_freq = config.get('modem', 'center_freq', 1500)
        self.bandwidth = config.get('modem', 'bandwidth', 2500)
        self.freq_display_multiplier = config.get('ui', 'freq_display_multiplier', 2.0)

        # Update buffer width based on current left margin
        self.total_width = 400  # Keep total width constant
        self.buffer_width = self.total_width - self.left_margin

        # Resize waterfall image if needed
        if self.waterfall_image.width() != self.total_width:
            self.waterfall_image = QImage(self.total_width, self.buffer_height, QImage.Format_RGB32)
            self.waterfall_image.fill(self.bg_color)

        # Update display settings
        ref_level = config.get('ui', 'spectrum_ref_level', -40)
        spectrum_range = config.get('ui', 'spectrum_range', 60)
        self.min_value = ref_level - spectrum_range
        self.max_value = ref_level

        # Recalculate frequency mapping
        self._calculate_freq_mapping()

        # Force a redraw
        self.update()

    def _recalculate_pixel_bins(self, bin_freq):
        """Recalculate the pixel to bin mapping for special cases."""
        # Create pixel to bin mapping with interpolation weights
        self.pixel_to_bins = {}

        bin_count = self.end_bin - self.start_bin

        # For improved smoothness, we'll map each pixel to multiple nearby bins with weights
        for pixel_x in range(self.buffer_width):
            # Calculate the frequency this pixel represents
            freq_ratio = pixel_x / self.buffer_width
            freq = self.start_freq + (self.end_freq - self.start_freq) * freq_ratio

            # Convert frequency to bin index
            bin_pos_float = freq / bin_freq

            # Make sure bin index is valid
            if bin_pos_float < 0:
                bin_pos_float = 0

            # Get the bin indices for interpolation
            bin_floor = int(bin_pos_float)
            bin_ceil = bin_floor + 1

            # Calculate interpolation weight
            weight_ceil = bin_pos_float - bin_floor
            weight_floor = 1.0 - weight_ceil

            # Store bins with their weights
            self.pixel_to_bins[pixel_x] = []

            # Add the primary bin
            if 0 <= bin_floor < self.fft_size // 2:
                self.pixel_to_bins[pixel_x].append((bin_floor, weight_floor))

            # Add the next bin for interpolation
            if bin_floor != bin_ceil and 0 <= bin_ceil < self.fft_size // 2:
                self.pixel_to_bins[pixel_x].append((bin_ceil, weight_ceil))
