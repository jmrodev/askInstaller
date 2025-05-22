#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
USER_BIN_DIR="$HOME/.local/bin"
APP_INSTALL_DIR="$HOME/.local/share/ask-gemini"
USER_MAN_DIR="$HOME/.local/share/man/man1"
PYTHON_CMD="python3" # Assume python3 is the command for Python 3
SCRIPT_VERSION="0.1.0" # Or a way to dynamically get this

# --- Helper Functions ---
print_info() {
    echo "INFO: $1"
}

print_warning() {
    echo "WARNING: $1"
}

print_error() {
    echo "ERROR: $1" >&2
}

# --- Dependency Checking ---
print_info "Starting Ask Gemini (v$SCRIPT_VERSION) installation..."
print_info "Checking dependencies..."

# 1. Python 3
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    print_error "$PYTHON_CMD is not installed or not in PATH. Please install Python 3."
    print_error "For Debian/Ubuntu: sudo apt update && sudo apt install python3"
    print_error "For Fedora: sudo dnf install python3"
    print_error "For macOS (using Homebrew): brew install python"
    exit 1
fi
print_info "Python 3 found: $($PYTHON_CMD --version)"

# 2. pip
if ! "$PYTHON_CMD" -m pip --version &> /dev/null; then
    print_error "pip for $PYTHON_CMD is not available."
    print_error "Please install pip for Python 3. For example:"
    print_error "Debian/Ubuntu: sudo apt update && sudo apt install python3-pip"
    print_error "Fedora: sudo dnf install python3-pip"
    print_error "Or visit https://pip.pypa.io/en/stable/installation/"
    exit 1
fi
print_info "pip for $PYTHON_CMD found."

# 3. Python 'requests' library
print_info "Checking for 'requests' Python library..."
if "$PYTHON_CMD" -m pip show requests &> /dev/null; then
    print_info "'requests' library is already installed."
else
    print_warning "'requests' library not found."
    read -r -p "Do you want to attempt to install it using '$PYTHON_CMD -m pip install --user requests'? (y/N): " install_requests
    if [[ "$install_requests" =~ ^[Yy]$ ]]; then
        print_info "Attempting to install 'requests' library..."
        if "$PYTHON_CMD" -m pip install --user requests; then
            print_info "'requests' library installed successfully."
        else
            print_error "Failed to install 'requests' library. Please install it manually (e.g., '$PYTHON_CMD -m pip install requests')."
            exit 1
        fi
    else
        print_error "'requests' library is required. Please install it manually (e.g., '$PYTHON_CMD -m pip install requests')."
        exit 1
    fi
fi

# --- Check for Source Files ---
REQUIRED_FILES=("ask_gemini.py" "ask" "ask.1" "LICENSE") # Assuming LICENSE file exists
print_info "Checking for required source files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "Required source file '$file' not found in the current directory. Aborting."
        print_error "Please ensure you are running this script from the root of the source directory where all components (ask_gemini.py, ask wrapper, ask.1, LICENSE) are present."
        exit 1
    fi
done
print_info "All required source files found."

# --- Installation Process ---
print_info "Starting installation process..."

# 1. Create installation directories
print_info "Creating installation directories..."
mkdir -p "$USER_BIN_DIR" || { print_error "Failed to create $USER_BIN_DIR. Aborting."; exit 1; }
mkdir -p "$APP_INSTALL_DIR" || { print_error "Failed to create $APP_INSTALL_DIR. Aborting."; exit 1; }
mkdir -p "$USER_MAN_DIR" || { print_error "Failed to create $USER_MAN_DIR. Aborting."; exit 1; }
print_info "Installation directories ensured: $USER_BIN_DIR, $APP_INSTALL_DIR, $USER_MAN_DIR"

# 2. Copy files
print_info "Copying application files..."
cp "ask_gemini.py" "$APP_INSTALL_DIR/ask_gemini.py" || { print_error "Failed to copy ask_gemini.py. Aborting."; exit 1; }
if [ -f "LICENSE" ]; then
    cp "LICENSE" "$APP_INSTALL_DIR/LICENSE" || { print_error "Failed to copy LICENSE. Aborting."; exit 1; }
    print_info "ask_gemini.py and LICENSE copied to $APP_INSTALL_DIR"
else
    print_warning "LICENSE file not found in the source directory. Skipping license installation."
    print_info "ask_gemini.py copied to $APP_INSTALL_DIR"
fi


# 3. Modify and install wrapper script
print_info "Installing wrapper script 'ask'..."
ASK_WRAPPER_TARGET="$APP_INSTALL_DIR/ask"
# Modify SCRIPT_DIR in the 'ask' wrapper to point to the new APP_INSTALL_DIR
# Handles cases where SCRIPT_DIR might be commented or have spaces around '='
# Note: This assumes the 'ask' script contains a line like 'SCRIPT_DIR="/path/to/original/dir"'
# or '# SCRIPT_DIR="/path/to/original/dir"' that needs to be updated.
# A more robust sed might be needed if the 'ask' script's SCRIPT_DIR line is very different.
sed "s|^#*\s*SCRIPT_DIR=.*|SCRIPT_DIR=\"$APP_INSTALL_DIR\"|g" "ask" > "$ASK_WRAPPER_TARGET" || { print_error "Failed to modify ask wrapper script. Aborting."; exit 1; }

chmod +x "$ASK_WRAPPER_TARGET" || { print_error "Failed to make $ASK_WRAPPER_TARGET executable. Aborting."; exit 1; }
print_info "Wrapper script 'ask' installed to $ASK_WRAPPER_TARGET and made executable."

# 4. Create symlink
print_info "Creating symbolic link in $USER_BIN_DIR..."
# Remove existing symlink or file at target location to avoid 'ln' error
if [ -L "$USER_BIN_DIR/ask" ] || [ -f "$USER_BIN_DIR/ask" ]; then
    print_warning "Existing file or symlink at $USER_BIN_DIR/ask found. Removing it."
    rm -f "$USER_BIN_DIR/ask" || { print_error "Failed to remove existing $USER_BIN_DIR/ask. Aborting."; exit 1; }
fi
ln -s "$ASK_WRAPPER_TARGET" "$USER_BIN_DIR/ask" || { print_error "Failed to create symbolic link. Aborting."; exit 1; }
print_info "Symbolic link created: $USER_BIN_DIR/ask -> $ASK_WRAPPER_TARGET"

# 5. Install man page
print_info "Installing man page..."
cp "ask.1" "$USER_MAN_DIR/ask.1" || { print_error "Failed to copy man page. Aborting."; exit 1; }
print_info "Man page 'ask.1' installed to $USER_MAN_DIR/ask.1"

# --- PATH Configuration Check ---
print_info "Checking PATH configuration..."
if [[ ":$PATH:" != *":$USER_BIN_DIR:"* ]]; then
    print_warning "$USER_BIN_DIR is not in your PATH."
    echo "To use the 'ask' command directly, please add $USER_BIN_DIR to your PATH."
    echo "You can do this by adding the following line to your shell configuration file"
    echo "(e.g., ~/.bashrc, ~/.zshrc, or ~/.profile):"
    echo ""
    echo "  export PATH=\"$USER_BIN_DIR:\$PATH\""
    echo ""
    echo "After adding the line, restart your terminal or source the configuration file"
    echo "(e.g., 'source ~/.bashrc')."
else
    print_info "$USER_BIN_DIR is already in your PATH."
fi

# --- MANPATH Configuration Check ---
print_info "Checking MANPATH configuration for man page access..."
MANPATH_ADDITION_NEEDED=true
if [ -n "$MANPATH" ]; then
    if [[ ":$MANPATH:" == *":$HOME/.local/share/man:"* ]] || [[ ":$MANPATH:" == *":$(dirname "$USER_MAN_DIR"):"* ]]; then
        MANPATH_ADDITION_NEEDED=false
    fi
else
    # If MANPATH is not set, man often checks default paths including $HOME/.local/share/man
    # However, explicitly informing the user is safer.
    print_warning "MANPATH environment variable is not set."
fi

if [ "$MANPATH_ADDITION_NEEDED" = true ]; then
    echo "To access the 'ask' man page using 'man ask', you might need to add $HOME/.local/share/man to your MANPATH."
    echo "You can do this by adding the following line to your shell configuration file"
    echo "(e.g., ~/.bashrc, ~/.zshrc, or ~/.profile):"
    echo ""
    echo "  export MANPATH=\"\$HOME/.local/share/man:\$MANPATH\""
    echo ""
    echo "If \$HOME/.local/share/man is already a standard path your 'man' command checks, this might not be necessary."
    echo "After adding the line (if needed), restart your terminal or source the configuration file."
else
    print_info "$(dirname "$USER_MAN_DIR") or $HOME/.local/share/man seems to be in your MANPATH or a default search location."
fi

# --- Final Instructions ---
echo ""
print_info "--------------------------------------------------------------------"
print_info "Installation of Ask Gemini (v$SCRIPT_VERSION) complete!"
print_info "--------------------------------------------------------------------"
echo ""
echo "IMPORTANT: The 'ask' command requires the GEMINI_API_KEY environment variable to be set."
echo "1. Obtain your API key from the Google AI Studio (https://aistudio.google.com/app/apikey)."
echo "2. Set the environment variable. For example, in your current terminal, run:"
echo "   export GEMINI_API_KEY=\"YOUR_API_KEY_HERE\""
echo "3. To make this permanent, add the export line to your shell's startup file"
echo "   (e.g., ~/.bashrc, ~/.zshrc, or ~/.profile) and then source it or open a new terminal."
echo ""
echo "You can now try running 'ask --help' to see command options."
echo "If the command is not found, please ensure $USER_BIN_DIR is in your PATH and you've opened a new terminal session."

exit 0
