# Maintainer: Jules <jules@example.com>
# Contributor: User <user@example.com>

pkgname=ask-gemini
pkgver=0.1.0 # Ensure this version is consistent with the Debian package
pkgrel=1
pkgdesc="Command-line interface to Google's Gemini API"
arch=('any')
url="https://github.com/jitsi/ask" # Placeholder URL, assuming jitsi/ask from context
license=('MIT') 
depends=('python' 'python-requests')
makedepends=()

# Variables for source file names
_script_name="ask"
_python_script="ask_gemini.py"
_man_page="ask.1"
_license_file="LICENSE" # Assume a license file named LICENSE exists

# Recalculate source array with variables
source=("${_script_name}" "${_python_script}" "${_man_page}")
# Add license to source array if it exists
if [ -f "$_license_file" ]; then
    source+=("$_license_file")
fi

sha256sums=('SKIP' 'SKIP' 'SKIP') # For local files, 'SKIP' is okay. Add 'SKIP' for LICENSE if included.
# If LICENSE is added to source, add another 'SKIP' to sha256sums
if [ -f "$_license_file" ]; then
    sha256sums+=('SKIP')
fi

package() {
    cd "$srcdir" # srcdir is where makepkg puts/finds the sources

    # Install Python script
    install -Dm755 "$_python_script" "$pkgdir/usr/lib/$pkgname/$_python_script"

    # Install wrapper script
    # IMPORTANT: The wrapper script 'ask' must be modified to point to the correct SCRIPT_DIR
    # This assumes the 'ask' script has a line like 'SCRIPT_DIR=...'
    # Create a temporary modified 'ask' script
    cp "$_script_name" "${_script_name}_arch_modified"
    sed -i "s|^SCRIPT_DIR=.*|SCRIPT_DIR=\"/usr/lib/$pkgname\"|g" "${_script_name}_arch_modified"
    install -Dm755 "${_script_name}_arch_modified" "$pkgdir/usr/bin/$_script_name"

    # Install man page
    install -Dm644 "$_man_page" "$pkgdir/usr/share/man/man1/$_man_page"
    
    # Install license file if it was included in sources
    if [ -f "$_license_file" ]; then
        install -Dm644 "$_license_file" "$pkgdir/usr/share/licenses/$pkgname/$_license_file"
    fi
}
