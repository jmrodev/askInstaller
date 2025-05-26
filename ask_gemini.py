#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import json
from datetime import datetime
import google.generativeai as genai # pyright: ignore[reportMissingTypeStubs]

HISTORY_FILE = ".ask_history.json"
LOCAL_CONTEXT_FILE = ".ask_context.local"
GENERAL_CONTEXT_FILE = os.path.expanduser("~/.ask_context.general")

def load_context(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Advertencia: No se pudo decodificar el archivo de historial {HISTORY_FILE}. Empezando con historial vacío.", file=sys.stderr)
                return []
    return []

def save_history(prompt, response, model_name_str):
    history = load_history()
    # Guardar el prompt original del usuario, no el prompt completo con contexto/historial
    history.append({
        "timestamp": datetime.now().isoformat(),
        "model": model_name_str,
        "prompt": prompt, # El prompt original del usuario
        "response": response
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def build_context_string():
    general = load_context(GENERAL_CONTEXT_FILE)
    local = load_context(LOCAL_CONTEXT_FILE)
    context_parts = []
    if general:
        context_parts.append(f"[Contexto General]\n{general}")
    if local:
        context_parts.append(f"[Contexto Local]\n{local}")
    return "\n\n".join(context_parts) + "\n\n" if context_parts else ""


def build_history_for_sdk(limit=10):
    """Construye el historial en el formato que espera el SDK (lista de dicts con role y parts)."""
    loaded_history = load_history()
    sdk_history = []
    for item in loaded_history[-limit:]:
        sdk_history.append({'role': 'user', 'parts': [{'text': item["prompt"]}]})
        sdk_history.append({'role': 'model', 'parts': [{'text': item["response"]}]})
    return sdk_history

def build_history_text_for_prompt(limit=10):
    """Construye una representación textual del historial para el modo prompt."""
    history = load_history()
    text_parts = []
    for item in history[-limit:]:
        text_parts.append(f"Usuario: {item['prompt']}\nGemini: {item['response']}")
    return "\n\n".join(text_parts) + "\n\n" if text_parts else ""


def chat_mode(model_name_str):
    try:
        model_instance = genai.GenerativeModel(model_name_str)
    except Exception as e:
        print(f"Error al inicializar GenerativeModel en chat_mode: {e}", file=sys.stderr)
        return

    # Construir historial para start_chat en el formato del SDK
    chat_history_sdk_format = build_history_for_sdk(limit=10)

    try:
        chat = model_instance.start_chat(history=chat_history_sdk_format)
    except Exception as e:
        print(f"Error al iniciar chat (start_chat): {e}", file=sys.stderr)
        return

    context_str = build_context_string() # El contexto general/local

    if context_str.strip():
        print("--- Contexto (informativo, no enviado explícitamente en cada turno de chat) ---")
        print(context_str.strip())
        print("-----------------------------------------------------------------------------")
        # Nota: El contexto general/local no se envía explícitamente en cada turno
        # con chat.send_message() a menos que lo concatenes manualmente al user_prompt.
        # start_chat lo podría usar como una instrucción inicial si el historial está vacío,
        # o podrías enviar un mensaje inicial con él. El SDK maneja el historial de la conversación.

    print("Modo chat. Escribe 'exit' para salir.")

    while True:
        try:
            user_prompt_text = input("Tú: ")
            if user_prompt_text.lower() in ["exit", "quit"]:
                break

            print("Gemini: ", end="", flush=True)
            # Enviar solo el prompt del usuario. El historial ya está gestionado por el objeto `chat`.
            # Si el contexto general/local necesitara ser re-enfatizado en cada turno,
            # tendrías que concatenarlo aquí: full_user_input = context_str + user_prompt_text
            # pero esto lo duplicaría en el historial guardado si save_history usa user_prompt_text.
            response_stream = chat.send_message(user_prompt_text, stream=True)
            response_text = ""
            for chunk in response_stream:
                for part in chunk.parts:
                    if hasattr(part, 'text') and part.text:
                        print(part.text, end="", flush=True)
                        response_text += part.text
            print()
            save_history(user_prompt_text, response_text, model_name_str) # Guardar prompt original y respuesta
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo del chat.")
            break
        except Exception as e:
            print(f"\nOcurrió un error durante el chat: {e}")
            break

def prompt_mode(model_name_str, user_prompt_text):
    try:
        model_instance = genai.GenerativeModel(model_name_str)
    except Exception as e:
        print(f"Error al inicializar GenerativeModel en prompt_mode: {e}", file=sys.stderr)
        return

    # Construir el contenido para enviar, similar a la estructura del curl
    # 1. Contexto general y local
    # 2. Historial de conversación
    # 3. Prompt actual del usuario

    full_prompt_string_parts = []
    
    context_str = build_context_string()
    if context_str.strip():
        full_prompt_string_parts.append(context_str.strip())

    history_str = build_history_text_for_prompt(limit=10) # Historial como texto
    if history_str.strip():
        full_prompt_string_parts.append(f"[Historial de Conversación Anterior]\n{history_str.strip()}")
    
    # Añadir el prompt actual del usuario
    full_prompt_string_parts.append(f"[Prompt Actual del Usuario]\n{user_prompt_text}")

    final_prompt_text_for_api = "\n\n".join(full_prompt_string_parts)

    # Estructura de contenido como en el curl
    contents_for_api = [
        {
            "parts": [{"text": final_prompt_text_for_api}]
        }
    ]
    
    # print(f"DEBUG: Contenido enviado a la API (prompt_mode):\n{json.dumps(contents_for_api, indent=2)}") # Para depuración

    print("Gemini: ", end="", flush=True)
    try:
        response = model_instance.generate_content(contents_for_api, stream=False)
        response_text = ""
        try:
            if response.parts:
                for part in response.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
            
            if response_text:
                print(response_text, end="", flush=True)
            else:
                print("[Respuesta vacía o bloqueada]", end="", flush=True)
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                    print(f" (Razón: {response.prompt_feedback.block_reason})", end="", flush=True)
                elif hasattr(response, 'candidates') and not response.candidates:
                    print(" (No se generaron candidatos)", end="", flush=True)

        except ValueError as ve:
            print(f"[Respuesta bloqueada o inválida: {ve}]", end="", flush=True)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f" (Razón: {response.prompt_feedback.block_reason})", end="", flush=True)
        except Exception as e_text:
            print(f"[Error procesando el contenido de la respuesta: {e_text}]", end="", flush=True)

        print()
        save_history(user_prompt_text, response_text, model_name_str) # Guardar prompt original y respuesta

    except Exception as e:
        print(f"\nOcurrió un error al generar contenido: {e}")
        # import traceback
        # traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Gemini CLI simple con historial y contexto")
    parser.add_argument("prompt", nargs="?", help="Prompt para Gemini (si no usas --chat)")
    # IMPORTANTE: Cambia 'gemini-1.5-flash-latest' si 'gemini-2.0-flash' es el correcto para ti.
    parser.add_argument("--model", default="gemini-1.5-flash-latest", 
                        help="Modelo Gemini (default: gemini-1.5-flash-latest). Si tu curl usa 'gemini-2.0-flash' y funciona, úsalo aquí.")
    parser.add_argument("--chat", action="store_true", help="Modo chat interactivo")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY no está definido en las variables de entorno.", file=sys.stderr)
        sys.exit(1)

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error al configurar la API de Gemini (genai.configure): {e}", file=sys.stderr)
        sys.exit(1)

    # Determinar el modelo a usar. args.model toma precedencia.
    # Si tu 'curl' usa gemini-2.0-flash y funciona, asegúrate de pasarlo con --model
    # o cambiar el default en argparse.
    model_to_use = args.model
    # print(f"DEBUG: Usando modelo: {model_to_use}")

    if args.chat:
        chat_mode(model_to_use)
    elif args.prompt:
        prompt_mode(model_to_use, args.prompt)
    else:
        print("Debes ingresar un prompt o usar --chat.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()