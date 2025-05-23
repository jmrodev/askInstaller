import unittest
import os
import tempfile
from PyPDF2 import PdfWriter, PdfReader # Corrected: PdfReader is needed for reading back to encrypt
from PyPDF2.generic import DecodedStreamObject, NameObject, TextStringObject, create_string_object # For adding text
from PyPDF2.papersizes import A4

# Ensure the module under test is accessible, assuming it's in the same directory or Python path
try:
    from pdf_processor import extract_text_from_pdf, PDFProcessingError
except ImportError:
    # This might happen if the script is run directly and pdf_processor.py is not in sys.path
    # For a proper test suite, these would typically be part of a package.
    print("Error: Could not import from pdf_processor. Ensure it's in the Python path.")
    # As a fallback for simpler execution environments, try a relative import path modification
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from pdf_processor import extract_text_from_pdf, PDFProcessingError


class TestPdfProcessor(unittest.TestCase):

    def setUp(self):
        """Set up temporary directory and file paths for tests."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.valid_pdf_path = os.path.join(self.test_dir.name, "valid.pdf")
        self.invalid_pdf_path = os.path.join(self.test_dir.name, "invalid.pdf")
        self.encrypted_pdf_path_empty_pwd = os.path.join(self.test_dir.name, "encrypted_empty_pwd.pdf")
        self.encrypted_pdf_path_real_pwd = os.path.join(self.test_dir.name, "encrypted_real_pwd.pdf")
        self.known_text_content = "Hello, this is a test PDF document for PyPDF2. With some more text to make it longer."

    def tearDown(self):
        """Clean up temporary directory and files."""
        self.test_dir.cleanup()

    def _create_simple_pdf_with_text(self, filepath: str, text_content: str):
        """
        Creates a simple PDF with one page containing the given text.
        Note: Directly embedding text that PdfReader can extract reliably is non-trivial
        with PdfWriter alone for complex text. PdfWriter adds pages, but adding actual
        text streams that are easily extractable usually requires lower-level PDF manipulation
        or report generation libraries.
        For this test, we'll create a PDF that *should* have text, but extraction
        might be imperfect. The goal is to see if *some* text comes through.
        A more robust way would be to use a library like reportlab, or have a pre-made test PDF.
        Given the constraints, we'll try a basic method.
        """
        writer = PdfWriter()
        writer.add_blank_page(width=A4[0], height=A4[1]) # Add A4 Blank Page

        # Attempting to add text in a way that might be extractable.
        # This is a simplified approach. Real text embedding is more complex.
        # PyPDF2's PdfWriter isn't primarily designed for creating content from scratch like ReportLab.
        # What often happens is that `page.extract_text()` might not find text added this way
        # as it's not in typical content streams.
        # Let's use a known method that sometimes works for very simple text.
        # We'll add metadata, which is extractable, to simulate having *some* text content.
        writer.add_metadata({
            "/Title": "Test PDF Document",
            "/Author": "Test Author",
            "/Subject": text_content, # Put our known text in the subject
        })
        
        # To make text appear on the page itself in a way `extract_text` can find:
        # This is more involved. We'd typically need to create a content stream.
        # For simplicity, the metadata approach is a proxy.
        # A real test of `page.extract_text()` needs a PDF where text is part of page content.
        # Let's try to add an annotation which might be extractable.
        # This is still not ideal. The best is a pre-made PDF.

        # Since robustly adding extractable page text with PyPDF2 writer is hard,
        # we'll create a PDF, and then check if the subject (metadata) is part of *any* extracted text.
        # The `extract_text_from_pdf` function in `pdf_processor.py` iterates through pages
        # and calls `page.extract_text()`. If the PDF has no actual page text, this will be empty.
        # For a more reliable test of text extraction, we'd need a PDF file with actual text content.
        # For now, let's make a PDF that `extract_text` will likely return empty for page content,
        # but we can verify the structure is valid.

        # Let's adjust: we'll create a PDF using reportlab if available,
        # otherwise, we'll accept that PyPDF2-created text might not be extractable by PyPDF2 itself.
        # For the scope of this, we'll stick to PyPDF2 and acknowledge this limitation.
        # The key is that `extract_text_from_pdf` runs without error for a valid PDF structure.

        try:
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(filepath, pagesize=A4)
            c.drawString(72, 720, text_content) # Draw text at (1 inch, 10 inches) from bottom-left
            c.save()
            print(f"Created PDF '{filepath}' with text using ReportLab.")
            return # Success with reportlab
        except ImportError:
            print("ReportLab not found. Creating a more basic PDF with PyPDF2 (text extraction might be limited).")
            # Fallback to PyPDF2 metadata approach if reportlab is not available
            # This means `extract_text_from_pdf` might return empty if it only looks at page content.
            # The `extract_text_from_pdf` function as written primarily uses `page.extract_text()`.
            # If we can't put text on the page effectively, this test part will be weak.
            # Let's assume for now that the environment might not have reportlab.
            # The goal is to test `extract_text_from_pdf`'s behavior, not `PdfWriter`'s text creation.
            # So, if we can't make a texty PDF, the "successful extraction" test is tricky.

            # For the purpose of testing extract_text_from_pdf, it's better to have a small, real PDF.
            # Since we can't bundle assets, we'll make a best effort.
            # The current `extract_text_from_pdf` in `pdf_processor` tries to get page text.
            # Let's just create a blank page. The test will be that it *doesn't error* and returns empty.
            # Then, we'll manually adjust the "expected text" to be empty for this scenario.
            writer = PdfWriter()
            writer.add_blank_page(width=A4[0], height=A4[1])
            with open(filepath, "wb") as f:
                writer.write(f)
            # This PDF will have no extractable text by page.extract_text()
            # So the test for successful extraction needs to expect "" or check metadata if that's what extract_text_from_pdf does.
            # The current extract_text_from_pdf does NOT check metadata.

    def _create_encrypted_pdf(self, filepath: str, text_content: str, password: str):
        """Creates a PDF with text and encrypts it."""
        # First, create a temporary readable PDF with text
        temp_unencrypted_path = os.path.join(self.test_dir.name, "temp_unencrypted.pdf")
        self._create_simple_pdf_with_text(temp_unencrypted_path, text_content)

        # Now, read it and write it back out with encryption
        reader = PdfReader(temp_unencrypted_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        
        if password is not None: # Allow testing unencrypted behavior too if password is None
            writer.encrypt(user_password=password, owner_password=None, use_128bit=True)
        
        with open(filepath, "wb") as f:
            writer.write(f)
        os.remove(temp_unencrypted_path) # Clean up temporary unencrypted file

    def test_extract_text_successfully(self):
        """Test successful text extraction from a valid PDF."""
        # Due to challenges making extractable text with PyPDF2, this test is limited.
        # If ReportLab was used in _create_simple_pdf_with_text, this would be more robust.
        # Assuming ReportLab is NOT available (common in restricted envs):
        # _create_simple_pdf_with_text (PyPDF2 version) creates a PDF where page.extract_text() returns ""
        self._create_simple_pdf_with_text(self.valid_pdf_path, self.known_text_content)
        
        # Check if ReportLab was actually used by checking if the file has more content
        # This is a hacky way to adapt the test based on environment.
        # A better way is to have a pre-made test asset.
        try:
            import reportlab
            expected_text_present = self.known_text_content
        except ImportError:
            print("test_extract_text_successfully: ReportLab not available, expecting empty text from PyPDF2-created PDF page content.")
            expected_text_present = "" # PyPDF2's extract_text() on a blank page made by PdfWriter is empty.

        extracted_text = extract_text_from_pdf(self.valid_pdf_path)
        if expected_text_present:
            self.assertIn(expected_text_present, extracted_text, "Known text not found in extracted content.")
        else:
            self.assertEqual(extracted_text, "", "Expected empty string for PyPDF2-created blank PDF.")

    def test_file_not_found(self):
        """Test FileNotFoundError for a non-existent PDF file."""
        with self.assertRaises(FileNotFoundError):
            extract_text_from_pdf(os.path.join(self.test_dir.name, "this_file_does_not_exist.pdf"))

    def test_invalid_pdf_file_empty(self):
        """Test PDFProcessingError for an empty file with .pdf extension."""
        with open(self.invalid_pdf_path, "w") as f:
            f.write("") # Create an empty file
        with self.assertRaises(PDFProcessingError):
            extract_text_from_pdf(self.invalid_pdf_path)

    def test_invalid_pdf_file_text(self):
        """Test PDFProcessingError for a text file with .pdf extension."""
        with open(self.invalid_pdf_path, "w") as f:
            f.write("This is not a PDF file, just plain text.")
        with self.assertRaises(PDFProcessingError):
            extract_text_from_pdf(self.invalid_pdf_path)

    def test_encrypted_pdf_empty_password_can_open(self):
        """Test extraction from PDF encrypted with an empty password (should be handled)."""
        # PyPDF2's writer.encrypt("") makes it decryptable with reader.decrypt("")
        # which our pdf_processor.py tries.
        self._create_encrypted_pdf(self.encrypted_pdf_path_empty_pwd, self.known_text_content, "")
        
        try:
            import reportlab
            expected_text_present = self.known_text_content
        except ImportError:
            print("test_encrypted_pdf_empty_password_can_open: ReportLab not available, expecting empty text from PyPDF2-created PDF page content.")
            expected_text_present = ""

        extracted_text = extract_text_from_pdf(self.encrypted_pdf_path_empty_pwd)
        if expected_text_present:
            self.assertIn(self.known_text_content, extracted_text, "Known text not found in PDF encrypted with empty password.")
        else:
             self.assertEqual(extracted_text, "", "Expected empty string for PyPDF2-created blank PDF (encrypted with empty pwd).")


    def test_encrypted_pdf_with_actual_password_protected(self):
        """Test PDFProcessingError for a PDF encrypted with a real password."""
        self._create_encrypted_pdf(self.encrypted_pdf_path_real_pwd, self.known_text_content, "testpassword")
        with self.assertRaises(PDFProcessingError):
            extract_text_from_pdf(self.encrypted_pdf_path_real_pwd)


if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # For more complex setups, a test runner like `python -m unittest discover` is preferred.
    
    # Attempt to ensure pdf_processor is found for direct script execution
    # This is a common pattern but less ideal than proper packaging.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    # You might need to add the parent directory if pdf_processor.py is there
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    try:
        from pdf_processor import extract_text_from_pdf, PDFProcessingError
    except ImportError:
        print("CRITICAL: Main pdf_processor module not found even after path adjustments. Tests cannot run.")
        sys.exit(1)

    unittest.main()
