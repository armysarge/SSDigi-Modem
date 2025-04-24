"""
Performance boost script for SSDigi Modem
This script patches the waterfall and spectrum views to improve performance
"""
import logging

logger = logging.getLogger(__name__)

def optimize_waterfall_view(waterfall_view):
    """Apply optimizations to the waterfall view"""
    logger.info("Applying waterfall view optimizations")

    # Reduce update frequency
    if hasattr(waterfall_view, 'init_timer'):
        waterfall_view.init_timer.stop()
        waterfall_view.init_timer.setInterval(300)  # Slower updates (300ms)
        waterfall_view.init_timer.start()

    # Disable all interaction
    waterfall_view.setMouseTracking(False)

    # Reduce buffer height for better performance
    waterfall_view.buffer_height = 150  # Smaller buffer = less processing

    # Create simplified colormap for better performance
    def create_simple_colormap():
        """Create a simplified colormap with fewer gradients"""
        from PyQt5.QtGui import QColor
        colors = []
        for i in range(256):
            if i < 85:
                r, g, b = 0, 0, min(255, i * 3)
            elif i < 170:
                r, g, b = 0, min(255, (i - 85) * 3), 255
            else:
                r, g, b = min(255, (i - 170) * 3), 255, 255
            colors.append(QColor(r, g, b).rgb())
        return colors

    # Replace the colormap function with simpler version
    waterfall_view._colormap_cache = create_simple_colormap()
    original_get_colormap = waterfall_view._get_colormap

    # Override with cached version
    def optimized_get_colormap():
        return waterfall_view._colormap_cache

    waterfall_view._get_colormap = optimized_get_colormap

    # Optimize scrolling function
    original_scroll = waterfall_view._scroll_waterfall_up

    def optimized_scroll():
        """Ultra-optimized scrolling"""
        img = waterfall_view.waterfall_image
        width, height = img.width(), img.height()

        # Process every other row and column for speed
        for y in range(0, height-1, 2):
            for x in range(0, width, 2):
                img.setPixel(x, y, img.pixel(x, min(height-1, y+2)))
                if x+1 < width:
                    img.setPixel(x+1, y, img.pixel(x+1, min(height-1, y+2)))

    waterfall_view._scroll_waterfall_up = optimized_scroll

    # Optimize demo data function
    original_demo = waterfall_view.update_with_demo_data

    def optimized_demo():
        """Simplified demo data"""
        import numpy as np
        from PyQt5.QtCore import QTimer

        # Generate simpler data
        width = waterfall_view.waterfall_image.width()
        center = width // 2

        # Simplify animation
        if not hasattr(waterfall_view, 'frame_counter'):
            waterfall_view.frame_counter = 0
        waterfall_view.frame_counter += 1

        # Create a basic signal - minimal processing
        signal = np.zeros(width, dtype=np.float32) - 100  # Base level

        # Add a single peak that moves slowly
        pos = center + int(np.sin(waterfall_view.frame_counter * 0.02) * width * 0.3)
        width_factor = width // 15

        # Simplified gaussian without expensive calculations
        for x in range(max(0, pos - width_factor), min(width, pos + width_factor)):
            dist = abs(x - pos) / width_factor
            if dist < 1:
                signal[x] = -100 + 40 * (1 - dist)

        # Just shift the image and add the row
        waterfall_view._scroll_waterfall_up()
        waterfall_view._add_simple_row(signal)

        # Update UI less frequently
        if waterfall_view.frame_counter % 3 == 0:
            waterfall_view.update()

        # Continue with more delay
        QTimer.singleShot(300, optimized_demo)

    # Add simplified row addition function
    def add_simple_row(signal):
        """Add a single row of data with minimal processing"""
        colormap = waterfall_view._get_colormap()
        width = min(waterfall_view.waterfall_image.width(), len(signal))
        height = waterfall_view.waterfall_image.height()

        # Map values directly to colors - skip every other pixel
        value_range = waterfall_view.max_value - waterfall_view.min_value
        for x in range(0, width, 2):
            value = (signal[x] - waterfall_view.min_value) / value_range
            value = max(0.0, min(0.98, value))

            color_idx = min(255, max(0, int(value * 255)))
            waterfall_view.waterfall_image.setPixel(x, height-1, colormap[color_idx])
            # Also set adjacent pixel
            if x+1 < width:
                waterfall_view.waterfall_image.setPixel(x+1, height-1, colormap[color_idx])

    waterfall_view._add_simple_row = add_simple_row
    waterfall_view.update_with_demo_data = optimized_demo

    # Start with optimized version
    if hasattr(waterfall_view, 'init_timer'):
        waterfall_view.init_timer.stop()
    optimized_demo()

    return True

def optimize_spectrum_view(spectrum_view):
    """Apply optimizations to spectrum view"""
    logger.info("Applying spectrum view optimizations")

    # Disable mouse tracking and interaction
    spectrum_view.setMouseTracking(False)

    # Original mousePressEvent
    original_mouse_press = spectrum_view.mousePressEvent

    # Disable mouse press events
    def disabled_mouse_press(event):
        pass

    spectrum_view.mousePressEvent = disabled_mouse_press

    # Simplify the demo data generation
    original_demo = spectrum_view.update_with_demo_data

    def optimized_spectrum_demo():
        """Simplified demo data generation"""
        import numpy as np

        # Generate less complex data
        x = np.arange(len(spectrum_view.data))

        # Simple animation counter
        if not hasattr(spectrum_view, 'demo_phase'):
            spectrum_view.demo_phase = 0
        spectrum_view.demo_phase += 0.05  # Slower movement

        # Simple noise floor
        spectrum_view.data = np.ones_like(spectrum_view.data) * -130

        # Just add one peak that moves
        peak_pos = len(spectrum_view.data) * (0.5 + 0.25 * np.sin(spectrum_view.demo_phase))
        peak_width = len(spectrum_view.data) * 0.015

        # Add peak with simple calculation
        for i in range(len(spectrum_view.data)):
            dist = abs(i - peak_pos) / peak_width
            if dist < 3.0:  # Limit calculation to nearby points
                spectrum_view.data[i] += 25 * np.exp(-(dist*dist)/2)

        # Update display
        spectrum_view.update()

    spectrum_view.update_with_demo_data = optimized_spectrum_demo

    # Optimize the drawing routine
    original_draw_spectrum = spectrum_view._draw_spectrum

    def optimized_draw_spectrum(painter, rect, max_bin_index):
        """Simplified spectrum drawing"""
        from PyQt5.QtGui import QPen
        from PyQt5.QtCore import Qt

        # Use simple line drawing instead of path (less CPU intensive)
        spectrum_pen = QPen(spectrum_view.spectrum_color)
        spectrum_pen.setWidth(2)
        painter.setPen(spectrum_pen)

        # Step size for points (skip some for performance)
        step = max(1, max_bin_index // 200)

        # Draw direct lines with fewer points
        last_x = spectrum_view.plot_rect.left()
        last_y = spectrum_view._data_to_y(spectrum_view.data[0], rect)

        for i in range(step, max_bin_index + 1, step):
            x = int(spectrum_view.plot_rect.left() + i * spectrum_view.plot_rect.width() / max_bin_index)
            y = int(spectrum_view._data_to_y(spectrum_view.data[i], rect))
            painter.drawLine(last_x, last_y, x, y)
            last_x, last_y = x, y

        # Skip fill operation - major performance gain

    spectrum_view._draw_spectrum = optimized_draw_spectrum

    return True

def apply_performance_optimizations(main_window):
    """Apply performance optimizations to main window and its components"""
    logger.info("Applying performance optimizations to SSDigi Modem")

    # Optimize waterfall and spectrum views
    if hasattr(main_window, 'waterfall_view'):
        optimize_waterfall_view(main_window.waterfall_view)

    if hasattr(main_window, 'spectrum_view'):
        optimize_spectrum_view(main_window.spectrum_view)

    logger.info("Performance optimizations applied successfully")
    return True
