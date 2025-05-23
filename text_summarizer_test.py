import unittest
from unittest.mock import patch, MagicMock
import math

# Ensure the module under test is accessible
import sys
import os
# Add parent directory to sys.path to allow direct import of text_summarizer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import text_summarizer
    from text_summarizer import (
        summarize_text,
        SummarizationError,
        MIN_TEXT_LENGTH_FOR_SUMMARIZATION,
        DEFAULT_MIN_SUMMARY_TOKENS,
        DEFAULT_MAX_SUMMARY_TOKENS
    )
except ImportError as e:
    print(f"Failed to import text_summarizer or its components: {e}")
    # This is a fallback for simpler execution environments or if paths are tricky.
    # For robust test suites, ensure PYTHONPATH or package structure handles this.
    # Attempting to locate text_summarizer.py if it's in the same directory as this test file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if 'text_summarizer.py' in os.listdir(current_dir): # Naive check
        sys.path.insert(0, current_dir)
        import text_summarizer
        from text_summarizer import (
            summarize_text,
            SummarizationError,
            MIN_TEXT_LENGTH_FOR_SUMMARIZATION,
            DEFAULT_MIN_SUMMARY_TOKENS,
            DEFAULT_MAX_SUMMARY_TOKENS
        )
    else: # If it's in parent (common structure for app/tests)
        parent_dir = os.path.dirname(current_dir)
        if 'text_summarizer.py' in os.listdir(parent_dir):
             sys.path.insert(0, parent_dir)
             import text_summarizer
             from text_summarizer import (
                summarize_text,
                SummarizationError,
                MIN_TEXT_LENGTH_FOR_SUMMARIZATION,
                DEFAULT_MIN_SUMMARY_TOKENS,
                DEFAULT_MAX_SUMMARY_TOKENS
            )
        else:
            raise # Re-raise if module can't be found.


class TestTextSummarizer(unittest.TestCase):

    def setUp(self):
        # Store original model name if tests modify it
        self.original_model_name = text_summarizer.MODEL_NAME
        # Ensure pipeline is reset before each test if it's cached globally
        text_summarizer.SUMMARIZER_PIPELINE = None


    def tearDown(self):
        # Reset the global pipeline cache in text_summarizer after each test
        text_summarizer.SUMMARIZER_PIPELINE = None
        # Restore original model name if it was changed
        text_summarizer.MODEL_NAME = self.original_model_name


    @patch('text_summarizer.AutoModelForSeq2SeqLM.from_pretrained')
    @patch('text_summarizer.AutoTokenizer.from_pretrained')
    @patch('text_summarizer.pipeline')
    def test_successful_summarization(self, mock_pipeline_func, mock_tokenizer, mock_model):
        """Test successful text summarization with mocked pipeline."""
        mock_summarizer_instance = MagicMock()
        mock_summarizer_instance.return_value = [{'summary_text': 'This is a mock summary.'}]
        mock_pipeline_func.return_value = mock_summarizer_instance

        sample_text = "This is a long piece of text that is suitable for summarization. " * 5
        expected_summary = 'This is a mock summary.'
        
        summary = summarize_text(sample_text)

        self.assertEqual(summary, expected_summary)
        mock_pipeline_func.assert_called_once_with("summarization", model=text_summarizer.MODEL_NAME, tokenizer=text_summarizer.MODEL_NAME)
        mock_summarizer_instance.assert_called_once()
        # Check some args passed to the summarizer instance
        args, kwargs = mock_summarizer_instance.call_args
        self.assertEqual(args[0], sample_text)
        self.assertTrue('min_length' in kwargs)
        self.assertTrue('max_length' in kwargs)

    @patch('text_summarizer.AutoModelForSeq2SeqLM.from_pretrained', side_effect=Exception("Model load failed"))
    @patch('text_summarizer.AutoTokenizer.from_pretrained') # Mock tokenizer as well if model load fails early
    def test_model_loading_failure(self, mock_tokenizer, mock_model_from_pretrained):
        """Test SummarizationError is raised when model loading fails."""
        sample_text = "This text won't be summarized due to model loading failure."
        with self.assertRaisesRegex(SummarizationError, "Failed to load summarization model"):
            summarize_text(sample_text)
        mock_model_from_pretrained.assert_called_once()

    @patch('text_summarizer.AutoModelForSeq2SeqLM.from_pretrained')
    @patch('text_summarizer.AutoTokenizer.from_pretrained')
    @patch('text_summarizer.pipeline')
    def test_summarization_process_failure(self, mock_pipeline_func, mock_tokenizer, mock_model):
        """Test SummarizationError is raised when the summarization call fails."""
        mock_summarizer_instance = MagicMock(side_effect=Exception("Summarization process failed"))
        mock_pipeline_func.return_value = mock_summarizer_instance

        sample_text = "This is a long piece of text. " * 5
        with self.assertRaisesRegex(SummarizationError, "Error during text summarization"):
            summarize_text(sample_text)
        mock_summarizer_instance.assert_called_once()


    @patch('text_summarizer.pipeline') # Patch to check if it's NOT called
    def test_input_text_too_short(self, mock_pipeline_func):
        """Test that short text returns original and pipeline is not called."""
        short_text = "Too short." # Assuming MIN_TEXT_LENGTH_FOR_SUMMARIZATION > 2 words
        self.assertLess(len(short_text.split()), MIN_TEXT_LENGTH_FOR_SUMMARIZATION, "Test setup: short_text is not shorter than MIN_TEXT_LENGTH_FOR_SUMMARIZATION")
        
        returned_text = summarize_text(short_text)
        
        self.assertEqual(returned_text, short_text)
        mock_pipeline_func.assert_not_called()

    @patch('text_summarizer.pipeline') # Patch to check if it's NOT called
    def test_empty_input_text(self, mock_pipeline_func):
        """Test that empty text returns empty string and pipeline is not called."""
        returned_text = summarize_text("")
        self.assertEqual(returned_text, "")
        mock_pipeline_func.assert_not_called()

    @patch('text_summarizer.AutoModelForSeq2SeqLM.from_pretrained')
    @patch('text_summarizer.AutoTokenizer.from_pretrained')
    @patch('text_summarizer.pipeline')
    def test_ratio_calculations_and_summarizer_call_args(self, mock_pipeline_func, mock_tokenizer, mock_model):
        """Test min/max length calculations based on ratios."""
        mock_summarizer_instance = MagicMock()
        mock_summarizer_instance.return_value = [{'summary_text': 'Mocked summary'}]
        mock_pipeline_func.return_value = mock_summarizer_instance

        text_word_count = 100
        sample_text = "word " * text_word_count # Approx 100 words/tokens

        min_r, max_r = 0.2, 0.4
        summarize_text(sample_text, min_length_ratio=min_r, max_length_ratio=max_r)

        expected_min_len = math.ceil(text_word_count * min_r)
        expected_min_len = max(DEFAULT_MIN_SUMMARY_TOKENS, expected_min_len)
        
        expected_max_len = math.ceil(text_word_count * max_r)
        expected_max_len = min(DEFAULT_MAX_SUMMARY_TOKENS, expected_max_len)

        mock_summarizer_instance.assert_called_once()
        args, kwargs = mock_summarizer_instance.call_args
        self.assertEqual(kwargs.get('min_length'), expected_min_len)
        self.assertEqual(kwargs.get('max_length'), expected_max_len)

    @patch('text_summarizer.AutoModelForSeq2SeqLM.from_pretrained')
    @patch('text_summarizer.AutoTokenizer.from_pretrained')
    @patch('text_summarizer.pipeline')
    def test_min_length_greater_than_max_length_adjustment(self, mock_pipeline_func, mock_tokenizer, mock_model):
        """Test adjustment when calculated min_length > max_length."""
        mock_summarizer_instance = MagicMock()
        mock_summarizer_instance.return_value = [{'summary_text': 'Mocked summary'}]
        mock_pipeline_func.return_value = mock_summarizer_instance

        # Text short enough that caps and ratios might conflict
        # e.g. 30 words. DEFAULT_MIN_SUMMARY_TOKENS = 10.
        # min_r = 0.1 (3 -> 10), max_r = 0.2 (6 -> 6) -> min=10, max=6 -> WRONG
        # The code should adjust min_length to be <= max_length.
        # Current logic: calculated_min_length = max(DEFAULT_MIN_SUMMARY_TOKENS, int(calculated_max_length * 0.5))
        # if calculated_min_length > calculated_max_length:
        #    calculated_min_length = calculated_max_length (if max_length is very small)

        text_word_count = 30 
        sample_text = "word " * text_word_count
        
        # Scenario 1: Ratios cause min > max (after default min is applied)
        # min_r = 0.1 (3 words -> capped by DEFAULT_MIN_SUMMARY_TOKENS to 10)
        # max_r = 0.2 (6 words)
        # So, initial calculated_min_length = 10, calculated_max_length = 6. This needs adjustment.
        # Expected: min_length becomes max(10, 6*0.5)=3 -> still 10. Then if 10 > 6, min_length = 6.
        summarize_text(sample_text, min_length_ratio=0.1, max_length_ratio=0.2)
        
        args, kwargs = mock_summarizer_instance.call_args
        final_min_len = kwargs.get('min_length')
        final_max_len = kwargs.get('max_length')

        self.assertIsNotNone(final_min_len)
        self.assertIsNotNone(final_max_len)
        self.assertLessEqual(final_min_len, final_max_len, "Adjusted min_length should not exceed max_length")
        
        # Based on current logic:
        # calc_min = ceil(30 * 0.1) = 3. Capped by DEFAULT_MIN_SUMMARY_TOKENS = 10. So, calc_min = 10.
        # calc_max = ceil(30 * 0.2) = 6. Capped by DEFAULT_MAX_SUMMARY_TOKENS = 512. So, calc_max = 6.
        # Since 10 (calc_min) > 6 (calc_max):
        #   calc_min = max(DEFAULT_MIN_SUMMARY_TOKENS, int(6 * 0.5)) = max(10, 3) = 10.
        #   Still, 10 > 6. So, the inner if `if calculated_min_length > calculated_max_length:` triggers.
        #   calc_min = calc_max = 6.
        self.assertEqual(final_min_len, 6, "Scenario 1: min_length adjustment failed")
        self.assertEqual(final_max_len, 6, "Scenario 1: max_length adjustment failed")

        mock_summarizer_instance.reset_mock()

        # Scenario 2: max_length itself is very small, less than DEFAULT_MIN_SUMMARY_TOKENS
        # min_r = 0.01 (DEFAULT_MIN_SUMMARY_TOKENS=10)
        # max_r = 0.01 (DEFAULT_MIN_SUMMARY_TOKENS=10, but max_length can be small if text is tiny)
        # Let's use text_word_count = 80.
        # calc_min = ceil(80 * 0.01) = 1. Capped by DEFAULT_MIN_SUMMARY_TOKENS = 10. So, calc_min = 10.
        # calc_max = ceil(80 * 0.01) = 1. Capped by DEFAULT_MAX_SUMMARY_TOKENS = 512. So, calc_max = 1.
        # Since 10 (calc_min) > 1 (calc_max):
        #   calc_min = max(DEFAULT_MIN_SUMMARY_TOKENS, int(1 * 0.5)) = max(10, 0) = 10.
        #   Still, 10 > 1. So, the inner if `if calculated_min_length > calculated_max_length:` triggers.
        #   calc_min = calc_max = 1.
        text_word_count_2 = 80
        sample_text_2 = "word " * text_word_count_2
        summarize_text(sample_text_2, min_length_ratio=0.01, max_length_ratio=0.01)
        args2, kwargs2 = mock_summarizer_instance.call_args
        final_min_len2 = kwargs2.get('min_length')
        final_max_len2 = kwargs2.get('max_length')

        self.assertLessEqual(final_min_len2, final_max_len2)
        # Expected: min_length = 1, max_length = 1
        self.assertEqual(final_min_len2, 1, "Scenario 2: min_length adjustment failed for tiny max_length")
        self.assertEqual(final_max_len2, 1, "Scenario 2: max_length adjustment failed for tiny max_length")


if __name__ == '__main__':
    unittest.main()
