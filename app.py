import streamlit as st
from database import init_connection
from modules import inventario, ventas, importador, dashboard, programacion, administrador_cargas

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
        "🚛 Administrador de Cargas",
        "📥
