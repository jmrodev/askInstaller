import os
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

class PDFProcessingError(Exception):
    """Custom exception for PDF processing errors."""
    pass

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from all pages of a PDF file.

    Args:
        pdf_path: The path to the PDF file.

    Returns:
        A string containing the concatenated text from all pages.
        Returns an empty string if there's an issue processing the PDF.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        PDFProcessingError: If the PDF is encrypted or invalid.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Error: PDF file not found at {pdf_path}")

    text_parts = []
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            if reader.is_encrypted:
                # Attempt to decrypt with an empty password, common for some PDFs
                try:
                    reader.decrypt('')
                except Exception as e:
                    print(f"Error: Could not decrypt PDF '{pdf_path}'. It might be password-protected. Error: {e}")
                    # Raising a specific error for encrypted PDFs that cannot be opened.
                    raise PDFProcessingError(f"Could not decrypt PDF '{pdf_path}'. It might be password-protected.")

            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                extracted_text = page.extract_text()
                if extracted_text:
                    text_parts.append(extracted_text)
    except FileNotFoundError: # Should be caught by the initial check, but good practice.
        raise FileNotFoundError(f"Error: PDF file not found at {pdf_path}")
    except PdfReadError as e:
        print(f"Error: Could not read PDF '{pdf_path}'. It may be corrupted or not a valid PDF. Details: {e}")
        # Raising a specific error for invalid/corrupt PDFs.
        raise PDFProcessingError(f"Could not read PDF '{pdf_path}'. It may be corrupted or not a valid PDF.")
    except Exception as e:
        print(f"An unexpected error occurred while processing PDF '{pdf_path}': {e}")
        # Raising a specific error for other unexpected issues.
        raise PDFProcessingError(f"An unexpected error occurred while processing PDF '{pdf_path}'.")

    return "\n".join(text_parts)

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    # Create a dummy PDF for testing if it doesn't exist
    try:
        from PyPDF2 import PdfWriter
        # Create a dummy PDF if one doesn't exist for basic testing
        if not os.path.exists("dummy.pdf"):
            writer = PdfWriter()
            writer.add_blank_page(width=210, height=297) # A4 size
            with open("dummy.pdf", "wb") as f:
                writer.write(f)
            print("Created dummy.pdf for testing.")

        # Test with a non-existent file
        try:
            extract_text_from_pdf("non_existent.pdf")
        except FileNotFoundError as e:
            print(e)

        # Test with the dummy PDF
        if os.path.exists("dummy.pdf"):
            print("\nExtracting text from dummy.pdf (should be empty or minimal):")
            text = extract_text_from_pdf("dummy.pdf")
            print(f"Extracted text: '{text}'")
        
        # Test with an encrypted PDF (manual setup needed or this will fail)
        # You would need to create an encrypted PDF named "encrypted.pdf"
        # For now, this part will likely show an error or be skipped.
        if os.path.exists("encrypted.pdf"):
            print("\nExtracting text from encrypted.pdf:")
            try:
                text = extract_text_from_pdf("encrypted.pdf")
                print(f"Extracted text: '{text}'")
            except PDFProcessingError as e:
                print(e)
        else:
            print("\nSkipping encrypted PDF test as 'encrypted.pdf' not found.")

    except ImportError:
        print("PyPDF2 is not installed. Skipping example usage.")
    except Exception as e:
        print(f"An error occurred in example usage: {e}")
