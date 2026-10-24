import pandas as pd
import streamlit as st


def render(conn):
  """Muestra la pantalla de inicio de sesión y valida contra la tabla 'usuarios_sistema' de Supabase."""
  st.markdown("## 🔐 Iniciar Sesión - Gestión de Suministro")
  st.write("Por favor, ingresa tus credenciales asignadas para continuar.")

  with st.form("form_login"):
    usuario_input = st.text_input("👤 Usuario:")
    password_input = st.text_input("🔑 Contraseña:", type="password")
    submit_login = st.form_submit_button("🚀 Ingresar", use_container_width=True)

    if submit_login:
      if not usuario_input or not password_input:
        st.warning("⚠️ Por favor ingresa tu usuario y contraseña.")
      else:
        try:
          cursor = conn.cursor()
          # Consulta directa con contraseñas en texto plano
          query = "SELECT rol FROM usuarios_sistema WHERE usuario = %s AND contrasena = %s;"
          cursor.execute(query, (usuario_input, password_input))
          resultado = cursor.fetchone()
          cursor.close()

          if resultado:
            rol_db = resultado[0]
            st.session_state["autenticado"] = True
            st.session_state["usuario_actual"] = usuario_input
            st.session_state["rol_actual"] = rol_db
            st.success("¡Inicio de sesión exitoso! Accediendo...")
            st.rerun()
          else:
            st.error(
                "❌ Usuario o contraseña incorrectos. Verifica tus datos."
            )
        except Exception as e:
          st.error(f"Error al conectar con la base de datos: {e}")
