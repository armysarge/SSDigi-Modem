"""
Audio management for SS Ham Modem
"""
import pyaudio
import numpy as np
import logging
import threading
import time
from collections import deque
import wave

logger = logging.getLogger(__name__)

class AudioManager:
    """Audio device management for SS Ham Modem"""

    def __init__(self, config):
        """Initialize audio manager"""
        self.config = config
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.input_device = None
        self.output_device = None
        self.sample_rate = config.get('audio', 'sample_rate')
        self.channels = config.get('audio', 'channels')
        self.buffer_size = config.get('audio', 'buffer_size')

        # Audio processing
        self.recording = False
        self.playing = False
        self.input_buffer = deque(maxlen=1000)  # Store ~20 seconds at 48kHz
        self.output_buffer = deque(maxlen=1000)

        # Initialize the audio processing thread
        self.audio_thread = None
        self.audio_thread_running = False

    def __del__(self):
        """Cleanup audio resources"""
        self.close()

    def get_input_devices(self):
        """Get list of available input devices"""
        devices = []

        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                name = device_info['name']
                devices.append((name, i))

        return devices

    def get_output_devices(self):
        """Get list of available output devices"""
        devices = []

        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxOutputChannels'] > 0:
                name = device_info['name']
                devices.append((name, i))

        return devices

    def set_devices(self, input_device_index, output_device_index):
        """Set the input and output devices"""
        try:
            # Store device indices
            self.input_device = input_device_index
            self.output_device = output_device_index

            # Update config
            self.config.set('audio', 'input_device', input_device_index)
            self.config.set('audio', 'output_device', output_device_index)
            self.config.save()

            # Log device info
            input_info = self.audio.get_device_info_by_index(input_device_index)
            output_info = self.audio.get_device_info_by_index(output_device_index)

            logger.info(f"Input device set to: {input_info['name']}")
            logger.info(f"Output device set to: {output_info['name']}")

            return True

        except Exception as e:
            logger.error(f"Error setting audio devices: {e}")
            return False

    def start(self):
        """Start audio processing"""
        if self.audio_thread_running:
            logger.warning("Audio processing already running")
            return True

        try:
            # Open audio streams
            if not self._open_streams():
                return False

            # Start audio processing thread
            self.audio_thread_running = True
            self.audio_thread = threading.Thread(target=self._audio_processing_loop)
            self.audio_thread.daemon = True
            self.audio_thread.start()

            logger.info("Audio processing started")
            return True

        except Exception as e:
            logger.error(f"Error starting audio processing: {e}")
            self.close()
            return False

    def stop(self):
        """Stop audio processing"""
        if not self.audio_thread_running:
            return

        # Stop the audio thread
        self.audio_thread_running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=1.0)

        # Close audio streams
        self._close_streams()

        # Clear buffers
        self.input_buffer.clear()
        self.output_buffer.clear()

        logger.info("Audio processing stopped")

    def close(self):
        """Close all audio resources"""
        self.stop()

        # Clean up PyAudio
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
            self.audio = None

    def _open_streams(self):
        """Open audio input and output streams"""
        try:
            # Close any existing streams
            self._close_streams()

            # Open input stream
            if self.input_device is not None:
                self.input_stream = self.audio.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.input_device,
                    frames_per_buffer=self.buffer_size,
                    stream_callback=self._input_callback
                )

            # Open output stream
            if self.output_device is not None:
                self.output_stream = self.audio.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    output=True,
                    output_device_index=self.output_device,
                    frames_per_buffer=self.buffer_size,
                    stream_callback=self._output_callback
                )

            return True

        except Exception as e:
            logger.error(f"Error opening audio streams: {e}")
            self._close_streams()
            return False

    def _close_streams(self):
        """Close audio streams"""
        try:
            if self.input_stream:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None

            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
        except Exception as e:
            logger.error(f"Error closing audio streams: {e}")

    def _input_callback(self, in_data, frame_count, time_info, status):
        """Callback for input stream"""
        if status:
            logger.warning(f"Input stream status: {status}")

        if self.recording:
            # Convert byte data to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)

            # Store in input buffer
            self.input_buffer.append(audio_data.copy())

        return None, pyaudio.paContinue

    def _output_callback(self, in_data, frame_count, time_info, status):
        """Callback for output stream"""
        if status:
            logger.warning(f"Output stream status: {status}")

        if self.playing and len(self.output_buffer) > 0:
            # Get data from output buffer
            audio_data = self.output_buffer.popleft()

            # Ensure correct frame count
            if len(audio_data) < frame_count * self.channels:
                # Pad with zeros if needed
                padding = np.zeros(frame_count * self.channels - len(audio_data), dtype=np.float32)
                audio_data = np.concatenate((audio_data, padding))
            elif len(audio_data) > frame_count * self.channels:
                # Truncate if too large
                audio_data = audio_data[:frame_count * self.channels]

            return audio_data.tobytes(), pyaudio.paContinue
        else:
            # Return silence if no data available
            return np.zeros(frame_count * self.channels, dtype=np.float32).tobytes(), pyaudio.paContinue

    def _audio_processing_loop(self):
        """Audio processing thread"""
        try:
            while self.audio_thread_running:
                # Process audio here (filtering, modem operations, etc.)
                # This is where integration with the modem would occur

                # Sleep to reduce CPU usage
                time.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in audio processing loop: {e}")

    def start_recording(self):
        """Start recording audio"""
        self.recording = True
        logger.info("Recording started")

    def stop_recording(self):
        """Stop recording audio"""
        self.recording = False
        logger.info("Recording stopped")

    def get_recorded_data(self):
        """Get recorded audio data"""
        if not self.input_buffer:
            return None

        # Combine all buffers
        combined_data = np.concatenate(list(self.input_buffer))
        return combined_data

    def play_data(self, audio_data):
        """Play audio data"""
        if not self.output_stream:
            logger.error("Output stream not available")
            return False

        # Split data into buffer-sized chunks
        chunk_size = self.buffer_size * self.channels
        chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]

        # Add to output buffer
        for chunk in chunks:
            self.output_buffer.append(chunk)

        # Start playback
        self.playing = True
        logger.info(f"Playback started ({len(chunks)} chunks)")
        return True

    def stop_playback(self):
        """Stop audio playback"""
        self.playing = False
        self.output_buffer.clear()
        logger.info("Playback stopped")

    def save_to_wav(self, file_path):
        """Save recorded audio to WAV file"""
        data = self.get_recorded_data()
        if data is None:
            logger.error("No data to save")
            return False

        try:
            with wave.open(file_path, 'w') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(4)  # 4 bytes for float32
                wf.setframerate(self.sample_rate)
                wf.writeframes(data.tobytes())

            logger.info(f"Audio saved to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving WAV file: {e}")
            return False

    def load_from_wav(self, file_path):
        """Load audio from WAV file"""
        try:
            with wave.open(file_path, 'r') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

                # Convert to float32
                if sample_width == 2:  # 16-bit audio
                    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                elif sample_width == 4:  # 32-bit audio
                    data = np.frombuffer(frames, dtype=np.float32)
                else:
                    logger.error(f"Unsupported sample width: {sample_width}")
                    return False

                # Resample if needed
                if sample_rate != self.sample_rate:
                    # Simple resampling - for production use scipy.signal.resample
                    ratio = self.sample_rate / sample_rate
                    data = np.interp(
                        np.arange(0, len(data) * ratio, ratio),
                        np.arange(0, len(data)),
                        data
                    )

                # Convert to stereo if needed
                if channels == 1 and self.channels == 2:
                    data = np.repeat(data, 2)

                # Clear existing data and store loaded data
                self.input_buffer.clear()

                # Split data into buffer-sized chunks
                chunk_size = self.buffer_size * self.channels
                chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

                # Add chunks to input buffer
                for chunk in chunks:
                    self.input_buffer.append(chunk)

                logger.info(f"Audio loaded from {file_path}")
                return True

        except Exception as e:
            logger.error(f"Error loading WAV file: {e}")
            return False
