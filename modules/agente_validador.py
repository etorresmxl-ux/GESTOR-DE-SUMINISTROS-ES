from datetime import datetime
import google.generativeai as genai
import pandas as pd
import streamlit as st
import os

def render(conn):
    st.markdown("### 👁️ Agente IA Multimodal - Lectura de Inventarios por Imagen")
    st.write("Sube una imagen o captura de pantalla del reporte de inventarios. El agente extraerá la información y la preparará para la base de datos.")
    st.markdown("---")

    # Configurar la API de Gemini (asegúrate de tener tu API Key en los secretos de Streamlit o variables de entorno)
    # st.secrets["GOOGLE_API_KEY"]
    
    archivo_imagen = st.file_uploader("Sube la imagen del reporte:", type=["png", "jpg", "jpeg"], key="img_inventario")

    if archivo_imagen is not None:
        st.image(archivo_imagen, caption="Imagen cargada para análisis", use_container_width=True)

        if st.button("🤖 Extraer Datos con IA", use_container_width=True):
            with st.spinner("El agente está analizando la imagen y extrayendo los inventarios..."):
                try:
                    # Configurar el modelo multimodal de Gemini
                    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY", "")))
                    model = genai.GenerativeModel('gemini-1.5-pro') # O gemini-1.5-flash

                    # Convertir la imagen para la API
                    bytes_imagen = archivo_imagen.getvalue()
                    
                    prompt = """
                    Analiza esta imagen de inventarios de gasolineras. 
                    Extrae la información en una estructura tabular limpia identificando:
                    - Fecha (si aparece en el encabezado, de lo contrario déjala vacía o null)
                    - id_estacion (ej. E01640)
                    - producto (regular, premium, diesel)
                    - volumen (número entero o decimal sin comas)
                    
                    Devuelve el resultado estrictamente en formato JSON o tabla estructurada.
                    """
                    
                    # Llamada multimodal a Gemini
                    # (Nota: Pasando los bytes de la imagen directamente al modelo)
                    response = model.generate_content([
                        prompt,
                        {"mime_type": archivo_imagen.type, "data": bytes_imagen}
                    ])

                    st.success("¡Información extraída con éxito por el agente!")
                    st.write(response.text)
                    
                    # Aquí puedes parsear la respuesta JSON del modelo y cargarla en un st.data_editor 
                    # para que el usuario valide antes de hacer el INSERT en Supabase.

                except Exception as e:
                    st.error(f"Error al procesar la imagen con el agente de IA: {e}")
