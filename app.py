import streamlit as st
from database import init_connection
from modules import tanques, inventario, ventas, cargas, estaciones, importador, dashboard, programacion

st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide"
)

st.title("⛽ Sistema de Gestión de Suministro e Inventarios")
st.markdown("---")

# Menú lateral fijo mediante radio buttons para visualización directa
st.sidebar.title("Navegación")
menu = st.sidebar.radio(
    "Selecciona un Módulo",
    [
        "📊 Dashboard Operativo",
        "📅 Matriz de Programación (MRP)",
        "🏢 Catálogo de Estaciones", 
        "📥 Importar Masivos (CSV)",
        "📊 Estado de Tanques", 
        "📝 Registro de Inventarios", 
        "📊 Registro de Ventas", 
        "🚛 Programación de Cargas"
    ]
)

conn = init_connection()

if conn:
    if menu == "📊 Dashboard Operativo":
        dashboard.render(conn)
    elif menu == "📅 Matriz de Programación (MRP)":
        programacion.render(conn)
    elif menu == "🏢 Catálogo de Estaciones":
        estaciones.render(conn)
    elif menu == "📥 Importar Masivos (CSV)":
        importador.render(conn)
    elif menu == "📊 Estado de Tanques":
        tanques.render(conn)
    elif menu == "📝 Registro de Inventarios":
        inventario.render(conn)
    elif menu == "📊 Registro de Ventas":
        ventas.render(conn)
    elif menu == "🚛 Programación de Cargas":
        cargas.render(conn)
    
    conn.close()
else:
    st.error("No se pudo establecer la conexión con la base de datos.")
