import streamlit as st
from database import init_connection
from modules import tanques, inventario, ventas, cargas, estaciones

# Configuración de la página en modo ancho (wide)
st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide"
)

st.title("⛽ Sistema de Gestión de Suministro y Inventarios")
st.markdown("---")

# Menú lateral de navegación con todos los módulos integrados
menu = st.sidebar.selectbox(
    "Selecciona un Módulo",
    [
        "🏢 Catálogo de Estaciones", 
        "📊 Estado de Tanques", 
        "📝 Registro de Inventarios", 
        "📊 Registro de Ventas", 
        "🚛 Programación de Cargas"
    ]
)

# Conexión activa a la base de datos de Supabase
conn = init_connection()

if conn:
    if menu == "🏢 Catálogo de Estaciones":
        estaciones.render(conn)
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
    st.error("No se pudo establecer la conexión con la base de datos. Revisa tus secretos en Streamlit Cloud.")
