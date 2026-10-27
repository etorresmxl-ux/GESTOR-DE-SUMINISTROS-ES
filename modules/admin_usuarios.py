import bcrypt
import pandas as pd
import streamlit as st


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _normalize_role(role_value):
    return "admin" if str(role_value or "").strip().lower() == "admin" else "usuario"


def render(conn):
    """Módulo para administrar usuarios y asignación de estaciones."""
    rol_actual = st.session_state.get("rol_actual", "").lower()
    if rol_actual != "admin":
        st.error("Solo el administrador puede acceder a esta sección.")
        return

    st.title("👤 Administración de usuarios")
    st.caption("Alta de usuarios, cambio de contraseña y asignación de estación.")

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

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id_estacion, nombre, plaza, tad FROM public.estaciones ORDER BY nombre"
            )
            estaciones = cursor.fetchall()
    except Exception as exc:
        st.error(f"No se pudo consultar la tabla de estaciones: {exc}")
        estaciones = []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ue.usuario, ue.id_estacion, e.nombre, e.plaza, ue.rol
                FROM public.usuarios_estaciones ue
                LEFT JOIN public.estaciones e ON e.id_estacion = ue.id_estacion
                ORDER BY ue.usuario, ue.id_estacion
                """
            )
            asignaciones = cursor.fetchall()
    except Exception as exc:
        st.error(f"No se pudieron consultar las asignaciones de estaciones: {exc}")
        asignaciones = []

    if asignaciones:
        df_asignaciones = pd.DataFrame(asignaciones, columns=["usuario", "id_estacion", "nombre_estacion", "plaza", "rol"])
        st.markdown("---")
        st.subheader("Asignación actual de estaciones")
        st.dataframe(df_asignaciones, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Alta o actualización de usuario")

    with st.form("form_admin_usuario"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Nueva contraseña", type="password")
        rol = st.selectbox("Rol", ["admin", "usuario"], index=1)
        enviado = st.form_submit_button("Guardar usuario")

    if enviado:
        usuario_value = (usuario or "").strip()
        if not usuario_value or not password:
            st.warning("Debes indicar usuario y contraseña.")
            return

        try:
            hash_password = _hash_password(password)
            role_value = _normalize_role(rol)
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM public.usuarios_sistema WHERE usuario = %s LIMIT 1",
                    (usuario_value,),
                )
                existe = cursor.fetchone()

                if existe:
                    cursor.execute(
                        "UPDATE public.usuarios_sistema SET contrasena = %s, rol = %s WHERE usuario = %s",
                        (hash_password, role_value, usuario_value),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO public.usuarios_sistema (usuario, contrasena, rol) VALUES (%s, %s, %s)",
                        (usuario_value, hash_password, role_value),
                    )

            conn.commit()
            st.success(f"Usuario '{usuario_value}' guardado correctamente con rol '{role_value}'.")
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

    st.markdown("---")
    st.subheader("Asignar estación a usuario")

    if estaciones:
        opciones_estaciones = [f"{row[0]} - {row[1]} ({row[2]})" for row in estaciones]
        with st.form("form_asignar_estacion"):
            usuario_estacion = st.selectbox("Usuario", lista_usuarios if lista_usuarios else [""], index=0)
            estacion_seleccionada = st.selectbox("Estación", opciones_estaciones if opciones_estaciones else [""], index=0)
            guardar_asignacion = st.form_submit_button("Guardar asignación")

        if guardar_asignacion:
            if not usuario_estacion or not estacion_seleccionada:
                st.warning("Debes seleccionar usuario y estación.")
            else:
                id_estacion = estacion_seleccionada.split(" - ", 1)[0].strip()
                try:
                    role_value = _normalize_role(
                        next((rol_user for usuario_user, rol_user in usuarios if usuario_user == usuario_estacion), "usuario")
                    )
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT 1 FROM public.usuarios_estaciones WHERE usuario = %s AND id_estacion = %s LIMIT 1",
                            (usuario_estacion, id_estacion),
                        )
                        existe = cursor.fetchone()

                        if existe:
                            cursor.execute(
                                "UPDATE public.usuarios_estaciones SET rol = %s WHERE usuario = %s AND id_estacion = %s",
                                (role_value, usuario_estacion, id_estacion),
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO public.usuarios_estaciones (id_estacion, usuario, rol) VALUES (%s, %s, %s)",
                                (id_estacion, usuario_estacion, role_value),
                            )
                    conn.commit()
                    st.success(f"Asignación guardada para '{usuario_estacion}' en la estación '{id_estacion}'.")
                    st.rerun()
                except Exception as exc:
                    conn.rollback()
                    st.error(f"Error al guardar la asignación: {exc}")
    else:
        st.info("No hay estaciones registradas en la tabla public.estaciones.")


__all__ = ["render"]
