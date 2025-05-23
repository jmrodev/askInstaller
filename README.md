# `ask-gemini`

`ask-gemini` is a powerful command-line interface (CLI) tool designed to interact with Google's Gemini API. It allows users to easily query Gemini models for text generation, multimodal understanding (text and image inputs), image generation, and engage in interactive chat sessions, all from the comfort of the terminal. The tool also supports persistent context and conversation history.

## Features

*   **Direct Prompts**: Send text prompts directly to Gemini models.
*   **File Input**: Prepend content from one or more text files to your prompt.
*   **Multimodal Input**: Provide images as input along with text prompts for vision-capable models.
*   **Image Generation**: Generate images from textual descriptions using compatible models (e.g., Imagen 2 via Gemini).
*   **Interactive Chat Mode**: Engage in multi-turn conversations with a Gemini model.
*   **Conversation History**: Automatically saves and reuses conversation history (from `.ask_history.json`) for context in subsequent queries and chat sessions.
*   **Persistent Context**:
    *   **Local Context**: Use a `.ask_context.local` file in the current directory for specific instructions.
    *   **General Context**: Use a `~/.ask_context.general` file in your home directory for global instructions.
*   **Model Selection**: Choose from various supported Gemini models for different tasks.
*   **Parameter Control**: Adjust generation parameters like temperature, max output tokens, etc.
*   **Easy Management**: Clear history and context files with simple commands.
*   **PDF Audio Summarization**: Generate an audio summary from a PDF file, with options for language and summary length.

## Setup

1.  **Get a Gemini API Key**:
    *   Obtain an API key from Google AI Studio (formerly MakerSuite) or your Google Cloud project.
    *   Visit the [Gemini API documentation](https://ai.google.dev/docs) for instructions on obtaining a key.

2.  **Set Environment Variable**:
    *   Set the `GEMINI_API_KEY` environment variable to your obtained API key. You can do this by adding the following line to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`):
        ```bash
        export GEMINI_API_KEY='YOUR_API_KEY_HERE'
        ```
    *   Remember to replace `YOUR_API_KEY_HERE` with your actual key and source the file (e.g., `source ~/.bashrc`) or open a new terminal session.

3.  **Make the Script Executable**:
    *   The `ask` bash wrapper script needs to be executable. Navigate to the directory containing `ask` and run:
        ```bash
        chmod +x ask
        ```

4.  **Place in PATH (Recommended)**:
    *   For convenient use from any directory, place the `ask` script and the `ask_gemini.py` Python script (they must be in the same directory) into a directory that is included in your system's `PATH` environment variable (e.g., `/usr/local/bin` or `~/bin`).
    *   Example:
        ```bash
        sudo cp ask ask_gemini.py /usr/local/bin/
        ```
        (Adjust the destination path as needed for your system.)

## Usage

Here are some common examples of how to use `ask-gemini`:

*   **Simple text prompt**:
    ```bash
    ask "What is the weather like today?"
    ```

*   **Using content from multiple files**:
    ```bash
    ask --file report_summary.txt meeting_notes.md --prompt "Extract key decisions from these documents."
    ```

*   **Image input (multimodal/vision query)**:
    ```bash
    ask --image-path diagram.png "Explain this diagram."
    ```

*   **Image generation**:
    ```bash
    ask --generate "A futuristic city skyline at sunset with flying cars."
    ```
    (Note: Generated images are saved locally, e.g., `generated_A_futuristic_city_YYYYMMDD_HHMMSS.png`)

*   **Generate an audio summary from a PDF**:
    ```bash
    ask --pdf-audio-summary my_document.pdf --output-audio summary.mp3 --audio-lang en --details-prompt "focus on conclusions"
    ```

*   **Interactive chat mode**:
    ```bash
    ask --chat
    ```
    (Type `exit` or `quit` or press Ctrl+D to end the chat session.)

*   **Listing available models**:
    ```bash
    ask --list-models
    ```

*   **Getting help with all command-line options**:
    ```bash
    ask --help
    ```

## Context Files

You can provide persistent instructions or context to the Gemini models using context files:

*   **Local Context (`.ask_context.local`)**:
    *   Create a file named `.ask_context.local` in your current working directory.
    *   Its content will be automatically prepended to your prompts for queries made from that directory.
    *   Useful for project-specific instructions.

*   **General Context (`~/.ask_context.general`)**:
    *   Create a file named `.ask_context.general` in your user home directory.
    *   Its content will be prepended to all prompts, acting as a global set of instructions.
    *   If both general and local contexts are present, the general context is applied first (outermost), then the local context.

## History

*   **Conversation History (`.ask_history.json`)**:
    *   All interactions (your prompts and the model's responses) for single-shot queries and chat sessions are saved to `.ask_history.json` in the current working directory.
    *   This history is automatically loaded to provide context for subsequent queries and chat sessions.
    *   Each directory can have its own independent history file.

## Command-Line Options

Here are some of the important command-line flags:

*   `prompt` (positional): The main text prompt.
*   `--model <MODEL_NAME>`: Specify the Gemini model to use.
*   `--temperature <0.0-1.0>`: Control the randomness of the output.
*   `--file <FILE_PATH ...>`: Prepend content from one or more files.
*   `--image-path <IMAGE_PATH>`: Provide an image for multimodal queries.
*   `--generate <IMAGE_PROMPT>`: Switch to image generation mode with the given prompt.
*   `--chat`: Enter interactive chat mode.
*   `--list-models`: List available models.
*   `--clear-local-history`: Clear the `.ask_history.json` file.
*   `--clear-local-context`: Clear the `.ask_context.local` file.
*   `--clear-general-context`: Clear the `~/.ask_context.general` file.
*   `--pdf-audio-summary <PDF_FILE_PATH>`: Generate an audio summary from the specified PDF file. This mode typically ignores other primary input modes.
*   `--details-prompt <TEXT>`: Optional. Provide specific instructions for the PDF audio summarization process (e.g., "focus on financial aspects").
*   `--output-audio <OUTPUT_MP3_PATH>`: Optional. Path for the generated audio summary file. Defaults to `<pdf_filename>_summary.mp3`.
*   `--audio-lang <LANGUAGE_CODE>`: Optional. Language for the audio summary (default: 'es').
*   `--min-sum-ratio <FLOAT>`: Optional. Minimum summary length as a ratio of original PDF text (default: 0.1).
*   `--max-sum-ratio <FLOAT>`: Optional. Maximum summary length as a ratio of original PDF text (default: 0.3).

For a full and detailed list of all options and their descriptions, run:
```bash
ask --help
```

## Note on Arch Linux Packaging

The structure of this tool (bash wrapper `ask` and Python script `ask_gemini.py`) is designed with future Arch Linux packaging in mind. The intention is for these files to be easily installable to standard system directories (e.g., `/usr/bin`).
