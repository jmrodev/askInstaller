# Arch Linux / Manjaro Installation Instructions for ask-gemini

To build and install the `ask-gemini` package on Arch Linux or Manjaro:

1.  **Ensure `base-devel` is installed:**
    If you haven't built packages before, you might need the `base-devel` group:
    ```bash
    sudo pacman -Syu --needed base-devel
    ```

2.  **Place Files:**
    Make sure the following files are in the same directory:
    *   `PKGBUILD` (this file)
    *   `ask` (the wrapper script)
    *   `ask_gemini.py` (the main Python script)
    *   `ask.1` (the man page)
    *   `LICENSE` (the license file)

3.  **Build and Install:**
    Navigate to this directory in your terminal and run:
    ```bash
    makepkg -si
    ```
    The `makepkg` command will build the package and the `-s` flag will install its dependencies using pacman. The `-i` flag will install the package itself after a successful build.

4.  **API Key:**
    Remember to set your `GEMINI_API_KEY` environment variable:
    ```bash
    export GEMINI_API_KEY="YOUR_API_KEY_HERE"
    ```
    You might want to add this to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`).
