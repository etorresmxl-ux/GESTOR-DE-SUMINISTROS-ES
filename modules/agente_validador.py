from datetime import datetime
import google.generativeai as genai
import pandas as pd
import streamlit as st
import os
import json
import re

def limpiar_fecha(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def limpiar_numero(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str == "" or val_str.lower() in ["none", "null", "nan", "-"]:
        return None
    val_limpio = re.sub(r'[^\d.-]', '', val_str)
    try:
        num = float(val_limpio)
        if pd.isna(num):
            return None
        return num
    except ValueError:
        return None

def normalizar_producto(producto_raw):
    if pd.isna(producto_raw):
        return ""
    p_str = str(producto_raw).strip().lower()
    if 'regular' in p_str or 'magna' in p_str:
        return 'regular'
    elif 'premium' in p_str:
        return 'premium'
    elif 'diesel' in p_str:
        return 'diesel'
    else:
        return p_str

def render(conn):
    st.markdown("### 👁️ Agente IA Validador - Lectura de Inventarios por Imagen")
    st.write("Sube una foto o captura de pantalla de tu reporte de inventarios. El agente extraerá la información para validarla e importarla a la base de datos.")
    st.markdown("---")

    try:
        # 1. Obtener listado oficial de estaciones para validación estricta
        query_est = 'SELECT id_estacion, nombre, plaza FROM estaciones;'
        df_estaciones = pd.read_sql(query_est, conn)
        ids_validos = set(df_estaciones["id_estacion"].astype(str).str.strip())

        # 2. Selector de fecha por si la imagen no la trae explícita
        fecha_default = st.date_input("📅 Fecha predeterminada para el reporte de la imagen:", datetime.now().date())

        # 3. Subir archivo de imagen
        archivo_imagen = st.file_uploader("Sube la imagen del reporte de inventarios:", type=["png", "jpg", "jpeg"], key="up_img_inventario")

        if archivo_imagen is not None:
            st.image(archivo_imagen, caption="Imagen cargada para análisis", use_container_width=True)

            if st.button("🤖 Extraer y Validar Datos con IA", use_container_width=True, key="btn_extraer_ia"):
                with st.spinner("El agente multimodal de Gemini está analizando la imagen..."):
                    try:
                        # Configurar API Key de Gemini
                        api_key = os.environ.get("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY", ""))
                        if not api_key:
                            st.error("⚠️ No se encontró la GOOGLE_API_KEY en los secretos o variables de entorno.")
                            return

                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-pro')

                        bytes_imagen = archivo_imagen.getvalue()

                        prompt = """
                        Analiza esta imagen de inventarios de gasolineras. 
                        Extrae cada fila en formato de arreglo JSON estricto, donde cada objeto tenga exactamente estas llaves:
                        - "id_estacion": el ID de la estación (ej. E01640, E06921).
                        - "regular": volumen numérico de regular (o 0 / null si no aplica).
                        - "premium": volumen numérico de premium (o 0 / null si no aplica).
                        - "diesel": volumen numérico de diesel (o 0 / null si no aplica).
                        
                        Devuelve ÚNICAMENTE el JSON válido, sin texto adicional ni bloques de Markdown si es posible, o limpio.
                        """

                        response = model.generate_content([
                            prompt,
                            {"mime_type": archivo_imagen.type, "data": bytes_imagen}
                        ])

                        # Limpiar la respuesta para asegurar formato JSON
                        texto_resp = response.text.strip()
                        texto_resp = re.sub(r'^```json\s*', '', texto_resp)
                        texto_resp = re.sub(r'^```\s*', '', texto_resp)
                        texto_resp = re.sub(r'\s*```$', '', texto_resp)

                        data_raw = json.loads(texto_resp)

                        # Procesar y aplanar a la estructura de la base de datos (fecha, id_estacion, producto, volumen)
                        filas_procesadas = []
                        for item in data_raw:
                            e_id = str(item.get("id_estacion", "")).strip().upper()
                            estatus_val = "✅ Válido" if e_id in ids_validos else "❌ Estación Inválida"

                            for prod in ["regular", "premium", "diesel"]:
                                val = limpiar_numero(item.get(prod))
                                if val is not None and val >= 0:
                                    filas_procesadas.append({
                                        "fecha": str(fecha_default),
                                        "id_estacion": e_id,
                                        "producto": prod,
                                        "volumen": int(val),
                                        "estatus": estatus_val
                                    })

                        if not filas_procesadas:
                            st.warning("El agente no pudo encontrar registros válidos en la imagen.")
                        else:
                            st.session_state["df_agente_vision"] = pd.DataFrame(filas_procesadas)
                            st.success("¡Información extraída exitosamente por el agente!")

                    except Exception as ai_err:
                        st.error(f"Error al procesar la imagen con IA: {ai_err}")

        # 4. Mostrar tabla editable/validable si ya fue procesada
        if "df_agente_vision" in st.session_state and not st.session_state["df_agente_vision"].empty:
            st.markdown("#### 📋 Datos Extraídos Listos para Validar e Importar")
            
            df_editado = st.data_editor(
                st.session_state["df_agente_vision"],
                column_config={
                    "fecha": st.column_config.TextColumn("Fecha", disabled=True),
                    "id_estacion": st.column_config.TextColumn("ID Estación"),
                    "producto": st.column_config.TextColumn("Producto", disabled=True),
                    "volumen": st.column_config.NumberColumn("Volumen (Lts)", min_value=0, format="%,d", step=100),
                    "estatus": st.column_config.TextColumn("Estatus", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_agente_vision"
            )

            if st.button("🚀 Importar Datos Validados a Base de Datos", use_container_width=True, key="btn_importar_vision"):
                cursor = conn.cursor()
                sql_upsert_inv = """
                    INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, id_estacion, producto) 
                    DO UPDATE SET volumen = EXCLUDED.volumen;
                """
                count = 0
                for _, r in df_editado.iterrows():
                    e_id = str(r["id_estacion"]).strip().upper()
                    if e_id in ids_validos and pd.notna(r["volumen"]):
                        cursor.execute(sql_upsert_inv, (
                            str(r["fecha"]),
                            e_id,
                            str(r["producto"]),
                            float(r["volumen"])
                        ))
                        count += 1

                conn.commit()
                cursor.close()
                st.success(f"¡Se importaron y sincronizaron exitosamente {count} registros en la tabla 'inventarios'!")
                del st.session_state["df_agente_vision"]
                st.rerun()

    except Exception as e:
        st.error(f"Error general en el módulo del agente: {e}")
