from datetime import datetime, timedelta, timezone 
from database import init_connection 
from modules import ( 
    dashboard, 
    herramientas, 
    importador, 
    inventarios, 
    programacion, 
    reportes,
    ventas, 
) 
import streamlit as st

### --- Configuración inicial de la página ---
st.set_page_config( 
    page_title="Gestión de Suministro - Gasolineras", 
    page_icon="⛽", 
    layout="wide", 
    initial_sidebar_state="expanded", 
)

### Inicializar conexión a base de datos
conn = init_connection()

### --- BARRA LATERAL DE NAVEGACIÓN ---
st.sidebar.markdown("## ⛽ Gestión de Suministro") 
st.sidebar.markdown("---") 
st.sidebar.markdown("### Navegación")

menu = st.sidebar.radio( 
    "Selecciona un módulo:", [ 
        "Dashboard", 
        "Programación (MRP)", 
        "Inventarios", 
        "Ventas", 
        "Reportes", 
        "Importador de Datos", 
        "Herramientas de Datos", 
    ], 
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

### --- ENRUTAMIENTO DE MÓDULOS ---
if menu == "Dashboard": 
    dashboard.render(conn) 
elif menu == "Programación (MRP)": 
    programacion.render(conn) 
elif menu == "Inventarios": 
    inventarios.render(conn) 
elif menu == "Ventas": 
    ventas.render(conn) 
elif menu == "Reportes": 
    reportes.render(conn) 
elif menu == "Importador de Datos": 
    importador.render(conn) 
elif menu == "Herramientas de Datos": 
    herramientas.render(conn)
