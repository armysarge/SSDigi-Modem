"""
Spectrum visualization for SS-Ham-Modem
"""
import numpy as np
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal

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

        # Minimum size
        self.setMinimumSize(400, 200)

    def update_settings(self, config):
        """Update settings from config"""
        self.config = config
        self.fft_size = config.get('ui', 'fft_size')
        self.sample_rate = config.get('audio', 'sample_rate')
        self.center_freq = config.get('modem', 'center_freq')
        self.bandwidth = int(config.get('modem', 'bandwidth'))

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
        noise = np.random.normal(0, 2, size=len(self.data))

        # Base noise floor
        self.data = -130 + noise

        # Add some peaks
        self.data += 15 * np.exp(-((x - len(self.data) * 0.25) ** 2) / (2 * (len(self.data) * 0.02) ** 2))
        self.data += 25 * np.exp(-((x - len(self.data) * 0.5) ** 2) / (2 * (len(self.data) * 0.01) ** 2))
        self.data += 10 * np.exp(-((x - len(self.data) * 0.75) ** 2) / (2 * (len(self.data) * 0.03) ** 2))

        # Update and redraw
        self.update()

    def paintEvent(self, event):
        """Paint the spectrum visualization"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get widget dimensions
        width = self.width()
        height = self.height()

        # Define margins
        left_margin = 60
        right_margin = 20
        top_margin = 20
        bottom_margin = 40

        # Calculate plotting area
        plot_width = width - left_margin - right_margin
        plot_height = height - top_margin - bottom_margin
        plot_rect = QRect(left_margin, top_margin, plot_width, plot_height)

        # Draw background
        painter.fillRect(self.rect(), self.bg_color)

        # Draw grid
        self._draw_grid(painter, plot_rect)

        # Draw frequency markers
        self._draw_freq_markers(painter, plot_rect)

        # Draw amplitude markers
        self._draw_amp_markers(painter, plot_rect)

        # Draw spectrum
        self._draw_spectrum(painter, plot_rect)

        # Draw selected frequency marker if any
        if self.selected_freq is not None:
            self._draw_selected_marker(painter, plot_rect)

        # Draw border around the plot area
        painter.setPen(QPen(self.grid_color, 1))
        painter.drawRect(plot_rect)

        painter.end()

    def _draw_grid(self, painter, rect):
        """Draw grid lines"""
        painter.setPen(QPen(self.grid_color, 1, Qt.DotLine))

        # Horizontal grid lines (amplitude)
        num_amp_lines = 8
        for i in range(1, num_amp_lines):
            y = rect.top() + (i * rect.height()) // num_amp_lines
            painter.drawLine(rect.left(), y, rect.right(), y)

        # Vertical grid lines (frequency)
        num_freq_lines = 10
        for i in range(1, num_freq_lines):
            x = rect.left() + (i * rect.width()) // num_freq_lines
            painter.drawLine(x, rect.top(), x, rect.bottom())

    def _draw_freq_markers(self, painter, rect):
        """Draw frequency markers on x-axis"""
        painter.setPen(QPen(self.text_color, 1))
        painter.setFont(self.font())

        # Calculate frequency range
        start_freq = 0
        end_freq = self.sample_rate // 2

        # Draw x-axis label
        painter.drawText(
            rect.left() + rect.width() // 2 - 20,
            rect.bottom() + 35,
            "Frequency (Hz)"
        )

        # Draw frequency markers
        num_markers = 5
        for i in range(num_markers + 1):
            freq = start_freq + (i * (end_freq - start_freq)) // num_markers
            x = rect.left() + (i * rect.width()) // num_markers

            # Format frequency label
            if freq >= 1000:
                label = f"{freq/1000:.1f}k"
            else:
                label = f"{freq}"

            painter.drawText(x - 15, rect.bottom() + 15, label)
            painter.drawLine(x, rect.bottom(), x, rect.bottom() + 5)

    def _draw_amp_markers(self, painter, rect):
        """Draw amplitude markers on y-axis"""
        painter.setPen(QPen(self.text_color, 1))
        painter.setFont(self.font())

        # Draw y-axis label
        painter.save()
        painter.translate(10, rect.top() + rect.height() // 2 + 20)
        painter.rotate(-90)
        painter.drawText(0, 0, "Amplitude (dB)")
        painter.restore()

        # Draw amplitude markers
        num_markers = 8
        for i in range(num_markers + 1):
            db = self.min_value + (i * (self.max_value - self.min_value)) // num_markers
            y = rect.bottom() - (i * rect.height()) // num_markers

            label = f"{db:.0f}"
            painter.drawText(rect.left() - 40, y + 5, label)
            painter.drawLine(rect.left() - 5, y, rect.left(), y)

    def _draw_spectrum(self, painter, rect):
        """Draw the spectrum data"""
        if len(self.data) == 0:
            return

        # Create a path for the spectrum
        path = QPainterPath()

        # Set the pen for the spectrum line
        painter.setPen(QPen(self.spectrum_color, 1.5))

        # Map the first point
        x = rect.left()

        # Scale the first data point to y coordinate
        y_scale = rect.height() / (self.max_value - self.min_value)
        y = rect.bottom() - (self.data[0] - self.min_value) * y_scale

        # Clamp y to plot rectangle
        y = max(rect.top(), min(rect.bottom(), y))

        # Start the path
        path.moveTo(x, y)

        # Add remaining points
        x_scale = rect.width() / (len(self.data) - 1)
        for i in range(1, len(self.data)):
            x = rect.left() + i * x_scale
            y = rect.bottom() - (self.data[i] - self.min_value) * y_scale

            # Clamp y to plot rectangle
            y = max(rect.top(), min(rect.bottom(), y))

            path.lineTo(x, y)

        # Draw the path
        painter.drawPath(path)

        # Fill area under the spectrum
        if self.config.get('ui', 'theme') != 'minimal':
            fill_path = QPainterPath(path)
            fill_path.lineTo(rect.right(), rect.bottom())
            fill_path.lineTo(rect.left(), rect.bottom())
            fill_path.closeSubpath()

            gradient = QBrush(QColor(50, 200, 50, 40))
            painter.fillPath(fill_path, gradient)

    def _draw_selected_marker(self, painter, rect):
        """Draw marker for the selected frequency"""
        if self.selected_freq is None:
            return

        # Calculate x position based on selected frequency
        freq_range = self.sample_rate / 2
        x = rect.left() + int((self.selected_freq / freq_range) * rect.width())

        # Ensure x is within plot area
        x = max(rect.left(), min(rect.right(), x))

        # Draw vertical line
        painter.setPen(QPen(self.marker_color, 1, Qt.DashLine))
        painter.drawLine(x, rect.top(), x, rect.bottom())

        # Draw frequency label
        painter.setPen(self.marker_color)
        painter.setFont(self.font())
        label = f"{self.selected_freq:.1f} Hz"
        painter.drawText(x - 40, rect.top() - 5, label)

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton:
            # Calculate frequency from x position
            left_margin = 60
            right_margin = 20
            plot_width = self.width() - left_margin - right_margin

            # Check if click is within plot area
            if event.x() >= left_margin and event.x() <= (self.width() - right_margin):
                x_frac = (event.x() - left_margin) / plot_width
                freq = x_frac * (self.sample_rate / 2)

                # Update selected frequency
                self.selected_freq = freq

                # Emit signal
                self.frequencySelected.emit(freq)

                # Update display
                self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        # Could add hover info about frequency/amplitude
        pass

    def sizeHint(self):
        """Suggested size for the widget"""
        return QSize(800, 250)
