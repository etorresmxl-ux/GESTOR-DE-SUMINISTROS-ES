import streamlit as st
import pandas as pd

def render(conn):
    st.header("🚛 Programación y Suministro de Combustible")
    st.write("Planifica las próximas pipas y recepción de producto.")
    
    try:
        query = "SELECT * FROM programacion_cargas;"
        df_cargas = pd.read_sql(query, conn)
        if not df_cargas.empty:
            st.dataframe(df_cargas, use_container_width=True)
        else:
            st.info("No hay cargas programadas actualmente.")
    except Exception as e:
        st.error(f"Error al consultar la programación de cargas: {e}")
