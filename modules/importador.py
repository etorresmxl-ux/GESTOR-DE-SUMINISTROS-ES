import streamlit as st
import pandas as pd
from datetime import date
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
    """Limpia el número permitiendo ceros (útil para cancelaciones en programación) y descartando vacíos."""
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
        return num # El 0.0 pasa perfectamente
    except ValueError:
        return None

def dataframe_a_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()

def render(conn):
    st.markdown("### 📥 Módulo de Importación Masiva (Excel / CSV)")
    st.write("Sube tus archivos de Excel (`.xlsx`) o CSV. Para las **Órdenes de Carga**, el sistema sincronizará y actualizará el programa futuro (desde hoy en adelante) con la nueva información, respetando el pasado histórico.")
    
    tab_inv, tab_ventas, tab_prog = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas", "🚛 Órdenes de Carga (Programa)"])
    
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
                st.dataframe(df_inv, width='stretch', height=250)

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
    # 2. VENTAS HISTÓRICAS
    # ==========================================
    with tab_ventas:
        st.subheader("Carga de Ventas Históricas")
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

                st.info(f"📊 Archivo cargado. Total de registros: {len(df_ventas)}")
                st.dataframe(df_ventas, width='stretch', height=250)

                if st.button("🚀 Procesar e Importar Ventas", key="btn_imp_ventas"):
                    cursor = conn.cursor()
                    sql_upsert_ventas = """
                        INSERT INTO ventas_historico (estacion_id, fecha, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha) 
                        DO UPDATE SET regular = COALESCE(EXCLUDED.regular, ventas_historico.regular),
                                      premium = COALESCE(EXCLUDED.premium, ventas_historico.premium),
                                      diesel = COALESCE(EXCLUDED.diesel, ventas_historico.diesel);
                    """
                    count = 0
                    for _, row in df_ventas.iterrows():
                        if pd.notna(row['fecha']) and str(row['estacion_id']).strip() != "":
                            cursor.execute(sql_upsert_ventas, (
                                str(row['estacion_id']).strip(),
                                str(row['fecha']),
                                float(row['regular']) if 'regular' in df_ventas.columns and pd.notna(row['regular']) else None,
                                float(row['premium']) if 'premium' in df_ventas.columns and pd.notna(row['premium']) else None,
                                float(row['diesel']) if 'diesel' in df_ventas.columns and pd.notna(row['diesel']) else None
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de ventas exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de ventas: {e}")

    # ==========================================
    # 3. ÓRDENES DE CARGA (PROGRAMACIÓN / SINCRONIZACIÓN FUTURA)
    # ==========================================
    with tab_prog:
        st.subheader("Carga Masiva de Órdenes de Carga (Actualización de Programa)")
        st.write("Sube la actualización semanal del programa. **El sistema sincronizará y actualizará el horizonte futuro** (a partir de hoy) con estos nuevos valores, permitiendo reflejar cambios o cancelaciones (ceros), sin modificar el pasado histórico.")
        
        df_plantilla_prog = pd.DataFrame(columns=["id_estacion", "producto", "fecha_programacion", "volumen_programado"])
        st.download_button(
            label="📥 Descargar Plantilla Excel (Órdenes de Carga)",
            data=dataframe_a_excel_bytes(df_plantilla_prog),
            file_name="plantilla_ordenes_carga.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="descargar_plantilla_prog_xlsx"
        )
        st.markdown("---")

        file_prog = st.file_uploader("Selecciona el archivo de Órdenes de Carga:", type=["xlsx", "xls", "csv"], key="up_prog_file")
        
        if file_prog is not None:
            try:
                df_prog = pd.read_csv(file_prog) if file_prog.name.endswith('.csv') else pd.read_excel(file_prog)
                df_prog['fecha_programacion'] = df_prog['fecha_programacion'].apply(limpiar_fecha)
                df_prog['volumen_programado'] = df_prog['volumen_programado'].apply(limpiar_numero_preservando_ceros)

                st.info(f"📊 Archivo cargado y sanitizado. Total de registros en archivo: {len(df_prog)}")
                st.dataframe(df_prog, width='stretch', height=250)

                if st.button("🚀 Sincronizar y Actualizar Programa Futuro", key="btn_imp_prog"):
                    hoy_str = date.today().strftime("%Y-%m-%d")
                    cursor = conn.cursor()
                    
                    # 1. Limpiamos / borramos el programa futuro (>= hoy) que viene en este archivo 
                    # para evitar duplicados y asegurar que la nueva foto del proveedor mande.
                    # Opcionalmente podemos hacer un DELETE por cada estación/producto/fecha futura presente en el Excel:
                    count_inserciones = 0
                    
                    for _, row in df_prog.iterrows():
                        fecha_p = row['fecha_programacion']
                        estacion = str(row['id_estacion']).strip()
                        producto = str(row['producto']).strip()
                        volumen = row['volumen_programado']

                        if pd.notna(fecha_p) and pd.notna(volumen) and estacion != "":
                            # Solo aplicamos la sobre-escritura inteligente si la fecha es de hoy en adelante (futuro)
                            if fecha_p >= hoy_str:
                                # Eliminamos cualquier orden previa duplicada para esa misma estación, producto y fecha futura
                                cursor.execute("""
                                    DELETE FROM programacion_cargas 
                                    WHERE id_estacion = %s AND producto = %s AND fecha_programacion = %s;
                                """, (estacion, producto, fecha_p))
                            
                            # Insertamos la nueva orden actualizada (incluso si el volumen es 0.0 para reflejar cancelación)
                            cursor.execute("""
                                INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado, "user", creado_en)
                                VALUES (%s, %s, %s, %s, 'Importación Masiva', NOW());
                            """, (estacion, producto, fecha_p, volumen))
                            count_inserciones += 1

                    conn.commit()
                    cursor.close()
                    st.success(f"¡Sincronización completada! Se procesaron {count_inserciones} órdenes actualizando el horizonte futuro correctamente.")
            except Exception as e:
                st.error(f"Error al procesar la programación: {e}")
