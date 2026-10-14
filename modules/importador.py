import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📥 Módulo de Importación de Masivos (CSV)")
    st.write("Sube tus archivos CSV para actualizar o registrar masivamente la información. Los valores que excedan los límites lógicos se marcarán como vacíos para corrección manual.")
    
    tab_inv, tab_ventas = st.tabs(["📦 Inventarios Históricos", "📊 Ventas Históricas"])
    
    with tab_inv:
        st.subheader("Carga de Inventarios Históricos")
        file_inv = st.file_uploader("Selecciona el archivo CSV de Inventarios", type=["csv"], key="up_inv_dinamico")
        
        if file_inv is not None:
            try:
                df_inv = pd.read_csv(file_inv)
                total_filas = len(df_inv)
                
                # 1. Obtener los VDPs ponderados actuales desde la base de datos para la validación dinámica
                cursor = conn.cursor()
                cursor.execute("SELECT estacion_id, vdp_regular, vdp_premium, vdp_diesel FROM vdp_ponderado_12w;")
                vdp_dict = {row[0]: {'regular': row[1] or 0, 'premium': row[2] or 0, 'diesel': row[3] or 0} for row in cursor.fetchall()}
                cursor.close()
                
                # 2. Validación y limpieza selectiva (Celda por Celda)
                MARGEN_TOLERANCIA = 1.30  # 30% por encima del VDP ponderado
                advertencias = []
                
                for idx, row in df_inv.iterrows():
                    est_id = str(row['estacion_id'])
                    if est_id in vdp_dict:
                        vdps = vdp_dict[est_id]
                        
                        for prod in ['regular', 'premium', 'diesel']:
                            val = row[prod]
                            if pd.notna(val) and vdps[prod] > 0:
                                limite = vdps[prod] * MARGEN_TOLERANCIA
                                if val > limite:
                                    # En lugar de rechazar, anulamos solo este valor específico en el DataFrame
                                    df_inv.at[idx, prod] = None
                                    advertencias.append(
                                        f"⚠️ **Fila {idx + 2} (Estación {est_id})**: El valor de **{prod}** ({val:,.0f} L) "
                                        f"supera el umbral esperado ({limite:,.0f} L). Se ha omitido automáticamente para evitar errores. "
                                        f"Por favor, ingrésalo o corrígelo manualmente."
                                    )
                
                st.info(f"📊 Archivo cargado. Total de registros: {total_filas}")
                
                # Mostrar avisos específicos si hubo anomalías detectadas
                if advertencias:
                    st.warning("Se detectaron algunos valores fuera de rango que fueron aislados automáticamente:")
                    for adv in advertencias:
                        st.markdown(f"- {adv}")
                
                st.write("Vista previa de los datos listos para importar (con celdas anómalas limpiadas):")
                st.dataframe(df_inv, use_container_width=True, height=250)
                
                if st.button("🚀 Procesar e Importar Inventarios", key="btn_imp_inv_dinamico"):
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
                    st.success(f"¡Se procesaron e importaron {count} registros exitosamente (los datos limpios se guardaron y las celdas fuera de rango quedaron pendientes de captura manual)! ")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")
