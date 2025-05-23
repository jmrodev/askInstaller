import unittest
from unittest.mock import patch, MagicMock, ANY
import sys
import os

# Ensure the module under test (ask_gemini.py) and its dependencies are accessible
# This assumes a structure like:
# project_root/
#   ask_gemini.py
#   pdf_processor.py (etc.)
#   tests/
#     ask_gemini_test.py
# If running from project_root/tests, parent_dir will be project_root
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# If running directly from the same directory as ask_gemini.py (less common for tests)
current_dir_for_module = os.path.dirname(os.path.abspath(__file__))
if current_dir_for_module not in sys.path and os.path.exists(os.path.join(current_dir_for_module, 'ask_gemini.py')):
    sys.path.insert(0, current_dir_for_module)

try:
    from ask_gemini import main as ask_gemini_main
    # Import exceptions for type checking if needed, though mocks are primary
    from pdf_processor import PDFProcessingError
    from text_summarizer import SummarizationError
    from audio_generator import AudioGenerationError
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import 'ask_gemini' or its helper modules/exceptions. Tests cannot run. Details: {e}")
    # Try a more direct path addition if the file is known to be in the parent directory
    # This helps if the test is run from a subdirectory like 'tests/'
    if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ask_gemini.py')):
         sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
         from ask_gemini import main as ask_gemini_main
         from pdf_processor import PDFProcessingError
         from text_summarizer import SummarizationError
         from audio_generator import AudioGenerationError
    else: # Fallback: if ask_gemini.py is in the same directory as the test file
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ask_gemini import main as ask_gemini_main
        from pdf_processor import PDFProcessingError
        from text_summarizer import SummarizationError
        from audio_generator import AudioGenerationError


class TestAskGeminiPdfAudioMode(unittest.TestCase):

    def _run_main_with_argv(self, argv_list):
        """Helper to run the main function with specified argv."""
        with patch.object(sys, 'argv', argv_list):
            ask_gemini_main()

    # Patch all external dependencies for PDF audio mode, and sys.exit
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.generate_audio_summary')
    @patch('ask_gemini.summarize_text')
    @patch('ask_gemini.extract_text_from_pdf')
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True) # Assume modules are available unless specified
    def test_pdf_mode_activation_and_defaults(self, mock_pdf_modules_available, mock_extract, mock_summarize, mock_generate_audio, mock_sys_exit):
        """Test mode activation and default parameters."""
        mock_extract.return_value = "extracted pdf text"
        mock_summarize.return_value = "summary of text"
        mock_generate_audio.return_value = "test_summary.mp3"
        
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf']
        self._run_main_with_argv(argv)

        mock_extract.assert_called_once_with('test.pdf')
        mock_summarize.assert_called_once_with("extracted pdf text", min_length_ratio=0.1, max_length_ratio=0.3)
        mock_generate_audio.assert_called_once_with("summary of text", output_filename="test_summary.mp3", lang='es')
        mock_sys_exit.assert_called_once_with(0) # Successful exit

    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.generate_audio_summary')
    @patch('ask_gemini.summarize_text')
    @patch('ask_gemini.extract_text_from_pdf')
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    def test_pdf_mode_all_custom_arguments(self, mock_pdf_modules_available, mock_extract, mock_summarize, mock_generate_audio, mock_sys_exit):
        """Test with all custom arguments for PDF audio summary mode."""
        mock_extract.return_value = "original extracted text"
        mock_summarize.return_value = "custom summary"
        mock_generate_audio.return_value = "custom.mp3"

        details_prompt_text = "focus on this"
        input_pdf = "my_doc.pdf"
        output_audio_file = "custom.mp3"
        lang = "en"
        min_r, max_r = 0.05, 0.25

        argv = [
            'ask_gemini.py', 
            '--pdf-audio-summary', input_pdf,
            '--details-prompt', details_prompt_text,
            '--output-audio', output_audio_file,
            '--audio-lang', lang,
            '--min-sum-ratio', str(min_r),
            '--max-sum-ratio', str(max_r)
        ]
        self._run_main_with_argv(argv)

        mock_extract.assert_called_once_with(input_pdf)
        
        expected_text_for_summarizer = f"User-provided details for summarization: {details_prompt_text}\n\n--- Extracted PDF Text ---\noriginal extracted text"
        mock_summarize.assert_called_once_with(expected_text_for_summarizer, min_length_ratio=min_r, max_length_ratio=max_r)
        
        mock_generate_audio.assert_called_once_with("custom summary", output_filename=output_audio_file, lang=lang)
        mock_sys_exit.assert_called_once_with(0)

    @patch('builtins.print') # To check error message
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', False) # Key part of this test
    def test_pdf_mode_missing_optional_modules(self, mock_pdf_modules_false, mock_sys_exit, mock_print):
        """Test error handling when PDF helper modules are not available."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf']
        self._run_main_with_argv(argv)

        mock_print.assert_any_call(
            "Error: PDF summarization helper modules (pdf_processor.py, text_summarizer.py, audio_generator.py) not found in the same directory.",
            file=sys.stderr
        )
        mock_sys_exit.assert_called_once_with(1)

    @patch('builtins.print')
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.extract_text_from_pdf', side_effect=FileNotFoundError("Mocked: PDF not found"))
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    def test_pdf_mode_extract_raises_file_not_found(self, mock_pdf_modules_true, mock_extract_raises, mock_sys_exit, mock_print):
        """Test error propagation when extract_text_from_pdf raises FileNotFoundError."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'nonexistent.pdf']
        self._run_main_with_argv(argv)
        
        mock_extract_raises.assert_called_once_with('nonexistent.pdf')
        mock_print.assert_any_call("Error: Input PDF file 'nonexistent.pdf' not found.", file=sys.stderr)
        mock_sys_exit.assert_called_once_with(1)

    @patch('builtins.print')
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.extract_text_from_pdf', side_effect=PDFProcessingError("Mocked: PDF processing failed"))
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    def test_pdf_mode_extract_raises_pdf_processing_error(self, mock_pdf_modules_true, mock_extract_raises, mock_sys_exit, mock_print):
        """Test error propagation for PDFProcessingError."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'corrupt.pdf']
        self._run_main_with_argv(argv)

        mock_extract_raises.assert_called_once_with('corrupt.pdf')
        mock_print.assert_any_call("An error occurred during PDF audio summarization: Mocked: PDF processing failed", file=sys.stderr)
        mock_sys_exit.assert_called_once_with(1)

    @patch('builtins.print')
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.summarize_text', side_effect=SummarizationError("Mocked: Summarization failed"))
    @patch('ask_gemini.extract_text_from_pdf', return_value="some text") # Ensure this part succeeds
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    def test_pdf_mode_summarize_raises_error(self, mock_pdf_modules_true, mock_extract, mock_summarize_raises, mock_sys_exit, mock_print):
        """Test error propagation for SummarizationError."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf']
        self._run_main_with_argv(argv)

        mock_summarize_raises.assert_called_once()
        mock_print.assert_any_call("An error occurred during PDF audio summarization: Mocked: Summarization failed", file=sys.stderr)
        mock_sys_exit.assert_called_once_with(1)

    @patch('builtins.print')
    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.generate_audio_summary', side_effect=AudioGenerationError("Mocked: Audio gen failed"))
    @patch('ask_gemini.summarize_text', return_value="summary") # Ensure this part succeeds
    @patch('ask_gemini.extract_text_from_pdf', return_value="some text") # Ensure this part succeeds
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    def test_pdf_mode_generate_audio_raises_error(self, mock_pdf_modules_true, mock_extract, mock_summarize, mock_generate_audio_raises, mock_sys_exit, mock_print):
        """Test error propagation for AudioGenerationError."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf']
        self._run_main_with_argv(argv)

        mock_generate_audio_raises.assert_called_once()
        mock_print.assert_any_call("An error occurred during PDF audio summarization: Mocked: Audio gen failed", file=sys.stderr)
        mock_sys_exit.assert_called_once_with(1)

    # Test mode precedence
    @patch('ask_gemini.sys.exit') # Mock sys.exit for all tests
    @patch('ask_gemini.generate_audio_summary', MagicMock(return_value="audio.mp3")) # Mock PDF pipeline funcs
    @patch('ask_gemini.summarize_text', MagicMock(return_value="summary"))
    @patch('ask_gemini.extract_text_from_pdf', MagicMock(return_value="text"))
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    @patch('ask_gemini.generate_content_with_gemini') # Mock the main Gemini API call for text prompts
    @patch('ask_gemini.chat_mode') # Mock chat mode function
    # For image generation, the logic is in main. We'll check if extract_text_from_pdf (PDF mode) was called.
    def test_pdf_mode_precedence_over_text_prompt(self, mock_chat_mode, mock_gen_content, mock_pdf_modules, mock_extract, mock_summarize, mock_gen_audio, mock_sys_exit):
        """Test PDF mode takes precedence over standard text prompt."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf', 'this is a text prompt']
        self._run_main_with_argv(argv)
        
        mock_extract.assert_called_once() # PDF mode function was called
        mock_gen_content.assert_not_called() # Standard prompt function was NOT called
        mock_sys_exit.assert_called_once_with(0) # PDF mode should complete successfully

    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.generate_audio_summary', MagicMock(return_value="audio.mp3"))
    @patch('ask_gemini.summarize_text', MagicMock(return_value="summary"))
    @patch('ask_gemini.extract_text_from_pdf', MagicMock(return_value="text"))
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    @patch('ask_gemini.generate_content_with_gemini') 
    @patch('ask_gemini.chat_mode') 
    def test_pdf_mode_precedence_over_chat_mode(self, mock_chat_mode, mock_gen_content, mock_pdf_modules, mock_extract, mock_summarize, mock_gen_audio, mock_sys_exit):
        """Test PDF mode takes precedence over chat mode."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf', '--chat']
        self._run_main_with_argv(argv)
        
        mock_extract.assert_called_once() # PDF mode function was called
        mock_chat_mode.assert_not_called() # Chat mode function was NOT called
        mock_sys_exit.assert_called_once_with(0)

    @patch('ask_gemini.sys.exit')
    @patch('ask_gemini.generate_audio_summary', MagicMock(return_value="audio.mp3"))
    @patch('ask_gemini.summarize_text', MagicMock(return_value="summary"))
    @patch('ask_gemini.extract_text_from_pdf', MagicMock(return_value="text"))
    @patch('ask_gemini.PDF_AUDIO_MODULES_AVAILABLE', True)
    # Mock the actual image generation call point if possible, or a function higher up
    # For now, we rely on checking that PDF mode ran and image gen specific parts (like genai.GenerativeModel for image) are not.
    # We can also check that `generate_content_with_gemini` is NOT called if image gen uses a different path.
    # The current ask_gemini.py uses a series of `if args.generate:` then calls to genai for image.
    # So, if mock_extract (PDF) is called, then image gen specific genai calls shouldn't be.
    # For simplicity, we'll assume if PDF mode runs (mock_extract called), it exits before image gen logic.
    @patch('google.generativeai.GenerativeModel') # Mock the model init for image gen to see if it's called
    def test_pdf_mode_precedence_over_image_generation(self, mock_genai_model_for_image, mock_pdf_modules, mock_extract, mock_summarize, mock_gen_audio, mock_sys_exit):
        """Test PDF mode takes precedence over image generation mode."""
        argv = ['ask_gemini.py', '--pdf-audio-summary', 'test.pdf', '--generate', 'an image']
        self._run_main_with_argv(argv)
        
        mock_extract.assert_called_once() # PDF mode function was called
        # Check that the genai.GenerativeModel call within the image generation block was not made
        # This is an indirect way to check. A more direct mock on a specific image gen function would be better if available.
        # For now, if `mock_extract` was called and `sys.exit(0)` happened for PDF mode, image gen part is skipped.
        # If the test setup is right, `mock_genai_model_for_image` inside the `if args.generate:` block shouldn't be hit.
        # However, `genai.GenerativeModel` is also used by text/chat.
        # A more precise mock would be on a function *unique* to image gen.
        # For now, the successful exit of PDF mode (checked by mock_sys_exit) is the primary indicator.
        mock_sys_exit.assert_called_once_with(0)
        # We can count calls to genai.GenerativeModel if we expect it to be called only once by PDF mode's dependencies (if any)
        # but PDF mode as implemented doesn't use genai.GenerativeModel directly.
        # So, if image gen was skipped, specific genai.GenerativeModel calls for it won't happen.

if __name__ == '__main__':
    unittest.main()
