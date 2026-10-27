import bcrypt
import pandas as pd
import streamlit as st


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def render(conn):
    """Módulo temporal de administración de usuarios del sistema."""
    rol_actual = st.session_state.get("rol_actual", "").lower()
    if rol_actual != "admin":
        st.error("Solo el administrador puede acceder a esta sección.")
        return

    st.title("👤 Administración de usuarios")
    st.caption("Módulo temporal para dar de alta usuarios y cambiar contraseñas.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT usuario, rol FROM public.usuarios_sistema ORDER BY usuario"
            )
            usuarios = cursor.fetchall()
    except Exception as exc:
        st.error(f"No se pudo consultar la tabla de usuarios: {exc}")
        return

    if usuarios:
        df_usuarios = pd.DataFrame(usuarios, columns=["usuario", "rol"])
        st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay usuarios registrados en public.usuarios_sistema.")

    st.markdown("---")
    st.subheader("Alta o actualización de usuario")

    with st.form("form_admin_usuario"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Nueva contraseña", type="password")
        rol = st.selectbox("Rol", ["admin", "operador", "supervisor", "analista"], index=1)
        enviado = st.form_submit_button("Guardar usuario")

    if enviado:
        usuario_value = (usuario or "").strip()
        if not usuario_value or not password:
            st.warning("Debes indicar usuario y contraseña.")
            return

        try:
            hash_password = _hash_password(password)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.usuarios_sistema (usuario, contrasena, rol)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET contrasena = EXCLUDED.contrasena, rol = EXCLUDED.rol
                    """,
                    (usuario_value, hash_password, rol),
                )
            conn.commit()
            st.success(f"Usuario '{usuario_value}' guardado correctamente con rol '{rol}'.")
            st.rerun()
        except Exception as exc:
            conn.rollback()
            st.error(f"Error al guardar usuario: {exc}")

    st.markdown("---")
    st.subheader("Cambiar contraseña de usuario existente")

    lista_usuarios = [row[0] for row in usuarios]
    usuario_sel = st.selectbox("Selecciona usuario", lista_usuarios if lista_usuarios else [""], index=0)

    if usuario_sel:
        with st.form("form_update_password"):
            nueva_password = st.text_input("Nueva contraseña", type="password", key="password_usuario_sel")
            cambiar = st.form_submit_button("Actualizar contraseña")

        if cambiar:
            if not nueva_password:
                st.warning("Debes escribir una contraseña nueva.")
            else:
                try:
                    hash_password = _hash_password(nueva_password)
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE public.usuarios_sistema SET contrasena = %s WHERE usuario = %s",
                            (hash_password, usuario_sel),
                        )
                    conn.commit()
                    st.success(f"Contraseña actualizada para '{usuario_sel}'.")
                    st.rerun()
                except Exception as exc:
                    conn.rollback()
                    st.error(f"Error al actualizar la contraseña: {exc}")


__all__ = ["render"]
