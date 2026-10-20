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

def limpiar_numero(val):
    """Limpia el número, elimina caracteres extra y convierte 0 o 0.0 en None (NULL)."""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str == "" or val_str.lower() in ["none", "null", "nan", "-"]:
        return None
    val_limpio = re.sub(r'[^\d.-]', '', val_str)
    try:
        num = float(val_limpio)
        if pd.isna(num) or num == 0.0:
            return None
        return num
    except ValueError:
        return None

def dataframe_a_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()

def render(conn):
    st.markdown("### 📥 Módulo de Importación Masiva (Excel / CSV)")
    st.write("Sube tus archivos de Excel (`.xlsx`) o CSV. El sistema validará los rangos y corregirá automáticamente formatos de fecha y valores numéricos.")
    
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

        file_inv = st.file_uploader("Selecciona el archivo (Excel o CSV) de Inventarios:", type=["xlsx", "xls", "csv"], key="up_inv_file")
        
        if file_inv is not None:
            try:
                if file_inv.name.endswith('.csv'):
                    df_inv = pd.read_csv(file_inv)
                else:
                    df_inv = pd.read_excel(file_inv)
                
                df_inv['fecha'] = df_inv['fecha'].apply(limpiar_fecha)
                for col in ['regular', 'premium', 'diesel']:
                    if col in df_inv.columns:
                        df_inv[col] = df_inv[col].apply(limpiar_numero)

                cursor = conn.cursor()
                cursor.execute("SELECT id_estacion, producto, capacidad_maxima FROM estaciones_detalle;")
                cap_dict = {}
                for row in cursor.fetchall():
                    cap_dict[(str(row[0]), str(row[1]).strip().lower())] = float(row[2]) if row[2] is not None else 0.0
                cursor.close()

                advertencias = []
                for idx, row in df_inv.iterrows():
                    est_id = str(row['estacion_id'])
                    for prod_key in ['regular', 'premium', 'diesel']:
                        if prod_key in df_inv.columns and pd.notna(row[prod_key]):
                            val = row[prod_key]
                            cap_max = 0.0
                            for (c_est, c_prod), c_val in cap_dict.items():
                                if c_est == est_id and prod_key in c_prod:
                                    cap_max = c_val
                                    break
                            if cap_max > 0 and val > cap_max:
                                df_inv.at[idx, prod_key] = None
                                advertencias.append(
                                    f"⚠️ **Fila {idx + 2} (Estación {est_id})**: El valor de **{prod_key}** ({val:,.0f} L) "
                                    f"supera la capacidad máxima ({cap_max:,.0f} L). Se omitió automáticamente."
                                )

                st.info(f"📊 Archivo cargado y sanitizado correctamente. Total de registros: {len(df_inv)}")
                if advertencias:
                    st.warning("Valores omitidos por exceder capacidad:")
                    for adv in advertencias:
                        st.markdown(f"- {adv}")

                st.write("Vista previa de los datos limpios a importar:")
                st.dataframe(df_inv, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv"):
                    cursor = conn.cursor()
                    sql_upsert_inv = """
                        INSERT INTO inventarios_historico (estacion_id, fecha, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha) 
                        DO UPDATE SET regular = EXCLUDED.regular,
                                      premium = EXCLUDED.premium,
                                      diesel = EXCLUDED.diesel;
                    """
                    count = 0
                    for _, row in df_inv.iterrows():
                        if pd.notna(row['fecha']) and str(row['estacion_id']).strip() != "":
                            reg_val = float(row['regular']) if 'regular' in df_inv.columns and pd.notna(row['regular']) else None
                            pre_val = float(row['premium']) if 'premium' in df_inv.columns and pd.notna(row['premium']) else None
                            die_val = float(row['diesel']) if 'diesel' in df_inv.columns and pd.notna(row['diesel']) else None

                            cursor.execute(sql_upsert_inv, (
                                str(row['estacion_id']).strip(),
                                str(row['fecha']),
                                reg_val,
                                pre_val,
                                die_val
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

        file_ventas = st.file_uploader("Selecciona el archivo (Excel o CSV) de Ventas:", type=["xlsx", "xls", "csv"], key="up_ventas_file")
        
        if file_ventas is not None:
            try:
                if file_ventas.name.endswith('.csv'):
                    df_ventas = pd.read_csv(file_ventas)
                else:
                    df_ventas = pd.read_excel(file_ventas)

                df_ventas['fecha'] = df_ventas['fecha'].apply(limpiar_fecha)
                for col in ['regular', 'premium', 'diesel']:
                    if col in df_ventas.columns:
                        df_ventas[col] = df_ventas[col].apply(limpiar_numero)

                # Consultar los promedios de venta ponderados o históricos por estación y producto
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT estacion_id, producto, vdp FROM vdp_ponderado_12w;")
                except Exception:
                    # Alternativa si la estructura difiere o usa id_estacion
                    try:
                        cursor.execute("SELECT id_estacion, producto, vdp FROM vdp_ponderado_12w;")
                    except Exception:
                        cursor.execute("SELECT estacion_id, producto, vdp FROM estaciones_detalle;")
                
                vdp_dict = {}
                for row in cursor.fetchall():
                    est_s = str(row[0]).strip()
                    prod_s = str(row[1]).strip().lower()
                    vdp_val = float(row[2]) if row[2] is not None else 0.0
                    vdp_dict[(est_s, prod_s)] = vdp_val
                cursor.close()

                # Validación del rango +/- 30% respecto al promedio diario de venta (VDP)
                advertencias_ventas = []
                for idx, row in df_ventas.iterrows():
                    est_id = str(row['estacion_id']).strip()
                    for prod_key in ['regular', 'premium', 'diesel']:
                        if prod_key in df_ventas.columns and pd.notna(row[prod_key]):
                            val_venta = float(row[prod_key])
                            
                            # Buscar el VDP correspondiente
                            vdp_promedio = 0.0
                            for (c_est, c_prod), c_val in vdp_dict.items():
                                if c_est == est_id and prod_key in c_prod:
                                    vdp_promedio = c_val
                                    break
                            
                            if vdp_promedio > 0:
                                limite_inferior = vdp_promedio * 0.70
                                limite_superior = vdp_promedio * 1.30
                                
                                if val_venta < limite_inferior or val_venta > limite_superior:
                                    advertencias_ventas.append(
                                        f"⚠️ **Fila {idx + 2} (Estación {est_id})**: La venta de **{prod_key}** ({val_venta:,.0f} L) "
                                        f"se desvía más del 30% de su promedio diario habitual ({vdp_promedio:,.0f} L/día)."
                                    )

                st.info(f"📊 Archivo cargado y sanitizado. Total de registros: {len(df_ventas)}")
                if advertencias_ventas:
                    st.warning("⚠️ Alertas de desviación detectadas (fuera del rango +/- 30% del promedio):")
                    for adv in advertencias_ventas:
                        st.markdown(f"- {adv}")

                st.write("Vista previa de los datos limpios a importar:")
                st.dataframe(df_ventas, use_container_width=True, height=250)

                if st.button("🚀 Procesar e Importar Ventas", key="btn_imp_ventas"):
                    cursor = conn.cursor()
                    sql_upsert_ventas = """
                        INSERT INTO ventas_historico (estacion_id, fecha, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha) 
                        DO UPDATE SET regular = EXCLUDED.regular,
                                      premium = EXCLUDED.premium,
                                      diesel = EXCLUDED.diesel;
                    """
                    count = 0
                    for _, row in df_ventas.iterrows():
                        if pd.notna(row['fecha']) and str(row['estacion_id']).strip() != "":
                            reg_val = float(row['regular']) if 'regular' in df_ventas.columns and pd.notna(row['regular']) else None
                            pre_val = float(row['premium']) if 'premium' in df_ventas.columns and pd.notna(row['premium']) else None
                            die_val = float(row['diesel']) if 'diesel' in df_ventas.columns and pd.notna(row['diesel']) else None

                            cursor.execute(sql_upsert_ventas, (
                                str(row['estacion_id']).strip(),
                                str(row['fecha']),
                                reg_val,
                                pre_val,
                                die_val
                            ))
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de ventas exitosamente!")
            except Exception as e:
                st.error(f5"Error al procesar el archivo de ventas: {e}")
