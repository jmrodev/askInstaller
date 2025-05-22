import os
import argparse
import requests
import json
import base64
import datetime # For image filenames

# === Constants ===
# Configuration for history length, API key environment variable, and file paths
MAX_HISTORY_TURNS = 10  # Max conversation turns (1 user + 1 model = 1 turn) sent to the API.
API_KEY_ENV_VAR = "GEMINI_API_KEY"  # Environment variable to store the Gemini API key.

# Context files for providing persistent instructions to the model
DEFAULT_GENERAL_CONTEXT_FILE = os.path.expanduser("~/.ask_context.general") # General context file in user's home.
LOCAL_CONTEXT_FILE = ".ask_context.local"  # Local context file in the current directory.

# History file for storing conversation records
HISTORY_FILE = ".ask_history.json"  # File to store conversation history.

# --- Model Definitions ---
# These lists should be updated based on currently available and supported Gemini models.
SUPPORTED_TEXT_MODELS = [
    "gemini-1.5-flash",      # Fast, versatile text model
    "gemini-1.5-pro-latest", # Advanced text model
    "gemini-1.0-pro"         # Older, but still capable text model
]
SUPPORTED_MULTIMODAL_MODELS = [  # Models that can take text and image as input
    "gemini-1.5-pro-latest", # Primary vision model
    "gemini-1.5-flash"       # Can also handle vision tasks
]
SUPPORTED_IMAGE_GENERATION_MODELS = [
    "imagen-2"  # Placeholder for a dedicated image generation model like Google's Imagen 2.
    # Note: Image generation via general Gemini models (e.g., gemini-1.5-flash with function calling/tools)
    # is a more complex, multi-turn process. This script's payload for it is experimental
    # and might need adjustments based on specific model capabilities and API documentation.
    # Dedicated models usually have their own, more direct APIs.
]

# --- Default Model Choices ---
# These are used if the user doesn't specify a model for a particular task.
DEFAULT_TEXT_MODEL = "gemini-1.5-flash"        # Default for general text queries.
DEFAULT_VISION_MODEL = "gemini-1.5-pro-latest" # Default when an image input is provided.
DEFAULT_IMAGE_GENERATION_MODEL = "imagen-2"    # Default for the --generate feature.
DEFAULT_CHAT_MODEL = "gemini-1.5-flash"        # Default for interactive --chat mode.


class APIError(Exception):
    """Custom exception for API-related errors encountered in this script."""
    pass

def load_api_key():
    """Loads the Gemini API key from the environment variable GEMINI_API_KEY."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print("Error: The GEMINI_API_KEY environment variable is not set. "
              "Please obtain an API key from the Gemini documentation and set it as an environment variable. "
              "For example: export GEMINI_API_KEY='YOUR_API_KEY'")
        exit(1)
    return api_key

# --- Argument Parsing ---
def parse_arguments():
    """Parses command-line arguments with logical groups for better help output."""
    parser = argparse.ArgumentParser(
        description="Command-line interface for Google Gemini API, supporting text, multimodal, and image generation tasks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows default values in help messages.
    )

    # Group for primary input methods (prompt, file, image for input)
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "prompt", 
        nargs="*",  # 0 or more arguments
        default=[], # Default to an empty list if no prompt is given
        help="The main prompt text for text or multimodal queries. Can be multi-word. Required if not using --generate or --chat."
    )
    input_group.add_argument(
        "--file", 
        type=str, 
        nargs='+', # 1 or more file paths
        metavar="FILE_PATH", 
        help="Path(s) to file(s) whose content will be read and prepended to the prompt."
    )
    input_group.add_argument(
        "--image-path", 
        type=str, 
        metavar="IMAGE_PATH", 
        help="Path to an image file (e.g., JPEG, PNG) for multimodal input with vision-capable models."
    )

    # Group for different modes of operation
    mode_group = parser.add_argument_group("Mode of Operation")
    mode_group.add_argument(
        "--generate", 
        type=str, 
        metavar="IMAGE_GEN_PROMPT", 
        help="Generate an image based on the given prompt. This mode takes priority over standard text/multimodal queries and file inputs."
    )
    mode_group.add_argument(
        "--chat", 
        action="store_true", 
        help="Enter interactive chat mode. Ignores other input/generation flags if used."
    )

    # Group for model selection and generation parameters
    model_config_group = parser.add_argument_group("Model Configuration")
    model_config_group.add_argument(
        "--model", 
        type=str, 
        default=DEFAULT_TEXT_MODEL, 
        help="Specify the model to use. See --list-models for available options."
    )
    model_config_group.add_argument(
        "--temperature", 
        type=float, 
        default=0.8, # Slightly more conservative default than 0.9
        metavar="VALUE", 
        help="Controls output randomness (0.0-1.0). Lower values are more deterministic."
    )
    model_config_group.add_argument(
        "--max-output-tokens", 
        type=int, 
        default=2048, 
        metavar="TOKENS", 
        help="Maximum number of tokens to generate for text responses."
    )
    model_config_group.add_argument(
        "--top-p", 
        type=float, 
        default=1.0, # Default is often 1.0, meaning no nucleus sampling unless specified
        metavar="VALUE", 
        help="Nucleus sampling parameter. Controls the cumulative probability mass of tokens considered."
    )
    model_config_group.add_argument(
        "--top-k", 
        type=int, 
        default=1,   # Default is often 1, meaning only the top token is considered (greedy)
        metavar="K_VALUE", 
        help="Top-k sampling parameter. Considers the top K most probable tokens."
    )

    # Group for managing local data (history and context)
    management_group = parser.add_argument_group("History and Context Management")
    management_group.add_argument(
        "--clear-local-history", 
        action="store_true", 
        help=f"Clear the local conversation history file ({HISTORY_FILE}) and exit."
    )
    management_group.add_argument(
        "--clear-local-context", 
        action="store_true", 
        help=f"Clear the local context file ({LOCAL_CONTEXT_FILE}) and exit."
    )
    management_group.add_argument(
        "--clear-general-context", 
        action="store_true", 
        help=f"Clear the general context file ({DEFAULT_GENERAL_CONTEXT_FILE}) and exit."
    )
    
    # Group for other utility options
    other_group = parser.add_argument_group("Other Options")
    other_group.add_argument(
        "--list-models", 
        action="store_true", 
        help="List all supported and default models by category and exit."
    )
    
    return parser.parse_args()

# === Context Management ===
def load_context_file(filepath, context_type="Local"):
    """
    Loads context from a given filepath if it exists.
    Handles file not found and read errors gracefully.
    """
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Warning: Could not load {context_type.lower()} context from {filepath}: {e}")
            return None
    return None

def clear_context_file(filepath, context_type="Local"):
    """
    Clears a context file.
    Handles file not found and delete errors gracefully.
    """
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"{context_type} context file {filepath} cleared.")
        except Exception as e:
            print(f"Error clearing {context_type.lower()} context file {filepath}: {e}")
    else:
        print(f"{context_type} context file {filepath} does not exist. Nothing to clear.")

# Aliases for specific context types for better code readability
def load_local_context(filepath=LOCAL_CONTEXT_FILE):
    """Loads context from the local context file."""
    return load_context_file(filepath, context_type="Local")

def clear_local_context(filepath=LOCAL_CONTEXT_FILE):
    """Clears the local context file."""
    clear_context_file(filepath, context_type="Local")

def load_general_context(filepath=DEFAULT_GENERAL_CONTEXT_FILE):
    """Loads context from the general (home directory) context file."""
    return load_context_file(filepath, context_type="General")

def clear_general_context(filepath=DEFAULT_GENERAL_CONTEXT_FILE):
    """Clears the general (home directory) context file."""
    clear_context_file(filepath, context_type="General")

# === History Management ===
# Functions for loading, saving, and clearing conversation history.
# History is stored in JSON format.

def load_local_history(filepath=HISTORY_FILE):
    """
    Loads conversation history from a local JSON file.
    Handles file not found, empty file, and JSON decoding errors.
    """
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: # File is empty
                    return []
                return json.loads(content) # Attempt to parse JSON
        except json.JSONDecodeError:
            print(f"Warning: History file {filepath} is corrupted or not valid JSON. Starting with empty history.")
            return []
        except Exception as e: # Catch other potential read errors
            print(f"Warning: Could not load history from {filepath}: {e}. Starting with empty history.")
            return []
    return [] # File does not exist

def save_local_history(history_data, filepath=HISTORY_FILE):
    """
    Saves conversation history to a local JSON file.
    Overwrites the file if it exists.
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save history to {filepath}: {e}")

def clear_local_history(filepath=HISTORY_FILE):
    """
    Clears the local conversation history file.
    Handles file not found and delete errors.
    """
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Local history file {filepath} cleared.")
        except Exception as e:
            print(f"Error clearing history file {filepath}: {e}")
    else:
        print(f"Local history file {filepath} does not exist. Nothing to clear.")

# === Interactive Chat Mode ===
def start_chat_session(args, client, initial_history):
    """
    Handles the interactive chat session.
    Loads and applies contexts, manages conversation history within the session,
    and saves history after each turn.
    """
    print(f"Starting interactive chat session with model {args.model}. Type 'exit' or 'quit' or Ctrl+D to end.")
    current_history = list(initial_history) # Make a mutable copy
    
    # Load contexts once for the session
    local_context_content = load_local_context(LOCAL_CONTEXT_FILE) 
    general_context_content = load_general_context(DEFAULT_GENERAL_CONTEXT_FILE)
    
    if general_context_content:
        print(f"Note: General context from {DEFAULT_GENERAL_CONTEXT_FILE} is active for this session.")
    if local_context_content:
        print(f"Note: Local context from {LOCAL_CONTEXT_FILE} is active for this session.")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                break
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat session.")
            break
        
        # Add user's current message to history for API call
        # The history_for_api should be what happened *before* this user_input
        history_for_api = current_history[-(MAX_HISTORY_TURNS * 2):] if MAX_HISTORY_TURNS > 0 else list(current_history)

        # Construct payload using the current user_input as the prompt_text
        # and history_for_api as the preceding conversation turns
        
        prompt_for_api_turn = user_input
        # Apply contexts: general first, then local
        if local_context_content: # Local context wraps the user input directly
            prompt_for_api_turn = f"Using local context:\n{local_context_content}\n---\nUser Prompt:\n{prompt_for_api_turn}"
        if general_context_content: # General context wraps whatever is inside (which might include local context)
            prompt_for_api_turn = f"Using general context:\n{general_context_content}\n---\n{prompt_for_api_turn}"
        
        payload_json = construct_api_payload(
            prompt_text=prompt_for_api_turn, # Current turn's prompt, potentially with all contexts
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            top_p=args.top_p,
            top_k=args.top_k,
            model_name=args.model, # Use the model specified for the chat session
            history=history_for_api, # History before this turn
            # Ensure other params like image_path, generation_prompt are None for pure chat
            image_path=None,
            generation_prompt=None
        )

        try:
            # print(f"DEBUG: Sending to API with history: {history_for_api}")
            # print(f"DEBUG: Current user prompt for API: {user_input}")
            json_response = client.call_api(args.model, payload_json)
            response_text = parse_api_response(json_response)
            
            print(f"Gemini: {response_text}")

            # Update full history with user input and model response
            current_history.append({"role": "user", "parts": [{"text": user_input}]})
            current_history.append({"role": "model", "parts": [{"text": response_text}]})
            save_local_history(current_history, HISTORY_FILE)

        except APIError as e:
            print(f"API Error: {e}")
            # Optionally, decide if the user's part of the failed turn should be saved.
            # Current behavior: If API call fails, this turn (user input + model error) is not saved to history.
        except Exception as e:
            print(f"An unexpected error occurred during chat turn: {e}")
            # Similar to APIError, consider history saving strategy for unexpected errors.

    print("Chat session ended.")


# === Image Handling (Input and Output) ===
def encode_image_to_base64(image_path):
    """
    Encodes an image file to a base64 string for API payload.
    Raises FileNotFoundError if the image_path is invalid.
    """
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def save_generated_image(base64_data, prompt_slug, extension="png"):
    """
    Decodes base64 image data and saves it to a file.
    Filename includes a timestamp and a slug from the generation prompt for uniqueness.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create a simple, filesystem-friendly slug from the first few words of the prompt.
    slug_words = "".join(c if c.isalnum() or c.isspace() else " " for c in prompt_slug).split()
    slug = "_".join(slug_words[:5]).strip("_")
    if not slug: slug = "image" # Default slug if prompt was empty or only special chars

    filename = f"generated_{slug}_{timestamp}.{extension}"
    try:
        with open(filename, "wb") as img_file:
            img_file.write(base64.b64decode(base64_data))
        print(f"Image saved as: {filename}")
        return filename
    except Exception as e:
        print(f"Error saving image '{filename}': {e}")
        return None

# === Payload Construction ===
def construct_api_payload(prompt_text, temperature, max_output_tokens, top_p, top_k, image_path=None, model_name="gemini-pro", history=None, generation_prompt=None):
    """
    Constructs the JSON payload for the Gemini API call.
    This function handles different types of requests:
    - Text-only queries.
    - Multimodal queries (text + input image).
    - Image generation requests (experimental, using a tool-based approach for capable models).

    Args:
        prompt_text (str): The user's prompt.
        temperature (float): Controls randomness in generation.
        max_output_tokens (int): Maximum number of tokens to generate.
        top_p (float): Nucleus sampling parameter.
        top_k (int): Top-k sampling parameter.
        image_path (str): Path to an image file (optional, for multimodal).
        model_name (str): The name of the Gemini model to use.
        history (list): A list of previous conversation turns (optional).
        generation_prompt (str): Prompt for image generation (optional).

    Returns:
        str: A JSON string representing the payload.
    """
    # Prioritize image generation payload if generation_prompt is provided
    if generation_prompt and model_name in SUPPORTED_IMAGE_GENERATION_MODELS:
        # This is a simplified payload for image generation.
        # Actual Gemini API for image generation (e.g., via Firebase or Vertex AI for Imagen)
        # might require a different structure, possibly using 'tools' or specific endpoints.
        # For this example, we'll assume a structure that fits the existing :generateContent
        # This payload structure is for models that support image generation via a tool/function calling mechanism.
        # The main prompt (`generation_prompt`) is embedded in a way that encourages the model to call the declared tool.
        # This is experimental and might need adjustment for specific models or future API changes.
        # A dedicated image generation model might have a simpler, direct payload structure.
        payload = {
            "contents": [
                # The user's request that should trigger the tool.
                {"role": "user", "parts": [{"text": f"Please generate an image based on this description: {generation_prompt}"}]}
            ],
            "tools": [{ # Declare the image generation tool to the model
                "function_declarations": [{
                    "name": "generate_image",
                    "description": "Generates an image based on a textual prompt provided by the user.",
                    "parameters": { # Define the parameters the tool (and model) expects
                        "type": "OBJECT",
                        "properties": {
                            "prompt": {
                                "type": "STRING",
                                "description": "The detailed textual prompt for image generation."
                            }
                        },
                        "required": ["prompt"]
                    }
                }]
            }],
            "tool_config": { # Configure the model to actually use the tool
                "mode": "ANY", # or "AUTO"; "ANY" allows the model to call any declared function.
                "function_calling_config": {
                    "mode": "ANY", 
                     "allowed_function_names": ["generate_image"] # Explicitly allow this function
                }
            },
            "generationConfig": { # General generation parameters; some might not apply to image generation
                "temperature": temperature,
                # "responseMimeType": "image/png", # Potentially useful if model could return image directly
            },
             "safetySettings": [ # Standard safety settings; review for image generation context
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            ]
        }
    else: # Default to text or multimodal chat/query
        conversation_history_payload = []
        if history: # Build the history part of the payload
            for item in history:
                # Assuming history items are already in the correct format: {"role": ..., "parts": [{"text": ...}]}
                conversation_history_payload.append({"role": item["role"], "parts": item["parts"]})

        # Prepare current turn's content (text and optional image)
        current_parts = [{"text": prompt_text if prompt_text else " "}] # API requires non-empty text part
        if image_path and model_name in SUPPORTED_MULTIMODAL_MODELS:
            try:
                image_b64 = encode_image_to_base64(image_path)
                current_parts.append(
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}} # Assuming JPEG, could be made more dynamic
                )
            except FileNotFoundError:
                # This error should ideally be caught before reaching here (e.g., in main or by encode_image_to_base64 raising it)
                # If it still occurs, raise an APIError to be handled by the main try-except block.
                raise APIError(f"Image file not found at path: {image_path}")
            except Exception as e:
                raise APIError(f"Error encoding image {image_path}: {e}")
        
        user_content = {"role": "user", "parts": current_parts}
        
        payload = {
            "contents": conversation_history_payload + [user_content], # Combine history with current user input
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "topK": top_k,
                "maxOutputTokens": max_output_tokens
            },
            "safetySettings": [ # Standard safety settings
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            ]
        }
    return json.dumps(payload)

# === API Client ===
class GeminiAPIClient:
    """
    A simple client to interact with the Google Gemini API.
    Manages API key and constructs HTTP requests.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def call_api(self, model_name, payload_json):
        """
        Calls the Gemini API with the constructed payload.

        Args:
            model_name (str): The name of the Gemini model to use.
            payload_json (str): The JSON payload for the API request.

        Returns:
            dict: The JSON response from the API as a Python dictionary.

        Raises:
            APIError: If any error occurs during the API call.
        """
        api_url = f"{self.base_url}/{model_name}:generateContent"
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(api_url, headers=headers, params=params, data=payload_json, timeout=60)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        except requests.exceptions.ConnectionError as e:
            raise APIError(f"Error connecting to the API. Please check your internet connection and the API endpoint: {api_url}. Original error: {e}")
        except requests.exceptions.Timeout as e:
            raise APIError(f"The request to the API timed out after 60 seconds. Original error: {e}")
        except requests.exceptions.HTTPError as e:
            error_message = f"API request failed with HTTP status code {response.status_code} ({response.reason})."
            try:
                error_details = response.json()
                if "error" in error_details and "message" in error_details["error"]:
                    error_message += f" API Error Message: {error_details['error']['message']}"
                else:
                    error_message += f" Full response: {response.text}"
            except ValueError:
                error_message += f" Full response: {response.text}"
            raise APIError(f"{error_message}. Original error: {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"An unexpected error occurred while calling the Gemini API: {e}")
        
        return response.json()

# --- Response Parsing ---
def parse_api_response(json_response):
    """
    Parses the JSON response from the API and extracts the generated text.


    Args:
        json_response (dict): The API response as a Python dictionary.
        generation_prompt_text (str, optional): The original prompt used for image generation;
                                                used here for creating a descriptive filename slug.

    Returns:
        str: Extracted text content from the response. If an image was generated and saved,
             this text might include confirmation messages or URIs. If only an image was expected
             and saved, the text might be minimal.

    Raises:
        APIError: If the response structure is not as expected or if essential data (like text or image data) is missing.
    """
    try:
        all_parts_text = [] # To collect all textual parts from the response
        image_saved_this_turn = False # Flag if an image was processed in this response

        # The API response typically includes a list of 'candidates' (potential completions).
        # We usually focus on the first candidate.
        candidates = json_response.get("candidates")
        if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
            raise APIError(f"API response is missing 'candidates' list or it is empty. Response: {json.dumps(json_response)}")

        for candidate_idx, candidate in enumerate(candidates):
            content = candidate.get("content")
            if not content or not content.get("parts"):
                # Log or store if a candidate has no processable parts, though usually we only care about the first.
                # all_parts_text.append(f"[Candidate {candidate_idx} has no processable 'parts' field]")
                if candidate_idx == 0: # If the primary candidate is bad, it's an issue.
                     raise APIError(f"Primary candidate in API response is missing 'content' or 'parts'. Response: {json.dumps(json_response)}")
                continue # Move to next candidate if any

            for part_idx, part in enumerate(content.get("parts", [])):
                # Extract textual content
                if "text" in part and part["text"]:
                    all_parts_text.append(part["text"])
                
                # Check for image data provided inline (base64 encoded)
                if "inlineData" in part and "data" in part["inlineData"] and "mimeType" in part["inlineData"]:
                    mime_type = part["inlineData"]["mimeType"]
                    if mime_type.startswith("image/"):
                        image_b64 = part["inlineData"]["data"]
                        extension = mime_type.split('/')[-1] # e.g., 'png', 'jpeg'
                        slug_for_filename = generation_prompt_text if generation_prompt_text else "generated_image"
                        saved_filename = save_generated_image(image_b64, slug_for_filename, extension)
                        if saved_filename:
                            image_saved_this_turn = True
                            # Add a message about the saved image to the text output if desired
                            # all_parts_text.append(f"[Image saved as {saved_filename}]") 
                    else:
                        all_parts_text.append(f"[Received unsupported inlineData mime_type: {mime_type}]")

                # Check for image data provided as a file URI (less common for direct generation output)
                elif "fileData" in part and "fileUri" in part["fileData"]:
                    all_parts_text.append(f"Image available at URI: {part['fileData']['fileUri']} (MIME: {part['fileData'].get('mimeType', 'N/A')})")
                    # Note: This script does not automatically download from URIs. User would be informed of the URI.
                
                # Check for function call response (relevant for tool-based image generation)
                elif "functionCall" in part:
                    # This means the model is trying to call a function (tool) we declared (e.g., "generate_image").
                    # A complete tool implementation would involve the client (this script) executing the function
                    # with the provided arguments and then sending the result back to the model in a new API call.
                    # For this script's current "experimental" image generation, we hope the model might provide
                    # image data in a subsequent part or if the API handles the tool call internally and returns data.
                    # If only a functionCall is returned, it means direct image data was not provided in *this* turn.
                    fc_name = part["functionCall"].get("name", "unknown_function")
                    fc_args = part["functionCall"].get("args", {})
                    all_parts_text.append(f"[Model wants to call function '{fc_name}' with arguments: {json.dumps(fc_args)}]")
                    all_parts_text.append("  (Note: This script's image generation is experimental and may require multi-turn tool handling not fully implemented here if only a function call is returned.)")


        # If after processing all parts, there's no textual output AND no image was saved,
        # it might indicate an issue or an unexpected response structure.
        if not all_parts_text and not image_saved_this_turn:
            # Re-check specifically for a functionCall as the *only* content, which is a valid but intermediate step in tool use.
            primary_candidate_parts = json_response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            if len(primary_candidate_parts) == 1 and primary_candidate_parts[0].get("functionCall"):
                 # This situation was already handled by appending text about the function call.
                 # The 'all_parts_text' will contain this information.
                 pass
            else:
                # No text, no image, and not just a function call means the response is effectively empty or unhandled.
                raise APIError(f"No usable text or image data found in API response. Response: {json.dumps(json_response)}")

        return "\n".join(all_parts_text).strip()

    except (KeyError, IndexError, TypeError) as e: # Catch errors from navigating the JSON structure
        raise APIError(f"Error parsing API response structure: {e}. Response: {json.dumps(json_response)}")

def display_supported_models():
    """Prints the categorized list of supported and default models to the console."""
    print("Supported Models by Category:")
    
    print("\n  Text-only Models (Optimized for text generation and understanding):")
    if SUPPORTED_TEXT_MODELS:
        for m in SUPPORTED_TEXT_MODELS: print(f"    - {m}")
    else:
        print("    No text models currently listed.")
    print(f"    (Default for text tasks: {DEFAULT_TEXT_MODEL})")

    print("\n  Multimodal Models (Text + Image/Video Input, Text Output):")
    if SUPPORTED_MULTIMODAL_MODELS:
        for m in SUPPORTED_MULTIMODAL_MODELS: print(f"    - {m}")
    else:
        print("    No multimodal models currently listed.")
    print(f"    (Default for vision tasks: {DEFAULT_VISION_MODEL})")
    
    print("\n  Image Generation Models (Generate images from text prompts):")
    if SUPPORTED_IMAGE_GENERATION_MODELS:
        for m in SUPPORTED_IMAGE_GENERATION_MODELS: print(f"    - {m}")
        print("    Note: Image generation via general Gemini models (e.g., gemini-1.5-flash with tools) is experimental.")
        print("    Dedicated models like 'imagen-2' are preferred for quality if available via this API.")
    else:
        print("    No dedicated image generation models currently listed.")
    print(f"    (Default for image generation: {DEFAULT_IMAGE_GENERATION_MODEL})")

    print(f"\nDefault model for interactive chat: {DEFAULT_CHAT_MODEL}")
    print("\nNote: Model availability and capabilities are subject to API updates.")


def build_prompt_from_files(file_paths, base_prompt_text):
    """Loads content from multiple files and prepends it to the base prompt text."""
    all_file_contents = []
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            all_file_contents.append(f"Content from file '{file_path}':\n{file_content}\n---")
        except FileNotFoundError:
            print(f"Error: File not found at path: {file_path}")
            exit(1)
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            exit(1)
    
    if not all_file_contents:
        return base_prompt_text

    # Join all file contents and append the final user prompt
    return "\n\n".join(all_file_contents) + f"\n\nUser Prompt:\n{base_prompt_text}"

def main():
    """
    Main function to orchestrate script operations:
    1. Parses command-line arguments.
    2. Handles utility flags (--list-models, --clear-*).
    3. Initializes API client and loads contexts/history.
    4. Enters chat mode if --chat is specified.
    5. Otherwise, proceeds with single-shot text, multimodal, or image generation query.
    6. Constructs payload, calls API, parses response, prints output.
    7. Saves interaction to history for single-shot queries.
    """
    args = parse_arguments()
    api_key = load_api_key() # Load API key early; script exits if not found.
    client = GeminiAPIClient(api_key) # Initialize API client.
    
    # Handle utility flags that cause immediate exit
    if args.list_models:
        display_supported_models()
        exit(0)

    # Handle multiple clear commands: if any are passed, perform them.
    # The last clear command in this sequence will cause an exit.
    # If multiple are passed, e.g. --clear-local-history --clear-local-context, both are cleared.
    did_clear_something = False
    if args.clear_local_history:
        clear_local_history(HISTORY_FILE)
        did_clear_something = True
            
    if args.clear_local_context:
        clear_local_context(LOCAL_CONTEXT_FILE)
        did_clear_something = True
    
    if args.clear_general_context:
        clear_general_context(DEFAULT_GENERAL_CONTEXT_FILE)
        did_clear_something = True
    
    if did_clear_something: # Exit if any clear operation was performed.
        exit(0)

    # Load persistent contexts (general and local)
    local_context_content = load_local_context(LOCAL_CONTEXT_FILE)
    general_context_content = load_general_context(DEFAULT_GENERAL_CONTEXT_FILE)

    # --- Chat Mode ---
    if args.chat:
        # Warn if other prompt-providing or mode-specific flags are used with --chat, as they'll be ignored.
        ignored_flags_in_chat = []
        if args.prompt: ignored_flags_in_chat.append("positional prompt") # `default=[]` means it's always present
        if args.file: ignored_flags_in_chat.append("--file")
        if args.image_path: ignored_flags_in_chat.append("--image-path (for input)")
        if args.generate: ignored_flags_in_chat.append("--generate")
        
        # Filter out empty prompt from ignored_flags list (if prompt was truly empty)
        ignored_flags_in_chat = [flag for flag in ignored_flags_in_chat if flag != "positional prompt" or args.prompt]

        if ignored_flags_in_chat:
            print(f"Warning: In --chat mode, the following arguments are ignored: {', '.join(ignored_flags_in_chat)}.")

        # Model selection for chat: User specified or the script's default chat model.
        # The default for args.model is DEFAULT_TEXT_MODEL. If user hasn't changed it for chat, switch to DEFAULT_CHAT_MODEL.
        if args.model == DEFAULT_TEXT_MODEL: 
             args.model = DEFAULT_CHAT_MODEL # Use dedicated chat model if user didn't specify one.
        
        initial_history = load_local_history(HISTORY_FILE) # Load history for the chat session.
        start_chat_session(args, client, initial_history) # Pass client, args (for model/params), and history.
                                                          # Contexts are loaded within start_chat_session.
        exit(0) # Exit after chat session concludes.


    # --- Standard Single-Shot Execution (Text, Multimodal, or Image Generation) ---
    
    # Validate that a prompt is provided if not generating an image (chat mode already exited).
    # `args.prompt` is a list; `"".join(args.prompt).strip()` checks if it's effectively empty.
    if not args.generate and (not args.prompt or not "".join(args.prompt).strip()):
        print("Error: The 'prompt' argument is required and cannot be empty when not using '--generate' or '--chat'.")
        exit(1)
    
    # Also validate --generate prompt if that mode is chosen
    if args.generate and not args.generate.strip():
        print("Error: The --generate prompt cannot be empty.")
        exit(1)


    current_history = load_local_history(HISTORY_FILE) # Load history for context.
    # Slice history for API call, keeping the most recent turns.
    history_for_api = current_history[-(MAX_HISTORY_TURNS * 2):] if MAX_HISTORY_TURNS > 0 else list(current_history)

    try:
        generation_mode = bool(args.generate) # True if --generate has a prompt.
        user_prompt_for_history = ""          # The raw prompt to be saved in history.
        base_prompt_for_api = ""              # Prompt after file content, before contexts.
        current_model = args.model            # Model specified by user or argparse default (DEFAULT_TEXT_MODEL).
        processed_image_path = None           # Path for input image if provided.

        # Determine the primary prompt and handle model switching based on mode/inputs.
        if generation_mode:
            user_prompt_for_history = args.generate
            base_prompt_for_api = args.generate # Image generation prompt.
            
            # Warn if other input types are redundantly provided with --generate.
            if args.prompt and "".join(args.prompt).strip(): print("Warning: Positional prompt arguments are ignored when --generate is used.")
            if args.file: print("Warning: --file arguments are ignored when --generate is used.")
            if args.image_path: print("Warning: --image-path argument (for input image) is ignored when --generate is used.")

            # Model selection for image generation:
            # If the current model (user-specified or default text) isn't explicitly for image generation, switch.
            if current_model not in SUPPORTED_IMAGE_GENERATION_MODELS:
                original_model_for_gen = current_model
                current_model = DEFAULT_IMAGE_GENERATION_MODEL
                print(f"Warning: Model '{original_model_for_gen}' may not be suitable for image generation. Switching to default image generation model: {current_model}.")
        else: # Text or multimodal query
            user_prompt_for_history = " ".join(args.prompt) # Raw user prompt for history.
            base_prompt_for_api = user_prompt_for_history   # Start with raw prompt.
            if args.file: # Prepend file contents if provided.
                base_prompt_for_api = build_prompt_from_files(args.file, base_prompt_for_api)
            
            processed_image_path = args.image_path # Path to an input image.
            if args.image_path: # Multimodal input (image + text)
                # If an image is provided, ensure the model supports multimodal input.
                if current_model not in SUPPORTED_MULTIMODAL_MODELS:
                    original_model_for_vision = current_model
                    current_model = DEFAULT_VISION_MODEL # Switch to default vision model.
                    print(f"Warning: Image provided for input, but model '{original_model_for_vision}' may not support images. Switching to default vision model: {current_model}.")
            # If no image path, and not generation mode, it's a text-only prompt.
            # Ensure the selected model is suitable for text (either a text model or a multimodal model).
            elif current_model not in SUPPORTED_TEXT_MODELS and current_model not in SUPPORTED_MULTIMODAL_MODELS:
                 # This catches cases where user might specify e.g., an image generation model for a text prompt.
                 original_model_for_text = current_model
                 current_model = DEFAULT_TEXT_MODEL # Switch to default text model.
                 print(f"Warning: Model '{original_model_for_text}' is not primarily a text/multimodal model. Switching to default text model: {current_model} for this text-only prompt.")
        
        # Construct the final prompt for the API, including any general or local contexts.
        final_prompt_for_api = base_prompt_for_api
        context_messages_to_print = [] # For notifying user if contexts are used.

        # Apply local context first (innermost wrapper around user's base prompt)
        if local_context_content:
            if generation_mode:
                final_prompt_for_api = f"Local Context for Image Gen: {local_context_content}\n---\n{final_prompt_for_api}"
            elif args.file: # If files are involved, local context prepends the already structured file content block
                final_prompt_for_api = f"Using local context:\n{local_context_content}\n---\n{final_prompt_for_api}"
            else: # Simple prompt or multimodal with an input image
                final_prompt_for_api = f"Using local context:\n{local_context_content}\n---\nUser Prompt:\n{final_prompt_for_api}"
            context_messages_to_print.append(f"--- Activated local context from {LOCAL_CONTEXT_FILE} ---")

        # Apply general context second (outermost wrapper)
        if general_context_content:
            if generation_mode:
                 final_prompt_for_api = f"General Context for Image Gen: {general_context_content}\n---\n{final_prompt_for_api}"
            else: # Covers simple, file, or multimodal prompts that might already have local context
                 final_prompt_for_api = f"Using general context:\n{general_context_content}\n---\n{final_prompt_for_api}"
            context_messages_to_print.append(f"--- Activated general context from {DEFAULT_GENERAL_CONTEXT_FILE} ---")
        
        # Print context activation messages (general first, then local) if not in chat mode (chat has its own notifications).
        if not args.chat and context_messages_to_print:
            for msg in reversed(context_messages_to_print): 
                 print(msg)

        # Construct the API payload.
        # History sent to API (`history_for_api`) should be turns *before* the current `final_prompt_for_api`.
        payload_json = construct_api_payload(
            prompt_text=final_prompt_for_api, 
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            top_p=args.top_p,
            top_k=args.top_k,
            image_path=processed_image_path, # Path to input image, if any.
            model_name=current_model,        # The determined model to use.
            history=history_for_api,         # Conversation history preceding current prompt.
            generation_prompt=args.generate if generation_mode else None # Specific prompt for image generation mode.
        )
        
        # Inform user which model is being used (especially if auto-switched).
        print(f"--- Using model: {current_model} ---")
        # For debugging payload:
        # print(f"DEBUG: Payload: {payload_json}") 

        # Call the API and parse the response.
        json_response = client.call_api(current_model, payload_json)
        response_text = parse_api_response(
            json_response, 
            generation_prompt_text=args.generate if generation_mode else None # For naming generated images.
        )

        print(response_text) # Print the final processed response.

        # Save the current interaction (original user prompt and model's final response) to the full history.
        current_history.append({"role": "user", "parts": [{"text": user_prompt_for_history}]})
        current_history.append({"role": "model", "parts": [{"text": response_text}]})
        save_local_history(current_history, HISTORY_FILE)
    
    except APIError as e: # Catch custom API errors from script logic.
        print(f"Error: {e}")
        exit(1)
    except Exception as e: # Catch any other unexpected errors.
        print(f"An unexpected error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    main()
