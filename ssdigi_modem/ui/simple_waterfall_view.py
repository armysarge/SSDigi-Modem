"""
Simplified waterfall visualization for SSDigi Modem
"""
import numpy as np
import logging
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPainter, QImage, QColor, QPen
from PyQt5.QtCore import Qt, QRect, QSize, QTimer

logger = logging.getLogger(__name__)

class SimpleWaterfallView(QWidget):
    """Simplified widget for waterfall display - optimized for performance"""

    def __init__(self, config, parent=None):
        """Initialize waterfall view widget"""
        super().__init__(parent)

        self.config = config
        self.fft_size = config.get('ui', 'fft_size', 2048)
        self.sample_rate = config.get('audio', 'sample_rate', 48000)
        self.center_freq = config.get('modem', 'center_freq', 1500)
        self.bandwidth = config.get('modem', 'bandwidth', 2500)

        # Very simple color scheme
        self.bg_color = QColor(20, 20, 30)
        self.grid_color = QColor(60, 60, 80)
        self.text_color = QColor(200, 200, 200)

        # Fixed dimensions for better performance
        self.buffer_height = 200
        self.buffer_width = 400  # Fixed width for stability

        # Create image buffer with simple dimensions
        self.waterfall_image = QImage(self.buffer_width, self.buffer_height, QImage.Format_RGB32)
        self.waterfall_image.fill(self.bg_color)

        # Fixed data range - no dynamic adjustment
        self.min_value = -120
        self.max_value = -40

        # Disable all mouse interaction
        self.setMouseTracking(False)

        # Pre-compute colormap for performance
        self._colormap = self._create_simple_colormap()

        # Set fixed size policy
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Basic demo data timer with longer interval
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self.update_with_simple_demo)
        self.demo_timer.start(200)  # Slower updates (200ms)

        # Animation counter
        self.frame_counter = 0

    def _create_simple_colormap(self):
        """Create a simplified colormap - blue to red"""
        colors = []
        for i in range(256):
            # Simple blue to red through green mapping
            if i < 85:  # Blue to cyan
                r, g, b = 0, i * 3, 255
            elif i < 170:  # Cyan to yellow
                r, g, b = (i - 85) * 3, 255, 255 - (i - 85) * 3
            else:  # Yellow to red
                r, g, b = 255, 255 - (i - 170) * 3, 0
            colors.append(QColor(r, g, b).rgb())
        return colors

    def update_with_simple_demo(self):
        """Update with simplified demo data"""
        # Create base signal
        x = np.arange(self.buffer_width)
        center = self.buffer_width // 2

        # Simple animation of signal position
        self.frame_counter += 1
        t = self.frame_counter * 0.1

        # Create a moving peak
        signal_pos = center + int(np.sin(t) * center * 0.5)
        width = self.buffer_width // 15

        # Simple gaussian peak
        signal = -100 + 40 * np.exp(-0.5 * ((x - signal_pos) / width) ** 2)

        # Scroll image up and add new row
        self._simple_scroll()
        self._add_simple_row(signal)

        # Update UI
        self.update()

    def _simple_scroll(self):
        """Ultra-simplified image scrolling"""
        img = self.waterfall_image
        width = img.width()
        height = img.height()

        # Copy rows upward (only process every other row for speed)
        for y in range(0, height-1, 2):
            for x in range(0, width, 2):
                img.setPixel(x, y, img.pixel(x, y+2 if y+2 < height else y+1))

        # No need to clear bottom row - it will be overwritten

    def _add_simple_row(self, signal):
        """Add a single row of data to the bottom of the image"""
        width = min(self.buffer_width, len(signal))
        height = self.waterfall_image.height()

        # Map values directly to colors
        value_range = self.max_value - self.min_value

        # Process every other pixel for speed
        for x in range(0, width, 2):
            value = (signal[x] - self.min_value) / value_range
            value = max(0.0, min(0.98, value))

            color_idx = int(value * 255)
            self.waterfall_image.setPixel(x, height-1, self._colormap[color_idx])
            # Duplicate pixel for the one we're skipping
            if x+1 < width:
                self.waterfall_image.setPixel(x+1, height-1, self._colormap[color_idx])

    def paintEvent(self, event):
        """Simplified painting with minimal processing"""
        painter = QPainter(self)

        # Fill background
        rect = self.rect()
        painter.fillRect(rect, self.bg_color)

        # Draw image without scaling
        painter.drawImage(0, 0, self.waterfall_image)
        painter.end()

    def sizeHint(self):
        """Fixed size hint"""
        return QSize(self.buffer_width, self.buffer_height)
