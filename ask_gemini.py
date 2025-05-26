#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import json
from datetime import datetime
import google.generativeai as genai

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
            except Exception:
                return []
    return []

def save_history(prompt, response, model):
    history = load_history()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def build_context():
    general = load_context(GENERAL_CONTEXT_FILE)
    local = load_context(LOCAL_CONTEXT_FILE)
    context = ""
    if general:
        context += f"[General Context]\n{general}\n\n"
    if local:
        context += f"[Local Context]\n{local}\n\n"
    return context

def build_history():
    history = load_history()
    text = ""
    for item in history[-10:]:  # Solo los últimos 10 turnos para no saturar
        text += f"User: {item['prompt']}\nGemini: {item['response']}\n\n"
    return text

def chat_mode(model):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(model)
    chat_history = []
    history = load_history()
    for item in history[-10:]:
        chat_history.append({'role': 'user', 'parts': [item["prompt"]]})
        chat_history.append({'role': 'model', 'parts': [item["response"]]})
    chat = model.start_chat(history=chat_history)
    context = build_context()
    if context:
        print("--- Contexto aplicado ---")
        print(context.strip())
        print("-------------------------")
    print("Chat mode. Escribe 'exit' para salir.")
    while True:
        try:
            prompt = input("Tú: ")
            if prompt.lower() in ["exit", "quit"]:
                break
            full_prompt = context + prompt
            print("Gemini: ", end="", flush=True)
            response = chat.send_message(full_prompt, stream=True)
            response_text = ""
            for chunk in response:
                for part in chunk.parts:
                    if hasattr(part, 'text'):
                        print(part.text, end="", flush=True)
                        response_text += part.text
            print()
            save_history(prompt, response_text, model._model_name)
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo del chat.")
            break

def prompt_mode(model, prompt):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(model)
    context = build_context()
    history = build_history()
    full_prompt = ""
    if context:
        full_prompt += context
    if history:
        full_prompt += f"[Historial]\n{history}\n"
    full_prompt += prompt
    # Cambia stream=True por stream=False
    response = model.generate_content(full_prompt, stream=False)
    response_text = ""
    # El resultado ya no es un stream, sino un objeto
    if hasattr(response, 'text'):
        print(response.text, end="", flush=True)
        response_text += response.text
    print()
    save_history(prompt, response_text, model._model_name)

def main():
    parser = argparse.ArgumentParser(description="Gemini CLI simple con historial y contexto")
    parser.add_argument("prompt", nargs="?", help="Prompt para Gemini (si no usas --chat)")
    parser.add_argument("--model", default="gemini-pro", help="Modelo Gemini (default: gemini-pro)")
    parser.add_argument("--chat", action="store_true", help="Modo chat interactivo")
    args = parser.parse_args()

    if "GEMINI_API_KEY" not in os.environ:
        print("Error: GEMINI_API_KEY no está definido.", file=sys.stderr)
        sys.exit(1)

    if args.chat:
        chat_mode(args.model)
    elif args.prompt:
        prompt_mode(args.model, args.prompt)
    else:
        print("Debes ingresar un prompt o usar --chat.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()