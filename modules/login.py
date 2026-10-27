import streamlit as st

from services.auth_service import authenticate_user


def render(conn):
    """Pantalla de login usando la tabla usuarios_sistema."""
    st.title("🔐 Iniciar sesión")
    st.write("Ingresa tus credenciales para continuar.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if st.session_state.get("autenticado"):
        st.success("Ya estás autenticado.")
        return

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        enviado = st.form_submit_button("Ingresar")

    if not enviado:
        return

    if not usuario or not password:
        st.warning("Debes ingresar usuario y contraseña.")
        return

    ok, rol, mensaje = authenticate_user(conn, usuario, password)
    if not ok:
        st.error(mensaje or "Usuario o contraseña incorrectos.")
        return

    st.session_state["autenticado"] = True
    st.session_state["usuario_actual"] = usuario
    st.session_state["rol_actual"] = rol
    st.rerun()


__all__ = ["render"]
