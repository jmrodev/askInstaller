#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, C0301
# pylint: disable=missing-function-docstring, C0302
# pylint: disable=missing-module-docstring, C0302
# pylint: disable=invalid-name, C0302
# pylint: disable=R0912, R0915, R0914, R0913, R0903, R0902, C0115, C0116, C0103, C0302,W0603,W0718,W0613,W0102,R1710


import argparse
import json
import os
import sys # Ensure sys is imported for sys.exit
from datetime import datetime
from pathlib import Path
import google.generativeai as genai
import google.ai.generativelanguage as glm
from PIL import Image

# Attempt to import project-specific modules for PDF audio summary
try:
    from pdf_processor import extract_text_from_pdf, PDFProcessingError
    from text_summarizer import summarize_text, SummarizationError
    from audio_generator import generate_audio_summary, AudioGenerationError
except ImportError:
    PDF_AUDIO_MODULES_AVAILABLE = False
else:
    PDF_AUDIO_MODULES_AVAILABLE = True

# --- Configuration and Globals ---
HISTORY_FILE = ".ask_history.json"
LOCAL_CONTEXT_FILE = ".ask_context.local"
GENERAL_CONTEXT_FILE = os.path.expanduser("~/.ask_context.general")
SUPPORTED_MODELS = {
    "gemini-pro": {"vision": False, "image_gen": False, "default": True},
    "gemini-1.0-pro": {"vision": False, "image_gen": False},
    "gemini-1.0-pro-latest": {"vision": False, "image_gen": False},
    "gemini-1.5-flash-latest": {"vision": True, "image_gen": False},
    "gemini-1.5-pro-latest": {"vision": True, "image_gen": False},
    "gemini-pro-vision": {"vision": True, "image_gen": False}, # Older vision model
    "imagen-2": {"vision": False, "image_gen": True, "source": "gemini-1.5-flash-latest"} # Placeholder, actual model used via Gemini
}
DEFAULT_MODEL = [k for k, v in SUPPORTED_MODELS.items() if v.get("default")][0] \
                if any(v.get("default") for v in SUPPORTED_MODELS.values()) else "gemini-1.0-pro"

# Safety settings for content generation (can be adjusted)
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# --- Helper Functions ---

def is_vision_model(model_name):
    return SUPPORTED_MODELS.get(model_name, {}).get("vision", False)

def is_image_gen_model(model_name):
    return SUPPORTED_MODELS.get(model_name, {}).get("image_gen", False)

def get_actual_model_for_image_gen(model_name):
    return SUPPORTED_MODELS.get(model_name, {}).get("source", model_name)

def load_context(context_file):
    if os.path.exists(context_file):
        with open(context_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_history(prompt, response_text, model_name):
    history = load_history()
    timestamp = datetime.now().isoformat()
    history.append({"timestamp": timestamp, "model": model_name, "prompt": prompt, "response": response_text})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
        print("Local history cleared.")
    else:
        print("No local history found to clear.")

def clear_local_context():
    if os.path.exists(LOCAL_CONTEXT_FILE):
        os.remove(LOCAL_CONTEXT_FILE)
        print(f"{LOCAL_CONTEXT_FILE} cleared.")
    else:
        print(f"No {LOCAL_CONTEXT_FILE} found to clear.")

def clear_general_context():
    if os.path.exists(GENERAL_CONTEXT_FILE):
        os.remove(GENERAL_CONTEXT_FILE)
        print(f"{GENERAL_CONTEXT_FILE} cleared.")
    else:
        print(f"No {GENERAL_CONTEXT_FILE} found to clear.")

def print_available_models():
    print("Available models:")
    for name, details in SUPPORTED_MODELS.items():
        info = []
        if details.get("vision"): info.append("vision")
        if details.get("image_gen"): info.append(f"image generation (via {details.get('source')})")
        if not info: info.append("text")
        print(f"  - {name} ({', '.join(info)})")

def handle_file_inputs(file_paths):
    combined_content = ""
    if file_paths:
        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    combined_content += f.read() + "\n\n"
            except FileNotFoundError:
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error reading file {file_path}: {e}", file=sys.stderr)
                sys.exit(1)
    return combined_content


def parse_arguments():
    parser = argparse.ArgumentParser(description="CLI tool to interact with Google's Gemini API.")
    parser.add_argument("prompt", nargs="?", help="The text prompt to send to the model. Required if not in chat mode or using other primary modes.")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=SUPPORTED_MODELS.keys(), help=f"Specify the model to use. Default: {DEFAULT_MODEL}")
    parser.add_argument("--temperature", type=float, default=None, help="Controls the randomness of the output. Range: 0.0 to 1.0.")
    parser.add_argument("--max-output-tokens", type=int, default=None, help="Maximum number of tokens to generate.")
    parser.add_argument("--top-k", type=int, default=None, help="Sample from the K most likely next tokens.")
    parser.add_argument("--top-p", type=float, default=None, help="Sample from the smallest set of tokens whose cumulative probability exceeds P.")
    parser.add_argument("--file", nargs="+", help="Path to one or more text files to prepend to the prompt.")
    parser.add_argument("--image-path", help="Path to an image file for multimodal prompts (for vision-capable models).")
    parser.add_argument("--generate", type=str, metavar="IMAGE_PROMPT", help="Switch to image generation mode with the given prompt. Other primary modes are ignored.")
    parser.add_argument("--chat", action="store_true", help="Enter interactive chat mode.")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit.")
    parser.add_argument("--clear-local-history", action="store_true", help="Clear the local history file and exit.")
    parser.add_argument("--clear-local-context", action="store_true", help="Clear the local context file and exit.")
    parser.add_argument("--clear-general-context", action="store_true", help="Clear the general context file and exit.")
    parser.add_argument("--no-history", action="store_true", help="Do not load or save conversation history for this session.")
    parser.add_argument("--no-context", action="store_true", help="Do not load local or general context files for this session.")

    # PDF Audio Summarization Options
    pdf_summary_group = parser.add_argument_group("PDF Audio Summarization Options")
    pdf_summary_group.add_argument(
        "--pdf-audio-summary",
        type=str,
        metavar="PDF_FILE_PATH",
        required=False,
        help="Path to a PDF file to generate an audio summary from. When this flag is used, other primary modes (prompt, chat, generate image) are ignored."
    )
    pdf_summary_group.add_argument(
        "--details-prompt",
        type=str,
        metavar="TEXT",
        required=False,
        help="Optional textual prompt providing specific details or instructions for the summarization or audio generation process (e.g., 'focus on financial aspects', 'use a cheerful voice')."
    )
    pdf_summary_group.add_argument(
        "--output-audio",
        type=str,
        metavar="OUTPUT_MP3_PATH",
        required=False,
        help="Optional. Path for the output audio summary file (e.g., summary.mp3). Defaults to '<pdf_filename>_summary.mp3'."
    )
    pdf_summary_group.add_argument(
        "--audio-lang",
        type=str,
        default='es',
        metavar="LANG_CODE",
        help="Optional. Language for the audio summary (e.g., 'en', 'es'). Default: 'es'."
    )
    pdf_summary_group.add_argument(
        "--min-sum-ratio",
        type=float,
        default=0.1,
        metavar="FLOAT",
        help="Optional. Minimum summary length as a ratio of original text (0.0 to 1.0). Default: 0.1."
    )
    pdf_summary_group.add_argument(
        "--max-sum-ratio",
        type=float,
        default=0.3,
        metavar="FLOAT",
        help="Optional. Maximum summary length as a ratio of original text (0.0 to 1.0). Default: 0.3."
    )

    return parser.parse_args()

# --- Main API Interaction Logic ---

def generate_content_with_gemini(args, full_prompt, image_parts=None):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    generation_config = genai.types.GenerationConfig(
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        top_k=args.top_k,
        top_p=args.top_p
    )
    model_name_to_use = args.model
    if is_image_gen_model(args.model):
        model_name_to_use = get_actual_model_for_image_gen(args.model)
        print(f"Generating image with prompt: \"{full_prompt[:100]}...\" using {args.model} (via {model_name_to_use})")
        model = genai.GenerativeModel(model_name_to_use, safety_settings=SAFETY_SETTINGS)
        response = model.generate_content(f"Generate an image: {full_prompt}") 
        if args.model == "imagen-2": 
            try:
                img_bytes = response.candidates[0].content.parts[0].inline_data.data
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"generated_{full_prompt[:20].replace(' ','_')}_{timestamp}.png"
                with open(filename, "wb") as img_file:
                    img_file.write(img_bytes)
                print(f"Image saved as {filename}")
                return f"Image generated and saved as {filename}" 
            except (AttributeError, IndexError, TypeError) as e:
                print(f"Could not extract image data from response for {args.model}. Error: {e}", file=sys.stderr)
                print(f"Raw response: {response}", file=sys.stderr)
                return "Image generation was requested, but no image data found in response."

    model = genai.GenerativeModel(model_name_to_use, safety_settings=SAFETY_SETTINGS)

    if image_parts: 
        if not is_vision_model(model_name_to_use):
            print(f"Warning: Model {model_name_to_use} may not be vision-capable. Attempting multimodal input anyway.", file=sys.stderr)
        contents = image_parts + [full_prompt]
        response = model.generate_content(contents, generation_config=generation_config, stream=True)
    else: 
        response = model.generate_content(full_prompt, generation_config=generation_config, stream=True)
    
    response_text_parts = []
    try:
        for chunk in response:
            if chunk.parts: 
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    print(f"Prompt blocked: {response.prompt_feedback.block_reason}", file=sys.stderr)
                    sys.exit(f"Error: Prompt blocked due to {response.prompt_feedback.block_reason}")

                if chunk.candidates and chunk.candidates[0].finish_reason != 1: 
                    finish_reason_map = {
                        0: "FINISH_REASON_UNSPECIFIED", 2: "MAX_TOKENS",
                        3: "SAFETY", 4: "RECITATION", 5: "OTHER"
                    }
                    reason = finish_reason_map.get(chunk.candidates[0].finish_reason, "UNKNOWN")
                    print(f"\n[Content generation stopped. Reason: {reason}]", file=sys.stderr)
                    if chunk.candidates[0].finish_reason == 3: 
                        partial_text = "".join(part.text for part in chunk.parts if hasattr(part, 'text'))
                        if not partial_text:
                            sys.exit(f"Error: Content generation blocked due to safety reasons. Reason: {reason}")
                for part in chunk.parts:
                    if hasattr(part, 'text'):
                        print(part.text, end="", flush=True)
                        response_text_parts.append(part.text)
    except Exception as e:
        if "DEADLINE_EXCEEDED" in str(e):
            print("\nError: The request timed out (DEADLINE_EXCEEDED). Please try again later or simplify your query.", file=sys.stderr)
            sys.exit(1)
        elif "API_KEY_INVALID" in str(e) or "PERMISSION_DENIED" in str(e) and "API key" in str(e):
            print("\nError: Invalid or missing API key. Please check your GEMINI_API_KEY environment variable.", file=sys.stderr)
            sys.exit(1)
        elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            print(f"\nError: Prompt blocked. Reason: {response.prompt_feedback.block_reason}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\nAn unexpected error occurred during content generation: {e}", file=sys.stderr)
            sys.exit(1)
    
    print() 
    return "".join(response_text_parts)


def chat_mode(args):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(args.model, safety_settings=SAFETY_SETTINGS)
    
    history_for_chat = []
    if not args.no_history:
        loaded_hist = load_history()
        for item in loaded_hist:
            if item.get("prompt"):
                 history_for_chat.append({'role': 'user', 'parts': [item["prompt"]]})
            if item.get("response"):
                 history_for_chat.append({'role': 'model', 'parts': [item["response"]]})

    chat = model.start_chat(history=history_for_chat)
    
    print(f"Entering chat mode with {args.model}. Type 'exit' or 'quit' or Ctrl+D to end.")

    general_context = load_context(GENERAL_CONTEXT_FILE) if not args.no_context else ""
    local_context = load_context(LOCAL_CONTEXT_FILE) if not args.no_context else ""
    context_header = ""
    if general_context: context_header += f"[General Context]\n{general_context}\n\n"
    if local_context: context_header += f"[Local Context]\n{local_context}\n\n"
    if context_header:
        print("--- Applied Context ---")
        print(context_header.strip())
        print("----------------------")

    while True:
        try:
            user_prompt = input("You: ")
            if user_prompt.lower() in ["exit", "quit"]:
                break

            full_chat_prompt = context_header + user_prompt
            
            image_parts_chat = []
            if user_prompt.startswith("!image ") and len(user_prompt.split()) > 1:
                image_path_chat = user_prompt.split(" ", 1)[1]
                if not is_vision_model(args.model):
                    print("Warning: Current model may not support images. To use images, switch to a vision-capable model.", file=sys.stderr)
                else:
                    try:
                        img = Image.open(image_path_chat)
                        image_parts_chat.append(img)
                        print(f"(Image {image_path_chat} attached)")
                    except FileNotFoundError:
                        print(f"Error: Image file not found: {image_path_chat}", file=sys.stderr)
                        continue 
                    except Exception as e:
                        print(f"Error loading image {image_path_chat}: {e}", file=sys.stderr)
                        continue
            
            print("Gemini: ", end="", flush=True)
            
            generation_config_chat = genai.types.GenerationConfig(
                temperature=args.temperature, 
                max_output_tokens=args.max_output_tokens, 
                top_k=args.top_k, 
                top_p=args.top_p  
            )

            if image_parts_chat:
                response = chat.send_message(
                    image_parts_chat + [full_chat_prompt], 
                    stream=True,
                    generation_config=generation_config_chat
                )
            else:
                response = chat.send_message(
                    full_chat_prompt,
                    stream=True,
                    generation_config=generation_config_chat
                )

            response_text_parts_chat = []
            for chunk in response:
                if chunk.parts:
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                        print(f"Prompt blocked: {response.prompt_feedback.block_reason}", file=sys.stderr)
                        break 
                    if chunk.candidates and chunk.candidates[0].finish_reason != 1: 
                        reason_map = {0:"UNSPECIFIED", 2:"MAX_TOKENS", 3:"SAFETY", 4:"RECITATION", 5:"OTHER"}
                        reason_str = reason_map.get(chunk.candidates[0].finish_reason, "UNKNOWN")
                        print(f"\n[Content generation stopped. Reason: {reason_str}]", file=sys.stderr)
                        if chunk.candidates[0].finish_reason == 3: 
                            partial_text = "".join(p.text for p in chunk.parts if hasattr(p, 'text'))
                            if not partial_text: 
                                print(f"Error: Content generation blocked due to safety ({reason_str}). Try rephrasing.", file=sys.stderr)
                                break
                    for part in chunk.parts:
                        if hasattr(part, 'text'):
                            print(part.text, end="", flush=True)
                            response_text_parts_chat.append(part.text)
            print() 
            
            if not args.no_history:
                save_history(user_prompt, "".join(response_text_parts_chat), args.model)

        except EOFError: 
            print("\nExiting chat mode.")
            break
        except KeyboardInterrupt: 
            print("\nExiting chat mode.")
            break
        except Exception as e:
            print(f"\nAn error occurred in chat mode: {e}", file=sys.stderr)
            if "API_KEY_INVALID" in str(e):
                sys.exit(1) 

def main():
    args = parse_arguments()

    if args.list_models:
        print_available_models()
        sys.exit(0)
    if args.clear_local_history:
        clear_history()
        sys.exit(0)
    if args.clear_local_context:
        clear_local_context()
        sys.exit(0)
    if args.clear_general_context:
        clear_general_context()
        sys.exit(0)

    # --- New PDF Audio Summary Mode ---
    if args.pdf_audio_summary: # This condition checks if the flag was used
        if not PDF_AUDIO_MODULES_AVAILABLE:
            print("Error: PDF summarization helper modules (pdf_processor.py, text_summarizer.py, audio_generator.py) not found in the same directory.", file=sys.stderr)
            sys.exit(1)

        print("PDF Audio Summary Mode Activated:")
        print(f"  PDF File: {args.pdf_audio_summary}")
        if args.details_prompt: # Check if optional details_prompt was provided
            print(f"  Details Prompt: {args.details_prompt}")
        
        output_audio_path = args.output_audio # This will be None if not provided
        if not output_audio_path: # If None, derive default
            pdf_basename = os.path.splitext(os.path.basename(args.pdf_audio_summary))[0]
            output_audio_path = f"{pdf_basename}_summary.mp3"
            print(f"  Output Audio (defaulted): {output_audio_path}")
        else:
            print(f"  Output Audio: {output_audio_path}")
            
        print(f"  Audio Language: {args.audio_lang}") # Will use default 'es' if not provided
        print(f"  Min Summary Ratio: {args.min_sum_ratio}") # Default 0.1
        print(f"  Max Summary Ratio: {args.max_sum_ratio}") # Default 0.3
        
        try:
            print(f"Step 1: Extracting text from PDF: {args.pdf_audio_summary}...")
            extracted_text = extract_text_from_pdf(args.pdf_audio_summary)
            if not extracted_text:
                print("Error: No text could be extracted from the PDF. Cannot proceed.", file=sys.stderr)
                sys.exit(1)
            print("Text extraction successful.")

            prompt_for_summary = extracted_text
            if args.details_prompt:
                # Simple approach: Prepend details prompt to the extracted text.
                prompt_for_summary = f"User-provided details for summarization: {args.details_prompt}\n\n--- Extracted PDF Text ---\n{extracted_text}"
                print(f"Info: Using details prompt to guide summarization.")

            print("Step 2: Summarizing extracted text...")
            summary_text = summarize_text(
                prompt_for_summary,
                min_length_ratio=args.min_sum_ratio,
                max_length_ratio=args.max_sum_ratio
            )
            if not summary_text: # Includes case where summary is empty
                print("Error: Text summarization failed to produce a summary.", file=sys.stderr)
                sys.exit(1)
            print("Summarization successful.")

            print("Step 3: Generating audio summary...")
            audio_file_path = generate_audio_summary(
                summary_text,
                output_filename=output_audio_path,
                lang=args.audio_lang
            )
            if audio_file_path:
                print(f"Success! Audio summary successfully saved to: {audio_file_path}")
            else:
                # This case should ideally be caught by AudioGenerationError
                print("Error: Audio generation failed (returned None).", file=sys.stderr)
                sys.exit(1)

        except FileNotFoundError: # Specifically for args.pdf_audio_summary
            print(f"Error: Input PDF file '{args.pdf_audio_summary}' not found.", file=sys.stderr)
            sys.exit(1)
        except (PDFProcessingError, SummarizationError, AudioGenerationError) as e:
            print(f"An error occurred during PDF audio summarization: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected critical error occurred during PDF audio summarization: {e}", file=sys.stderr)
            sys.exit(1)
        
        sys.exit(0) # Successfully exit after PDF audio summary mode.
    # --- End of New PDF Audio Summary Mode ---


    # Check for API Key after PDF summary mode (which might not need it if modules are local)
    # and before other modes that definitely need it.
    if "GEMINI_API_KEY" not in os.environ:
        print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # --- Image Generation Mode ---
    if args.generate:
        if not args.model: 
            print("Error: Model must be specified for image generation if default is not image-gen capable.", file=sys.stderr)
            sys.exit(1)
        if not is_image_gen_model(args.model) and args.model not in ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"]:
            print(f"Warning: Model {args.model} is not explicitly marked for image generation. Attempting anyway.", file=sys.stderr)

        image_prompt = args.generate
        general_context_img = load_context(GENERAL_CONTEXT_FILE) if not args.no_context else ""
        local_context_img = load_context(LOCAL_CONTEXT_FILE) if not args.no_context else ""
        full_image_prompt = ""
        if general_context_img: full_image_prompt += f"{general_context_img}\n"
        if local_context_img: full_image_prompt += f"{local_context_img}\n"
        full_image_prompt += image_prompt

        print(f"Attempting to generate image with prompt: \"{full_image_prompt[:100]}...\" using model {args.model}")
        
        try:
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            actual_model_for_gen = get_actual_model_for_image_gen(args.model)
            img_model = genai.GenerativeModel(actual_model_for_gen) 
            img_response = img_model.generate_content(
                glm.Content(parts=[glm.Part(text=f"Generate an image of: {full_image_prompt}")])
            )
            
            image_generated = False
            if img_response.candidates and img_response.candidates[0].content.parts:
                for part in img_response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        img_bytes = part.inline_data.data
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        clean_prompt = "".join(c if c.isalnum() else "_" for c in image_prompt[:30])
                        filename = f"generated_{clean_prompt}_{timestamp}.png"
                        with open(filename, "wb") as img_file:
                            img_file.write(img_bytes)
                        print(f"Image successfully generated and saved as {filename}")
                        image_generated = True
                        break 
            if not image_generated:
                print("Image generation requested, but no image data found in the expected part of the response.")
                try:
                    print("Response text (if any):", img_response.text)
                except ValueError: 
                    if img_response.prompt_feedback and img_response.prompt_feedback.block_reason:
                         print(f"Image generation likely blocked. Reason: {img_response.prompt_feedback.block_reason}")
                    else:
                         print("No textual response or specific block reason found.")
        except Exception as e:
            print(f"Error during image generation with {args.model}: {e}", file=sys.stderr)
        sys.exit(0)

    # --- Chat Mode ---
    if args.chat:
        chat_mode(args)
        sys.exit(0)

    # --- Standard Prompt Mode ---
    if not args.prompt:
        print("Error: Prompt is required for single-turn queries if not in other modes.", file=sys.stderr)
        sys.exit(1)
    
    general_context = load_context(GENERAL_CONTEXT_FILE) if not args.no_context else ""
    local_context = load_context(LOCAL_CONTEXT_FILE) if not args.no_context else ""
    history_context = ""
    if not args.no_history:
        history = load_history()
        for item in history: 
            history_context += f"User: {item['prompt']}\nGemini: {item['response']}\n\n"

    file_content = handle_file_inputs(args.file)
    full_prompt_parts = []
    if general_context: full_prompt_parts.append(f"[General Context]\n{general_context}")
    if local_context: full_prompt_parts.append(f"[Local Context]\n{local_context}")
    if history_context: full_prompt_parts.append(f"[Past Interactions]\n{history_context}")
    if file_content: full_prompt_parts.append(f"[File Content]\n{file_content}")
    full_prompt_parts.append(args.prompt)
    full_prompt = "\n\n".join(full_prompt_parts).strip()

    image_parts = []
    if args.image_path:
        if not is_vision_model(args.model):
            print(f"Warning: Model {args.model} is not vision-capable. Image input will likely be ignored or cause an error.", file=sys.stderr)
        try:
            img = Image.open(args.image_path)
            image_parts.append(img) 
        except FileNotFoundError:
            print(f"Error: Image file not found: {args.image_path}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error loading image {args.image_path}: {e}", file=sys.stderr)
            sys.exit(1)

    response_text = generate_content_with_gemini(args, full_prompt, image_parts if image_parts else None)

    if not args.no_history:
        save_history(args.prompt, response_text, args.model)

if __name__ == "__main__":
    main()
