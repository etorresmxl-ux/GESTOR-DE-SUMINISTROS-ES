import streamlit as st
from database import init_connection
from modules import tanques, inventario, cargas

# Configuración de la página
st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide"
)

st.title("⛽ Sistema de Gestión de Suministro y Inventarios")
st.markdown("---")

# Menú lateral de navegación
menu = st.sidebar.selectbox(
    "Selecciona un Módulo",
    ["📊 Estado de Tanques", "📝 Registro Histórico", "🚛 Programación de Cargas"]
)

# Conexión activa a la base de datos
conn = init_connection()

if conn:
    if menu == "📊 Estado de Tanques":
        tanques.render(conn)
    elif menu == "📝 Registro Histórico":
        inventario.render(conn)
    elif menu == "🚛 Programación de Cargas":
        cargas.render(conn)
    
    conn.close()
else:
    st.error("No se pudo establecer la conexión con la base de datos. Revisa tus secretos en Streamlit Cloud.")
