import streamlit as st
from datetime import datetime, timezone, timedelta
from database import init_connection
from modules import inventario, ventas, importador, dashboard, programacion, administrador_cargas

st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide"
)

# Título resumido en la parte superior del menú lateral
st.sidebar.title("⛽ Gestión de Suministro")
st.sidebar.markdown("---")

# Menú lateral fijo mediante radio buttons con el orden solicitado
st.sidebar.markdown("### Navegación")
menu = st.sidebar.radio(
    "Selecciona un Módulo",
    [
        "📊 Dashboard Operativo",
        "📅 Matriz de Programación (MRP)",
        "📝 Registro de Inventarios",
        "📊 Registro de Ventas",
        "🚛 Administrador de Cargas",
        "📥 Importar Masivos (CSV)"
    ],
    label_visibility="collapsed"
)

# ==========================================
# INDICADOR PERMANENTE DE FECHA Y HORA (ALINEADO A LA IZQUIERDA)
# ==========================================
tz_local = timezone(timedelta(hours=-7))
ahora_local = datetime.now(tz_local)

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"<div style='text-align: left; color: #aaa; font-size: 0.85em; padding: 5px;'>"
    f"🕒 <b>Reloj del Sistema</b><br>"
    f"📅 {ahora_local.strftime('%Y-%m-%d')}<br>"
    f"⏱️ {ahora_local.strftime('%H:%M:%S')} (UTC-7)"
    f"</div>",
    unsafe_allow_html=True
)

# ==========================================
# BOTÓN DE REFRESCADO DE BASE DE DATOS
# ==========================================
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refrescar Base de Datos", use_container_width=True):
    # Limpia la caché de datos de Streamlit para obligar a consultar Supabase de nuevo
    st.cache_data.clear()
    st.sidebar.success("✅ Conexión con Supabase verificada y datos actualizados.")

conn = init_connection()

if conn:
    if menu == "📊 Dashboard Operativo":
        dashboard.render(conn)
    elif menu == "📅 Matriz de Programación (MRP)":
        programacion.render(conn)
    elif menu == "📝 Registro de Inventarios":
        inventario.render(conn)
    elif menu == "📊 Registro de Ventas":
        ventas.render(conn)
    elif menu == "🚛 Administrador de Cargas":
        administrador_cargas.render(conn)
    elif menu == "📥 Importar Masivos (CSV)":
        importador.render(conn)
    
    conn.close()
else:
    st.error("No se pudo establecer la conexión con la base de datos.")
