import streamlit as st
import pandas as pd

def render(conn):
    st.header("⛽ Catálogo de Estaciones de Servicio")
    st.write("Administra la clasificación, plazas y terminales (TAD) de la red.")
    
    # Pestañas internas para organizar la vista y el registro
    tab1, tab2 = st.tabs(["📋 Listado de Estaciones", "➕ Registrar Nueva Estación"])
    
    with tab1:
        try:
            query = "SELECT id AS \"ID\", nombre AS \"Nombre Comercial\", plaza AS \"Plaza\", tad AS \"TAD\" FROM estaciones ORDER BY id;"
            df_estaciones = pd.read_sql(query, conn)
            if not df_estaciones.empty:
                st.dataframe(df_estaciones, use_container_width=True, hide_index=True)
            else:
                st.info("No hay estaciones registradas en la base de datos todavía.")
        except Exception as e:
            st.error(f"Error al consultar las estaciones: {e}")
            
    with tab2:
        st.subheader("Registrar Nueva Estación")
        with st.form("form_nueva_estacion", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                est_id = st.text_input("ID de Estación (ej. E12345)")
                nombre = st.text_input("Nombre Comercial Práctico")
            with col2:
                plaza = st.selectbox("Plaza / Ciudad", ["Mexicali", "SLRC", "Hermosillo", "Otra"])
                tad = st.text_input("TAD (Número de Terminal, ej. 150)")
                
            submitted = st.form_submit_button("Guardar Estación")
            if submitted:
                if est_id and nombre and plaza and tad:
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO estaciones (id, nombre, plaza, tad) VALUES (%s, %s, %s, %s)",
                            (est_id.upper(), nombre, plaza, tad)
                        )
                        conn.commit()
                        cursor.close()
                        st.success(f"¡Estación {est_id.upper()} registrada exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar la estación (es posible que el ID ya exista): {e}")
                else:
                    st.warning("Por favor, completa todos los campos obligatorios.")
