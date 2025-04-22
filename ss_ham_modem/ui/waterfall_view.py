"""
Waterfall visualization for SS Ham Modem
"""
import numpy as np
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QImage, QColor, QPen
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal

logger = logging.getLogger(__name__)

class WaterfallView(QWidget):
    """Widget that displays signal waterfall (spectrum over time)"""

    frequencySelected = pyqtSignal(float)

    def __init__(self, config, parent=None):
        """Initialize waterfall view widget"""
        super().__init__(parent)

        self.config = config
        self.fft_size = config.get('ui', 'fft_size')
        self.sample_rate = config.get('audio', 'sample_rate')

        # Color map settings
        self.colormap_name = config.get('ui', 'waterfall_colors')

        # Create image buffer
        self.buffer_height = 300  # Number of lines to keep in history
        self.waterfall_image = QImage(self.fft_size // 2, self.buffer_height, QImage.Format_RGB32)
        self.waterfall_image.fill(QColor(0, 0, 0))

        # Data range for color mapping
        self.min_value = -160
        self.max_value = -60

        # Mouse tracking
        self.setMouseTracking(True)

        # Selected frequency
        self.selected_freq = None

        # Minimum size
        self.setMinimumSize(400, 200)

    def update_settings(self, config):
        """Update settings from config"""
        self.config = config
        self.fft_size = config.get('ui', 'fft_size')
        self.sample_rate = config.get('audio', 'sample_rate')
        self.colormap_name = config.get('ui', 'waterfall_colors')

        # Resize image buffer if needed
        if self.waterfall_image.width() != self.fft_size // 2:
            new_image = QImage(self.fft_size // 2, self.buffer_height, QImage.Format_RGB32)
            new_image.fill(QColor(0, 0, 0))
            self.waterfall_image = new_image

        # Update display
        self.update()

    def append_data(self, fft_data):
        """Add new FFT data to the waterfall"""
        if fft_data is None or len(fft_data) != self.fft_size // 2:
            return

        # Scroll the image up by 1 pixel
        new_image = QImage(self.waterfall_image.width(), self.waterfall_image.height(), QImage.Format_RGB32)
        painter = QPainter(new_image)

        # Copy the old image shifted up by 1 pixel
        painter.drawImage(0, 0, self.waterfall_image, 0, 1, -1, -1)
        painter.end()
        self.waterfall_image = new_image

        # Add the new data to the bottom row
        self._add_data_row(fft_data)

        # Update dynamic range
        min_val = np.min(fft_data)
        max_val = np.max(fft_data)

        # Smooth min/max values
        self.min_value = 0.95 * self.min_value + 0.05 * min_val
        self.max_value = 0.95 * self.max_value + 0.05 * max_val

        # Ensure minimum range
        if self.max_value - self.min_value < 40:
            mean_val = (self.max_value + self.min_value) / 2
            self.max_value = mean_val + 20
            self.min_value = mean_val - 20

        # Update the widget
        self.update()

    def update_with_demo_data(self):
        """Update with demo data when not connected"""
        # Generate some demo data that looks like a signal in a waterfall
        x = np.arange(self.waterfall_image.width())
        center = self.waterfall_image.width() // 2
        width = self.waterfall_image.width() // 10

        # Base noise floor
        data = -140 + np.random.normal(0, 3, size=self.waterfall_image.width())

        # Add a drifting signal
        drift = 10 * np.sin(2 * np.pi * 0.05 * (self.counter if hasattr(self, 'counter') else 0))
        signal_center = center + int(drift)
        data += 50 * np.exp(-((x - signal_center) ** 2) / (2 * width ** 2))

        # Add some interference
        data += 20 * np.exp(-((x - center * 0.5) ** 2) / (2 * (width * 0.5) ** 2))

        # Increment counter for animation
        self.counter = getattr(self, 'counter', 0) + 1

        # Append the data
        self.append_data(data)

    def _add_data_row(self, fft_data):
        """Add a new row of data to the bottom of the waterfall image"""
        for i in range(min(len(fft_data), self.waterfall_image.width())):
            # Map the value to a color
            color = self._map_to_color(fft_data[i])

            # Set the pixel at the bottom row
            self.waterfall_image.setPixelColor(i, self.waterfall_image.height() - 1, color)

    def _map_to_color(self, value):
        """Map a value to a color using the selected colormap"""
        # Normalize the value to 0-1 range
        normalized = (value - self.min_value) / (self.max_value - self.min_value)
        normalized = max(0, min(1, normalized))

        # Apply the selected colormap
        if self.colormap_name == 'viridis':
            return self._viridis_colormap(normalized)
        elif self.colormap_name == 'hot':
            return self._hot_colormap(normalized)
        elif self.colormap_name == 'blue':
            return self._blue_colormap(normalized)
        else:  # default
            return self._default_colormap(normalized)

    def _default_colormap(self, value):
        """Default colormap (blue to green to red)"""
        if value < 0.25:
            # Dark blue to blue
            r = 0
            g = 0
            b = int(255 * (value / 0.25))
        elif value < 0.5:
            # Blue to cyan to green
            r = 0
            g = int(255 * ((value - 0.25) / 0.25))
            b = 255
        elif value < 0.75:
            # Green to yellow
            r = int(255 * ((value - 0.5) / 0.25))
            g = 255
            b = int(255 * (1 - ((value - 0.5) / 0.25)))
        else:
            # Yellow to red
            r = 255
            g = int(255 * (1 - ((value - 0.75) / 0.25)))
            b = 0

        return QColor(r, g, b)

    def _viridis_colormap(self, value):
        """Viridis colormap (dark blue, blue, green, yellow)"""
        if value < 0.33:
            # Dark blue to blue
            r = int(68 * (value / 0.33))
            g = int(1 + 100 * (value / 0.33))
            b = int(84 + 80 * (value / 0.33))
        elif value < 0.66:
            # Blue to green
            normalized = (value - 0.33) / 0.33
            r = int(68 + 49 * normalized)
            g = int(101 + 68 * normalized)
            b = int(164 - 60 * normalized)
        else:
            # Green to yellow
            normalized = (value - 0.66) / 0.34
            r = int(117 + 136 * normalized)
            g = int(169 + 50 * normalized)
            b = int(104 - 90 * normalized)

        return QColor(r, g, b)

    def _hot_colormap(self, value):
        """Hot colormap (black, red, yellow, white)"""
        if value < 0.33:
            # Black to red
            r = int(255 * (value / 0.33))
            g = 0
            b = 0
        elif value < 0.66:
            # Red to yellow
            r = 255
            g = int(255 * ((value - 0.33) / 0.33))
            b = 0
        else:
            # Yellow to white
            r = 255
            g = 255
            b = int(255 * ((value - 0.66) / 0.34))

        return QColor(r, g, b)

    def _blue_colormap(self, value):
        """Blue colormap (black to blue to cyan to white)"""
        if value < 0.33:
            # Black to blue
            r = 0
            g = 0
            b = int(255 * (value / 0.33))
        elif value < 0.66:
            # Blue to cyan
            r = 0
            g = int(255 * ((value - 0.33) / 0.33))
            b = 255
        else:
            # Cyan to white
            r = int(255 * ((value - 0.66) / 0.34))
            g = 255
            b = 255

        return QColor(r, g, b)

    def paintEvent(self, event):
        """Paint the waterfall visualization"""
        painter = QPainter(self)

        # Get widget dimensions
        width = self.width()
        height = self.height()

        # Define margins
        left_margin = 60
        right_margin = 20
        top_margin = 10
        bottom_margin = 40

        # Calculate plotting area
        plot_width = width - left_margin - right_margin
        plot_height = height - top_margin - bottom_margin
        plot_rect = QRect(left_margin, top_margin, plot_width, plot_height)

        # Draw background
        bg_color = QColor(20, 20, 30)
        painter.fillRect(self.rect(), bg_color)

        # Draw the waterfall image
        if not self.waterfall_image.isNull():
            # Scale the waterfall image to fit the plot area
            painter.drawImage(plot_rect, self.waterfall_image)

        # Draw frequency markers
        self._draw_freq_markers(painter, plot_rect)

        # Draw time markers
        self._draw_time_markers(painter, plot_rect)

        # Draw selected frequency marker if any
        if self.selected_freq is not None:
            self._draw_selected_marker(painter, plot_rect)

        # Draw border around the plot area
        grid_color = QColor(60, 60, 80)
        painter.setPen(QPen(grid_color, 1))
        painter.drawRect(plot_rect)

        painter.end()

    def _draw_freq_markers(self, painter, rect):
        """Draw frequency markers on x-axis"""
        text_color = QColor(200, 200, 200)
        painter.setPen(QPen(text_color, 1))
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

    def _draw_time_markers(self, painter, rect):
        """Draw time markers on y-axis"""
        text_color = QColor(200, 200, 200)
        painter.setPen(QPen(text_color, 1))

        # Draw y-axis label
        painter.save()
        painter.translate(10, rect.top() + rect.height() // 2 + 20)
        painter.rotate(-90)
        painter.drawText(0, 0, "Time")
        painter.restore()

        # Calculate time range (assuming 10 lines per second)
        update_rate = self.config.get('ui', 'spectrum_update_rate')
        total_time = self.buffer_height / update_rate  # in seconds

        # Draw time markers (newest at bottom, oldest at top)
        num_markers = 5
        for i in range(num_markers + 1):
            time = i * total_time / num_markers
            y = rect.top() + (i * rect.height()) // num_markers

            # Format time label
            if time >= 60:
                label = f"{int(time / 60)}m {int(time % 60)}s"
            else:
                label = f"{time:.1f}s"

            painter.drawText(rect.left() - 50, y + 5, label)
            painter.drawLine(rect.left() - 5, y, rect.left(), y)

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
        marker_color = QColor(255, 200, 50)
        painter.setPen(QPen(marker_color, 1, Qt.DashLine))
        painter.drawLine(x, rect.top(), x, rect.bottom())

        # Draw frequency label
        painter.setPen(marker_color)
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

    def sizeHint(self):
        """Suggested size for the widget"""
        return QSize(800, 300)
