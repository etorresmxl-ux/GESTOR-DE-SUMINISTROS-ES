import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.header("📝 Registro de Inventarios Diarios")
    st.write("Captura los niveles actuales de combustible por estación para la fecha de hoy.")
    
    try:
        # Cargar la lista de estaciones para los selectores
        query_est = "SELECT id, nombre, plaza FROM estaciones ORDER BY plaza, id;"
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning("Primero debes registrar estaciones en el Catálogo de Estaciones.")
            return

        # Crear una lista legible para el usuario: "E1783 - LAS FUENTES (Mexicali)"
        df_estaciones["etiqueta"] = df_estaciones["id"] + " - " + df_estaciones["nombre"] + " (" + df_estaciones["plaza"] + ")"
        
        with st.form("form_inventario_diario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                estacion_seleccionada = st.selectbox(
                    "Selecciona la Estación",
                    df_estaciones["etiqueta"].tolist()
                )
                fecha_registro = st.date_input("Fecha de Inventario", date.today())
                
            with col2:
                combustible = st.selectbox(
                    "Tipo de Combustible",
                    ["Magna", "Premium", "Diesel"]
                )
                volumen_actual = st.number_input(
                    "Volumen Actual (Litros)",
                    min_value=0.0,
                    step=100.0,
                    format="%.2f"
                )
            
            submitted = st.form_submit_button("Guardar Inventario Diario")
            
            if submitted:
                # Extraer el ID real de la estación seleccionada (ej. 'E01783')
                est_id = estacion_seleccionada.split(" - ")[0]
                
                try:
                    cursor = conn.cursor()
                    # Nota: Aseguramos insertar relacionando con el ID de la estación
                    cursor.execute(
                        """
                        INSERT INTO inventarios_historico (estacion_id, combustible, volumen, fecha) 
                        VALUES (%s, %s, %s, %s)
                        """,
                        (est_id, combustible, volumen_actual, fecha_registro)
                    )
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Inventario de {combustible} registrado exitosamente para la estación {est_id}!")
                except Exception as e:
                    st.error(f"Error al registrar en la base de datos: {e}")

        st.markdown("---")
        st.subheader("📊 Historial de Registros Recientes")
        
        # Mostrar una tabla con los últimos inventarios capturados
        query_hist = """
            SELECT h.fecha AS "Fecha", e.id AS "ID Estación", e.nombre AS "Estación", 
                   h.combustible AS "Combustible", h.volumen AS "Volumen (Lts)"
            FROM inventarios_historico h
            JOIN estaciones e ON h.estacion_id = e.id
            ORDER BY h.fecha DESC, e.id DESC
            LIMIT 50;
        """
        df_historial = pd.read_sql(query_hist, conn)
        if not df_historial.empty:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay registros de inventarios históricos capturados.")
            
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
