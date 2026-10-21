import streamlit as st
import pandas as pd
import io
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

def normalizar_producto(producto_raw):
    """Estandariza los nombres de productos estrictamente en minúsculas para consistencia con el dashboard."""
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

def dataframe_a_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()

def render(conn):
    st.markdown("### 📥 Módulo de Importación Masiva (Excel / CSV)")
    st.write("Sube tus archivos de Excel (.xlsx) o CSV apegados a la estructura normalizada (`fecha`, `id_estacion`, `producto`, `volumen`).")
    
    tab_inv, tab_ventas = st.tabs(["📦 Inventarios", "📊 Ventas"])

    # ==========================================
    # 1. INVENTARIOS
    # ==========================================
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos y Actuales")
        df_plantilla_inv = pd.DataFrame(columns=["fecha", "id_estacion", "producto", "volumen"])
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
                
                cols_requeridas = ['fecha', 'id_estacion', 'producto', 'volumen']
                if not all(col in df_inv.columns for col in cols_requeridas):
                    st.error(f"El archivo debe contener las columnas exactas: {cols_requeridas}")
                    return

                df_inv['fecha'] = df_inv['fecha'].apply(limpiar_fecha)
                df_inv['id_estacion'] = df_inv['id_estacion'].astype(str).str.strip()
                df_inv['producto'] = df_inv['producto'].apply(normalizar_producto)
                df_inv['volumen'] = df_inv['volumen'].apply(limpiar_numero_preservando_ceros)

                # Sumar volúmenes automáticamente si existen múltiples registros (ej. tanques múltiples)
                df_inv = df_inv.groupby(['fecha', 'id_estacion', 'producto'], as_index=False)['volumen'].sum()

                st.info(f"📊 Archivo cargado y sanitizado. Total de registros consolidados: {len(df_inv)}")
                st.dataframe(df_inv, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv"):
                    cursor = conn.cursor()
                    sql_upsert_inv = """
                        INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (fecha, id_estacion, producto) 
                        DO UPDATE SET volumen = EXCLUDED.volumen;
                    """
                    count = 0
                    for _, row in df_inv.iterrows():
                        if pd.notna(row['fecha']) and row['id_estacion'] != "":
                            vol_val = float(row['volumen']) if pd.notna(row['volumen']) else None
                            cursor.execute(sql_upsert_inv, (
                                str(row['fecha']),
                                str(row['id_estacion']),
                                str(row['producto']),
                                vol_val
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de inventarios exitosamente en la tabla 'inventarios'!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de inventarios: {e}")

    # ==========================================
    # 2. VENTAS
    # ==========================================
    with tab_ventas:
        st.subheader("Carga de Ventas Históricas")
        df_plantilla_ventas = pd.DataFrame(columns=["fecha", "id_estacion", "producto", "volumen"])
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
                
                cols_requeridas = ['fecha', 'id_estacion', 'producto', 'volumen']
                if not all(col in df_ventas.columns for col in cols_requeridas):
                    st.error(f"El archivo debe contener las columnas exactas: {cols_requeridas}")
                    return

                df_ventas['fecha'] = df_ventas['fecha'].apply(limpiar_fecha)
                df_ventas['id_estacion'] = df_ventas['id_estacion'].astype(str).str.strip()
                df_ventas['producto'] = df_ventas['producto'].apply(normalizar_producto)
                df_ventas['volumen'] = df_ventas['volumen'].apply(limpiar_numero_preservando_ceros)

                # Sumar volúmenes automáticamente si existen múltiples registros
                df_ventas = df_ventas.groupby(['fecha', 'id_estacion', 'producto'], as_index=False)['volumen'].sum()

                st.info(f"📊 Archivo cargado y sanitizado. Total de registros consolidados: {len(df_ventas)}")
                st.dataframe(df_ventas, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Ventas", key="btn_imp_ventas"):
                    cursor = conn.cursor()
                    sql_upsert_ventas = """
                        INSERT INTO ventas (fecha, id_estacion, producto, volumen)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (fecha, id_estacion, producto) 
                        DO UPDATE SET volumen = EXCLUDED.volumen;
                    """
                    count = 0
                    for _, row in df_ventas.iterrows():
                        if pd.notna(row['fecha']) and row['id_estacion'] != "":
                            vol_val = float(row['volumen']) if pd.notna(row['volumen']) else None
                            cursor.execute(sql_upsert_ventas, (
                                str(row['fecha']),
                                str(row['id_estacion']),
                                str(row['producto']),
                                vol_val
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de ventas exitosamente en la tabla 'ventas'!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de ventas: {e}")
