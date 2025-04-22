# SS-Ham-Modem

![SS-Ham-Modem Logo](images/ss-ham-modem-logo.png)

## Overview

SS-Ham-Modem is a comprehensive digital modem application for amateur radio operators. It provides a modern interface for ARDOP (Amateur Radio Digital Open Protocol) communication with features similar to VARA but in an open-source implementation. The application includes spectrum analysis, waterfall display, rig control via Hamlib, and a flexible configuration system.

## Features

- **Digital Modes**: Implements ARDOP protocol for reliable digital communication
- **Spectrum Display**: Real-time FFT spectrum analyzer showing frequency domain data
- **Waterfall Display**: Time-frequency visualization with multiple color schemes
- **Rig Control**: Full HAMLIB integration for controlling amateur radio equipment
- **Audio Processing**: Configurable audio device selection, recording, and playback
- **License System**: Different feature tiers with varying capabilities (Free, Basic, Pro)
- **Cross Platform**: Runs on both Windows and Linux systems

## Screenshots

![Main Interface](images/screenshot-main.png)
![Waterfall Display](images/screenshot-waterfall.png)
![Settings](images/screenshot-settings.png)

## Requirements

- Python 3.7 or higher
- PyQt5
- HAMLIB (for rig control)
- ARDOP binaries

## Installation

### From Source

1. Clone this repository:
   ```powershell
   git clone https://github.com/yourusername/SS-Ham-Modem.git
   cd SS-Ham-Modem
   ```

2. Create a virtual environment (recommended):
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

4. Run the application:
   ```powershell
   python run_modem.py
   ```

### Pre-built Packages

Pre-built packages are available for Windows and Linux. Download from the [releases page](https://github.com/yourusername/SS-Ham-Modem/releases).

## Usage

### Basic Operation

1. Launch the application
2. Select your audio input and output devices in the Settings dialog
3. Configure your radio via HAMLIB (if applicable)
4. Use the spectrum and waterfall displays to monitor signals
5. Connect to digital mode applications for message exchange

### Configuration

The application can be configured via the Settings dialog:

- **Audio**: Select audio devices, sample rate, and buffer size
- **Modem**: Configure ARDOP parameters like bandwidth and center frequency
- **HAMLIB**: Set up rig control for your specific radio model
- **Display**: Customize the user interface appearance
- **Network**: Configure interfaces to host applications

## License System

SS-Ham-Modem offers different feature tiers:

- **Free**: Basic functionality with limited bandwidth (500 Hz)
- **Basic**: Increased bandwidth (2000 Hz) and speed
- **Pro**: Maximum bandwidth (5000 Hz), speed, and advanced features

Licenses are tied to your amateur radio callsign. Contact the project maintainer to purchase a license.

## Building from Source

### Prerequisites

- Python 3.7+
- Qt development tools (for PyQt5)
- C++ compiler (for HAMLIB and ARDOP)

### Build Steps

1. Install development dependencies:
   ```powershell
   pip install -r requirements-dev.txt
   ```

2. Package the application:
   ```powershell
   python tools/package.py --platform all
   ```

### Create license key file

```
python tools/license_generator.py --callsign W1ABC --tier pro --out W1ABC_license.dat
```

## Build package

```
python tools/package.py [options]

Options:
  --platform {windows,linux,all}  Platform to build for
  --obfuscate                     Obfuscate Python code for protection
  --no-binaries                   Skip bundling binaries
  --build-only                    Build without packaging
  --version VERSION               Version number for the package
```

```
python tools/package.py --platform windows --obfuscate
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the LICENSE file for details.

## Acknowledgments

- Thanks to [ARDOP](https://ardop.org) for the digital protocol implementation
- [HAMLIB](https://hamlib.github.io) for the amateur radio control library
- The amateur radio community for continued testing and feedback
