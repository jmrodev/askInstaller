#!/bin/bash

# Script Bash para interactuar con la API de Gemini (ask.sh)

HISTORY_FILE=".ask_history.json"
LOCAL_CONTEXT_FILE=".ask_context.local"
GENERAL_CONTEXT_FILE="${HOME}/.ask_context.general" # Expande ~ a la ruta completa

DEFAULT_MODEL="gemini-1.5-flash-latest" # Cambia si usas gemini-2.0-flash y te funciona
MODEL_NAME="$DEFAULT_MODEL"
INTERACTIVE_CHAT=false
USER_PROMPT=""

# --- Funciones Auxiliares ---

# Función para mostrar el uso
usage() {
    echo "Uso: $0 [opciones] \"[prompt]\""
    echo "Opciones:"
    echo "  --model MODEL_NAME  Especifica el modelo de Gemini (default: $DEFAULT_MODEL)"
    echo "  --chat              Activa el modo chat interactivo"
    echo "  -h, --help          Muestra esta ayuda"
    exit 1
}

# Función para cargar contexto
load_context() {
    local file_path="$1"
    if [[ -f "$file_path" ]]; then
        cat "$file_path"
    fi
}

# Función para construir el string de contexto
build_context_string() {
    local general_ctx local_ctx full_ctx

    general_ctx=$(load_context "$GENERAL_CONTEXT_FILE")
    local_ctx=$(load_context "$LOCAL_CONTEXT_FILE")

    if [[ -n "$general_ctx" ]]; then
        full_ctx+="[Contexto General]\n${general_ctx}\n\n"
    fi
    if [[ -n "$local_ctx" ]]; then
        full_ctx+="[Contexto Local]\n${local_ctx}\n\n"
    fi
    echo -e "$full_ctx" # -e para interpretar \n
}

# Función para construir el historial como texto para el prompt (últimas 10 interacciones)
build_history_text_for_prompt() {
    if [[ ! -f "$HISTORY_FILE" ]]; then
        echo ""
        return
    fi
    # jq para extraer los últimos 10, formatear y revertir el orden para que el más reciente esté al final
    jq -r '.[-10:] | reverse | .[] | "Usuario: \(.prompt)\nGemini: \(.response)\n" ' "$HISTORY_FILE" | tac # tac para revertir de nuevo al orden cronológico
}

# Función para construir el historial para el modo chat (formato SDK)
build_history_for_chat_sdk() {
    if [[ ! -f "$HISTORY_FILE" ]]; then
        echo "[]" # Devuelve un array JSON vacío
        return
    fi
    # jq para tomar los últimos 10 y formatearlos como espera la API para historial de chat
    jq '.[-10:] | map({role: "user", parts: [{text: .prompt}]}, {role: "model", parts: [{text: .response}]})' "$HISTORY_FILE"
}


# Función para guardar en el historial
# $1: prompt del usuario
# $2: respuesta del modelo
# $3: nombre del modelo
save_to_history() {
    local user_p="$1"
    local model_r="$2"
    local model_n="$3"
    local timestamp

    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ") # ISO 8601 UTC

    local new_entry
    # Necesitamos escapar comillas y saltos de línea dentro del prompt y la respuesta para JSON válido
    user_p_json=$(echo "$user_p" | jq -Rsa .)
    model_r_json=$(echo "$model_r" | jq -Rsa .)

    new_entry=$(jq -n \
                  --arg ts "$timestamp" \
                  --arg mn "$model_n" \
                  --argjson up "$user_p_json" \
                  --argjson mr "$model_r_json" \
                  '{timestamp: $ts, model: $mn, prompt: $up, response: $mr}')

    if [[ ! -f "$HISTORY_FILE" ]]; then
        echo "[$new_entry]" > "$HISTORY_FILE"
    else
        # Añade la nueva entrada al array JSON existente
        jq ". += [$new_entry]" "$HISTORY_FILE" > "${HISTORY_FILE}.tmp" && mv "${HISTORY_FILE}.tmp" "$HISTORY_FILE"
    fi
}

# Función para llamar a la API de Gemini
# $1: Modelo
# $2: JSON del cuerpo de la solicitud (contents)
# $3: (opcional) "stream" para activar streaming (no implementado completamente para chat aquí)
call_gemini_api() {
    local model="$1"
    local request_body_json="$2"
    local stream_mode="$3" # No totalmente implementado para chat simple
    local api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/${model}"
    local action=":generateContent"
    
    if [[ "$stream_mode" == "stream" ]]; then
        action=":streamGenerateContent" # Para streaming (requiere manejo diferente de la respuesta)
    fi

    local full_url="${api_endpoint}${action}?key=${GEMINI_API_KEY}"

    # echo "DEBUG: Request body: $request_body_json" # Descomentar para depurar
    # echo "DEBUG: URL: $full_url" # Descomentar para depurar

    local response
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$request_body_json" \
        "$full_url")

    # echo "DEBUG: API Response: $response" # Descomentar para depurar

    # Extraer texto de la respuesta. Puede haber múltiples partes o candidatos.
    # Tomamos el texto del primer candidato y primera parte.
    # jq también maneja el caso de error donde la ruta no existe, devolviendo null.
    local extracted_text
    extracted_text=$(echo "$response" | jq -r '.candidates[0].content.parts[0].text // ""')

    if [[ -z "$extracted_text" ]] && echo "$response" | jq -e '.error' > /dev/null; then
        echo "Error de la API de Gemini:" >&2
        echo "$response" | jq '.error' >&2
        return 1
    elif [[ -z "$extracted_text" ]] && echo "$response" | jq -e '.candidates[0].finishReason' > /dev/null && [[ $(echo "$response" | jq -r '.candidates[0].finishReason') != "STOP" ]]; then
        echo "Respuesta recibida pero podría estar incompleta o bloqueada:" >&2
        echo "Razón de finalización: $(echo "$response" | jq -r '.candidates[0].finishReason // "N/A"')" >&2
        echo "Ratings de seguridad del prompt: $(echo "$response" | jq -c '.promptFeedback.safetyRatings // "N/A"')" >&2
        echo "Ratings de seguridad de la respuesta: $(echo "$response" | jq -c '.candidates[0].safetyRatings // "N/A"')" >&2
    fi
    echo "$extracted_text"
}

# --- Procesamiento de Argumentos ---

if [[ $# -eq 0 ]]; then
    usage
fi

# Parseo de argumentos simple
# Nota: getopts no maneja bien argumentos largos como --model,
# se requiere un bucle manual para opciones más complejas.
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --model)
            if [[ -n "$2" ]]; then
                MODEL_NAME="$2"
                shift # past argument
                shift # past value
            else
                echo "Error: --model requiere un argumento." >&2
                usage
            fi
            ;;
        --chat)
            INTERACTIVE_CHAT=true
            shift # past argument
            ;;
        -h|--help)
            usage
            ;;
        *)
            # Asume que lo restante es el prompt
            # Si ya hay un prompt, concatena
            if [[ -z "$USER_PROMPT" ]]; then
                USER_PROMPT="$1"
            else
                USER_PROMPT="$USER_PROMPT $1"
            fi
            shift # past argument
            ;;
    esac
done


# --- Lógica Principal ---

if [[ -z "$GEMINI_API_KEY" ]]; then
    echo "Error: La variable de entorno GEMINI_API_KEY no está definida." >&2
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: El comando 'jq' no se encontró. Por favor, instálalo." >&2
    exit 1
fi


if "$INTERACTIVE_CHAT"; then
    # --- Modo Chat ---
    echo "Modo Chat. Modelo: $MODEL_NAME. Escribe 'exit' o 'quit' para salir."
    context_str=$(build_context_string)
    if [[ -n "$context_str" ]]; then
        echo "--- Contexto Aplicado (informativo) ---"
        echo -e "${context_str}" | sed '$d' # Eliminar último \n\n si existe
        echo "------------------------------------"
    fi

    # El historial para el modo chat se construye iterativamente en la API o se pasa completo.
    # Para una implementación más simple en bash, enviaremos el historial acumulado
    # en cada turno, similar a cómo lo haría el modo no-chat.
    # Una implementación de chat verdadera con el SDK mantiene estado.
    # Aquí, cada turno es una nueva llamada a generateContent.

    current_chat_history_json="[]" # Inicia vacío para el cuerpo de la API

    while true; do
        read -r -p "Tú: " chat_prompt
        if [[ "$chat_prompt" == "exit" || "$chat_prompt" == "quit" ]]; then
            break
        fi
        if [[ -z "$chat_prompt" ]]; then
            continue
        fi

        # Construir el historial para la API en formato de "contents"
        # Incluye el contexto, el historial de chat guardado y el prompt actual
        
        # Historial de .ask_history.json (como en SDK)
        sdk_history_for_api=$(build_history_for_chat_sdk)

        # Prompt actual del usuario
        current_user_part_json=$(jq -n --arg text "$chat_prompt" '{role: "user", parts: [{text: $text}]}')

        # Combinar historial SDK con el prompt actual para `contents`
        # Si hay contexto, se podría añadir como un "system prompt" o parte del primer turno.
        # Por simplicidad, el contexto impreso es informativo. Para incluirlo activamente,
        # necesitaría ser el primer elemento de `contents_for_api_json`.
        
        # Esta es una simplificación. En un chat real, 'contents' se construye
        # con todos los turnos anteriores.
        # El SDK lo maneja. Para bash, lo simulamos:
        # 1. Cargamos el historial guardado
        # 2. Añadimos el nuevo mensaje del usuario
        # 3. Enviamos todo.
        
        # Contenido para enviar a la API:
        # El historial guardado + el nuevo prompt del usuario
        # Si el contexto (general/local) debe ser el primer mensaje:
        # Si context_str no está vacío, y sdk_history_for_api es '[]',
        # podrías añadir: context_part_json=$(jq -n --arg text "$context_str" '{role: "user", parts: [{text: $text}]}')
        # y luego: contents_for_api_json=$(jq -n --argjson ctx "$context_part_json" --argjson hist "$sdk_history_for_api" --argjson curr "$current_user_part_json" '[$ctx] + $hist + [$curr]')
        # Pero esto haría que el contexto se repita si ya está en el historial.

        # Enfoque: tomar el historial del SDK, añadir el prompt actual.
        # contents_for_api_json=$(echo "$sdk_history_for_api" | jq ". + [$current_user_part_json]")
        contents_for_api_json=$(jq -n \
          --argjson sdk_hist "$sdk_history_for_api" \
          --argjson current_user_prompt "$current_user_part_json" \
          --arg context_str "$context_str" \
          '
            if $context_str == "" or $context_str == null then
              $sdk_hist + [$current_user_prompt]
            else
              # Context part, then SDK history, then current user prompt
              [{role: "user", parts: [{text: $context_str}]}] + $sdk_hist + [$current_user_prompt]
            end
          ')
        
        # Construir el cuerpo completo de la solicitud
        request_body=$(jq -n --argjson contents "$contents_for_api_json" '{contents: $contents}')

        echo -n "Gemini: "
        api_response_text=$(call_gemini_api "$MODEL_NAME" "$request_body")

        if [[ $? -eq 0 && -n "$api_response_text" ]]; then
            echo "$api_response_text"
            save_to_history "$chat_prompt" "$api_response_text" "$MODEL_NAME"
        elif [[ -z "$api_response_text" ]]; then
            echo # Nueva línea si no hubo texto
        fi
    done
else
    # --- Modo Prompt ---
    if [[ -z "$USER_PROMPT" ]]; then
        echo "Error: Se requiere un prompt si no se usa --chat." >&2
        usage
    fi

    context_str=$(build_context_string)
    history_str=$(build_history_text_for_prompt)

    # Combinar todo en un solo texto para la API
    # (similar al script Python para modo prompt)
    full_prompt_text=""
    if [[ -n "$context_str" ]]; then
        full_prompt_text+="${context_str}"
    fi
    if [[ -n "$history_str" ]]; then
        full_prompt_text+="[Historial de Conversación Anterior]\n${history_str}\n"
    fi
    full_prompt_text+="[Prompt Actual del Usuario]\n${USER_PROMPT}"

    # Crear el cuerpo JSON para la API
    # La API espera un array "contents", cada elemento con "parts" que es un array de "text"
    request_body=$(jq -n \
        --arg prompt_text "$full_prompt_text" \
        '{contents: [{parts: [{text: $prompt_text}]}]}')

    echo -n "Gemini: "
    api_response_text=$(call_gemini_api "$MODEL_NAME" "$request_body")
    
    if [[ $? -eq 0 && -n "$api_response_text" ]]; then
        echo "$api_response_text"
        save_to_history "$USER_PROMPT" "$api_response_text" "$MODEL_NAME"
    elif [[ -z "$api_response_text" ]]; then
        echo # Nueva línea si no hubo texto de API (ej. bloqueado)
    fi
fi

exit 0