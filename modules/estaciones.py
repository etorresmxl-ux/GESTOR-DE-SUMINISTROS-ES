import streamlit as st
import pandas as pd

def render(conn):
    st.header("🏢 Catálogo de Estaciones de Servicio")
    st.write("Red operativa de estaciones clasificadas por Programador, Plaza y Terminal (TAD).")
    
    try:
        query = "SELECT id AS \"ID\", nombre AS \"Nombre Comercial\", plaza AS \"Plaza\", tad AS \"TAD\", usuario AS \"Programador\" FROM estaciones ORDER BY usuario, plaza, id;"
        df_estaciones = pd.read_sql(query, conn)
        
        if not df_estaciones.empty:
            # Filtros superiores
            col1, col2 = st.columns(2)
            with col1:
                programadores = ["Todos"] + list(df_estaciones["Programador"].dropna().unique())
                prog_seleccionado = st.selectbox("Filtrar por Programador", programadores)
            with col2:
                plazas = ["Todas"] + list(df_estaciones["Plaza"].unique())
                plaza_seleccionada = st.selectbox("Filtrar por Plaza / Ciudad", plazas)
                
            # Aplicar filtros
            df_filtrado = df_estaciones
            if prog_seleccionado != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Programador"] == prog_seleccionado]
            if plaza_seleccionada != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Plaza"] == plaza_seleccionada]
                
            st.metric("Total de Estaciones Filtradas", len(df_filtrado))
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("No hay estaciones registradas en la base de datos todavía.")
    except Exception as e:
        st.error(f"Error al consultar las estaciones: {e}")
