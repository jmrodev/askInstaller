#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Introduction ---
echo "This script helps build the 'ask-gemini' package or provides instructions for Arch Linux."
echo "---------------------------------------------------------------------------------------"
echo ""

# --- Debian/Ubuntu Package Build Option ---
read -r -p "Do you want to build the Debian/Ubuntu (.deb) package? (yes/no): " build_deb_choice

if [[ "${build_deb_choice,,}" == "yes" ]]; then
    print_info() {
        echo "INFO: $1"
    }
    print_error() {
        echo "ERROR: $1" >&2
    }

    print_info "Starting Debian package build..."

    # Check if the debian/ directory exists
    if [ ! -d "debian" ]; then
        print_error "'debian' directory not found. Make sure you are in the project root"
        print_error "and Debian packaging files (control, rules, changelog, etc.) are set up in the 'debian' subdirectory."
        exit 1
    fi
    print_info "'debian' directory found."

    # Check if dpkg-buildpackage is available
    if ! command -v dpkg-buildpackage &> /dev/null; then
        print_error "dpkg-buildpackage not found. Please install it."
        print_error "On Debian/Ubuntu, you can usually install it with: sudo apt update && sudo apt install build-essential devscripts debhelper"
        exit 1
    fi
    print_info "dpkg-buildpackage found."

    print_info "Attempting to build the .deb package..."
    # The dpkg-buildpackage command should be run from the directory containing the 'debian' subdirectory
    # and the main source files (ask_gemini.py, ask wrapper, etc.).
    # This script assumes it's already in that directory.
    if dpkg-buildpackage -us -uc -b; then
        # Try to find the .deb file. It's usually in the parent directory.
        # Package name is 'ask-gemini', version is assumed '0.1.0', arch 'all' from debian/control
        # This is a heuristic and might need adjustment if versioning or arch changes significantly.
        # A more robust way would be to parse debian/changelog for version or use dpkg-genchanges output.
        DEB_FILE_NAME_PATTERN="../ask-gemini_0.1.0*_all.deb" # Assuming version starts with 0.1.0
        
        # Use a loop to find the file, as the exact version part might vary slightly (e.g., -1, -1ubuntu1)
        deb_file_found=""
        for f in $DEB_FILE_NAME_PATTERN; do
            if [ -f "$f" ]; then
                deb_file_found="$f"
                break
            fi
        done

        if [ -n "$deb_file_found" ]; then
            print_info "---------------------------------------------------------------------------------------"
            print_info "Debian package built successfully! You can find it at: $deb_file_found"
            print_info "---------------------------------------------------------------------------------------"
        else
            # If set -e is active, this part might not be reached on dpkg-buildpackage failure.
            # However, if dpkg-buildpackage succeeds but the file isn't found (e.g., name pattern mismatch),
            # this provides feedback.
            print_warning "Debian package build command seemed to succeed, but the .deb file was not found with pattern '$DEB_FILE_NAME_PATTERN'."
            print_warning "Please check the parent directory ('../') for the generated .deb file manually."
        fi
    else
        # This else block might not be reached if set -e causes exit on dpkg-buildpackage failure.
        # It's here for completeness in case set -e behavior is altered or the command fails in a way that doesn't exit.
        print_error "Debian package build failed."
        exit 1
    fi
else
    echo "Skipping Debian package build."
fi

echo "" # Newline for separation

# --- Arch Linux Instructions ---
echo "--- Arch Linux / Manjaro Users ---"
if [ -f "ARCH_INSTALL_INSTRUCTIONS.md" ]; then
    echo "For Arch Linux / Manjaro, please follow the instructions in 'ARCH_INSTALL_INSTRUCTIONS.md'"
    echo "to build and install the package using the provided PKGBUILD."
    echo "Ensure PKGBUILD, ask, ask_gemini.py, ask.1, and LICENSE are in the same directory for building."
else
    echo "PKGBUILD and installation instructions for Arch Linux should be available."
    echo "Please look for 'PKGBUILD' and 'ARCH_INSTALL_INSTRUCTIONS.md' in the project files."
    echo "Ensure ask, ask_gemini.py, ask.1, and LICENSE are in the same directory as PKGBUILD for building."
fi

echo "" # Newline for separation

# --- Final Message ---
echo "---------------------------------------------------------------------------------------"
echo "Build script finished."
echo "Remember to set your GEMINI_API_KEY environment variable to use the 'ask' command."
echo "---------------------------------------------------------------------------------------"

exit 0
