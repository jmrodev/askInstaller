from gtts import gTTS, gTTSError
import os

class AudioGenerationError(Exception):
    """Custom exception for audio generation errors."""
    pass

def generate_audio_summary(text: str, output_filename: str = "audio_summary.mp3", lang: str = "es") -> str | None:
    """
    Generates an audio file from the input text using gTTS.

    Args:
        text: The text to convert to speech.
        output_filename: The name of the output audio file (e.g., "audio_summary.mp3").
                         The directory for this path must exist, or an error might occur.
        lang: The language code for the text-to-speech conversion (default 'es' for Spanish).

    Returns:
        The output_filename if audio generation was successful, None otherwise.
    
    Raises:
        AudioGenerationError: If there's an issue with text input, gTTS processing, or file saving.
    """
    if not text or not isinstance(text, str):
        message = "Input text is empty or not a string. Cannot generate audio."
        print(f"Warning: {message}")
        raise AudioGenerationError(message)

    # Ensure the output directory exists if a path is specified
    output_dir = os.path.dirname(output_filename)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            message = f"Could not create output directory '{output_dir}'. Error: {e}"
            print(f"Error: {message}")
            raise AudioGenerationError(message)
    
    try:
        print(f"Generating audio in '{lang}' for text: \"{text[:50]}...\"")
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_filename)
        print(f"Audio summary saved successfully as {output_filename}")
        return output_filename
    except gTTSError as e:
        message = f"gTTS Error: Could not generate audio. Details: {e}. This might be due to an invalid language code ('{lang}') or network issues."
        print(f"Error: {message}")
        raise AudioGenerationError(message)
    except Exception as e:
        message = f"An unexpected error occurred during audio generation or saving: {e}"
        print(f"Error: {message}")
        raise AudioGenerationError(message)

if __name__ == '__main__':
    print("Running audio_generator.py example...")

    sample_text_es = "Hola, este es un resumen de audio generado en español. La inteligencia artificial está transformando nuestro mundo."
    short_valid_text = "Prueba."
    
    # Test 1: Valid Spanish text
    print("\n--- Test 1: Generating audio for sample Spanish text ---")
    try:
        output_file1 = generate_audio_summary(sample_text_es, "test_audio_es.mp3", "es")
        if output_file1:
            print(f"Test 1 Succeeded. Audio saved to: {output_file1}")
            # You can manually check test_audio_es.mp3
            if os.path.exists(output_file1):
                print(f"File '{output_file1}' confirmed to exist.")
            else:
                print(f"File '{output_file1}' NOT found after generation.")
    except AudioGenerationError as e:
        print(f"Test 1 Failed. AudioGenerationError: {e}")
    except Exception as e:
        print(f"Test 1 Failed. Unexpected error: {e}")

    # Test 2: Empty text
    print("\n--- Test 2: Attempting to generate audio for empty text ---")
    try:
        generate_audio_summary("", "test_audio_empty.mp3")
    except AudioGenerationError as e:
        print(f"Test 2 Caught expected AudioGenerationError: {e}")
    except Exception as e:
        print(f"Test 2 Failed. Unexpected error: {e}")


    # Test 3: Invalid language code
    print("\n--- Test 3: Attempting to generate audio with an invalid language code ---")
    try:
        generate_audio_summary(short_valid_text, "test_audio_invalid_lang.mp3", "xx-invalid")
    except AudioGenerationError as e:
        print(f"Test 3 Caught expected AudioGenerationError: {e}")
    except Exception as e:
        print(f"Test 3 Failed. Unexpected error: {e}")

    # Test 4: Valid text, default filename and language
    print("\n--- Test 4: Generating audio with default filename and language ---")
    try:
        # Ensure previous default file is removed if it exists, to confirm new creation
        if os.path.exists("audio_summary.mp3"):
            os.remove("audio_summary.mp3")
        output_file4 = generate_audio_summary(short_valid_text)
        if output_file4:
            print(f"Test 4 Succeeded. Audio saved to: {output_file4}")
            if os.path.exists(output_file4):
                print(f"File '{output_file4}' confirmed to exist.")
            else:
                print(f"File '{output_file4}' NOT found after generation.")
    except AudioGenerationError as e:
        print(f"Test 4 Failed. AudioGenerationError: {e}")
    except Exception as e:
        print(f"Test 4 Failed. Unexpected error: {e}")

    # Test 5: Output to a subdirectory
    print("\n--- Test 5: Generating audio in a subdirectory ---")
    output_subdir_file = os.path.join("audio_output", "test_subdir.mp3")
    try:
        # Clean up previous test if it exists
        if os.path.exists(output_subdir_file):
            os.remove(output_subdir_file)
        if os.path.exists("audio_output") and not os.listdir("audio_output"): # remove dir if empty
            os.rmdir("audio_output")

        output_file5 = generate_audio_summary("Audio en subdirectorio.", output_subdir_file, "es")
        if output_file5:
            print(f"Test 5 Succeeded. Audio saved to: {output_file5}")
            if os.path.exists(output_file5):
                print(f"File '{output_file5}' confirmed to exist.")
            else:
                print(f"File '{output_file5}' NOT found after generation.")
    except AudioGenerationError as e:
        print(f"Test 5 Failed. AudioGenerationError: {e}")
    except Exception as e:
        print(f"Test 5 Failed. Unexpected error: {e}")


    print("\nAudio generator example run complete.")
    print("Please manually check the generated .mp3 files for correctness if tests passed.")
