import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📥 Módulo de Importación de Masivos (CSV)")
    st.write("Sube tus archivos CSV para actualizar o registrar masivamente la información. Los valores que excedan la capacidad máxima permitida de los tanques se marcarán como vacíos para corrección manual.")
    
    tab_inv, tab_ventas, tab_prog = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas", "🚛 Programación de Cargas"])
    
    # 1. INVENTARIOS HISTÓRICOS
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos")
        
        # Plantilla CSV de ejemplo para Inventarios
        df_plantilla_inv = pd.DataFrame(columns=["estacion_id", "fecha", "regular", "premium", "diesel"])
        csv_inv_bytes = df_plantilla_inv.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Plantilla CSV (Inventarios)",
            data=csv_inv_bytes,
            file_name="plantilla_inventarios.csv",
            mime="text/csv",
            key="descargar_plantilla_inv"
        )
        st.markdown("---")

        file_inv = st.file_uploader("Selecciona el archivo CSV de Inventarios", type=["csv"], key="up_inv_sin_turno")
        
        if file_inv is not None:
            try:
                df_inv = pd.read_csv(file_inv)
                total_filas = len(df_inv)
                
                # Obtener las capacidades máximas reales por estación y producto desde estaciones_detalle
                cursor = conn.cursor()
                cursor.execute("SELECT id_estacion, producto, capacidad_maxima FROM estaciones_detalle;")
                
                cap_dict = {}
                for row in cursor.fetchall():
                    est_id = str(row[0])
                    prod = str(row[1]).strip().lower()
                    cap = float(row[2]) if row[2] is not None else 0.0
                    cap_dict[(est_id, prod)] = cap
                cursor.close()
                
                advertencias = []
                for idx, row in df_inv.iterrows():
                    est_id = str(row['estacion_id'])
                    
                    for prod_key, prod_col in [('regular', 'regular'), ('premium', 'premium'), ('diesel', 'diesel')]:
                        if prod_col in df_inv.columns:
                            val = row[prod_col]
                            if pd.notna(val):
                                cap_max = 0.0
                                for (c_est, c_prod), c_val in cap_dict.items():
                                    if c_est == est_id and prod_key in c_prod:
                                        cap_max = c_val
                                        break
                                
                                if cap_max > 0 and val > cap_max:
                                    df_inv.at[idx, prod_col] = None
                                    advertencias.append(
                                        f"⚠️ **Fila {idx + 2} (Estación {est_id})**: El valor de **{prod_key}** ({val:,.0f} L) "
                                        f"supera la capacidad máxima permitida ({cap_max:,.0f} L). Se ha omitido automáticamente."
                                    )
                
                st.info(f"📊 Archivo cargado. Total de registros: {total_filas}")
                
                if advertencias:
                    st.warning("Se detectaron algunos valores que superan la capacidad máxima de almacenamiento:")
                    for adv in advertencias:
                        st.markdown(f"- {adv}")
                
                st.write("Vista previa de los datos listos para importar:")
                st.dataframe(df_inv, width='stretch', height=250)
                
                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv_st"):
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
                        cursor.execute(sql_upsert_inv, (
                            str(row['estacion_id']),
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

    # 2. VENTAS HISTÓRICAS
    with tab_ventas:
        st.subheader("Carga de Ventas Históricas")
        
        # Plantilla CSV de ejemplo para Ventas
        df_plantilla_ventas = pd.DataFrame(columns=["estacion_id", "fecha", "regular", "premium", "diesel"])
        csv_ventas_bytes = df_plantilla_ventas.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Plantilla CSV (Ventas)",
            data=csv_ventas_bytes,
            file_name="plantilla_ventas.csv",
            mime="text/csv",
            key="descargar_plantilla_ventas"
        )
        st.markdown("---")

        file_ventas = st.file_uploader("Selecciona el archivo CSV de Ventas", type=["csv"], key="up_ventas_csv")
        
        if file_ventas is not None:
            try:
                df_ventas = pd.read_csv(file_ventas)
                st.info(f"📊 Archivo cargado. Total de registros: {len(df_ventas)}")
                st.dataframe(df_ventas, width='stretch', height=250)
                
                if st.button("🚀 Procesar e Importar Ventas", key="btn_imp_ventas_csv"):
                    cursor = conn.cursor()
                    sql_upsert_ventas = """
                        INSERT INTO ventas_historicas (estacion_id, fecha, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha) 
                        DO UPDATE SET regular = EXCLUDED.regular,
                                      premium = EXCLUDED.premium,
                                      diesel = EXCLUDED.diesel;
                    """
                    count = 0
                    for _, row in df_ventas.iterrows():
                        cursor.execute(sql_upsert_ventas, (
                            str(row['estacion_id']),
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

    # 3. PROGRAMACIÓN DE CARGAS
    with tab_prog:
        st.subheader("Carga Masiva de Programación de Cargas (Pedidos)")
        
        # Plantilla CSV de ejemplo para Programación
        df_plantilla_prog = pd.DataFrame(columns=["id_estacion", "producto", "fecha_programacion", "volumen_programado", "user"])
        csv_prog_bytes = df_plantilla_prog.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Plantilla CSV (Programación)",
            data=csv_prog_bytes,
            file_name="plantilla_programacion.csv",
            mime="text/csv",
            key="descargar_plantilla_prog"
        )
        st.markdown("---")

        file_prog = st.file_uploader("Selecciona el archivo CSV de Programación", type=["csv"], key="up_prog_csv")
        
        if file_prog is not None:
            try:
                df_prog = pd.read_csv(file_prog)
                st.info(f"📊 Archivo cargado. Total de registros: {len(df_prog)}")
                st.dataframe(df_prog, width='stretch', height=250)
                
                if st.button("🚀 Procesar e Importar Programación", key="btn_imp_prog_csv"):
                    cursor = conn.cursor()
                    sql_insert_prog = """
                        INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado, "user")
                        VALUES (%s, %s, %s, %s, %s);
                    """
                    count = 0
                    for _, row in df_prog.iterrows():
                        cursor.execute(sql_insert_prog, (
                            str(row['id_estacion']),
                            str(row['producto']),
                            str(row['fecha_programacion']),
                            float(row['volumen_programado']) if pd.notna(row['volumen_programado']) else 0.0,
                            str(row['user']) if 'user' in df_prog.columns and pd.notna(row['user']) else 'Sistema'
                        ))
                        count += 1
                        
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} registros de programación exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de programación: {e}")
