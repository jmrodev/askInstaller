    import os                                                            
    import argparse                                                      
    import requests                                                      
    import json                                                          
                                                                         
    # Constantes                                                         
    MAX_HISTORY_TURNS = 5                                                
    GOOGLE_AI_API_URL = "https://generativelanguage.googleapis.          
  com/v1beta/models/gemini-pro:generateContent"                          
    API_KEY_ENV_VAR = "GEMINI_API_KEY"                                   
    DEFAULT_GENERAL_CONTEXT_FILE = ".ask_context.general"  # Relativo al 
  directorio del script                                                  
                                                                         
    class APIError(Exception):                                           
        """Excepción para errores específicos de la API de Google AI.""" 
        pass                                                             
                                                                         
    def load_api_key():                                                  
        """Carga la clave API desde la variable de entorno."""           
        api_key = os.environ.get(API_KEY_ENV_VAR)                        
        if not api_key:                                                  
            raise APIError(f"La variable de entorno {API_KEY_ENV_VAR} no está
  definida.")                                                            
        return api_key                                                   
                                                                         
    def construct_payload(prompt, history, api_key):                     
        """Construye el payload JSON para la API."""                     
                                                                         
        # Configura el historial de conversación                         
        conversation_history = []                                        
        for item in history:                                             
            conversation_history.append({"role": item["role"], "parts": [{"text":
  item["content"]}]})                                                    
                                                                         
        # Construye el payload                                           
        payload = {                                                      
            "contents": conversation_history + [{"role": "user", "parts":
  [{"text": prompt}]}],                                                  
            "generationConfig": {                                        
                "temperature": 0.9,                                      
                "topP": 1,                                               
                "topK": 1,                                               
                "maxOutputTokens": 2048                                  
            },                                                           
            "safetySettings": [                                          
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold":    
  "BLOCK_MEDIUM_AND_ABOVE"},                                             
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold":   
  "BLOCK_MEDIUM_AND_ABOVE"},                                             
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold":
  "BLOCK_MEDIUM_AND_ABOVE"},                                             
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold":
  "BLOCK_MEDIUM_AND_ABOVE"}                                              
            ]                                                            
        }                                                                
                                                                         
        return json.dumps(payload)                                       
                                                                         
    def call_gemini_api(payload, api_key):                               
        """Llama a la API de Gemini y devuelve la respuesta."""          
        params = {"key": api_key}                                        
        headers = {"Content-Type": "application/json"}                   
        try:                                                             
            response = requests.post(GOOGLE_AI_API_URL, headers=headers, 
  params=params, data=payload, timeout=60)                               
            response.raise_for_status()  # Lanza una excepción para códigos de
  error HTTP                                                             
        except requests.exceptions.RequestException as e:                
            raise APIError(f"Error al llamar a la API de Gemini: {e}")   
                                                                         
        return response.json()                                           
                                                                         
    def parse_response(json_response):                                   
        """Parsea la respuesta JSON de la API y devuelve el texto."""    
        try:                                                             
            candidates = json_response.get("candidates")                 
            if not candidates:                                           
                raise APIError("La respuesta de la API no contiene candidatos.")
                                                                         
            content = candidates[0].get("content")                       
            if not content:                                              
                raise APIError("La respuesta de la API no contiene contenido en el
  primer candidato.")                                                    
                                                                         
            parts = content.get("parts")                                 
            if not parts:                                                
                raise APIError("La respuesta de la API no contiene partes en el
  contenido.")                                                           
                                                                         
            text = parts[0].get("text")                                  
            if not text:                                                 
                raise APIError("La respuesta de la API no contiene texto en la
  primera parte.")                                                       
                                                                         
            return text                                                  
        except (KeyError, IndexError) as e:                              
            raise APIError(f"Error al parsear la respuesta de la API: {e}")
                                                                         
    def main():                                                          
        """Función principal."""                                         
        parser = argparse.ArgumentParser(description="Interactúa con la API de
  Gemini.")                                                              
        parser.add_argument("prompt", nargs="+", help="El prompt para enviar a la
  API.")                                                                 
        args = parser.parse_args()                                       
                                                                         
        try:                                                             
            api_key = load_api_key()                                     
            prompt = " ".join(args.prompt)                               
                                                                         
            payload = construct_payload(prompt, [], api_key)             
            json_response = call_gemini_api(payload, api_key)            
            response_text = parse_response(json_response)                
                                                                         
            print(response_text)                                         
                                                                         
        except APIError as e:                                            
            print(f"Error: {e}")                                         
            exit(1)                                                      
        except Exception as e:                                           
            print(f"Error inesperado: {e}")                              
            exit(1)                                                      
                                                                         
    if __name__ == "__main__":                                           
        main()                                                           