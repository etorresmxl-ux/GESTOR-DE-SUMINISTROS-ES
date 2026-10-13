import streamlit as st
import pandas as pd

def render(conn):
    st.header("📊 Monitoreo de Tanques por Estación")
    st.info("Visualiza el estatus actual de los tanques en Mexicali, SLRC y Hermosillo.")
    
    try:
        query = "SELECT * FROM tanques;"
        df_tanques = pd.read_sql(query, conn)
        if not df_tanques.empty:
            st.dataframe(df_tanques, use_container_width=True)
        else:
            st.warning("No hay registros de tanques en la base de datos todavía.")
    except Exception as e:
        st.error(f"Error al consultar la tabla tanques: {e}")
