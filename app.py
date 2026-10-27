from datetime import datetime, timedelta, timezone
import importlib

import streamlit as st

from database import init_connection
from services.auth_service import get_menu_for_role


MODULE_MAPPING = {
    "dashboard": "modules.dashboard",
    "descargas": "modules.descargas",
    "herramientas": "modules.herramientas",
    "importador": "modules.importador",
    "inventarios": "modules.inventarios",
    "login": "modules.login",
    "programacion": "modules.programacion",
    "reportes": "modules.reportes",
    "ventas": "modules.ventas",
    "admin_usuarios": "modules.admin_usuarios",
}

LOADED_MODULES = {}
for name, module_path in MODULE_MAPPING.items():
    try:
        LOADED_MODULES[name] = importlib.import_module(module_path)
    except Exception as exc:
        st.error(f"No se pudo cargar el módulo '{module_path}': {exc}")
        st.stop()

dashboard = LOADED_MODULES["dashboard"]
descargas = LOADED_MODULES["descargas"]
herramientas = LOADED_MODULES["herramientas"]
importador = LOADED_MODULES["importador"]
inventarios = LOADED_MODULES["inventarios"]
login = LOADED_MODULES["login"]
programacion = LOADED_MODULES["programacion"]
reportes = LOADED_MODULES["reportes"]
ventas = LOADED_MODULES["ventas"]
admin_usuarios = LOADED_MODULES["admin_usuarios"]

st.set_page_config(
    page_title="Gestión de Suministro - Gasolineras",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 1.5rem !important;
    }
    h1, h2, h3 {
        margin-top: 0.5rem !important;
        margin-bottom: 0.4rem !important;
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }
    h4, h5, h6 {
        margin-top: 0.4rem !important;
        margin-bottom: 0.2rem !important;
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }
    p {
        margin-bottom: 0.4rem !important;
        margin-top: 0rem !important;
    }
    hr {
        margin-top: 0.8rem !important;
        margin-bottom: 0.8rem !important;
    }
    @media (max-width: 768px) {
        .stButton button {
            width: 100% !important;
        }
        .stDataFrame {
            font-size: 12px !important;
        }
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 2rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

conn = init_connection()

if conn is None:
    st.warning(
        "La aplicación no pudo conectarse a la base de datos. "
        "Verifica la configuración del entorno o el secreto de Supabase."
    )
    st.stop()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login.render(conn)
else:
    usuario_logueado = st.session_state.get("usuario_actual", "")
    rol_logueado = str(st.session_state.get("rol_actual", "")).strip().lower()

    st.sidebar.markdown("## ⛽ Gestión de Suministro")
    st.sidebar.markdown(f"👤  **Usuario:**  {usuario_logueado} ({rol_logueado})")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Navegación")

    opciones_menu = get_menu_for_role(conn, usuario_logueado)
    if not opciones_menu:
        st.sidebar.warning("No tienes permisos para acceder a esta aplicación.")
        st.stop()

    menu = st.sidebar.radio("Selecciona un módulo:", opciones_menu)

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

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["rol_actual"] = ""
        st.session_state["usuario_estaciones"] = []
        st.session_state["estacion_actual"] = None
        st.rerun()

    if menu == "Dashboard":
        dashboard.render(conn)
    elif menu == "Programación (MRP)":
        programacion.render(conn)
    elif menu == "Inventarios":
        inventarios.render(conn)
    elif menu == "Ventas":
        ventas.render(conn)
    elif menu == "Descargas":
        descargas.render(conn)
    elif menu == "Reportes":
        if rol_logueado != "admin":
            st.error("No tienes permisos para acceder a Reportes.")
            st.stop()
        reportes.render(conn)
    elif menu == "Importador de Datos":
        if rol_logueado != "admin":
            st.error("No tienes permisos para acceder a Importador de Datos.")
            st.stop()
        importador.render(conn)
    elif menu == "Herramientas de Datos":
        if rol_logueado != "admin":
            st.error("No tienes permisos para acceder a Herramientas de Datos.")
            st.stop()
        herramientas.render(conn)
    elif menu == "Administración de Usuarios":
        if rol_logueado != "admin":
            st.error("No tienes permisos para acceder a Administración de Usuarios.")
            st.stop()
        admin_usuarios.render(conn)
