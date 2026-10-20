import streamlit as st
import pandas as pd
import io
import re
import numpy as np

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

def limpiar_numero_preservando_ceros(val):
    """Limpia el número permitiendo ceros y descartando vacíos."""
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

def dataframe_a_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()

def evaluar_y_gestionar_venta(conn, estacion_id, fecha_str, producto, volumen, metodo_carga):
    """
    Evalúa una venta usando Z-Score basado en las columnas horizontales (regular, premium, diesel)
    de la misma estación y el mismo día de la semana (últimas 12 semanas).
    """
    cursor = conn.cursor()
    try:
        # 1. Consultar el histórico usando la columna específica del producto
        query_stats = f"""
            SELECT {producto} AS volumen 
            FROM ventas_historico
            WHERE estacion_id = %s
              AND EXTRACT(DOW FROM fecha) = EXTRACT(DOW FROM TIMESTAMP %s)
              AND fecha >= CURRENT_DATE - INTERVAL '12 weeks'
              AND ignorar_en_promedio = FALSE;
        """
        df_hist = pd.read_sql(query_stats, conn, params=(estacion_id, fecha_str))
        
        # Si no hay suficiente historia (< 3 registros), dejamos pasar el registro por seguridad
        if len(df_hist) < 3 or df_hist['volumen'].dropna().empty:
            _insertar_venta_oficial(cursor, estacion_id, fecha_str, producto, volumen)
            return "APROBADO_SIN_HISTORIA"

        volúmenes = df_hist['volumen'].dropna().astype(float).values
        if len(volúmenes) < 3:
            _insertar_venta_oficial(cursor, estacion_id, fecha_str, producto, volumen)
            return "APROBADO_SIN_HISTORIA"

        media = np.mean(volúmenes)
        desv_est = np.std(volúmenes, ddof=1) # Desviación estándar muestral

        # 2. Calcular Z-Score
        z_score = float(abs(volumen - media) / desv_est) if desv_est > 0 else 0.0
        UMBRAL_Z = 2.5 # Ocurre en menos del 1% de los casos por azar

        if z_score > UBRAL_Z:
            # ¡Anomalía detectada! Mandar a Cuarentena (ventas_anomalias)
            _enviar_a_cuarentena(cursor, estacion_id, fecha_str, producto, volumen, media, desv_est, z_score, metodo_carga)
            return "ANOMALIA"
        else:
            # Venta normal, va directo al histórico oficial
            _insertar_venta_oficial(cursor, estacion_id, fecha_str, producto, volumen)
            return "NORMAL"

    except Exception as e:
        print(f"Error al evaluar anomalía para {estacion_id} - {producto}: {e}")
        return "ERROR"

def _insertar_venta_oficial(cursor, estacion_id, fecha_str, producto, volumen):
    prod_col = producto.lower().strip()
    if prod_col not in ['regular', 'premium', 'diesel']:
        return

    sql_upsert = f"""
        INSERT INTO ventas_historico (estacion_id, fecha, {prod_col}, ignorar_en_promedio)
        VALUES (%s, %s, %s, FALSE)
        ON CONFLICT (estacion_id, fecha) 
        DO UPDATE SET 
            {prod_col} = COALESCE(EXCLUDED.{prod_col}, ventas_historico.{prod_col});
    """
    cursor.execute(sql_upsert, (estacion_id, fecha_str, volumen))

def _enviar_a_cuarentena(cursor, estacion_id, fecha_str, producto, volumen, media, desv_est, z_score, metodo_carga):
    sql_cuarentena = """
        INSERT INTO ventas_anomalias 
        (estacion_id, fecha, producto, volumen_capturado, media_historica, desviacion_estandar, z_score, metodo_carga, estatus)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE');
    """
    cursor.execute(sql_cuarentena, (estacion_id, fecha_str, producto, volumen, media, desv_est, z_score, metodo_carga))

def render(conn):
    st.markdown("### 📥 Módulo de Importación Masiva (Excel / CSV)")
    st.write("Sube tus archivos de Excel (`.xlsx`) o CSV. El sistema validará automáticamente las anomalías estadísticas mediante Z-Score.")
    
    tab_inv, tab_ventas = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas"])
    
    # ==========================================
    # 1. INVENTARIOS HISTÓRICOS
    # ==========================================
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos")
        df_plantilla_inv = pd.DataFrame(columns=["estacion_id", "fecha", "regular", "premium", "diesel"])
        st.download_button(
            label="📥 Descargar Plantilla Excel (Inventarios)",
            data=dataframe_a_excel_bytes(df_plantilla_inv),
            file_name="plantilla_inventarios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="descargar_plantilla_inv_xlsx"
        )
        st.markdown("---")
        file_inv = st.file_uploader("Selecciona el archivo de Inventarios:", type=["xlsx", "xls", "csv"], key="up_inv_file")
        
        if file_inv is not None:
            try:
                df_inv = pd.read_csv(file_inv) if file_inv.name.endswith('.csv') else pd.read_excel(file_inv)
                df_inv['fecha'] = df_inv['fecha'].apply(limpiar_fecha)
                for col in ['regular', 'premium', 'diesel']:
                    if col in df_inv.columns:
                        df_inv[col] = df_inv[col].apply(limpiar_numero_preservando_ceros)

                st.info(f"📊 Archivo cargado. Total de registros: {len(df_inv)}")
                st.dataframe(df_inv, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv"):
                    cursor = conn.cursor()
                    sql_upsert_inv = """
                        INSERT INTO inventarios_historico (estacion_id, fecha, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha) 
                        DO UPDATE SET regular = COALESCE(EXCLUDED.regular, inventarios_historico.regular),
                                      premium = COALESCE(EXCLUDED.premium, inventarios_historico.premium),
                                      diesel = COALESCE(EXCLUDED.diesel, inventarios_historico.diesel);
                    """
                    count = 0
                    for _, row in df_inv.iterrows():
                        if pd.notna(row['fecha']) and str(row['estacion_id']).strip() != "":
                            cursor.execute(sql_upsert_inv, (
                                str(row['estacion_id']).strip(),
                                str(row['fecha']),
                                float(row['regular']) if 'regular' in df_inv.columns and pd.notna(row['regular']) else None,
                                float(row['premium']) if 'premium' in df_inv.columns and pd.notna(row['premium']) else None,
                                float(row['diesel']) if 'diesel' in df_inv.columns and pd.notna(row['diesel']) else None
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de inventarios exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

    # ==========================================
    # 2. VENTAS HISTÓRICAS (Con Motor Z-Score y Cuarentena)
    # ==========================================
    with tab_ventas:
        st.subheader("Carga de Ventas Históricas (Auditoría Inteligente)")
        df_plantilla_ventas = pd.DataFrame(columns=["estacion_id", "fecha", "regular", "premium", "diesel"])
        st.download_button(
            label="📥 Descargar Plantilla Excel (Ventas)",
            data=dataframe_a_excel_bytes(df_plantilla_ventas),
            file_name="plantilla_ventas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="descargar_plantilla_ventas_xlsx"
        )
        st.markdown("---")
        file_ventas = st.file_uploader("Selecciona el archivo de Ventas:", type=["xlsx", "xls", "csv"], key="up_ventas_file")
        
        if file_ventas is not None:
            try:
                df_ventas = pd.read_csv(file_ventas) if file_ventas.name.endswith('.csv') else pd.read_excel(file_ventas)
                df_ventas['fecha'] = df_ventas['fecha'].apply(limpiar_fecha)
                for col in ['regular', 'premium', 'diesel']:
                    if col in df_ventas.columns:
                        df_ventas[col] = df_ventas[col].apply(limpiar_numero_preservando_ceros)

                st.info(f"📊 Archivo cargado y sanitizado. Total de registros: {len(df_ventas)}")
                st.dataframe(df_ventas, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Ventas con Validación Z-Score", key="btn_imp_ventas"):
                    cursor = conn.cursor()
                    normales_count = 0
                    anomalias_count = 0
                    
                    for _, row in df_ventas.iterrows():
                        fecha_v = row['fecha']
                        est_id = str(row['estacion_id']).strip()

                        if pd.notna(fecha_v) and est_id != "":
                            for prod in ['regular', 'premium', 'diesel']:
                                if prod in df_ventas.columns and pd.notna(row[prod]):
                                    vol = float(row[prod])
                                    
                                    # Evaluamos cada producto de forma independiente con Z-Score
                                    resultado = evaluar_y_gestionar_venta(
                                        conn, est_id, fecha_v, prod, vol, "Importador Masivo"
                                    )
                                    
                                    if resultado == "ANOMALIA":
                                        anomalias_count += 1
                                    else:
                                        normales_count += 1

                    conn.commit()
                    cursor.close()
                    
                    st.success(f"¡Proceso finalizado! Registros normales importados: {normales_count}.")
                    if anomalias_count > 0:
                        st.warning(f"⚠️ Se detectaron y enviaron **{anomalias_count} registros a Cuarentena (ventas_anomalias)** por superar el umbral estadístico de desviación.")
                    else:
                        st.info("✨ No se detectaron anomalías estadísticas en este lote.")
            except Exception as e:
                st.error(f"Error al procesar el archivo de ventas: {e}")
