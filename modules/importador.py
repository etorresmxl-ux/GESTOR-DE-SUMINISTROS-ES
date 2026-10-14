import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📥 Módulo de Importación de Masivos (CSV)")
    st.write("Sube tus archivos CSV para actualizar o registrar masivamente la información. Los valores que excedan la capacidad máxima permitida de los tanques se marcarán como vacíos para corrección manual.")
    
    tab_inv, tab_ventas = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas"])
    
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos")
        file_inv = st.file_uploader("Selecciona el archivo CSV de Inventarios", type=["csv"], key="up_inv_dinamico")
        
        if file_inv is not None:
            try:
                df_inv = pd.read_csv(file_inv)
                total_filas = len(df_inv)
                
                # 1. Obtener las capacidades máximas reales por estación y producto desde estaciones_detalle
                cursor = conn.cursor()
                cursor.execute("SELECT id_estacion, producto, capacidad_maxima FROM estaciones_detalle;")
                
                # Creamos un diccionario estructurado como {(estacion_id, producto_lower): capacidad_maxima}
                cap_dict = {}
                for row in cursor.fetchall():
                    est_id = str(row[0])
                    prod = str(row[1]).strip().lower()
                    cap = float(row[2]) if row[2] is not None else 0.0
                    cap_dict[(est_id, prod)] = cap
                cursor.close()
                
                # 2. Validación basada estrictamente en la capacidad máxima de cada producto
                advertencias = []
                
                for idx, row in df_inv.iterrows():
                    est_id = str(row['estacion_id'])
                    
                    for prod_key, prod_col in [('regular', 'regular'), ('premium', 'premium'), ('diesel', 'diesel')]:
                        val = row[prod_col]
                        if pd.notna(val):
                            # Buscar la capacidad máxima correspondiente en el diccionario (manejando variaciones comunes de nombres)
                            cap_max = 0.0
                            for (c_est, c_prod), c_val in cap_dict.items():
                                if c_est == est_id and prod_key in c_prod:
                                    cap_max = c_val
                                    break
                            
                            # Validar si el inventario supera la capacidad máxima de la estación
                            if cap_max > 0 and val > cap_max:
                                df_inv.at[idx, prod_col] = None
                                advertencias.append(
                                    f"⚠️ **Fila {idx + 2} (Estación {est_id})**: El valor de **{prod_key}** ({val:,.0f} L) "
                                    f"supera la capacidad máxima permitida ({cap_max:,.0f} L). Se ha omitido automáticamente. "
                                    f"Por favor, corrígelo manualmente."
                                )
                
                st.info(f"📊 Archivo cargado. Total de registros: {total_filas}")
                
                # Mostrar avisos específicos si hubo anomalías detectadas
                if advertencias:
                    st.warning("Se detectaron algunos valores que superan la capacidad máxima de almacenamiento y fueron aislados:")
                    for adv in advertencias:
                        st.markdown(f"- {adv}")
                
                st.write("Vista previa de los datos listos para importar (con valores fuera de capacidad limpiados):")
                st.dataframe(df_inv, width='stretch', height=250)
                
                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv_dinamico", width='stretch'):
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
                    st.success(f"¡Se procesaron e importaron {count} registros exitosamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")
