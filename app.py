import streamlit as st
from datetime import datetime, timezone, timedelta
from database import init_connection

# Configuración inicial de la página
st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar conexión a base de datos
conn = init_connection()

# --- BARRA LATERAL DE NAVEGACIÓN ---
st.sidebar.markdown("## ⛽ Gestión de Suministro")
st.sidebar.markdown("---")

st.sidebar.markdown("### Navegación")

# Definir las opciones de navegación disponibles de forma segura
# (Asegúrate de importar solo los módulos que existen en tu carpeta 'modules')
from modules import dashboard, ventas

menu = st.sidebar.radio(
    "Selecciona un módulo:",
    [
        "Dashboard Operativo",
        "Registro de Ventas",
        # Puedes ir agregando los demás módulos conforme los vayamos conectando
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Reloj del Sistema")
tz_local = timezone(timedelta(hours=-7))
ahora_local = datetime.now(tz_local)
st.sidebar.write(f"📅 {ahora_local.strftime('%Y-%m-%d')}")
st.sidebar.write(f"⏰ {ahora_local.strftime('%H:%M:%S (UTC-7)')}")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refrescar Base de Datos", use_container_width=True):
    st.cache_data.clear()
    st.success("¡Caché refrescada con éxito!")
    st.rerun()

# --- ENRUTAMIENTO DE MÓDULOS ---
if menu == "Dashboard Operativo":
    dashboard.render(conn)
elif menu == "Registro de Ventas":
    ventas.render(conn)
