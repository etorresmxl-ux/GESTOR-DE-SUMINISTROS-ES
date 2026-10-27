from datetime import date, timedelta

import hashlib
import pandas as pd
import streamlit as st

from database import init_connection
from services.programacion_service import (
    COLOR_PRODUCTO,
    DIAS_SEMANA,
    MESES,
    PRODUCTOS_ORDEN,
    _clave_producto,
    _etiqueta_fecha,
    construir_calendario,
    estilo_calendario,
    obtener_capacidades_por_estacion,
    obtener_cargas_guardadas,
    obtener_inventario_actual,
    obtener_ordenes_estacion,
)


@st.dialog("⚠️ Confirmar Eliminación")
def confirmar_eliminacion(conn, orden_id, detalles_str):
    st.write(
        f"¿Estás seguro de que deseas eliminar permanentemente la **Orden de Carga #{orden_id}**?"
    )
    st.caption(detalles_str)
    c_si, c_no = st.columns(2)
    with c_si:
        if st.button("Confirmar y Eliminar", type="primary", use_container_width=True):
            active_conn = conn
            try:
                if active_conn is None or (
                    hasattr(active_conn, "closed") and active_conn.closed != 0
                ):
                    active_conn = init_connection()

                cursor = active_conn.cursor()
                q_del = f"DELETE FROM programacion_cargas WHERE id = {orden_id};"
                cursor.execute(q_del)
                active_conn.commit()
                cursor.close()
                st.session_state["mensaje_exito_orden"] = (
                    f"🗑️ Orden de Carga #{orden_id} eliminada del sistema."
                )
                st.rerun()
            except Exception as e_del:
                try:
                    if active_conn and hasattr(active_conn, "rollback"):
                        active_conn.rollback()
                except Exception:
                    pass
                st.error(f"Error al eliminar: {e_del}")

    with c_no:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def render(conn):
    st.markdown("### 🚛 Matriz de Programación y Gestión de Órdenes")
    st.write(
        "Administra de forma independiente cada Orden de Carga (Folio) y "
        "visualiza el resumen consolidado a 14 días."
    )

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    usuario_actual = st.session_state.get("usuario_actual", "")
    rol_actual = st.session_state.get("rol_actual", "operador")

    try:
        if rol_actual == "admin":
            query_base = """
                SELECT DISTINCT e.id_estacion, e.nombre AS estacion_nombre, e.tad AS proveedor,
                       e.plaza, COALESCE(NULLIF(ue.usuario, ''), 'Sin Asignar') AS programador
                FROM estaciones e
                LEFT JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
                ORDER BY programador, e.plaza, e.id_estacion;
            """
        else:
            query_base = f"""
                SELECT DISTINCT e.id_estacion, e.nombre AS estacion_nombre, e.tad AS proveedor,
                       e.plaza, ue.usuario AS programador
                FROM estaciones e
                JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
                WHERE ue.usuario = '{usuario_actual}'
                ORDER BY e.plaza, e.id_estacion;
            """

        df_estaciones = pd.read_sql(query_base, conn)
        if df_estaciones.empty:
            st.warning("No se encontraron registros de estaciones asignadas a tu usuario.")
            return

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if rol_actual == "admin":
                programadores_disponibles = sorted(df_estaciones["programador"].unique())
                selected_prog = st.selectbox(
                    "Programador / Usuario:", programadores_disponibles
                )
            else:
                selected_prog = usuario_actual
                st.text_input(
                    "Programador / Usuario:", value=selected_prog, disabled=True
                )

        df_filtrado_prog = df_estaciones[df_estaciones["programador"] == selected_prog]

        with col_f2:
            estaciones_nombres = [
                f"{row['id_estacion']} - {row['estacion_nombre']}"
                for _, row in df_filtrado_prog.drop_duplicates(subset=["id_estacion"]).iterrows()
            ]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este usuario.")
                return
            selected_est_str = st.selectbox("Selecciona la Estación:", estaciones_nombres)

        estacion_id_sel = selected_est_str.split(" - ")[0]
        row_estacion = df_filtrado_prog[
            df_filtrado_prog["id_estacion"] == estacion_id_sel
        ].iloc[0]

        capacidades, productos_disponibles_estacion = obtener_capacidades_por_estacion(
            conn, estacion_id_sel
        )

        st.markdown("---")
        st.markdown(f"### ⛽ {estacion_id_sel} - {row_estacion['estacion_nombre']}")
        st.markdown("---")

        tab_resumen, tab_gestion = st.tabs([
            "📊 Matriz Resumen (MRP)", "📝 Gestión de Órdenes de Carga"
        ])

        with tab_resumen:
            st.markdown("#### Vista Consolidada a 14 Días")
            st.write(
                "Suma de volúmenes por producto programados mediante Órdenes de "
                "Carga individuales (Considerando rango de volumen operativo entre "
                "5,000 L y capacidad máxima)."
            )

            dias_proyeccion = 14
            hoy = date.today()
            hoy_str = hoy.strftime("%Y-%m-%d")
            fechas = [hoy + timedelta(days=i) for i in range(dias_proyeccion)]

            col_names_matrix = [
                f"{DIAS_SEMANA[f.weekday()]} {f.day:02d}-{MESES[f.month - 1]}"
                for f in fechas
            ]

            cargas_guardadas = obtener_cargas_guardadas(conn, estacion_id_sel)
            inv_actuales, fecha_inventario = obtener_inventario_actual(conn, estacion_id_sel)

            def formato_inv_inicial(litros, fecha_inv):
                if pd.isna(fecha_inv):
                    return f"*{litros:,.0f} L"
                f_str = pd.to_datetime(fecha_inv).strftime("%Y-%m-%d")
                es_teorico = f_str < hoy_str
                prefijo = "*" if es_teorico else ""
                return f"{prefijo}{litros:,.0f} L"

            vdp_data_dict = {}
            try:
                query_vdp = f"""
                    SELECT producto, vdp_ponderada
                    FROM v_vdp_analisis
                    WHERE id_estacion = '{estacion_id_sel}';
                """
                df_vdp = pd.read_sql(query_vdp, conn)
                if not df_vdp.empty:
                    for _, r in df_vdp.iterrows():
                        p_name = str(r["producto"]).lower()
                        if "regular" in p_name or "magna" in p_name:
                            prod_k = "regular"
                        elif "premium" in p_name:
                            prod_k = "premium"
                        elif "diesel" in p_name:
                            prod_k = "diesel"
                        else:
                            continue
                        vdp_val = float(r["vdp_ponderada"]) if pd.notna(r["vdp_ponderada"]) else 0.0
                        factores = {i: 1.0 for i in range(7)}
                        vdp_data_dict[prod_k] = {"vdp": vdp_val, "factores": factores}
            except Exception as e:
                st.warning(f"Aviso al consultar VDP: {e}")

            productos_todos = [
                ("REGULAR", "regular", "<span style='color:#2ecc71;'>REGULAR</span>"),
                ("PREMIUM", "premium", "<span style='color:#e67e22;'>PREMIUM</span>"),
                ("DIESEL", "diesel", "<span style='color:#7f8c8d;'>DIESEL</span>"),
            ]

            for prod_label, prod_key, prod_title_html in productos_todos:
                if (
                    prod_key not in productos_disponibles_estacion
                    and capacidades.get(prod_key, 0.0) <= 0
                ):
                    continue

                st.markdown(f"#### {prod_title_html}", unsafe_allow_html=True)
                inv_ini_row, espacio_disp_row, carga_row, vta_row, inv_fin_row, ds_row = ([], [], [], [], [], [])
                inv_actual = inv_actuales.get(prod_key, 0.0)
                prod_info = vdp_data_dict.get(prod_key, {"vdp": 0.0, "factores": {i: 1.0 for i in range(7)}})
                vdp_base, factores_dia, cap_max = (
                    prod_info["vdp"],
                    prod_info["factores"],
                    capacidades.get(prod_key, 50000.0),
                )
                inv_fin_prev = 0.0

                for i, f_date in enumerate(fechas):
                    inv_ini = inv_actual if i == 0 else inv_fin_prev
                    inv_ini_str = (
                        formato_inv_inicial(inv_ini, fecha_inventario) if i == 0 else f"{inv_ini:,.0f}"
                    )
                    espacio_disp = cap_max - inv_ini
                    f_str_key = f_date.strftime("%Y-%m-%d")
                    carga = cargas_guardadas.get((f_str_key, prod_key), 0.0)
                    vta_proyectada = vdp_base * factores_dia.get(f_date.weekday(), 1.0)
                    inv_bruto = inv_ini + carga
                    volumen_operativo = max(5000.0, min(inv_bruto, cap_max))
                    inventario_disponible_para_venta = volumen_operativo - 5000.0
                    if inventario_disponible_para_venta <= 0:
                        vta = 0.0
                    else:
                        vta = min(vta_proyectada, inventario_disponible_para_venta)

                    inv_fin = inv_bruto - vta
                    inv_fin_prev = inv_fin
                    ds = (inv_fin / vta) if vta > 0 else 0.0

                    inv_fin_str = f"⚠️ {inv_fin:,.0f}" if inv_fin < 5000 else f"{inv_fin:,.0f}"
                    carga_str = (
                        f"⚠️ {carga:,.0f}"
                        if (carga > 0 and carga > espacio_disp)
                        else (f"{carga:,.0f}" if carga > 0 else "-")
                    )
                    ds_str = (
                        f"🔴 {ds:.1f} d"
                        if ds < 1.0
                        else (f"🟡 {ds:.1f} d" if ds < 2.0 else f"🟢 {ds:.1f} d")
                    )

                    inv_ini_row.append(inv_ini_str)
                    espacio_disp_row.append(f"{espacio_disp:,.0f}")
                    carga_row.append(carga_str)
                    vta_row.append(f"{vta:,.0f}")
                    inv_fin_row.append(inv_fin_str)
                    ds_row.append(ds_str)

                df_matriz = pd.DataFrame(
                    [
                        inv_ini_row,
                        espacio_disp_row,
                        carga_row,
                        vta_row,
                        inv_fin_row,
                        ds_row,
                    ],
                    index=[
                        "Inventario Inicial",
                        "Espacio disponible",
                        "Programa (Carga Total)",
                        "Venta Proyectada",
                        "Inventario Final",
                        "D/S (Final)",
                    ],
                    columns=col_names_matrix,
                )
                st.dataframe(df_matriz, use_container_width=True)
                st.markdown("")

        with tab_gestion:
            st.markdown(
                "#### 📋 Gestión, Alta, Modificación y Eliminación de Órdenes de Carga"
            )
            st.write(
                "Consulta el calendario de cargas registradas y administra "
                "individualmente cada orden mediante el selector unificado."
            )

            if "mensaje_exito_orden" in st.session_state:
                st.success(st.session_state["mensaje_exito_orden"])
                del st.session_state["mensaje_exito_orden"]

            try:
                df_ordenes = obtener_ordenes_estacion(conn, estacion_id_sel)
                st.markdown("##### 🔍 Órdenes de Carga Registradas")

                if df_ordenes.empty:
                    st.info("No hay órdenes de carga registradas para esta estación.")
                    opciones_gestion = ["Registrar Nueva Orden de Carga"]
                else:
                    calendario, fuera_de_rango = construir_calendario(
                        df_ordenes,
                        {p.upper() for p in productos_disponibles_estacion},
                        date.today(),
                    )

                    lunes_actual = date.today() - timedelta(days=date.today().weekday())
                    fecha_por_columna = {
                        c: lunes_actual + timedelta(days=i)
                        for i, c in enumerate(calendario.columns)
                    }

                    ordenes_idx = df_ordenes.assign(
                        _prod=df_ordenes["producto"].map(_clave_producto),
                        _fecha=pd.to_datetime(df_ordenes["fecha_programacion"]).dt.date,
                    )
                    huella = hashlib.md5(
                        "|".join(calendario.to_numpy().ravel()).encode()
                    ).hexdigest()[:8]

                    st.caption(
                        "Volumen programado por semana completa (lunes a domingo). "
                        "👆 Haz clic en una celda para autoseleccionar su folio abajo (o "
                        "en una vacía para crear una nueva)."
                    )
                    try:
                        evento = st.dataframe(
                            estilo_calendario(calendario),
                            use_container_width=True,
                            key=f"cal_ordenes_{estacion_id_sel}_{huella}",
                            on_select="rerun",
                            selection_mode="single-cell",
                        )
                    except Exception:
                        evento = None
                        st.dataframe(estilo_calendario(calendario), use_container_width=True)

                    celdas = ((evento.get("selection") or {}).get("cells") or []) if evento is not None else []
                    celda_clave, folios_celda, prod_celda, fecha_celda = (None, [], None, None)
                    if celdas:
                        fila_pos, col_nombre = celdas[0]
                        prod_celda = str(calendario.index[fila_pos]).upper()
                        celda_clave = (estacion_id_sel, prod_celda, col_nombre)
                        fecha_celda = fecha_por_columna.get(col_nombre)
                        folios_celda = sorted(
                            int(f)
                            for f in ordenes_idx.loc[
                                (ordenes_idx["_prod"] == prod_celda)
                                & (ordenes_idx["_fecha"] == fecha_celda),
                                "orden_carga",
                            ]
                        )

                    if celda_clave is None:
                        st.session_state.pop("_celda_orden_procesada", None)
                    elif st.session_state.get("_celda_orden_procesada") != celda_clave:
                        st.session_state["_celda_orden_procesada"] = celda_clave
                        if folios_celda:
                            st.session_state["folio_sel_orden"] = folios_celda[0]
                        else:
                            st.session_state["folio_sel_orden"] = "Registrar Nueva Orden de Carga"
                            st.session_state["prefill_fecha_alta"] = fecha_celda
                            st.session_state["prefill_prod_alta"] = prod_celda

                    if fuera_de_rango:
                        st.caption(
                            f"Hay {fuera_de_rango} orden(es) más allá del rango de las 2 semanas mostradas."
                        )

                    with st.expander("Ver detalle por folio"):
                        st.dataframe(df_ordenes, use_container_width=True, hide_index=True)

                    etiquetas_ordenes = {
                        int(r.orden_carga): (
                            f"#{int(r.orden_carga)} · {r.producto} · "
                            f"{_etiqueta_fecha(pd.to_datetime(r.fecha_programacion).date())} · "
                            f"{float(r.volumen_programado or 0):,.0f} L"
                        )
                        for r in df_ordenes.itertuples()
                    }
                    opciones_gestion = ["Registrar Nueva Orden de Carga"] + [
                        int(i) for i in df_ordenes["orden_carga"].tolist()
                    ]
                st.markdown("---")
                st.markdown("##### ⚙️ Formulario de Alta, Modificación o Eliminación")

                default_index = 0
                if (
                    "folio_sel_orden" in st.session_state
                    and st.session_state["folio_sel_orden"] in opciones_gestion
                ):
                    default_index = opciones_gestion.index(st.session_state["folio_sel_orden"])

                sel_opcion = st.selectbox(
                    "Selecciona acción o Folio a administrar:",
                    opciones_gestion,
                    index=default_index,
                    key="folio_sel_orden",
                    format_func=lambda x: (
                        "Registrar Nueva Orden de Carga"
                        if x == "Registrar Nueva Orden de Carga"
                        else etiquetas_ordenes.get(int(x), str(x))
                    ),
                )

                if sel_opcion == "Registrar Nueva Orden de Carga":
                    st.markdown("##### ➕ Registrar Nueva Orden de Carga")
                    val_fecha_default = st.session_state.pop("prefill_fecha_alta", date.today())
                    val_prod_default = st.session_state.pop("prefill_prod_alta", None)

                    with st.form("form_crear_orden_uni", clear_on_submit=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            sel_fecha_alta = st.date_input(
                                "Fecha de Programaci��n:", value=val_fecha_default
                            )
                        with c2:
                            prod_opciones = [
                                p[0]
                                for p in productos_todos
                                if p[1] in productos_disponibles_estacion
                                or capacidades.get(p[1], 0.0) > 0
                            ]
                            if not prod_opciones:
                                prod_opciones = ["REGULAR", "PREMIUM", "DIESEL"]
                            idx_prod_def = 0
                            if val_prod_default in prod_opciones:
                                idx_prod_def = prod_opciones.index(val_prod_default)
                            sel_prod_alta = st.selectbox(
                                "Producto:", prod_opciones, index=idx_prod_def
                            )
                        with c3:
                            sel_vol_alta = st.number_input(
                                "Volumen (Litros):",
                                min_value=1,
                                value=None,
                                step=1,
                                format="%d",
                                placeholder="Ingresa el volumen...",
                            )

                        submitted_alta = st.form_submit_button(
                            "🚀 Generar Orden de Carga", use_container_width=True
                        )
                        if submitted_alta:
                            if sel_vol_alta is None or sel_vol_alta <= 0:
                                st.warning("⚠️ Por favor ingresa un volumen válido mayor a 0 litros.")
                            else:
                                cursor = conn.cursor()
                                try:
                                    f_str = sel_fecha_alta.strftime("%Y-%m-%d")
                                    insert_query = f"""
                                        INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado)
                                        VALUES ('{estacion_id_sel}', '{sel_prod_alta}', '{f_str}', {sel_vol_alta});
                                    """
                                    cursor.execute(insert_query)
                                    conn.commit()
                                    cursor.close()
                                    st.session_state["mensaje_exito_orden"] = (
                                        f"✅ ¡Orden de Carga registrada exitosamente! "
                                        f"({sel_prod_alta} - {sel_vol_alta:,.0f} L para {f_str})"
                                    )
                                    st.rerun()
                                except Exception as err:
                                    conn.rollback()
                                    cursor.close()
                                    st.error(f"Error al registrar la orden: {err}")
                else:
                    sel_orden_id = int(sel_opcion)
                    row_orden_act = df_ordenes[df_ordenes["orden_carga"] == sel_orden_id].iloc[0]

                    col_info, col_btn_del = st.columns([3, 1], vertical_alignment="bottom")
                    with col_info:
                        st.markdown(f"##### ✏️ Modificar o Eliminar Orden de Carga #{sel_orden_id}")
                    with col_btn_del:
                        if st.button(
                            "🗑️ Eliminar Orden",
                            type="secondary",
                            use_container_width=True,
                            key=f"btn_del_{sel_orden_id}",
                        ):
                            detalles_orden = etiquetas_ordenes.get(
                                sel_orden_id, f"Folio #{sel_orden_id}"
                            )
                            confirmar_eliminacion(conn, sel_orden_id, detalles_orden)

                    sufijo_form = f"{sel_orden_id}_{row_orden_act['volumen_programado']}_{row_orden_act['fecha_programacion']}_{row_orden_act['producto']}"

                    with st.form("form_editar_orden_uni"):
                        ce1, ce2, ce3 = st.columns(3)
                        with ce1:
                            nueva_fecha = st.date_input(
                                "Modificar Fecha:",
                                value=pd.to_datetime(row_orden_act["fecha_programacion"]).date(),
                                key=f"ed_fecha_{sufijo_form}",
                            )
                        with ce2:
                            prod_actual = row_orden_act["producto"]
                            nuevo_prod = st.selectbox(
                                "Modificar Producto:",
                                ["REGULAR", "PREMIUM", "DIESEL"],
                                index=(0 if "REGULAR" in prod_actual.upper() else (1 if "PREMIUM" in prod_actual.upper() else 2)),
                                key=f"ed_prod_{sufijo_form}",
                            )
                        with ce3:
                            nuevo_vol = st.number_input(
                                "Modificar Volumen (L):",
                                value=int(float(row_orden_act["volumen_programado"])),
                                step=1,
                                format="%d",
                                key=f"ed_vol_{sufijo_form}",
                            )

                        submitted_update = st.form_submit_button(
                            "💾 Guardar Cambios en la Orden", use_container_width=True
                        )

                        if submitted_update:
                            cursor = conn.cursor()
                            try:
                                f_str_u = nueva_fecha.strftime("%Y-%m-%d")
                                q_upd = f"""
                                    UPDATE programacion_cargas
                                    SET volumen_programado = {nuevo_vol}, fecha_programacion = '{f_str_u}', producto = '{nuevo_prod}'
                                    WHERE id = {sel_orden_id};
                                """
                                cursor.execute(q_upd)
                                conn.commit()
                                cursor.close()
                                st.session_state["mensaje_exito_orden"] = (
                                    f"✅ Orden de Carga #{sel_orden_id} actualizada correctamente."
                                )
                                st.rerun()
                            except Exception as e_upd:
                                conn.rollback()
                                cursor.close()
                                st.error(f"Error al actualizar: {e_upd}")

            except Exception as e_ord:
                st.warning(f"Error al consultar las órdenes de carga: {e_ord}")

    except Exception as e:
        st.error(f"Error en la matriz de programación: {e}")


__all__ = ["render", "confirmar_eliminacion"]


# Reuse this variable for the form selection in the current module scope.
productos_todos = [
    ("REGULAR", "regular", "<span style='color:#2ecc71;'>REGULAR</span>"),
    ("PREMIUM", "premium", "<span style='color:#e67e22;'>PREMIUM</span>"),
    ("DIESEL", "diesel", "<span style='color:#7f8c8d;'>DIESEL</span>"),
]
