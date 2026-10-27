from datetime import date
import pandas as pd
import streamlit as st

from services.inventario_service import (
    construir_matriz_inventario,
    guardar_inventarios,
    obtener_inventarios_existentes,
    obtener_tanques_por_estaciones,
)


def render(conn):
    st.markdown("### 📦 Módulo de Registro de Inventarios")
    st.write(
        "Selecciona tu usuario y la fecha para consultar, ingresar o modificar "
        "los inventarios de tus estaciones asignadas."
    )
    st.markdown("---")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    usuario_actual = st.session_state.get("usuario_actual", "")
    rol_actual = st.session_state.get("rol_actual", "operador")

    try:
        col1, col2 = st.columns(2)
        with col1:
            if rol_actual == "admin":
                query_usuarios = (
                    "SELECT DISTINCT usuario FROM usuarios_estaciones "
                    "WHERE usuario IS NOT NULL ORDER BY usuario;"
                )
                df_usuarios = pd.read_sql(query_usuarios, conn)
                lista_usuarios = (
                    df_usuarios["usuario"].tolist() if not df_usuarios.empty else []
                )
                usuario_seleccionado = st.selectbox(
                    "👤 Selecciona el Usuario", lista_usuarios, key="inv_usuario_sel"
                )
            else:
                usuario_seleccionado = usuario_actual
                st.text_input(
                    "👤 Usuario:",
                    value=usuario_seleccionado,
                    disabled=True,
                    key="inv_usuario_text_disabled",
                )

        with col2:
            fecha_seleccionada = st.date_input(
                "📅 Selecciona la Fecha", date.today(), key="inv_fecha_sel"
            )

        st.info(
            f"Mostrando estaciones asignadas al usuario **{usuario_seleccionado}** "
            f"para la fecha: **{fecha_seleccionada}**."
        )
        st.markdown("---")

        query_estaciones = f"""
            SELECT e.id_estacion AS "ID", e.nombre AS "Estacion",
                   e.plaza AS "Plaza", e.tad AS "TAD"
            FROM estaciones e
            JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
            WHERE ue.usuario = '{usuario_seleccionado}'
            ORDER BY e.plaza, e.id_estacion;
        """
        df_estaciones = pd.read_sql(query_estaciones, conn)

        if df_estaciones.empty:
            st.warning(
                f"El usuario **{usuario_seleccionado}** no tiene estaciones asignadas "
                "actualmente."
            )
            return

        ids_estaciones = tuple(df_estaciones["ID"].tolist())
        tanques_estaciones = obtener_tanques_por_estaciones(conn, ids_estaciones)
        df_existentes = obtener_inventarios_existentes(
            conn, fecha_seleccionada, ids_estaciones
        )

        df_estaciones = construir_matriz_inventario(
            df_estaciones,
            tanques_estaciones,
            df_existentes,
        )

        if not df_existentes.empty:
            st.success(
                f"📂 Se encontraron registros previos guardados para el día "
                f"{fecha_seleccionada}. Puedes modificarlos directamente."
            )
        else:
            st.info(
                f"ℹ️ No hay registros previos para el día {fecha_seleccionada}. "
                "Ingresa los volúmenes correspondientes."
            )

        st.markdown(
            f"#### Matriz de Inventarios - `{usuario_seleccionado}`\n"
            f"({fecha_seleccionada})"
        )

        with st.form("form_inventarios_matriz"):
            df_editado = st.data_editor(
                df_estaciones,
                column_config={
                    "ID": st.column_config.TextColumn("ID Estación", disabled=True),
                    "TAD": st.column_config.TextColumn("TAD", disabled=True),
                    "Plaza": st.column_config.TextColumn("Plaza", disabled=True),
                    "Estacion": st.column_config.TextColumn(
                        "Nombre Estación", disabled=True
                    ),
                    "Regular": st.column_config.NumberColumn(
                        "Regular (Lts)", min_value=0, format="%,d", step=100
                    ),
                    "Premium": st.column_config.NumberColumn(
                        "Premium (Lts)", min_value=0, format="%,d", step=100
                    ),
                    "Diesel": st.column_config.NumberColumn(
                        "Diesel (Lts)", min_value=0, format="%,d", step=100
                    ),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                height=500,
            )

            st.markdown("")
            submitted = st.form_submit_button(
                "💾 Guardar Inventarios", use_container_width=True
            )

            if submitted:
                try:
                    count = guardar_inventarios(
                        conn,
                        df_editado,
                        tanques_estaciones,
                        fecha_seleccionada,
                    )
                    st.success(
                        f"¡Se guardaron y actualizaron {count} registros de inventario "
                        f"exitosamente para el usuario {usuario_seleccionado}!"
                    )
                    st.rerun()
                except Exception as exc:
                    conn.rollback()
                    st.error(f"Error al guardar inventarios: {exc}")

    except Exception as e:
        st.error(f"Error al cargar o procesar el módulo de inventarios: {e}")


def configurar_modulo_inventario():
    return render


__all__ = ["render", "configurar_modulo_inventario"]
