import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 🔍 Auditoría de Anomalías y Cuarentena de Ventas")
    st.write("Revisa, corrige o aprueba los registros de venta que superaron el umbral estadístico de desviación (Z-Score).")

    try:
        cursor = conn.cursor()
        
        # 1. Consultar anomalías pendientes
        query_pendientes = """
            SELECT id, estacion_id, fecha, producto, volumen_capturado, media_historica, desviacion_estandar, z_score, metodo_carga, creado_en
            FROM ventas_anomalias
            WHERE estatus = 'PENDIENTE'
            ORDER BY fecha DESC, estacion_id;
        """
        df_anomalias = pd.read_sql(query_pendientes, conn)

        if df_anomalias.empty:
            st.success("✨ ¡Excelente noticia! No hay registros en cuarentena pendientes de revisión.")
            return

        st.warning(f"⚠️ Hay **{len(df_anomalias)} registros** en cuarentena esperando auditoría.")
        st.markdown("---")

        # Mostrar tabla de anomalías con formato amigable
        for _, row in df_anomalias.iterrows():
            anom_id = row["id"]
            est_id = row["estacion_id"]
            fecha = row["fecha"]
            prod = row["producto"]
            vol_capturado = row["volumen_capturado"]
            media = row["media_historica"]
            desv = row["desviacion_estandar"]
            z = row["z_score"]
            metodo = row["metodo_carga"]

            with st.container():
                col1, col2, col3 = st.columns([2, 3, 3])
                
                with col1:
                    st.markdown(f"**Estación:** `{est_id}`")
                    st.markdown(f"**Fecha:** {fecha}")
                    st.markdown(f"**Producto:** `{prod.upper()}`")
                
                with col2:
                    st.markdown(f"📊 **Volumen Capturado:** `{vol_capturado:,.0f} L`")
                    st.markdown(f"📈 **Media Esperada:** `{media:,.0f} L`")
                    st.markdown(f"⚡ **Z-Score:** `{z:.2f}` (Desv. Est: `{desv:,.0f}`)")
                
                with col3:
                    st.markdown(f"📥 *Origen:* {metodo}")
                    
                    # Opciones de corrección / aprobación rápida
                    accion = st.radio(
                        "Acción a tomar:",
                        ["Pendiente", "✅ Aprobar como Evento Aislado", "✏️ Corregir Volumen y Aprobar", "❌ Descartar"],
                        key=f"accion_{anom_id}",
                        horizontal=False
                    )

                    nuevo_volumen = vol_capturado
                    if accion == "✏️ Corregir Volumen y Aprobar":
                        nuevo_volumen = st.number_input(
                            "Volumen Correcto (Lts):",
                            value=float(vol_capturado),
                            step=100.0,
                            key=f"nuevo_vol_{anom_id}"
                        )

                    if st.button(f"🚀 Aplicar Decisión #{anom_id}", key=f"btn_aplicar_{anom_id}", use_container_width=True):
                        if accion == "Pendiente":
                            st.info("Selecciona una acción válida.")
                        else:
                            try:
                                if accion == "✅ Aprobar como Evento Aislado":
                                    # Insertar a histórico oficial ignorando en promedio
                                    sql_insert = f"""
                                        INSERT INTO ventas_historico (estacion_id, fecha, {prod}, ignorar_en_promedio)
                                        VALUES (%s, %s, %s, TRUE)
                                        ON CONFLICT (estacion_id, fecha) 
                                        DO UPDATE SET {prod} = EXCLUDED.{prod}, ignorar_en_promedio = TRUE;
                                    """
                                    cursor.execute(sql_insert, (est_id, fecha, vol_capturado))
                                    
                                    # Marcar anomalía como APROBADA
                                    cursor.execute("UPDATE ventas_anomalias SET estatus = 'APROBADO_AISLADO' WHERE id = %s;", (anom_id,))
                                    conn.commit()
                                    st.success(f"¡Registro aprobado como evento aislado para {est_id}!")
                                    st.rerun()

                                elif accion == "✏️ Corregir Volumen y Aprobar":
                                    # Insertar volumen corregido al histórico normal (cuenta para promedio)
                                    sql_insert = f"""
                                        INSERT INTO ventas_historico (estacion_id, fecha, {prod}, ignorar_en_promedio)
                                        VALUES (%s, %s, %s, FALSE)
                                        ON CONFLICT (estacion_id, fecha) 
                                        DO UPDATE SET {prod} = EXCLUDED.{prod}, ignorar_en_promedio = FALSE;
                                    """
                                    cursor.execute(sql_insert, (est_id, fecha, nuevo_volumen))
                                    
                                    # Marcar anomalía como CORREGIDA
                                    cursor.execute("UPDATE ventas_anomalias SET estatus = 'CORREGIDO_Y_APROBADO' WHERE id = %s;", (anom_id,))
                                    conn.commit()
                                    st.success(f"¡Volumen corregido a {nuevo_volumen:,.0f} L y guardado exitosamente!")
                                    st.rerun()

                                elif accion == "❌ Descartar":
                                    # Marcar como descartado
                                    cursor.execute("UPDATE ventas_anomalias SET estatus = 'DESCARTADO' WHERE id = %s;", (anom_id,))
                                    conn.commit()
                                    st.warning("Registro descartado de la cuarentena.")
                                    st.rerun()

                            except Exception as db_err:
                                conn.rollback()
                                st.error(f"Error al procesar la decisión: {db_err}")

                st.markdown("---")
        cursor.close()

    except Exception as e:
        st.error(f"Error al cargar la cuarentena de anomalías: {e}")
