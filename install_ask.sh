  #!/bin/bash                                                          
                                                                         
    # Directorios de instalación                                         
    USER_EXECUTABLE_DIR="/home/jmro/.local/bin"  # Usar el directorio    
  proporcionado                                                          
    APP_INSTALL_DIR="$USER_EXECUTABLE_DIR/ask"  # Subdirectorio para la app
    SCRIPT_NAME="ask"                                                    
                                                                         
    # Comprobar si los directorios existen                               
    if [ ! -d "$USER_EXECUTABLE_DIR" ]; then                             
      mkdir -p "$USER_EXECUTABLE_DIR" || { echo "Error al crear          
  '$USER_EXECUTABLE_DIR': $? Abortando." >&2; exit 1; }                  
    fi                                                                   
                                                                         
    if [ ! -d "$APP_INSTALL_DIR" ]; then                                 
      mkdir -p "$APP_INSTALL_DIR" || { echo "Error al crear '$APP_INSTALL_DIR': $?
  Abortando." >&2; exit 1; }                                             
    fi                                                                   
                                                                         
    # Comprobar permisos de escritura                                    
    if [ ! -w "$USER_EXECUTABLE_DIR" ]; then                             
      echo "Error: No tienes permisos de escritura en '$USER_EXECUTABLE_DIR'.
  Abortando." >&2                                                        
      exit 1                                                             
    fi                                                                   
                                                                         
    if [ ! -w "$APP_INSTALL_DIR" ]; then                                 
      echo "Error: No tienes permisos de escritura en '$APP_INSTALL_DIR'.
  Abortando." >&2                                                        
      exit 1                                                             
    fi                                                                   
                                                                         
    # Archivos a copiar                                                  
    FILES=(                                                              
      "ask"                                                              
      "ask.1"                                                            
      "ask_gemini.py"                                                    
      ".ask_context.general.example"                                     
    )                                                                    
                                                                         
    # Comprobar que todos los archivos existen antes de continuar        
    for file in "${FILES[@]}"; do                                        
      if [ ! -f "$file" ]; then                                          
        echo "Error: El archivo '$file' no existe. Asegúrate de que todos los
  archivos necesarios están en el mismo directorio que el script de instalación.
  Abortando." >&2                                                        
        exit 1                                                           
      fi                                                                 
    done                                                                 
                                                                         
    # Copiar archivos                                                    
    echo "Instalando $SCRIPT_NAME..."                                    
                                                                         
    for file in "${FILES[@]}"; do                                        
      cp "$file" "$APP_INSTALL_DIR/" || { echo "Error al copiar '$file' a
  '$APP_INSTALL_DIR/': $? Abortando." >&2; exit 1; }                     
      echo "Copiado '$file' a '$APP_INSTALL_DIR/'"                       
    done                                                                 
                                                                         
    # Crear enlace simbólico                                             
    ln -s "$APP_INSTALL_DIR/ask" "$USER_EXECUTABLE_DIR/ask" || { echo "Error al
  crear el enlace simbólico en '$USER_EXECUTABLE_DIR/ask': $? Abortando." >&2;
  exit 1; }                                                              
    echo "Enlace simbólico creado en '$USER_EXECUTABLE_DIR/ask'"         
                                                                         
    # Reemplazar marcadores en el script 'ask'                           
    sed -i "s|# ESTA LÍNEA SERÁ REEMPLAZADA POR EL INSTALADOR.*|         
  APP_INSTALL_DIR=\"$APP_INSTALL_DIR\"|g" "$APP_INSTALL_DIR/ask"         
    sed -i "s|# ESTA LÍNEA SERÁ REEMPLAZADA POR EL INSTALADOR.*|         
  USER_EXECUTABLE_DIR=\"$USER_EXECUTABLE_DIR\"|g" "$APP_INSTALL_DIR/ask" 
    sed -i "s|# ESTA LÍNEA SERÁ REEMPLAZADA POR EL INSTALADOR.*|         
  PYTHON_CMD=\"$(command -v python3)\"|g" "$APP_INSTALL_DIR/ask"         
                                                                         
    # Añadir el directorio al PATH                                       
    add_to_path() {                                                      
      local dir="$1"                                                     
      local config_file                                                  
      local shell=$(basename "$SHELL")                                   
                                                                         
      case "$shell" in                                                   
        bash)                                                            
          config_file="$HOME/.bashrc"                                    
          ;;                                                             
        zsh)                                                             
          config_file="$HOME/.zshrc"                                     
          ;;                                                             
        *)                                                               
          echo "Shell no soportado. Por favor, añade '$dir' a tu PATH manualmente.
  "                                                                      
          return                                                         
          ;;                                                             
      esac                                                               
                                                                         
      # Comprobar si el directorio ya está en el PATH                    
      if grep -q "export PATH=\"\$PATH:$dir\"" "$config_file"; then      
        echo "'$dir' ya está en el PATH en '$config_file'."              
        return                                                           
      fi                                                                 
                                                                         
      # Añadir el directorio al PATH                                     
      echo "export PATH=\"\$PATH:$dir\"" >> "$config_file"               
      echo "Añadido '$dir' al PATH en '$config_file'.  Por favor, reinicia tu
  terminal o ejecuta 'source $config_file' para aplicar los cambios."    
    }                                                                    
                                                                         
    add_to_path "$USER_EXECUTABLE_DIR"                                   
                                                                         
    echo "Instalación completada."  