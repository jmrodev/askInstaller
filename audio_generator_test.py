import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock

# Ensure the module under test is accessible
import sys
# Add parent directory to sys.path to allow direct import of audio_generator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from audio_generator import generate_audio_summary, AudioGenerationError
    from gtts.tts import gTTSError
except ImportError as e:
    print(f"Failed to import audio_generator or its components: {e}")
    # Fallback for simpler execution environments
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if 'audio_generator.py' in os.listdir(parent_dir):
         sys.path.insert(0, parent_dir)
         from audio_generator import generate_audio_summary, AudioGenerationError
         from gtts.tts import gTTSError
    else:
        raise


class TestAudioGenerator(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for test output files."""
        self.test_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir_path = self.test_dir_obj.name
        self.sample_text = "This is a sample text for audio generation."
        self.default_lang = "es"
        self.output_filename = os.path.join(self.test_dir_path, "test_audio.mp3")

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    @patch('audio_generator.os.path.exists', return_value=True) # Assume output dir exists for this test
    @patch('audio_generator.gTTS')
    def test_successful_audio_generation(self, mock_gtts_class, mock_path_exists):
        """Test successful audio generation with mocked gTTS."""
        mock_gtts_instance = MagicMock()
        mock_gtts_class.return_value = mock_gtts_instance

        returned_filename = generate_audio_summary(
            self.sample_text, self.output_filename, self.default_lang
        )

        mock_gtts_class.assert_called_once_with(
            text=self.sample_text, lang=self.default_lang, slow=False
        )
        mock_gtts_instance.save.assert_called_once_with(self.output_filename)
        self.assertEqual(returned_filename, self.output_filename)

    @patch('audio_generator.os.path.exists', return_value=True)
    @patch('audio_generator.gTTS', side_effect=gTTSError("Mocked gTTS init error"))
    def test_gtts_processing_failure_on_init(self, mock_gtts_class, mock_path_exists):
        """Test AudioGenerationError when gTTS initialization fails."""
        with self.assertRaisesRegex(AudioGenerationError, "gTTS Error: Could not generate audio. Details: Mocked gTTS init error"):
            generate_audio_summary(self.sample_text, self.output_filename, self.default_lang)
        mock_gtts_class.assert_called_once()

    @patch('audio_generator.os.path.exists', return_value=True)
    @patch('audio_generator.gTTS')
    def test_gtts_processing_failure_on_save(self, mock_gtts_class, mock_path_exists):
        """Test AudioGenerationError when gTTS save method fails."""
        mock_gtts_instance = MagicMock()
        mock_gtts_instance.save.side_effect = gTTSError("Mocked gTTS save error")
        mock_gtts_class.return_value = mock_gtts_instance

        with self.assertRaisesRegex(AudioGenerationError, "gTTS Error: Could not generate audio. Details: Mocked gTTS save error"):
            generate_audio_summary(self.sample_text, self.output_filename, self.default_lang)
        
        mock_gtts_class.assert_called_once_with(
            text=self.sample_text, lang=self.default_lang, slow=False
        )
        mock_gtts_instance.save.assert_called_once_with(self.output_filename)

    @patch('audio_generator.os.path.exists', return_value=True)
    @patch('audio_generator.gTTS')
    def test_file_saving_io_error(self, mock_gtts_class, mock_path_exists):
        """Test AudioGenerationError when save method raises IOError."""
        mock_gtts_instance = MagicMock()
        mock_gtts_instance.save.side_effect = IOError("Mocked IOError on save")
        mock_gtts_class.return_value = mock_gtts_instance

        with self.assertRaisesRegex(AudioGenerationError, "An unexpected error occurred during audio generation or saving: Mocked IOError on save"):
            generate_audio_summary(self.sample_text, self.output_filename, self.default_lang)
        mock_gtts_instance.save.assert_called_once_with(self.output_filename)

    @patch('audio_generator.gTTS') # To check it's not called
    def test_empty_input_text(self, mock_gtts_class):
        """Test AudioGenerationError for empty input text and that gTTS is not called."""
        with self.assertRaisesRegex(AudioGenerationError, "Input text is empty or not a string."):
            generate_audio_summary("", self.output_filename, self.default_lang)
        mock_gtts_class.assert_not_called()

    @patch('audio_generator.os.makedirs')
    @patch('audio_generator.os.path.exists')
    @patch('audio_generator.gTTS') # Mock gTTS to prevent actual audio generation
    def test_output_directory_creation_successful(self, mock_gtts_class, mock_path_exists, mock_makedirs):
        """Test that os.makedirs is called when output directory does not exist."""
        mock_gtts_instance = MagicMock()
        mock_gtts_class.return_value = mock_gtts_instance
        
        # Configure os.path.exists: False for dir, True for file (or simplify)
        # For this test, we only care about the directory.
        output_dir = os.path.join(self.test_dir_path, "new_subdir")
        output_file_in_subdir = os.path.join(output_dir, "test.mp3")

        # First call to exists is for the directory, second for the file (if logic implies)
        # audio_generator.py: if output_dir and not os.path.exists(output_dir):
        mock_path_exists.return_value = False # Simulate directory does not exist

        generate_audio_summary(self.sample_text, output_file_in_subdir, self.default_lang)

        mock_path_exists.assert_called_once_with(output_dir)
        mock_makedirs.assert_called_once_with(output_dir)
        mock_gtts_instance.save.assert_called_once_with(output_file_in_subdir)


    @patch('audio_generator.os.makedirs', side_effect=OSError("Mocked OSError on makedirs"))
    @patch('audio_generator.os.path.exists', return_value=False) # Dir does not exist
    @patch('audio_generator.gTTS')
    def test_output_directory_creation_failure(self, mock_gtts_class, mock_path_exists, mock_makedirs):
        """Test AudioGenerationError when os.makedirs fails."""
        output_dir = os.path.join(self.test_dir_path, "new_subdir_fail")
        output_file_in_subdir = os.path.join(output_dir, "test_fail.mp3")

        with self.assertRaisesRegex(AudioGenerationError, f"Could not create output directory '{output_dir}'. Error: Mocked OSError on makedirs"):
            generate_audio_summary(self.sample_text, output_file_in_subdir, self.default_lang)

        mock_path_exists.assert_called_once_with(output_dir)
        mock_makedirs.assert_called_once_with(output_dir)
        mock_gtts_class.assert_not_called() # Should fail before gTTS is invoked

    @patch('audio_generator.os.makedirs')
    @patch('audio_generator.os.path.exists', return_value=True) # Dir already exists
    @patch('audio_generator.gTTS')
    def test_output_directory_already_exists(self, mock_gtts_class, mock_path_exists, mock_makedirs):
        """Test that os.makedirs is NOT called when output directory already exists."""
        mock_gtts_instance = MagicMock()
        mock_gtts_class.return_value = mock_gtts_instance

        output_dir = os.path.dirname(self.output_filename) # e.g. self.test_dir_path

        generate_audio_summary(self.sample_text, self.output_filename, self.default_lang)

        mock_path_exists.assert_called_once_with(output_dir) # Check if the directory exists
        mock_makedirs.assert_not_called() # Since it exists, makedirs should not be called
        mock_gtts_instance.save.assert_called_once_with(self.output_filename)


if __name__ == '__main__':
    unittest.main()
