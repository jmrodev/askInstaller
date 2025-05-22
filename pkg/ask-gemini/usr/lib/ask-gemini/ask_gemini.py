import os
import argparse
import requests
import json

# Constantes
MAX_HISTORY_TURNS = 5
    # GOOGLE_AI_API_URL will be constructed in call_gemini_api based on the model
API_KEY_ENV_VAR = "GEMINI_API_KEY"
    DEFAULT_GENERAL_CONTEXT_FILE = ".ask_context.general"  # Not actively used, but kept for context from original script

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

def construct_payload(prompt, history, temperature, max_output_tokens, top_p, top_k):
    """
    Constructs the JSON payload for the Gemini API call.

    Args:
        prompt (str): The user's prompt.
        history (list): A list of previous conversation turns (not fully implemented in this version).
        temperature (float): Controls randomness in generation.
        max_output_tokens (int): Maximum number of tokens to generate.
        top_p (float): Nucleus sampling parameter.
        top_k (int): Top-k sampling parameter.

    Returns:
        str: A JSON string representing the payload.
    """
    conversation_history = []
    # Basic history construction; for complex conversations, this would need more sophisticated handling.
    for item in history:
        conversation_history.append({"role": item["role"], "parts": [{"text": item["content"]}]})

    payload = {
        "contents": conversation_history + [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "topK": top_k,
            "maxOutputTokens": max_output_tokens
        },
        "safetySettings": [ # Default safety settings from the original script
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        ]
    }
    return json.dumps(payload)

def call_gemini_api(payload, api_key, model_name):
    """
    Calls the Gemini API with the constructed payload.

    Args:
        payload (str): The JSON payload for the API request.
        api_key (str): The Gemini API key.
        model_name (str): The name of the Gemini model to use.

    Returns:
        dict: The JSON response from the API as a Python dictionary.

    Raises:
        APIError: If any error occurs during the API call.
    """
    google_ai_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    params = {"key": api_key}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(google_ai_api_url, headers=headers, params=params, data=payload, timeout=60)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
    except requests.exceptions.ConnectionError as e:
        raise APIError(f"Error connecting to the API. Please check your internet connection and the API endpoint: {google_ai_api_url}. Original error: {e}")
    except requests.exceptions.Timeout as e:
        raise APIError(f"The request to the API timed out after 60 seconds. Original error: {e}")
    except requests.exceptions.HTTPError as e:
        # Attempt to get more details from the API's JSON error response
        error_message = f"API request failed with HTTP status code {response.status_code} ({response.reason})."
        try:
            error_details = response.json()
            if "error" in error_details and "message" in error_details["error"]:
                error_message += f" API Error Message: {error_details['error']['message']}"
            else: # If the error structure is not as expected, append the full text
                error_message += f" Full response: {response.text}"
        except ValueError: # If the response is not JSON
            error_message += f" Full response: {response.text}"
        raise APIError(f"{error_message}. Original error: {e}")
    except requests.exceptions.RequestException as e: # Catch any other request-related errors
        raise APIError(f"An unexpected error occurred while calling the Gemini API: {e}")
    
    return response.json()

def parse_response(json_response):
    """
    Parses the JSON response from the API and extracts the generated text.

    Args:
        json_response (dict): The API response as a Python dictionary.

    Returns:
        str: The extracted text content from the first candidate.

    Raises:
        APIError: If the response structure is not as expected or text is missing.
    """
    try:
        candidates = json_response.get("candidates")
        if not candidates:
            # More detailed error if 'candidates' is missing or empty
            raise APIError(f"API response is missing the 'candidates' field or it is empty. Response: {json.dumps(json_response)}")
        
        if not isinstance(candidates, list) or len(candidates) == 0:
            raise APIError(f"The 'candidates' field in the API response is not a list or is empty. Response: {json.dumps(json_response)}")

        content = candidates[0].get("content")
        if not content:
            raise APIError(f"The first candidate in the API response does not contain the 'content' field. Response: {json.dumps(json_response)}")

        parts = content.get("parts")
        if not parts:
            raise APIError(f"The 'content' of the first candidate in the API response does not contain the 'parts' field. Response: {json.dumps(json_response)}")

        if not isinstance(parts, list) or len(parts) == 0:
            raise APIError(f"The 'parts' field in the API response is not a list or is empty. Response: {json.dumps(json_response)}")

        text = parts[0].get("text")
        if text is None: # Explicitly check for None, as an empty string might be a valid (though unlikely) response part
            raise APIError(f"The first part of the content in the API response does not contain the 'text' field or its value is null. Response: {json.dumps(json_response)}")
        
        return text
    # Catch specific parsing errors and provide context
    except (KeyError, IndexError, TypeError) as e: 
        raise APIError(f"Error parsing the API response: {e}. Malformed response structure. Response: {json.dumps(json_response)}")

def main():
    """Main function to parse arguments, construct payload, call API, and print response.""" # Updated docstring
    parser = argparse.ArgumentParser(description="A command-line tool to interact with the Google Gemini API.")
    parser.add_argument("prompt", nargs="+", help="The text prompt to send to the API.")
    parser.add_argument("--model", type=str, default="gemini-pro", help="The model to use (e.g., 'gemini-pro', 'gemini-pro-vision'). Default: gemini-pro.")
    parser.add_argument("--temperature", type=float, default=0.9, help="Controls randomness. Lower values are more deterministic. Default: 0.9.")
    parser.add_argument("--max-output-tokens", type=int, default=2048, help="Maximum number of tokens to generate. Default: 2048.")
    parser.add_argument("--top-p", type=float, default=1.0, help="Nucleus sampling parameter. Default: 1.0.")
    parser.add_argument("--top-k", type=int, default=1, help="Top-k sampling parameter. Default: 1.")
        parser.add_argument("--file-path", type=str, help="Path to a text file whose content will be prepended to the prompt.") # New file-path argument
    args = parser.parse_args()

    try:
        api_key = load_api_key()
            prompt_text = " ".join(args.prompt) 
            
            # Handle file content if --file-path is provided
            if args.file_path:
                try:
                    # Ensure UTF-8 encoding for broader compatibility
                    with open(args.file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    # Prepend file content to the main prompt
                    prompt_text = f"Content from file '{args.file_path}':\n{file_content}\n\n---\n\nUser Prompt:\n{prompt_text}"
                except FileNotFoundError:
                    print(f"Error: File not found at path: {args.file_path}")
                    exit(1)
                except Exception as e: # Catch other potential file reading errors
                    print(f"Error reading file {args.file_path}: {e}")
                    exit(1)
            
            current_history = [] 

            payload = construct_payload(prompt_text, current_history, args.temperature, args.max_output_tokens, args.top_p, args.top_k) 
            json_response = call_gemini_api(payload, api_key, args.model) 
        response_text = parse_response(json_response)

        print(response_text)
    
    except APIError as e:
        print(f"Error: {e}") 
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}") # Updated error message
        exit(1)

if __name__ == "__main__":
    main()
