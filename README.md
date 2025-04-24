[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/armysarge/ssdigi-modem)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-brightgreen?logo=buymeacoffee)](https://www.buymeacoffee.com/armysarge)

[![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15.4-blue.svg)](https://pypi.org/project/PyQt5/)
[![NumPy](https://img.shields.io/badge/NumPy-1.19.2-blue.svg)](https://numpy.org/install/)
[![SoundDevice](https://img.shields.io/badge/SoundDevice-0.4.1-blue.svg)](https://pypi.org/project/sounddevice/)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![GitHub issues](https://img.shields.io/github/issues/armysarge/ssdigi-modem)](https://github.com/armysarge/ssdigi-modem/issues)

# SSDigi Modem

 SSDigi Modem is a software modem for amateur radio digital communications. It provides a flexible platform for transmitting and receiving digital data over radio frequencies with various modulation schemes. Supports Windows, Linux, and MacOS.

## Features

- **Spectrum Analyzer**: Real-time visualization of frequency spectrum with configurable display range
- **Waterfall Display**: Time-based visualization of signal strength across frequencies
- **Configurable Bandwidth**: Adjustable signal bandwidth with visual indicators
- **Frequency Selection**: Interactive frequency selection directly from the spectrum display
- **Audio Processing**: Direct interface with sound card input/output for signal processing

## Installation

### Requirements
- Python 3.6+
- PyQt5
- NumPy
- SoundDevice (for audio I/O)

### Setup
1. Clone the repository:
   ```
   git clone https://github.com/armysarge/SSDigi-Modem.git
   cd SSDigi-Modem
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running and Packaging

### Running the Application

After installing dependencies (see Installation), you can run the app with:

```pwsh
python run_modem.py
```

### Packaging for Windows and Linux

This project includes a packaging script at `tools/package.py` that automates building and packaging for both Windows and Linux.

#### 1. Install Requirements

Make sure you have all dependencies installed:
```pwsh
pip install -r requirements.txt
```
You may also need PyInstaller and other build tools:
```pwsh
pip install pyinstaller
```

#### 2. Run the Packaging Script

From the project root, run:
```pwsh
python tools/package.py --platform windows
```
or for Linux:
```pwsh
python tools/package.py --platform linux
```
or to build for both:
```pwsh
python tools/package.py --platform all
```

You can see all available options with:
```pwsh
python tools/package.py --help
```

#### 3. Output

- The packaged executables and archives will be placed in the `dist/` directory.
- For Windows, you’ll get a `.zip` file; for Linux, a `.tar.gz` archive.

#### 4. Notes

- The script will attempt to build native ARDOP binaries for each platform.
- If you want to skip building binaries, use `--no-binaries`.
- For advanced options (obfuscation, build-only, etc.), see the help output.

## Usage

The main interface displays both spectrum and waterfall views of the received signal. The spectrum view shows signal strength across frequencies at the current moment, while the waterfall displays signal history over time.

- **Adjust Bandwidth**: Change the bandwidth settings in the configuration panel
- **Select Frequency**: Click on the spectrum display to select a specific frequency
- **Adjust Display Range**: Configure the spectrum display multiplier to see more context beyond the operating bandwidth

## Configuration

The software uses a configuration system with these key parameters:

- **Audio Settings**:
  - `sample_rate`: Audio sampling rate (default: 48000 Hz)
  - `input_device`: Audio input device selection
  - `output_device`: Audio output device selection

- **Modem Settings**:
  - `center_freq`: Center frequency for the modem operation
  - `bandwidth`: Operating bandwidth in Hz

- **UI Settings**:
  - `fft_size`: Size of the FFT for spectrum analysis
  - `spectrum_ref_level`: Reference level for spectrum display in dB
  - `spectrum_range`: Range of the spectrum display in dB
  - `freq_display_multiplier`: Multiplier for frequency display range (2.0 = show twice the bandwidth)

## Development

This project is under active development. Contributions are welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

Ardobcf is a derivative of the original ARDOP project, which is a software modem for amateur radio digital communications. The SSDigi Modem builds upon the concepts and codebase of ARDOP to provide a more flexible and user-friendly experience.

## License

This software is distributed under the MIT License. See the LICENSE file for more information.