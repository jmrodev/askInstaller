import argparse
import os
import sys

# Attempt to import project-specific modules
try:
    from pdf_processor import extract_text_from_pdf, PDFProcessingError
    from text_summarizer import summarize_text, SummarizationError
    from audio_generator import generate_audio_summary, AudioGenerationError
except ImportError as e:
    print(f"Error: Failed to import necessary modules. Please ensure all modules (pdf_processor.py, text_summarizer.py, audio_generator.py) are in the Python path. Details: {e}")
    sys.exit(1)

def main():
    """
    Orchestrates the PDF to audio summary generation process.
    1. Parses command-line arguments.
    2. Extracts text from the PDF.
    3. Summarizes the extracted text.
    4. Generates an audio file from the summary.
    """
    parser = argparse.ArgumentParser(
        description="Generates an audio summary from a PDF file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--pdf", "-p",
        type=str,
        required=True,
        help="Path to the input PDF file."
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        required=False,
        help="Path for the output audio summary file (e.g., summary.mp3). "
             "Defaults to '<pdf_basename>_summary.mp3' in the current directory if not provided."
    )

    parser.add_argument(
        "--lang", "-l",
        type=str,
        default='es',
        help="Language for the audio summary (e.g., 'en', 'es')."
    )

    parser.add_argument(
        "--min_summary_ratio", "--min_r",
        type=float,
        default=0.1,
        help="Minimum summary length as a ratio of original text (0.0 to 1.0)."
    )

    parser.add_argument(
        "--max_summary_ratio", "--max_r",
        type=float,
        default=0.3,
        help="Maximum summary length as a ratio of original text (0.0 to 1.0)."
    )

    args = parser.parse_args()

    # --- Argument Validation ---
    if not (0.0 <= args.min_summary_ratio <= 1.0):
        print("Error: --min_summary_ratio must be between 0.0 and 1.0")
        sys.exit(1)
    if not (0.0 <= args.max_summary_ratio <= 1.0):
        print("Error: --max_summary_ratio must be between 0.0 and 1.0")
        sys.exit(1)
    if args.min_summary_ratio > args.max_summary_ratio:
        print("Error: --min_summary_ratio cannot be greater than --max_summary_ratio")
        sys.exit(1)

    # --- Determine Output Filename ---
    final_output_filename = args.output
    if not final_output_filename:
        pdf_basename = os.path.splitext(os.path.basename(args.pdf))[0]
        final_output_filename = f"{pdf_basename}_summary.mp3"
        print(f"Info: Output filename not specified. Defaulting to: {final_output_filename}")


    # --- Processing Pipeline ---
    extracted_text = None
    summary_text = None

    try:
        # Step 1: Extract Text from PDF
        print(f"\nStep 1: Extracting text from PDF: {args.pdf}...")
        extracted_text = extract_text_from_pdf(args.pdf)
        if not extracted_text:
            print("Error: No text could be extracted from the PDF. The PDF might be image-based or empty.")
            # No sys.exit here, as some PDFs genuinely have no text. Downstream will handle empty text.
        else:
            print(f"Successfully extracted text (first 100 chars): '{extracted_text[:100].replace('\n', ' ')}...'")

    except FileNotFoundError:
        print(f"Error: PDF file not found at '{args.pdf}'. Please check the path.")
        sys.exit(1)
    except PDFProcessingError as e:
        print(f"Error processing PDF: {e}")
        sys.exit(1)
    except Exception as e: # Catch any other unexpected errors during PDF processing
        print(f"An unexpected error occurred during PDF text extraction: {e}")
        sys.exit(1)

    # Step 2: Summarize Text
    if extracted_text: # Proceed only if text was extracted
        try:
            print("\nStep 2: Summarizing extracted text...")
            print(f"  Min ratio: {args.min_summary_ratio}, Max ratio: {args.max_summary_ratio}")
            summary_text = summarize_text(
                extracted_text,
                min_length_ratio=args.min_summary_ratio,
                max_length_ratio=args.max_summary_ratio
            )
            if not summary_text or summary_text == extracted_text: # summarize_text might return original if too short
                print("Info: The generated summary is the same as the original text (possibly due to short input) or no summary could be generated.")
                # If original text was very short, it might be returned as is. This is not an error.
                # If summarize_text returns empty for some reason, that's also handled.
            else:
                 print(f"Successfully generated summary (first 100 chars): '{summary_text[:100].replace('\n', ' ')}...'")

        except SummarizationError as e:
            print(f"Error during text summarization: {e}")
            # Decide if to exit or try to use original text for audio
            print("Info: Proceeding with audio generation using the full extracted text (if available) due to summarization error.")
            summary_text = extracted_text # Fallback to full text if summarization failed but text extraction worked
        except Exception as e: # Catch any other unexpected errors during summarization
            print(f"An unexpected error occurred during text summarization: {e}")
            print("Info: Proceeding with audio generation using the full extracted text (if available) due to unexpected summarization error.")
            summary_text = extracted_text # Fallback
    else:
        print("\nSkipping Step 2 (Summarization) and Step 3 (Audio Generation) as no text was extracted from the PDF.")
        sys.exit(0) # Exit gracefully if no text to process


    # Step 3: Generate Audio
    if summary_text: # Proceed only if there's text to convert to audio (either summary or fallback original)
        try:
            print("\nStep 3: Generating audio summary...")
            print(f"  Output file: {final_output_filename}")
            print(f"  Language: {args.lang}")
            
            audio_file_path = generate_audio_summary(
                summary_text,
                output_filename=final_output_filename,
                lang=args.lang
            )
            if audio_file_path:
                print(f"\nSuccess! Audio summary successfully saved to: {audio_file_path}")
            else:
                # This case should ideally be caught by AudioGenerationError
                print("Error: Audio generation failed for an unknown reason (returned None).")
                sys.exit(1)

        except AudioGenerationError as e:
            print(f"Error during audio generation: {e}")
            sys.exit(1)
        except Exception as e: # Catch any other unexpected errors during audio generation
            print(f"An unexpected error occurred during audio generation: {e}")
            sys.exit(1)
    else:
        print("\nSkipping Step 3 (Audio Generation) as there is no text content (summary or original) to process.")
        sys.exit(0) # Exit gracefully if no text for audio

if __name__ == '__main__':
    main()
