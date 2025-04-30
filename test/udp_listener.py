#!/usr/bin/env python3
"""
Robust UDP listener for ARDOP spectrum data
This script listens on a UDP port and prints any data received
"""
import socket
import sys
import time
import struct
import logging
import binascii
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more information
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def listen_udp(host='0.0.0.0', port=8514, buffer_size=32768, timeout=0.5):
    """Listen for any UDP data on the specified port and print information about it"""
    # Initialize tracking variables
    listen_udp.last_timeout_log = time.time()
    listen_udp.dots = 0
    listen_udp.last_activation_time = 0
    listen_udp.fft_packets = 0  # Counter for real FFT packets (not echoes)

    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set SO_REUSEADDR to avoid "address in use" errors when restarting
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(timeout)

        print(f"Listening for UDP packets on {host}:{port}...")
        print("Press Ctrl+C to exit")

        # Statistics
        packets_received = 0
        start_time = time.time()
        last_packet_time = 0

        # Send initial activation - this is now a function for easier reuse
        send_activation_commands()

        while True:
            try:
                # Send periodic activation commands (every 15 seconds)
                current_time = time.time()
                if (current_time - listen_udp.last_activation_time) > 15:
                    print("\nSending periodic activation commands...")
                    send_activation_commands()
                    listen_udp.last_activation_time = current_time

                # Wait for data
                data, addr = sock.recvfrom(buffer_size)
                current_time = time.time()
                packets_received += 1

                # Reset dots counter when we get a packet
                listen_udp.dots = 0

                # Calculate time since last packet
                if last_packet_time > 0:
                    time_since_last = current_time - last_packet_time
                    if time_since_last > 1.0:  # Only log if gap is significant
                        print(f"\nTime since last packet: {time_since_last:.3f} seconds")

                last_packet_time = current_time

                # Print info about the packet
                print(f"\nReceived packet #{packets_received} from {addr[0]}:{addr[1]}")
                print(f"Packet size: {len(data)} bytes")

                # Print the first few bytes in hex
                print(f"First 16 bytes: {binascii.hexlify(data[:16]).decode()}")

                # Try to interpret the first byte as a type indicator
                if data:
                    first_byte = data[0]
                    print(f"First byte (type indicator): {first_byte} (ASCII: {chr(first_byte) if 32 <= first_byte <= 126 else 'non-printable'})")

                    # If it's our expected 'W' type (87 in ASCII) for waterfall/spectrum
                    if first_byte == ord('W'):
                        # Check if this is actually the text command "Waterfall" being echoed back
                        if len(data) < 20:
                            try:
                                text_data = data.decode('ascii', errors='ignore').strip()
                                if text_data.startswith("Waterfall") or text_data.startswith("Spectrum"):
                                    print(f"This is an echo of the activation command: '{text_data}'")
                                    print("This is not spectrum data - waiting for actual FFT data...")
                                    continue
                            except:
                                pass

                        print("This appears to be Waterfall/Spectrum data!")

                        # Try to parse the number of samples
                        if len(data) >= 3:
                            num_samples = (data[1] << 8) | data[2]
                            print(f"Number of spectrum samples: {num_samples}")

                            # Sanity check - if num_samples is unreasonably large, this is probably not real FFT data
                            if num_samples > 4096 or num_samples < 1:
                                print(f"WARNING: Sample count {num_samples} seems incorrect.")
                                print(f"This is likely not FFT data but the command being echoed back.")
                                hex_view = ' '.join(f"{b:02x}" for b in data[:min(32, len(data))])
                                print(f"Hex view: {hex_view}")
                                text_view = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[:min(32, len(data))])
                                print(f"ASCII view: {text_view}")
                                continue

                            # Check if the packet is the expected size
                            expected_size = 3 + num_samples * 4  # 3 bytes header + 4 bytes per float
                            if len(data) == expected_size:
                                print(f"Packet size matches expected size for {num_samples} samples")
                                listen_udp.fft_packets += 1
                                print(f"FFT packets received: {listen_udp.fft_packets}")
                            else:
                                print(f"Packet size mismatch: got {len(data)}, expected {expected_size}")
                                print(f"NOTE: This might be a different format than expected, but we'll still try to parse it")

                            # Print a few sample values
                            if len(data) >= 7:  # At least header + one float
                                sample_values = []
                                for i in range(min(5, num_samples)):
                                    offset = 3 + i * 4
                                    if offset + 4 <= len(data):
                                        try:
                                            value = struct.unpack('f', data[offset:offset+4])[0]
                                            # Check if value is reasonable - FFT values are usually between 0 and 1
                                            if value > 0 and value < 10000:
                                                sample_values.append(value)
                                            else:
                                                print(f"Warning: Sample {i} value {value} seems out of range")
                                        except:
                                            print(f"Error unpacking sample at offset {offset}")

                                # Calculate dB values if we have any samples
                                if sample_values:
                                    db_values = [10 * np.log10(v + 1e-10) for v in sample_values]
                                    print(f"First few sample values: {sample_values}")
                                    print(f"First few sample values (dB): {db_values}")
                                else:
                                    # If we couldn't parse sample values, show raw bytes for analysis
                                    raw_bytes = [f"{b:02x}" for b in data[3:min(23, len(data))]]
                                    print(f"Raw bytes after header: {' '.join(raw_bytes)}")
                    else:
                        # Handle non-W type packets - show content preview
                        try:
                            # Attempt to decode as text
                            text_preview = data[:32].decode('utf-8', errors='replace')
                            print(f"Data content preview: {text_preview}")

                            # Show more detailed hex view for first 32 bytes
                            hex_view = ' '.join(f"{b:02x}" for b in data[:32])
                            print(f"First 32 bytes (hex): {hex_view}")
                        except Exception as e:
                            print(f"Error decoding packet data: {str(e)}")

                # Print packet rate every 10 packets
                if packets_received % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = packets_received / elapsed if elapsed > 0 else 0
                    print(f"\nReceived {packets_received} packets in {elapsed:.1f} seconds ({rate:.2f} packets/sec)")

            except socket.timeout:
                # This is normal, just continue
                listen_udp.dots += 1

                # Print a dot for every timeout to show the script is still running
                sys.stdout.write(".")

                # Add a newline every 80 dots for better readability
                if listen_udp.dots % 80 == 0:
                    sys.stdout.write("\n")

                sys.stdout.flush()

                # Log timeout with timestamp periodically to help diagnose timing issues
                current_time = time.time()
                if current_time - listen_udp.last_timeout_log > 10:
                    listen_udp.last_timeout_log = current_time
                    print(f"\nNo packets received for {timeout} seconds at {time.strftime('%H:%M:%S')}")

                    # Every 30 seconds, show a more detailed reminder if no packets yet
                    if listen_udp.fft_packets == 0 and (listen_udp.dots % (30/timeout)) < 1:
                        print("\nStill waiting for first FFT packet... ")
                        print("Try these troubleshooting steps:")
                        print(" 1. Make sure ARDOP is configured to send spectrum data")
                        print(" 2. Check ARDOP log files for UDP-related errors")
                        print(" 3. Try changing the port being used (8514 or 8515)")
                        print(" 4. Restart ARDOP and this listener")

            except ConnectionResetError:
                # This can happen if the sending application closes unexpectedly
                print("\nConnection reset by peer. This is normal for UDP - continuing to listen...")
                # Try resending activation commands
                send_activation_commands()

            except OSError as e:
                # Handle OS-level socket errors with more helpful guidance
                print(f"\nSocket error: {e}. Continuing to listen...")

                # If it's an "address in use" error, provide specific guidance
                if "address already in use" in str(e).lower():
                    print("\nERROR: The port is already in use.")
                    print("Try a different port or close any other applications using this port.")

            except Exception as e:
                # Catch any other exceptions to keep the script running
                print(f"\nUnexpected error while processing packet: {str(e)}")
                logger.exception("Error processing packet")

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        if 'sock' in locals():
            sock.close()


def check_for_ardop():
    """Check if ARDOP is running by attempting to connect to known ports"""
    results = []

    # Try to get local IP addresses
    try:
        hostname = socket.gethostname()
        addresses = socket.gethostbyname_ex(hostname)[2]
    except:
        addresses = ['127.0.0.1']

    # Always include localhost
    if '127.0.0.1' not in addresses:
        addresses.insert(0, '127.0.0.1')

    print("Checking for ARDOP on your system...")

    # Check common ARDOP ports
    for addr in addresses:
        for port in [8515, 8516, 8514]:
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                test_socket.connect((addr, port))
                test_socket.close()
                results.append(f"Found service on {addr}:{port} (possibly ARDOP)")
            except:
                pass

    if results:
        print("Detected possible ARDOP services:")
        for result in results:
            print(f" - {result}")
    else:
        print("No ARDOP services detected. Make sure ARDOP is running.")

    return bool(results)


def send_activation_commands():
    """Send various commands to ARDOP to activate spectrum display"""
    try:
        # Create UDP socket for sending commands
        enable_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        enable_sock.settimeout(0.5)

        # Try different formats for the commands
        commands = [
            (b"Spectrum", 8514),
            (b"Waterfall", 8514),
            (b"Spectrum\r", 8514),
            (b"Waterfall\r", 8514),
            # Also try backup ports
            (b"Spectrum", 8515),
            (b"Waterfall", 8515),
        ]

        # Send each command
        for cmd, cmd_port in commands:
            try:
                enable_sock.sendto(cmd, ("127.0.0.1", cmd_port))
            except:
                pass

        enable_sock.close()

        # Record the time we sent activation commands
        listen_udp.last_activation_time = time.time()
        return True

    except Exception as e:
        print(f"Error sending activation commands: {e}")
        return False


if __name__ == "__main__":
    # Print header
    print("\n" + "=" * 60)
    print("ROBUST UDP LISTENER FOR ARDOP SPECTRUM DATA".center(60))
    print("=" * 60)

    # Get command line arguments if provided
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'  # Default to all interfaces
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8514  # Default to 8514 (ARDOP GUI port)
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5

    # Print startup information
    print(f"UDP Listener v3.1 - Starting up...")
    print(f"Host: {host} (0.0.0.0 means listen on all interfaces)")
    print(f"Port: {port}")
    print(f"Socket timeout: {timeout} seconds")
    print(f"Buffer size: 32768 bytes")

    # Display network interfaces
    print("\nAvailable network interfaces:")
    try:
        hostname = socket.gethostname()
        addresses = socket.gethostbyname_ex(hostname)[2]
        for ip in addresses:
            print(f" - {ip}")
    except Exception as e:
        print(f"Error getting network interfaces: {e}")

    # Check for running ARDOP services
    if check_for_ardop():
        print("\nARDOP seems to be running. Will attempt to activate spectrum display.")
    else:
        print("\nWARNING: No ARDOP services detected! Please start ARDOP first.")
        choice = input("Do you want to continue anyway? (y/n): ")
        if choice.lower() != 'y':
            print("Exiting...")
            sys.exit(0)

    # Final startup message
    print("\n" + "*" * 60)
    print("* LISTENER IS RUNNING - WAITING FOR PACKETS                 *")
    print("* Sending activation commands to port 8514...               *")
    print("*" * 60 + "\n")

    # Start listening
    listen_udp(host, port, timeout=timeout)
