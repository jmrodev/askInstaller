import unittest
from unittest.mock import patch, MagicMock, ANY # ANY is useful for some call assertions
import sys
import os

# Ensure the module under test is accessible
# Add parent directory to sys.path to allow direct import of summarize_pdf_audio
# Assumes structure: project_root/summarize_pdf_audio.py and project_root/tests/summarize_pdf_audio_test.py
parent_dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir_path not in sys.path:
    sys.path.insert(0, parent_dir_path)

try:
    from summarize_pdf_audio import main as summarize_main
except ImportError as e:
    print(f"Error: Failed to import 'summarize_pdf_audio'. Ensure it's in the Python path. Details: {e}")
    # Fallback for simpler execution environments (e.g. if test is in same dir as module)
    current_dir_path = os.path.dirname(os.path.abspath(__file__))
    if 'summarize_pdf_audio.py' in os.listdir(current_dir_path):
        sys.path.insert(0, current_dir_path)
        from summarize_pdf_audio import main as summarize_main
    else: # If it's in parent (common structure for app/tests)
        # This was already attempted with parent_dir_path, re-raising.
        raise


# To prevent the full pipeline from running, we mock all external calls.
# These mocks will be applied to all test methods in the class.
@patch('summarize_pdf_audio.generate_audio_summary', MagicMock(return_value="mock_audio.mp3"))
@patch('summarize_pdf_audio.summarize_text', MagicMock(return_value="mock summary text"))
@patch('summarize_pdf_audio.extract_text_from_pdf', MagicMock(return_value="mock extracted text"))
class TestSummarizePdfAudioArgs(unittest.TestCase):

    def _run_main_with_args(self, argv_list):
        """Helper to run the main function with specified argv and catch SystemExit."""
        with patch.object(sys, 'argv', argv_list):
            summarize_main()

    def test_required_pdf_arg_present(self):
        """Test with required --pdf argument."""
        test_pdf_path = "test.pdf"
        # Access the globally patched mocks
        mock_extract = sys.modules['summarize_pdf_audio'].extract_text_from_pdf
        
        self._run_main_with_args(['script_name', '--pdf', test_pdf_path])
        mock_extract.assert_called_with(test_pdf_path)

    def test_required_pdf_arg_missing(self):
        """Test SystemExit when --pdf argument is missing."""
        with self.assertRaises(SystemExit):
            self._run_main_with_args(['script_name'])

    def test_output_arg_present(self):
        """Test with --output argument provided."""
        test_pdf_path = "test.pdf"
        test_output_path = "output.mp3"
        mock_audio_gen = sys.modules['summarize_pdf_audio'].generate_audio_summary
        
        self._run_main_with_args(['script_name', '--pdf', test_pdf_path, '--output', test_output_path])
        # generate_audio_summary(summary_text, output_filename=final_output_filename, lang=args.lang)
        mock_audio_gen.assert_called_with(ANY, output_filename=test_output_path, lang=ANY)

    def test_output_arg_missing_uses_default_derived(self):
        """Test default output filename derivation when --output is missing."""
        test_pdf_path = "input.pdf" # Base name is "input"
        expected_default_output = "input_summary.mp3"
        mock_audio_gen = sys.modules['summarize_pdf_audio'].generate_audio_summary
        
        self._run_main_with_args(['script_name', '--pdf', test_pdf_path])
        mock_audio_gen.assert_called_with(ANY, output_filename=expected_default_output, lang=ANY)

    def test_lang_arg_present(self):
        """Test with --lang argument provided."""
        test_pdf_path = "test.pdf"
        test_lang = "en"
        mock_audio_gen = sys.modules['summarize_pdf_audio'].generate_audio_summary

        self._run_main_with_args(['script_name', '--pdf', test_pdf_path, '--lang', test_lang])
        mock_audio_gen.assert_called_with(ANY, output_filename=ANY, lang=test_lang)

    def test_lang_arg_missing_defaults_to_es(self):
        """Test --lang argument defaults to 'es'."""
        test_pdf_path = "test.pdf"
        expected_default_lang = "es"
        mock_audio_gen = sys.modules['summarize_pdf_audio'].generate_audio_summary

        self._run_main_with_args(['script_name', '--pdf', test_pdf_path])
        mock_audio_gen.assert_called_with(ANY, output_filename=ANY, lang=expected_default_lang)

    def test_summary_ratios_present(self):
        """Test with --min_summary_ratio and --max_summary_ratio provided."""
        test_pdf_path = "test.pdf"
        min_r, max_r = 0.15, 0.35
        mock_summarizer = sys.modules['summarize_pdf_audio'].summarize_text

        self._run_main_with_args([
            'script_name', '--pdf', test_pdf_path,
            '--min_summary_ratio', str(min_r),
            '--max_summary_ratio', str(max_r)
        ])
        # summarize_text(extracted_text, min_length_ratio=args.min_summary_ratio, max_length_ratio=args.max_summary_ratio)
        mock_summarizer.assert_called_with(ANY, min_length_ratio=min_r, max_length_ratio=max_r)

    def test_summary_ratios_missing_defaults(self):
        """Test default summary ratios."""
        test_pdf_path = "test.pdf"
        expected_min_r, expected_max_r = 0.1, 0.3 # Default values in summarize_pdf_audio.py
        mock_summarizer = sys.modules['summarize_pdf_audio'].summarize_text

        self._run_main_with_args(['script_name', '--pdf', test_pdf_path])
        mock_summarizer.assert_called_with(ANY, min_length_ratio=expected_min_r, max_length_ratio=expected_max_r)

    def test_invalid_min_ratio_too_high(self):
        """Test SystemExit for --min_summary_ratio > 1.0."""
        # This validation is done *after* argparse.parse_args() in summarize_pdf_audio.py
        # So, we need to also patch sys.exit to check if it's called due to this.
        # However, argparse itself might also raise SystemExit if type conversion fails or choices are set.
        # The current setup: parser.error() is called, which raises SystemExit.
        with self.assertRaises(SystemExit):
            self._run_main_with_args(['script_name', '--pdf', 'test.pdf', '--min_summary_ratio', '1.5'])

    def test_invalid_max_ratio_too_low(self):
        """Test SystemExit for --max_summary_ratio < 0.0."""
        with self.assertRaises(SystemExit):
            self._run_main_with_args(['script_name', '--pdf', 'test.pdf', '--max_summary_ratio', '-0.1'])
            
    def test_invalid_min_ratio_greater_than_max_ratio(self):
        """Test SystemExit when min_summary_ratio > max_summary_ratio."""
        with self.assertRaises(SystemExit):
            self._run_main_with_args([
                'script_name', '--pdf', 'test.pdf',
                '--min_summary_ratio', '0.5',
                '--max_summary_ratio', '0.2'
            ])

    def test_output_arg_is_none_if_not_provided_at_parse_time(self):
        """
        Test that args.output is None after parsing if not supplied.
        The default filename derivation happens *after* parsing in the script.
        This test relies on the fact that generate_audio_summary's output_filename
        argument will be the result of that derivation.
        """
        test_pdf_path = "some.pdf"
        expected_derived_output = "some_summary.mp3" # Based on logic in main()
        mock_audio_gen = sys.modules['summarize_pdf_audio'].generate_audio_summary
        
        self._run_main_with_args(['script_name', '--pdf', test_pdf_path])
        
        # We check that the derived default is used by generate_audio_summary
        # This indirectly confirms that args.output was initially None or not set by argparse
        # and then the script's logic took over.
        mock_audio_gen.assert_called_with(ANY, output_filename=expected_derived_output, lang=ANY)
        
        # To directly check args.output being None at parse time is harder without modifying main()
        # or patching parse_args itself. This indirect check is sufficient given current structure.

if __name__ == '__main__':
    unittest.main()
