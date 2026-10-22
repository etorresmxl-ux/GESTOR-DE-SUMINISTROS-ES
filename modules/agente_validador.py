from datetime import datetime
import pandas as pd
import streamlit as st
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
    st.markdown("### 🤖 Agente IA Validador de Inventarios")
    st.write("Valida, clasifica y limpia la información de inventarios proveniente de texto o reportes antes de importarla a la base de datos.")
    st.markdown("---")

    try:
        # 1. Obtener listado oficial de estaciones desde Supabase para validación estricta
        query_est = 'SELECT id_estacion, nombre, plaza FROM estaciones;'
        df_estaciones = pd.read_sql(query_est, conn)
        ids_validos = set(df_estaciones["id_estacion"].astype(str).str.strip())

        # 2. Área de entrada de datos crudos (Texto / Correo / Reporte)
        st.markdown("#### 📥 Entrada de Datos Crudos")
        texto_entrada = st.text_area(
            "Pega aquí la información del reporte (texto, correo o mensaje):",
            placeholder="Ejemplo:\nFecha: 2026-10-21\nEstación: E01640\nRegular: 46093\nPremium: 20041\nDiesel: 21699",
            height=180
        )

        if st.button("🔍 Analizar y Validar con el Agente", use_container_width=True):
            if not texto_entrada.strip():
                st.warning("Por favor, ingresa texto para que el agente pueda procesarlo.")
                return

            lineas = texto_entrada.split("\n")
            fecha_detectada = None
            estacion_detectada = None
            vol_regular = None
            vol_premium = None
            vol_diesel = None

            # Heurísticas de extracción inteligente del agente
            for linea in lineas:
                l_lower = linea.lower()
                if "fecha" in l_lower:
                    match_f = re.search(r'\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}', linea)
                    if match_f:
                        fecha_detectada = limpiar_fecha(match_f.group(0))
                if "estacion" in l_lower or "id" in l_lower or "e" in l_lower:
                    match_e = re.search(r'e?\d+', linea, re.IGNORECASE)
                    if match_e:
                        est_candidate = match_e.group(0).upper()
                        if est_candidate in ids_validos:
                            estacion_detectada = est_candidate

                if "regular" in l_lower or "magna" in l_lower:
                    vol_regular = limpiar_numero(linea)
                elif "premium" in l_lower:
                    vol_premium = limpiar_numero(linea)
                elif "diesel" in l_lower:
                    vol_diesel = limpiar_numero(linea)

            # Construir filas validadas
            filas_procesadas = []
            if estacion_detectada and fecha_detectada:
                productos_encontrados = [
                    ("regular", vol_regular),
                    ("premium", vol_premium),
                    ("diesel", vol_diesel)
                ]
                for prod, vol in productos_encontrados:
                    if vol is not None:
                        filas_procesadas.append({
                            "fecha": fecha_detectada,
                            "id_estacion": estacion_detectada,
                            "producto": prod,
                            "volumen": int(vol),
                            "estatus": "✅ Válido" if estacion_detectada in ids_validos else "❌ Estación Inválida"
                        })

            if not filas_procesadas:
                st.error("El agente no pudo estructurar la información clave (fecha, id_estacion o volumen). Verifica el formato del texto ingresado.")
            else:
                df_resultado = pd.DataFrame(filas_procesadas)
                st.success("¡Información analizada, clasificada y validada exitosamente por el agente!")
                st.dataframe(df_resultado, use_container_width=True)

                # Botón de importación a Supabase
                if st.button("🚀 Importar a la Base de Datos (Inventarios)", use_container_width=True, key="btn_importar_agente"):
                    cursor = conn.cursor()
                    sql_upsert = """
                        INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (fecha, id_estacion, producto) 
                        DO UPDATE SET volumen = EXCLUDED.volumen;
                    """
                    count = 0
                    for _, r in df_resultado.iterrows():
                        if r["estatus"] == "✅ Válido":
                            cursor.execute(sql_upsert, (
                                str(r["fecha"]),
                                str(r["id_estacion"]),
                                str(r["producto"]),
                                float(r["volumen"])
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡{count} registros validados fueron importados y sincronizados exitosamente en la tabla 'inventarios'!")
                    st.rerun()

    except Exception as e:
        st.error(f"Error en el agente validador: {e}")
