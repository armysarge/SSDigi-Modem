"""
Spectrum visualization for SSDigi Modem
"""
import numpy as np
import logging
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal, QPoint

logger = logging.getLogger(__name__)

class SpectrumView(QWidget):
    """Widget that displays FFT spectrum data"""
    # Signal emitted when user clicks on a frequency
    frequencySelected = pyqtSignal(float)
    def __init__(self, config, parent=None):
        """Initialize spectrum view widget"""
        super().__init__(parent)
        self.config = config
        self.fft_size = config.get('ui', 'fft_size')
        self.sample_rate = config.get('audio', 'sample_rate')
        # Color scheme
        self.bg_color = QColor(20, 20, 30)
        self.grid_color = QColor(60, 60, 80)
        self.spectrum_color = QColor(50, 200, 50)
        self.marker_color = QColor(255, 200, 50)
        self.text_color = QColor(200, 200, 200)

        # Frequency display range multiplier (show at least 2x the bandwidth)
        self.freq_display_multiplier = config.get('ui', 'freq_display_multiplier', 2.0)

        # Disable mouse tracking for better performance
        self.setMouseTracking(False)

        # Spectrum data (initial empty data)
        self.data = np.zeros(self.fft_size // 2)
        self.max_value = -120
        self.min_value = -160
        self.center_freq = config.get('modem', 'center_freq')
        self.bandwidth = int(config.get('modem', 'bandwidth'))

        # Selection marker
        self.selected_freq = None

        # Enable mouse tracking
        self.setMouseTracking(True)

        # Set size policy to fixed
        self.setMinimumSize(400, 150)
        self.setMaximumSize(400, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_settings(self, config):
        """Update settings from config"""
        self.config = config
        self.fft_size = config.get('ui', 'fft_size')
        self.sample_rate = config.get('audio', 'sample_rate')
        self.center_freq = config.get('modem', 'center_freq')
        self.bandwidth = int(config.get('modem', 'bandwidth'))
        self.freq_display_multiplier = config.get('ui', 'freq_display_multiplier', 2.0)

        # Resize data array if needed
        if len(self.data) != self.fft_size // 2:
            self.data = np.zeros(self.fft_size // 2)

        # Update and redraw
        self.update()

    def update_with_data(self, fft_data):
        """Update with new FFT data"""
        if fft_data is not None and len(fft_data) == len(self.data):
            self.data = fft_data

            # Update dynamic range
            min_val = np.min(fft_data)
            max_val = np.max(fft_data)

            # Smooth min/max values
            self.min_value = 0.9 * self.min_value + 0.1 * min_val
            self.max_value = 0.9 * self.max_value + 0.1 * max_val

            # Ensure minimum range
            if self.max_value - self.min_value < 30:
                mean_val = (self.max_value + self.min_value) / 2
                self.max_value = mean_val + 15
                self.min_value = mean_val - 15

            # Update display
            self.update()

    def update_with_demo_data(self):
        """Update with demo data when not connected"""
        # Generate some demo data that looks like a spectrum
        x = np.arange(len(self.data))

        # Determine max index based on frequency range limitation
        limit_freq = self.config.get('ui', 'limit_freq_range', True)
        if limit_freq:
            max_freq = self.center_freq * 2
            max_index = int(max_freq * len(self.data) / (self.sample_rate / 2))
            max_index = min(max_index, len(self.data) - 1)
        else:
            max_index = len(self.data) - 1

        # Base noise floor with random variation
        noise = np.random.normal(0, 2, size=len(self.data))
        self.data = -130 + noise

        # Calculate time-dependent phase for animation
        if not hasattr(self, 'demo_phase'):
            self.demo_phase = 0
        self.demo_phase += 0.1

        # Add some moving peaks to simulate signals
        peak1_pos = len(self.data) * (0.25 + 0.05 * np.sin(self.demo_phase * 0.2))
        peak2_pos = len(self.data) * (0.5 + 0.03 * np.sin(self.demo_phase * 0.3 + 1))
        peak3_pos = len(self.data) * (0.75 - 0.04 * np.sin(self.demo_phase * 0.25 + 2))

        # Create realistic-looking peaks
        self.data += 15 * np.exp(-((x - peak1_pos) ** 2) / (2 * (len(self.data) * 0.02) ** 2))
        self.data += 25 * np.exp(-((x - peak2_pos) ** 2) / (2 * (len(self.data) * 0.01) ** 2))
        self.data += 10 * np.exp(-((x - peak3_pos) ** 2) / (2 * (len(self.data) * 0.015) ** 2))

        # Add some harmonic content
        self.data += 8 * np.exp(-((x - peak2_pos * 0.5) ** 2) / (2 * (len(self.data) * 0.008) ** 2))
        self.data += 5 * np.exp(-((x - peak2_pos * 1.5) ** 2) / (2 * (len(self.data) * 0.01) ** 2))

        # Add subtle wave-like pattern to the noise floor
        self.data += 3 * np.sin(x * 0.05 + self.demo_phase) * np.exp(-((x - len(self.data) * 0.5) ** 2) / (2 * (len(self.data) * 0.8) ** 2))

        # Update and redraw
        self.update()

    def paintEvent(self, event):
        """Paint the spectrum view"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get drawing rect
        rect = self.rect()

        # Draw background
        painter.fillRect(rect, self.bg_color)

        # Check if we have valid data
        if len(self.data) < 2:
            return

        # Limit frequency range to center_freq * 2 if setting is enabled
        limit_freq = self.config.get('ui', 'limit_freq_range', True)
        if limit_freq:
            # Calculate how many samples correspond to center_freq * 2
            max_freq = self.center_freq * 2
            max_bin_index = int(max_freq * len(self.data) / (self.sample_rate / 2))
            # Ensure we're not exceeding array bounds
            max_bin_index = min(max_bin_index, len(self.data) - 1)
        else:
            max_bin_index = len(self.data) - 1

        # Get reference level and display range from config
        ref_level = self.config.get('ui', 'spectrum_ref_level', -60)
        display_range = self.config.get('ui', 'spectrum_range', 70)
        self.max_value = ref_level
        self.min_value = ref_level - display_range

        # Define the plotting area, leaving space for labels
        self.plot_rect = QRect(
            rect.left() + 40,           # Left margin for labels
            rect.top() + 20,            # Top margin for labels
            rect.width() - 50,          # Right margin for labels
            rect.height() - 30          # Bottom margin for labels
        )

        # Draw grid
        self._draw_grid(painter, rect, max_bin_index)

        # Draw spectrum line
        self._draw_spectrum(painter, rect, max_bin_index)

        # Draw bandwidth limit lines
        self._draw_bandwidth_limits(painter, rect)

        # Draw marker for selected frequency if any
        if self.selected_freq is not None:
            self._draw_frequency_marker(painter, rect)

        painter.end()

    def _draw_grid(self, painter, rect, max_bin_index):
        """Draw grid lines and frequency labels"""
        show_grid = self.config.get('ui', 'show_grid', True)
        show_freq_markers = self.config.get('ui', 'show_freq_markers', True)

        # Create margin to prevent text cutoff
        left_margin = 40  # Space for dB labels
        bottom_margin = 20  # Space for frequency labels
        plot_rect = QRect(
            rect.left() + left_margin,
            rect.top() + 5,
            rect.width() - left_margin - 5,
            rect.height() - bottom_margin - 5
        )

        # Set grid pen
        grid_pen = QPen(self.grid_color)
        grid_pen.setStyle(Qt.DotLine)
        painter.setPen(grid_pen)

        # Draw horizontal grid lines (amplitude)
        h_lines = 8
        for i in range(h_lines + 1):
            y = int(plot_rect.bottom() - i * plot_rect.height() / h_lines)
            if show_grid:
                painter.drawLine(plot_rect.left(), y, plot_rect.right(), y)

            # Draw dB labels with improved alignment
            if show_freq_markers:
                db_val = self.min_value + i * (self.max_value - self.min_value) / h_lines
                db_text = f"{db_val:.0f}"
                text_width = painter.fontMetrics().horizontalAdvance(db_text)
                painter.setPen(self.text_color)
                # Right-align dB labels in margin area
                label_rect = QRect(
                    rect.left(),
                    y - 8,  # Center vertically on grid line
                    left_margin - 5,  # Leave small gap before grid
                    16  # Standard text height
                )
                painter.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, db_text)
                painter.setPen(grid_pen)

        # Draw vertical grid lines (frequency)
        v_lines = 10
        # Use at least twice the bandwidth as maximum frequency
        max_freq = self.bandwidth * self.freq_display_multiplier

        for i in range(v_lines + 1):
            freq = i * max_freq / v_lines
            # Convert frequency to x position relative to plot area
            x = int(plot_rect.left() + (freq / max_freq) * plot_rect.width())

            if show_grid:
                painter.drawLine(x, plot_rect.top(), x, plot_rect.bottom())

            # Draw frequency labels with adjusted position
            if show_freq_markers:
                freq_text = f"{freq/1000:.1f}"  # Show as kHz
                text_width = painter.fontMetrics().horizontalAdvance(freq_text)
                painter.setPen(self.text_color)
                # Center text on grid line and position below plot area
                painter.drawText(x - text_width // 2, rect.bottom() - 5, freq_text)
                painter.setPen(grid_pen)

        # Store plot_rect for other drawing methods
        self.plot_rect = plot_rect

    def _freq_to_x(self, freq, rect):
        """Convert frequency to x coordinate"""
        # Calculate max frequency based on the multiplier
        max_freq = self.bandwidth * self.freq_display_multiplier

        # Clip frequency to range
        freq = max(0, min(max_freq, freq))
        # Map frequency to x coordinate using plot_rect
        ratio = freq / max_freq
        return self.plot_rect.left() + ratio * self.plot_rect.width()

    def _x_to_freq(self, x, rect):
        """Convert x coordinate to frequency"""
        # Calculate max frequency based on the multiplier
        max_freq = self.bandwidth * self.freq_display_multiplier

        # Calculate frequency from x position relative to plot area
        plot_x = max(self.plot_rect.left(), min(x, self.plot_rect.right()))
        ratio = (plot_x - self.plot_rect.left()) / self.plot_rect.width()
        return ratio * max_freq

    def _data_to_y(self, value, rect):
        """Convert dB value to y coordinate"""
        # Clip value to range
        value = max(self.min_value, min(self.max_value, value))
        # Map value to y coordinate using plot_rect
        ratio = (value - self.min_value) / (self.max_value - self.min_value)
        return self.plot_rect.bottom() - ratio * self.plot_rect.height()

    def _draw_spectrum(self, painter, rect, max_bin_index):
        """Draw the spectrum line"""
        # Set spectrum pen
        spectrum_pen = QPen(self.spectrum_color)
        spectrum_pen.setWidth(2)
        painter.setPen(spectrum_pen)

        # Use QPainterPath for smoother line
        path = QPainterPath()

        # Start at the left edge
        first_x = self.plot_rect.left()
        first_y = self._data_to_y(self.data[0], rect)
        path.moveTo(first_x, first_y)

        # Add points to the path
        for i in range(1, max_bin_index + 1):
            x = self.plot_rect.left() + i * self.plot_rect.width() / max_bin_index
            y = self._data_to_y(self.data[i], rect)
            path.lineTo(x, y)

        # Draw the path
        painter.drawPath(path)

        # Fill area under the graph with gradient
        gradient_brush = QBrush(QColor(50, 200, 50, 80))
        painter.fillPath(self._create_fill_path(path, rect), gradient_brush)

    def _create_fill_path(self, path, rect):
        """Create a path for filling under the spectrum curve"""
        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()
        return fill_path

    def _draw_frequency_marker(self, painter, rect):
        """Draw frequency marker at selected frequency"""
        if self.selected_freq is None:
            return

        # Calculate x position and convert to QPoint
        x = int(self._freq_to_x(self.selected_freq, rect))
        top_point = QPoint(x, rect.top() + 15)  # Move start point down to avoid overlapping top text
        bottom_point = QPoint(x, rect.bottom() - 15)  # Move end point up to avoid overlapping bottom text

        # Set up marker pen
        marker_pen = QPen(self.marker_color)
        marker_pen.setWidth(1)  # Thinner line
        painter.setPen(marker_pen)

        # Draw vertical line using points
        painter.drawLine(top_point, bottom_point)

        # Draw frequency text at top of marker
        freq_text = f"{self.selected_freq:.0f} Hz"
        text_width = painter.fontMetrics().horizontalAdvance(freq_text)
        text_rect = QRect(x - text_width // 2, rect.top(), text_width, 15)
        painter.fillRect(text_rect, self.bg_color)  # Add background to improve readability
        painter.drawText(text_rect, Qt.AlignCenter, freq_text)

    def _draw_bandwidth_limits(self, painter, rect):
        """Draw vertical lines showing bandwidth limits"""
        # Calculate the edges of the bandwidth
        lower_edge = self.center_freq - (self.bandwidth / 2)
        upper_edge = self.center_freq + (self.bandwidth / 2)

        # Calculate the display frequency range
        display_bandwidth = self.bandwidth * self.freq_display_multiplier
        display_start = self.center_freq - (display_bandwidth / 2)
        display_end = self.center_freq + (display_bandwidth / 2)

        # Calculate position of bandwidth indicators as a percentage of the display width
        lower_percent = (lower_edge - display_start) / display_bandwidth
        upper_percent = (upper_edge - display_start) / display_bandwidth

        # Convert to pixel positions
        lower_x = self.plot_rect.left() + lower_percent * self.plot_rect.width()
        upper_x = self.plot_rect.left() + upper_percent * self.plot_rect.width()

        # Set up pen for bandwidth lines
        bandwidth_pen = QPen(QColor(255, 150, 0, 180))  # Orange with some transparency
        bandwidth_pen.setWidth(1)
        bandwidth_pen.setStyle(Qt.DashLine)
        painter.setPen(bandwidth_pen)

        # Draw the lines
        painter.drawLine(int(lower_x), self.plot_rect.top(), int(lower_x), self.plot_rect.bottom())
        painter.drawLine(int(upper_x), self.plot_rect.top(), int(upper_x), self.plot_rect.bottom())

    def mousePressEvent(self, event):
        """Handle mouse press to select frequency"""
        if event.button() == Qt.LeftButton:
            freq = self._x_to_freq(event.x(), self.rect())
            # Allow selection across the full display range
            max_freq = self.bandwidth * self.freq_display_multiplier
            self.selected_freq = max(0, min(max_freq, freq))
            self.frequencySelected.emit(self.selected_freq)
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse movement to show frequency at cursor"""
        if event.buttons() & Qt.LeftButton:
            freq = self._x_to_freq(event.x(), self.rect())
            # Allow selection across the full display range
            max_freq = self.bandwidth * self.freq_display_multiplier
            self.selected_freq = max(0, min(max_freq, freq))
            self.frequencySelected.emit(self.selected_freq)
            self.update()
