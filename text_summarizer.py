import torch
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer
import math

# Global variable to cache the summarizer pipeline
SUMMARIZER_PIPELINE = None
MODEL_NAME = "sshleifer/distilbart-cnn-12-6" # Also suitable for Spanish as it's multilingual
# Alternative Spanish specific model, but might be larger or require more setup: "facebook/bart-large-cnn-samsum" (general)
# or "Narrativa/bsc-roberta2roberta-base-finetuned-summarization-es" (Spanish specific, might be better if available and compatible)

# It's good practice to define a minimum number of words/tokens for a text to be summarizable
MIN_TEXT_LENGTH_FOR_SUMMARIZATION = 20 # Minimum number of words
DEFAULT_MIN_SUMMARY_TOKENS = 10 # Absolute minimum tokens for a summary
DEFAULT_MAX_SUMMARY_TOKENS = 512 # Absolute maximum tokens for a summary output by the function

class SummarizationError(Exception):
    """Custom exception for summarization errors."""
    pass

def _load_summarizer():
    """Loads the summarization pipeline if not already loaded."""
    global SUMMARIZER_PIPELINE
    if SUMMARIZER_PIPELINE is None:
        try:
            # Check if the model and tokenizer exist before loading the pipeline
            # This helps in providing clearer error messages if a model is not found.
            AutoTokenizer.from_pretrained(MODEL_NAME)
            AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
            SUMMARIZER_PIPELINE = pipeline("summarization", model=MODEL_NAME, tokenizer=MODEL_NAME)
            print(f"Summarization pipeline loaded successfully with model: {MODEL_NAME}")
        except Exception as e:
            # This can catch network issues, model not found, etc.
            error_message = f"Failed to load summarization model '{MODEL_NAME}'. Error: {e}"
            print(error_message)
            raise SummarizationError(error_message)
    return SUMMARIZER_PIPELINE

def summarize_text(text: str, min_length_ratio: float = 0.1, max_length_ratio: float = 0.3) -> str:
    """
    Summarizes the input text using a pre-trained Hugging Face model.

    Args:
        text: The text to summarize.
        min_length_ratio: The desired minimum length of the summary as a fraction of the original text length.
        max_length_ratio: The desired maximum length of the summary as a fraction of the original text length.

    Returns:
        The summarized text, or the original text if it's too short or an error occurs.
    
    Raises:
        SummarizationError: If there's an issue with model loading or the summarization process.
    """
    if not text or not isinstance(text, str):
        print("Warning: Input text is empty or not a string. Returning empty string.")
        return ""

    try:
        summarizer = _load_summarizer()
    except SummarizationError as e:
        # If model loading fails, re-raise the error or return original text
        # For this implementation, let's re-raise to make the caller aware.
        raise SummarizationError(f"Summarization failed due to model loading issue: {e}")


    # Calculate text length in terms of words/tokens (approximate by splitting)
    # Using word count as a proxy for token count for ratio calculation simplicity.
    # For more accurate token count, a tokenizer would be needed here, but word count is often sufficient for ratios.
    text_word_count = len(text.split())

    if text_word_count < MIN_TEXT_LENGTH_FOR_SUMMARIZATION:
        print(f"Warning: Input text is too short for meaningful summarization (words: {text_word_count}). Returning original text.")
        return text

    # Calculate min_length and max_length for the summary
    # These are often interpreted as token counts by the model
    calculated_min_length = math.ceil(text_word_count * min_length_ratio)
    calculated_max_length = math.ceil(text_word_count * max_length_ratio)

    # Apply absolute minimum and maximum token limits for the summary
    calculated_min_length = max(DEFAULT_MIN_SUMMARY_TOKENS, calculated_min_length)
    calculated_max_length = min(DEFAULT_MAX_SUMMARY_TOKENS, calculated_max_length)
    
    # Ensure min_length is not greater than max_length
    if calculated_min_length > calculated_max_length:
        # This can happen if the text is short and ratios are close, or after applying caps.
        # Adjust min_length to be less than or equal to max_length, or set to a fraction of max_length.
        calculated_min_length = max(DEFAULT_MIN_SUMMARY_TOKENS, int(calculated_max_length * 0.5)) # e.g., min is at most half of max
        if calculated_min_length > calculated_max_length: # If max_length is very small (e.g. after capping)
             calculated_min_length = calculated_max_length


    # The pipeline's underlying model (e.g., BART) has a max input sequence length (e.g., 1024 tokens).
    # The pipeline should handle truncation of input text if it's too long.
    # The max_length parameter in the pipeline call refers to the *summary* length.
    # Some models have a max_length limit for the generated summary (e.g. distilbart-cnn-12-6 default is 142)
    # We are overriding it with our calculated_max_length.
    # The model's own max_position_embeddings (e.g., 1024 for sshleifer/distilbart-cnn-12-6)
    # is for the input, which the pipeline handles.
    # If calculated_max_length exceeds what the model can generate for a summary, it might be capped by the model.
    # For sshleifer/distilbart-cnn-12-6, max_length for summary can be set.

    try:
        print(f"Summarizing with: min_length={calculated_min_length}, max_length={calculated_max_length}")
        summary_result = summarizer(
            text,
            min_length=calculated_min_length,
            max_length=calculated_max_length,
            do_sample=False,
            truncation=True # Ensure input text is truncated if it exceeds model's max input length
        )
        summary = summary_result[0]['summary_text']
        return summary
    except Exception as e:
        # This can catch various errors during the summarization call itself
        error_message = f"Error during text summarization: {e}"
        print(error_message)
        # Optionally, return the original text or an empty string, or re-raise
        raise SummarizationError(error_message)

if __name__ == '__main__':
    print("Running text_summarizer.py example...")
    
    # Example Spanish text (adjust as needed for testing)
    sample_text_es = """
    La inteligencia artificial (IA) es un campo de la informática que se enfoca en crear sistemas capaces de realizar tareas que típicamente requieren inteligencia humana. 
    Estas tareas incluyen el aprendizaje, el razonamiento, la resolución de problemas, la percepción, la comprensión del lenguaje y la toma de decisiones. 
    La IA se manifiesta en diversas aplicaciones, desde motores de búsqueda y asistentes virtuales hasta vehículos autónomos y diagnósticos médicos.
    El desarrollo de la IA ha sido impulsado por el aumento en la capacidad computacional y la disponibilidad de grandes cantidades de datos.
    Existen diferentes enfoques dentro de la IA, incluyendo el aprendizaje automático (machine learning), el aprendizaje profundo (deep learning) y el procesamiento del lenguaje natural (NLP).
    A pesar de sus avances, la IA también plantea desafíos éticos y sociales significativos que deben ser abordados.
    """

    short_text = "Este es un texto muy corto."

    # Test 1: Summarize Spanish text
    print("\n--- Test 1: Summarizing Spanish sample text ---")
    try:
        summary1 = summarize_text(sample_text_es, min_length_ratio=0.15, max_length_ratio=0.4)
        print(f"Original Length (words): {len(sample_text_es.split())}")
        print(f"Summary 1: {summary1}")
        print(f"Summary Length (words): {len(summary1.split())}")
    except SummarizationError as e:
        print(f"SummarizationError: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    # Test 2: Summarize short text
    print("\n--- Test 2: Summarizing very short text ---")
    try:
        summary2 = summarize_text(short_text)
        print(f"Original: {short_text}")
        print(f"Summary 2: {summary2}") # Should return original text
    except SummarizationError as e:
        print(f"SummarizationError: {e}")

    # Test 3: Text that might be slightly above the MIN_TEXT_LENGTH_FOR_SUMMARIZATION
    medium_short_text = " ".join(["palabra"] * 25) # 25 words
    print("\n--- Test 3: Summarizing medium-short text ---")
    try:
        summary3 = summarize_text(medium_short_text, min_length_ratio=0.2, max_length_ratio=0.5)
        print(f"Original Length (words): {len(medium_short_text.split())}")
        print(f"Summary 3: {summary3}")
        print(f"Summary Length (words): {len(summary3.split())}")
    except SummarizationError as e:
        print(f"SummarizationError: {e}")

    # Test 4: Empty text
    print("\n--- Test 4: Summarizing empty text ---")
    try:
        summary4 = summarize_text("")
        print(f"Summary 4: '{summary4}'") # Should be empty
    except SummarizationError as e:
        print(f"SummarizationError: {e}")

    # Test 5: Simulate model loading failure (hard to do directly without altering global state / internet)
    # This can be manually tested by, e.g., providing an invalid model name temporarily
    # or disconnecting from the internet if the model isn't cached.
    # For now, we rely on the _load_summarizer's exception handling.
    print("\n--- Test 5: Model loading error (conceptual) ---")
    # To truly test, you might temporarily change MODEL_NAME to something invalid
    # global MODEL_NAME
    # _old_model_name = MODEL_NAME
    # MODEL_NAME = "invalid/model-name-that-does-not-exist"
    # global SUMMARIZER_PIPELINE # Reset pipeline to force reload
    # SUMMARIZER_PIPELINE = None
    # try:
    #     summarize_text("This text won't be summarized due to model load failure.")
    # except SummarizationError as e:
    #     print(f"Caught expected SummarizationError for invalid model: {e}")
    # finally:
    #     MODEL_NAME = _old_model_name # Restore
    #     SUMMARIZER_PIPELINE = None # Reset again
    print("Note: True model loading failure test requires manual intervention or network changes.")

    print("\nText summarizer example run complete.")
