import streamlit as st
import pandas as pd
from datetime import date, timedelta

def render(conn):
    st.markdown("### 🚛 Matriz de Programación y Gestión de Órdenes")
    st.write("Administra de forma independiente cada Orden de Carga (Folio) y visualiza el resumen consolidado a 14 días.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    try:
        # 1. Consultar estaciones y programadores desde estaciones_detalle
        query_base = """
            SELECT DISTINCT 
                id_estacion, 
                nombre AS estacion_nombre, 
                tad AS proveedor, 
                plaza,
                COALESCE(NULLIF("user", ''), 'Sin Asignar') AS programador,
                capacidad_maxima,
                producto
            FROM estaciones_detalle
            ORDER BY programador, plaza, id_estacion;
        """
        df_estaciones = pd.read_sql(query_base, conn)
        
        if df_estaciones.empty:
            st.warning("No se encontraron registros en estaciones_detalle.")
            return

        # 2. Filtros Superiores de Navegación
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            programadores_disponibles = sorted(df_estaciones['programador'].unique())
            selected_prog = st.selectbox("Programador / Usuario:", programadores_disponibles)
            
        df_filtrado_prog = df_estaciones[df_estaciones['programador'] == selected_prog]
        
        with col_f2:
            estaciones_nombres = [f"{row['id_estacion']} - {row['estacion_nombre']}" for _, row in df_filtrado_prog.drop_duplicates(subset=['id_estacion']).iterrows()]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este programador.")
                return
            selected_est_str = st.selectbox("Selecciona la Estación:", estaciones_nombres)
            
        estacion_id_sel = selected_est_str.split(" - ")[0]
        row_estacion = df_filtrado_prog[df_filtrado_prog['id_estacion'] == estacion_id_sel].iloc[0]

        # Obtener capacidades máximas por producto y verificar qué productos maneja la estación
        capacidades = {}
        productos_disponibles_estacion = set()
        df_caps = df_filtrado_prog[df_filtrado_prog['id_estacion'] == estacion_id_sel]
        for _, r in df_caps.iterrows():
            p_raw = str(r['producto']).strip().lower()
            cap = float(r['capacidad_maxima']) if pd.notna(r['capacidad_maxima']) else 0.0
            
            if 'regular' in p_raw or 'magna' in p_raw:
                p_key = 'regular'
            elif 'premium' in p_raw:
                p_key = 'premium'
            elif 'diesel' in p_raw:
                p_key = 'diesel'
            else:
                p_key = p_raw
                
            capacidades[p_key] = cap
            if cap > 0:
                productos_disponibles_estacion.add(p_key)

        # 3. Título Destacado con ID y Nombre de la Estación
        st.markdown("---")
        st.markdown(f"## ⛽ {estacion_id_sel} - {row_estacion['estacion_nombre']}")
        st.markdown("---")

        # Pestañas principales del módulo
        tab_resumen, tab_gestion = st.tabs(["📊 Matriz Resumen (MRP)", "📝 Gestión de Órdenes de Carga"])

        # ==========================================
        # PESTAÑA 1: MATRIZ RESUMEN (MRP)
        # ==========================================
        with tab_resumen:
            st.markdown("#### Vista Consolidada a 14 Días")
            st.write("Suma de volúmenes por producto programados mediante Órdenes de Carga individuales.")

            dias_proyeccion = 14
            hoy = date.today()
            hoy_str = hoy.strftime("%Y-%m-%d")
            fechas = [hoy + timedelta(days=i) for i in range(dias_proyeccion)]
            
            dias_semana = ['lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.']
            meses = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']
            col_names_matrix = [f"{dias_semana[f.weekday()]} {f.day:02d}-{meses[f.month-1]}" for f in fechas]

            # Consultar cargas programadas sumadas por fecha y producto
            cargas_guardadas = {}
            try:
                query_cargas_db = f"""
                    SELECT fecha_programacion, producto, SUM(volumen_programado) as total_vol 
                    FROM programacion_cargas 
                    WHERE id_estacion = '{estacion_id_sel}'
                    GROUP BY fecha_programacion, producto;
                """
                df_cargas_db = pd.read_sql(query_cargas_db, conn)
                if not df_cargas_db.empty:
                    for _, r in df_cargas_db.iterrows():
                        f_str = str(r['fecha_programacion']).split("T")[0]
                        p_str = str(r['producto']).strip().lower()
                        vol = float(r['total_vol']) if pd.notna(r['total_vol']) else 0.0
                        cargas_guardadas[(f_str, p_str)] = vol
            except Exception as e:
                st.warning(f"Aviso al cargar pedidos: {e}")

            # Inventario actual
            inv_actuales = {"regular": 0.0, "premium": 0.0, "diesel": 0.0}
            fecha_inventario = None
            try:
                query_inv = f"""
                    SELECT fecha, regular, premium, diesel 
                    FROM inventarios_historico 
                    WHERE estacion_id = '{estacion_id_sel}' 
                    ORDER BY fecha DESC 
                    LIMIT 1;
                """
                df_inv = pd.read_sql(query_inv, conn)
                if not df_inv.empty:
                    inv_actuales['regular'] = float(df_inv['regular'].iloc[0]) if pd.notna(df_inv['regular'].iloc[0]) else 0.0
                    inv_actuales['premium'] = float(df_inv['premium'].iloc[0]) if pd.notna(df_inv['premium'].iloc[0]) else 0.0
                    inv_actuales['diesel'] = float(df_inv['diesel'].iloc[0]) if pd.notna(df_inv['diesel'].iloc[0]) else 0.0
                    fecha_inventario = df_inv['fecha'].iloc[0]
            except Exception as e:
                st.warning(f"Aviso al consultar inventarios: {e}")

            def formato_inv_inicial(litros, fecha_inv):
                if pd.isna(fecha_inv):
                    return f"*{litros:,.0f} L"
                f_str = pd.to_datetime(fecha_inv).strftime("%Y-%m-%d")
                es_teorico = f_str < hoy_str
                prefijo = "*" if es_teorico else ""
                return f"{prefijo}{litros:,.0f} L"

            # VDP y factores
            vdp_data_dict = {}
            try:
                query_vdp = f"""
                    SELECT producto, vdp_ponderada, 
                           fact_real_lun, fact_real_mar, fact_real_mie, 
                           fact_real_jue, fact_real_vie, fact_real_sab, fact_real_dom 
                    FROM vw_factor_real_vdp_ponderada 
                    WHERE estacion_id = '{estacion_id_sel}';
                """
                df_vdp = pd.read_sql(query_vdp, conn)
                if not df_vdp.empty:
                    for _, r in df_vdp.iterrows():
                        p_name = str(r['producto']).lower()
                        prod_k = 'regular' if ('regular' in p_name or 'magna' in p_name) else ('premium' if 'premium' in p_name else ('diesel' if 'diesel' in p_name else ''))
                        if not prod_k: continue
                        vdp_val = float(r['vdp_ponderada']) if pd.notna(r['vdp_ponderada']) else 0.0
                        factores = {i: float(r[f'fact_real_{["lun","mar","mie","jue","vie","sab","dom"][i]}']) if pd.notna(r[f'fact_real_{["lun","mar","mie","jue","vie","sab","dom"][i]}']) else 1.0 for i in range(7)}
                        vdp_data_dict[prod_k] = {'vdp': vdp_val, 'factores': factores}
            except Exception as e:
                st.warning(f"Aviso al consultar VDP: {e}")

            productos_todos = [
                ("REGULAR", "regular", "<span style='color:#2ecc71;'>REGULAR</span>"), 
                ("PREMIUM", "premium", "<span style='color:#e67e22;'>PREMIUM</span>"), 
                ("DIESEL", "diesel", "<span style='color:#7f8c8d;'>DIESEL</span>")
            ]

            for prod_label, prod_key, prod_title_html in productos_todos:
                if prod_key not in productos_disponibles_estacion and capacidades.get(prod_key, 0.0) <= 0:
                    continue

                st.markdown(f"#### {prod_title_html}", unsafe_allow_html=True)
                
                inv_ini_row, espacio_disp_row, carga_row, vta_row, inv_fin_row, ds_row = [], [], [], [], [], []
                inv_actual = inv_actuales.get(prod_key, 0.0)
                prod_info = vdp_data_dict.get(prod_key, {'vdp': 0.0, 'factores': {i: 1.0 for i in range(7)}})
                vdp_base, factores_dia, cap_max = prod_info['vdp'], prod_info['factores'], capacidades.get(prod_key, 100000.0)
                inv_fin_prev = 0.0

                for i, f_date in enumerate(fechas):
                    inv_ini = inv_actual if i == 0 else inv_fin_prev
                    inv_ini_str = formato_inv_inicial(inv_ini, fecha_inventario) if i == 0 else f"{inv_ini:,.0f}"

                    espacio_disp = cap_max - inv_ini
                    f_str_key = f_date.strftime("%Y-%m-%d")
                    carga = cargas_guardadas.get((f_str_key, prod_key), 0.0)
                    
                    vta = vdp_base * factores_dia.get(f_date.weekday(), 1.0)
                    inv_fin = inv_ini + carga - vta
                    inv_fin_prev = inv_fin
                    ds = (inv_fin / vta) if vta > 0 else 0.0

                    inv_fin_str = f"⚠️ {inv_fin:,.0f}" if inv_fin < 5000 else f"{inv_fin:,.0f}"
                    carga_str = f"⚠️ {carga:,.0f}" if (carga > 0 and carga > espacio_disp) else (f"{carga:,.0f}" if carga > 0 else "-")
                    ds_str = f"🔴 {ds:.1f} d" if ds < 1.0 else (f"🟡 {ds:.1f} d" if ds < 2.0 else f"🟢 {ds:.1f} d")

                    inv_ini_row.append(inv_ini_str)
                    espacio_disp_row.append(f"{espacio_disp:,.0f}")
                    carga_row.append(carga_str)
                    vta_row.append(f"{vta:,.0f}")
                    inv_fin_row.append(inv_fin_str)
                    ds_row.append(ds_str)

                df_matriz = pd.DataFrame(
                    [inv_ini_row, espacio_disp_row, carga_row, vta_row, inv_fin_row, ds_row],
                    index=["Inventario Inicial", "Espacio disponible", "Programa (Carga Total)", "Venta Proyectada", "Inventario Final", "D/S (Final)"],
                    columns=col_names_matrix
                )
                st.dataframe(df_matriz, width='stretch')
                st.markdown("")

        # ==========================================
        # PESTAÑA 2: GESTIÓN DE ÓRDENES DE CARGA
        # ==========================================
        with tab_gestion:
            st.markdown("#### 📋 Alta, Modificación y Eliminación de Órdenes de Carga")
            st.write("Crea órdenes independientes (soporta múltiples cargas el mismo día). **Candado activo:** No se permiten fechas de programación pasadas.")

            # Formulario de alta
            with st.form("form_crear_orden_carga"):
                st.markdown("##### ➕ Registrar Nueva Orden de Carga")
                c1, c2, c3 = st.columns(3)
                with c1:
                    prod_opciones = [p[0] for p in productos_todos if p[1] in productos_disponibles_estacion or capacidades.get(p[1], 0.0) > 0]
                    if not prod_opciones: prod_opciones = ["REGULAR", "PREMIUM", "DIESEL"]
                    sel_prod_alta = st.selectbox("Producto:", prod_opciones)
                with c2:
                    # Candado: min_value es hoy
                    sel_fecha_alta = st.date_input("Fecha de Programación:", value=date.today(), min_value=date.today())
                with c3:
                    sel_vol_alta = st.number_input("Volumen (Litros):", min_value=100.0, value=20000.0, step=100.0)

                submitted_alta = st.form_submit_button("🚀 Generar Orden de Carga")
                if submitted_alta:
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
                        st.success("✅ ¡Orden de Carga generada con éxito!")
                        st.rerun()
                    except Exception as err:
                        conn.rollback()
                        cursor.close()
                        st.error(f"Error al registrar la orden: {err}")

            st.markdown("---")
            st.markdown("##### 🔍 Órdenes de Carga Registradas (Vigentes y Futuras)")
            
            try:
                query_tabla_ordenes = f"""
                    SELECT id AS orden_carga, producto, fecha_programacion, volumen_programado, creado_en
                    FROM programacion_cargas
                    WHERE id_estacion = '{estacion_id_sel}' AND fecha_programacion >= '{date.today().strftime("%Y-%m-%d")}'
                    ORDER BY fecha_programacion ASC;
                """
                df_ordenes = pd.read_sql(query_tabla_ordenes, conn)

                if df_ordenes.empty:
                    st.info("No hay órdenes de carga activas para esta estación.")
                else:
                    st.dataframe(df_ordenes, width='stretch', hide_index=True)

                    st.markdown("##### ⚙️ Modificar o Eliminar una Orden de Carga")
                    col_id_sel, col_acc = st.columns(2)
                    with col_id_sel:
                        ids_disponibles = df_ordenes['orden_carga'].tolist()
                        sel_orden_id = st.selectbox("Selecciona el Folio (Orden de Carga) a administrar:", ids_disponibles)
                    
                    row_orden_act = df_ordenes[df_ordenes['orden_carga'] == sel_orden_id].iloc[0]

                    with st.form("form_editar_orden"):
                        ce1, ce2, ce3 = st.columns(3)
                        with ce1:
                            nuevo_vol = st.number_input("Modificar Volumen (L):", value=float(row_orden_act['volumen_programado']), step=100.0)
                        with ce2:
                            fecha_actual_obj = pd.to_datetime(row_orden_act['fecha_programacion']).date()
                            nueva_fecha = st.date_input("Modificar Fecha:", value=fecha_actual_obj, min_value=date.today())
                        with ce3:
                            prod_actual = row_orden_act['producto']
                            nuevo_prod = st.selectbox("Modificar Producto:", ["REGULAR", "PREMIUM", "DIESEL"], index=0 if "REGULAR" in prod_actual.upper() else (1 if "PREMIUM" in prod_actual.upper() else 2))

                        b_upd, b_del = st.columns(2)
                        with b_upd:
                            submitted_update = st.form_submit_button("💾 Guardar Cambios en la Orden")
                        with b_del:
                            submitted_delete = st.form_submit_button("🗑️ Eliminar Orden de Carga", type="primary")

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
                                st.success(f"✅ Orden de Carga #{sel_orden_id} actualizada correctamente.")
                                st.rerun()
                            except Exception as e_upd:
                                conn.rollback()
                                cursor.close()
                                st.error(f"Error al actualizar: {e_upd}")

                        if submitted_delete:
                            cursor = conn.cursor()
                            try:
                                q_del = f"DELETE FROM programacion_cargas WHERE id = {sel_orden_id};"
                                cursor.execute(q_del)
                                conn.commit()
                                cursor.close()
                                st.success(f"🗑️ Orden de Carga #{sel_orden_id} eliminada del sistema.")
                                st.rerun()
                            except Exception as e_del:
                                conn.rollback()
                                cursor.close()
                                st.error(f"Error al eliminar: {e_del}")

            except Exception as e_ord:
                st.warning(f"Error al consultar las órdenes de carga: {e_ord}")

    except Exception as e:
        st.error(f"Error en la matriz de programación: {e}")
