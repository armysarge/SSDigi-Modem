"""
Helper script to copy ARDOP binaries for inclusion in PyInstaller package
"""
import os
import sys
import shutil
import platform
import glob

def ensure_ardop_binaries():
    """
    Copy ARDOP binaries to a location where they will be properly included
    in the PyInstaller package
    """
    print("Setting up ARDOP binaries for packaging...")

    # Get the base directory for the project
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Create bin directory if it doesn't exist
    bin_dir = os.path.join(base_dir, "ss_ham_modem", "bin")
    os.makedirs(bin_dir, exist_ok=True)

    # Determine the platform
    if platform.system() == 'Windows':
        # Check all possible locations for the ARDOP binary, in priority order
        possible_paths = [
            # First check the build directory where it's most likely to be
            os.path.join(base_dir, "build", "ardop", "Release", "ardop.exe"),
            os.path.join(base_dir, "build", "Release", "ardop.exe"),
            os.path.join(base_dir, "build", "ardop.exe"),
            # Then check the ardop directory
            os.path.join(base_dir, "ardop", "ardopcf.exe"),
            os.path.join(base_dir, "ardop", "ardop.exe"),
            # Then check the bin directory
            os.path.join(base_dir, "bin", "ardop", "windows", "ardop.exe"),
            # Last resort, search for any ardop*.exe in the workspace
        ]

        source_path = None
        for path in possible_paths:
            if os.path.exists(path):
                source_path = path
                print(f"Found ARDOP binary at: {source_path}")
                break

        # If still not found, do a broader search
        if source_path is None:
            print("ARDOP binary not found in standard locations, searching broadly...")
            search_patterns = [
                os.path.join(base_dir, "**", "ardop*.exe"),
                os.path.join(base_dir, "build", "**", "ardop*.exe"),
                os.path.join(base_dir, "bin", "**", "ardop*.exe"),
            ]

            for pattern in search_patterns:
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    source_path = matches[0]
                    print(f"Found ARDOP binary at: {source_path}")
                    break

        if not source_path or not os.path.exists(source_path):
            print("ERROR: ARDOP binary not found in any location!")
            return False

        dest_path = os.path.join(bin_dir, "ardop.exe")
        print(f"Copying ARDOP binary: {source_path} -> {dest_path}")
        shutil.copy2(source_path, dest_path)
        print(f"Successfully copied ARDOP binary to {dest_path}")

    elif platform.system() == 'Linux':
        # Copy Linux ARDOP binary
        source_path = os.path.join(base_dir, "ardop", "ardopcf")
        if not os.path.exists(source_path):
            # Try fallback location
            source_path = os.path.join(base_dir, "bin", "ardop", "linux", "ardop")

        if not os.path.exists(source_path):
            print(f"ERROR: ARDOP binary not found at {source_path}")
            return False

        dest_path = os.path.join(bin_dir, "ardop")
        shutil.copy2(source_path, dest_path)
        print(f"Copied ARDOP binary: {source_path} -> {dest_path}")

        # Make it executable
        os.chmod(dest_path, 0o755)
    else:
        print(f"ERROR: Unsupported platform: {platform.system()}")
        return False

    return True

if __name__ == "__main__":
    if ensure_ardop_binaries():
        print("ARDOP binaries prepared successfully for packaging")
        sys.exit(0)
    else:
        print("Failed to prepare ARDOP binaries for packaging")
        sys.exit(1)
