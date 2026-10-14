import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📥 Módulo de Importación de Masivos (CSV)")
    st.write("Sube tus archivos CSV para actualizar o registrar masivamente la información en la base de datos.")
    
    tab_inv, tab_ventas = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas"])
    
    # ==========================================
    # PESTAÑA 1: INVENTARIOS
    # ==========================================
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos")
        st.markdown("El archivo CSV debe contener las columnas: `estacion_id`, `fecha`, `turno`, `regular`, `premium`, `diesel`.")
        
        file_inv = st.file_uploader("Selecciona el archivo CSV de Inventarios", type=["csv"], key="up_inv")
        
        if file_inv is not None:
            try:
                df_inv = pd.read_csv(file_inv)
                total_filas = len(df_inv)
                
                # Métrica y resumen rápido
                st.info(f"📊 Archivo cargado correctamente. **Total de registros a procesar: {total_filas}**")
                
                st.write("Vista previa de los datos:")
                st.dataframe(df_inv, use_container_width=True, height=250)
                
                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv"):
                    cursor = conn.cursor()
                    sql_upsert_inv = """
                        INSERT INTO inventarios_historico (estacion_id, fecha, turno, regular, premium, diesel)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (estacion_id, fecha, turno) 
                        DO UPDATE SET regular = EXCLUDED.regular,
                                      premium = EXCLUDED.premium,
                                      diesel = EXCLUDED.diesel;
                    """
                    
                    count = 0
                    for _, row in df_inv.iterrows():
                        cursor.execute(sql_upsert_inv, (
                            str(row['estacion_id']),
                            str(row['fecha']),
                            str(row['turno']),
                            float(row['regular']) if pd.notna(row['regular']) else None,
                            float(row['premium']) if pd.notna(row['premium']) else None,
                            float(row['diesel']) if pd.notna(row['diesel']) else None
                        ))
                        count += 1
                        
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} de {total_filas} registros de inventarios exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de inventarios: {e}")

    # ==========================================
    # PESTAÑA 2: VENTAS
    # ==========================================
    with tab_ventas:
        st.subheader("Carga de Ventas Históricas")
        st.markdown("El archivo CSV debe contener las columnas: `estacion_id`, `fecha`, `regular`, `premium`, `diesel`.")
        
        file_ventas = st.file_uploader("Selecciona el archivo CSV de Ventas", type=["csv"], key="up_ventas")
        
        if file_ventas is not None:
            try:
                df_ventas = pd.read_csv(file_ventas)
                total_filas_v = len(df_ventas)
                
                # Métrica y resumen rápido
                st.info(f"📊 Archivo cargado correctamente. **Total de registros a procesar: {total_filas_v}**")
                
                st.write("Vista previa de los datos:")
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
                        cursor.execute(sql_upsert_ventas, (
                            str(row['estacion_id']),
                            str(row['fecha']),
                            float(row['regular']) if pd.notna(row['regular']) else None,
                            float(row['premium']) if pd.notna(row['premium']) else None,
                            float(row['diesel']) if pd.notna(row['diesel']) else None
                        ))
                        count += 1
                        
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Se procesaron e importaron {count} de {total_filas_v} registros de ventas exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo de ventas: {e}")
