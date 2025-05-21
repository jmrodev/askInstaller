    #!/bin/bash                                                          
                                                                         
    # Dependencias                                                       
    if ! command -v pactl &> /dev/null; then                             
      echo "Error: pactl no está instalado.  Es necesario para controlar el
  volumen." >&2                                                          
      exit 1                                                             
    fi                                                                   
                                                                         
    if ! command -v volnoti &> /dev/null; then                           
      echo "Error: volnoti no está instalado.  Es necesario para mostrar 
  notificaciones de volumen." >&2                                        
      exit 1                                                             
    fi                                                                   
                                                                         
    if ! command -v notify-send &> /dev/null; then                       
      echo "Error: notify-send no está instalado. Es necesario para mostrar
  notificaciones." >&2                                                   
      exit 1                                                             
    fi                                                                   
                                                                         
    # Configuración                                                      
    VOLUME_INCREMENT=10                                                  
    DEFAULT_SINK=$(pactl get-default-sink) #  El sink de audio predeterminado.
    DEFAULT_SOURCE=$(pactl get-default-source) # La fuente de audio predeterminada.
                                                                         
    # Obtener el volumen actual                                          
    get_volume() {                                                       
      local sink="$1"                                                    
      pactl get-sink-volume "$sink" | grep -oP '\d+%' | tr -d '%'        
    }                                                                    
                                                                         
    # Establecer el volumen                                              
    set_volume() {                                                       
      local sink="$1"                                                    
      local volume="$2"                                                  
                                                                         
      pactl set-sink-volume "$sink" "$volume%"                           
      if [ $? -ne 0 ]; then                                              
        echo "Error: Falló al establecer el volumen a '$volume%'" >&2    
        exit 1                                                           
      fi                                                                 
    }                                                                    
                                                                         
    # Mostrar notificación                                               
    show_notification() {                                                
      local volume="$1"                                                  
                                                                         
      volnoti -m "$volume"                                               
      notify-send -i audio-volume-high "Volumen" "$volume%"              
    }                                                                    
                                                                         
    # Subir volumen                                                      
    volume_up() {                                                        
      local sink="$DEFAULT_SINK"                                         
                                                                         
      local current_volume=$(get_volume "$sink")                         
      local new_volume=$((current_volume + VOLUME_INCREMENT))            
                                                                         
      if [ "$new_volume" -gt 100 ]; then                                 
        new_volume=100                                                   
      fi                                                                 
                                                                         
      set_volume "$sink" "$new_volume"                                   
      show_notification "$new_volume"                                    
    }                                                                    
                                                                         
    # Bajar volumen                                                      
    volume_down() {                                                      
      local sink="$DEFAULT_SINK"                                         
                                                                         
      local current_volume=$(get_volume "$sink")                         
      local new_volume=$((current_volume - VOLUME_INCREMENT))            
                                                                         
      if [ "$new_volume" -lt 0 ]; then                                   
        new_volume=0                                                     
      fi                                                                 
                                                                         
      set_volume "$sink" "$new_volume"                                   
      show_notification "$new_volume"                                    
    }                                                                    
                                                                         
    # Silenciar/Activar volumen                                          
    toggle_mute() {                                                      
        pactl set-sink-mute @DEFAULT_SINK@ toggle                        
    }                                                                    
                                                                         
    # Manejar argumentos (si es necesario)                               
    # ...                                                                
                                                                         
    # Ejecutar acción                                                    
    case "$1" in                                                         
      up)                                                                
        volume_up                                                        
        ;;                                                               
      down)                                                              
        volume_down                                                      
        ;;                                                               
      toggle)                                                            
        toggle_mute                                                      
        ;;                                                               
      *)                                                                 
        echo "Uso: $0 [up|down|toggle]"                                  
        exit 1                                                           
        ;;                                                               
    esac                                                                 
                                                                         
    exit 0                                         