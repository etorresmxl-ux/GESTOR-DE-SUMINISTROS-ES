import streamlit as st


def render(conn):
    """Renderiza la pantalla de autenticación.

    Esta vista no debe importar el paquete `modules` ni otros módulos del
    paquete, porque eso provoca ciclos de importación al cargarse `app.py`.
    """
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

    # Autenticación temporal, sin depender de otros módulos.
    # Reemplazar esta validación por la lógica real contra la base de datos.
    if usuario and password:
        st.session_state["autenticado"] = True
        st.session_state["usuario_actual"] = usuario
        st.session_state["rol_actual"] = "admin" if usuario.lower() == "admin" else "operador"
        st.rerun()


__all__ = ["render"]
