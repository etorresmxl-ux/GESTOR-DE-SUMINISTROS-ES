import streamlit as st
import pandas as pd
from datetime import date, timedelta

def render(conn):
    st.markdown("### 🚛 Matriz de Programación y Suministro (MRP)")
    st.write("Planificación multicierre a 14 días por estación y producto con registro masivo de pedidos.")

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

        # Obtener capacidades máximas por producto para la estación
        capacidades = {}
        df_caps = df_filtrado_prog[df_filtrado_prog['id_estacion'] == estacion_id_sel]
        for _, r in df_caps.iterrows():
            p_key = str(r['producto']).lower()
            capacidades[p_key] = float(r['capacidad_maxima']) if pd.notna(r['capacidad_maxima']) else 100000.0

        # 3. Título Destacado con ID y Nombre de la Estación (Sin tabla de usuario/plaza)
        st.markdown("---")
        st.markdown(f"## ⛽ {estacion_id_sel} - {row_estacion['estacion_nombre']}")
        st.markdown("---")
        
        # 4. Definir rango de fechas (14 días a partir de hoy)
        dias_proyeccion = 14
        hoy = date.today()
        fechas = [hoy + timedelta(days=i) for i in range(dias_proyeccion)]
        
        dias_semana = ['lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.']
        meses = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']
        
        # Formato para las tablas de productos: "ddd. dd-mmm" (ej. jue. 15-oct.)
        col_names_matrix = [f"{dias_semana[f.weekday()]} {f.day:02d}-{meses[f.month-1]}" for f in fechas]
        
        # Formato exclusivo para el editor: "dd-mmm" (ej. 15-oct.)
        col_names_editor = [f"{f.day:02d}-{meses[f.month-1]}" for f in fechas]

        # Mapeo inverso de columnas del editor a objetos date para guardar
        col_to_date = {col_names_editor[i]: fechas[i] for i in range(len(fechas))}

        # 5. Consultar Cargas Programadas guardadas en la base de datos para esta estación
        cargas_guardadas = {} # {(fecha_str, producto): volumen}
        try:
            query_cargas_db = f"""
                SELECT fecha_programacion, producto, volumen_programado 
                FROM programacion_cargas 
                WHERE id_estacion = '{estacion_id_sel}';
            """
            df_cargas_db = pd.read_sql(query_cargas_db, conn)
            if not df_cargas_db.empty:
                for _, r in df_cargas_db.iterrows():
                    f_str = str(r['fecha_programacion']).split("T")[0]
                    p_str = str(r['producto']).strip().lower()
                    vol = float(r['volumen_programado']) if pd.notna(r['volumen_programado']) else 0.0
                    cargas_guardadas[(f_str, p_str)] = vol
        except Exception as e:
            st.warning(f"Aviso al cargar pedidos guardados: {e}")

        # 6. Obtener Inventario Inicial actual del producto (Sin turno)
        inv_actuales = {"regular": 0.0, "premium": 0.0, "diesel": 0.0}
        try:
            query_inv = f"""
                SELECT regular, premium, diesel 
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
        except Exception as e:
            st.warning(f"Aviso al consultar inventarios históricos: {e}")

        # 7. Obtener VDP Ponderada y Factores de Temporalidad por Día de la Semana
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
                    if 'regular' in p_name or 'magna' in p_name:
                        prod_k = 'regular'
                    elif 'premium' in p_name:
                        prod_k = 'premium'
                    elif 'diesel' in p_name:
                        prod_k = 'diesel'
                    else:
                        continue
                    
                    vdp_val = float(r['vdp_ponderada']) if pd.notna(r['vdp_ponderada']) else 0.0
                    factores = {
                        0: float(r['fact_real_lun']) if pd.notna(r['fact_real_lun']) else 1.0,
                        1: float(r['fact_real_mar']) if pd.notna(r['fact_real_mar']) else 1.0,
                        2: float(r['fact_real_mie']) if pd.notna(r['fact_real_mie']) else 1.0,
                        3: float(r['fact_real_jue']) if pd.notna(r['fact_real_jue']) else 1.0,
                        4: float(r['fact_real_vie']) if pd.notna(r['fact_real_vie']) else 1.0,
                        5: float(r['fact_real_sab']) if pd.notna(r['fact_real_sab']) else 1.0,
                        6: float(r['fact_real_dom']) if pd.notna(r['fact_real_dom']) else 1.0
                    }
                    vdp_data_dict[prod_k] = {'vdp': vdp_val, 'factores': factores}
        except Exception as e:
            st.warning(f"Aviso al consultar la VDP ponderada y factores: {e}")

        # 8. Renderizar Matriz por Producto (con col_names_matrix que incluye el día de la semana)
        productos = [
            ("REGULAR", "regular", "<span style='color:#2ecc71;'>REGULAR</span>"), 
            ("PREMIUM", "premium", "<span style='color:#e67e22;'>PREMIUM</span>"), 
            ("DIESEL", "diesel", "<span style='color:#7f8c8d;'>DIESEL</span>")
        ]

        for prod_label, prod_key, prod_title_html in productos:
            st.markdown(f"#### {prod_title_html}", unsafe_allow_html=True)
            
            inv_ini_row = []
            espacio_disp_row = []
            carga_row = []
            vta_row = []
            inv_fin_row = []
            ds_row = []
            pct_row = []

            inv_actual = inv_actuales.get(prod_key, 0.0)
            prod_info = vdp_data_dict.get(prod_key, {'vdp': 0.0, 'factores': {i: 1.0 for i in range(7)}})
            vdp_base = prod_info['vdp']
            factores_dia = prod_info['factores']
            
            cap_max = capacidades.get(prod_key, 100000.0)
            inv_fin_prev = 0.0

            for i, f_date in enumerate(fechas):
                if i == 0:
                    inv_ini = inv_actual
                else:
                    inv_ini = inv_fin_prev

                espacio_disp = cap_max - inv_ini
                f_str_key = f_date.strftime("%Y-%m-%d")
                carga = cargas_guardadas.get((f_str_key, prod_key), 0.0)
                
                dia_semana_idx = f_date.weekday()
                factor_estacionario = factores_dia.get(dia_semana_idx, 1.0)
                vta = vdp_base * factor_estacionario

                inv_fin = inv_ini + carga - vta
                inv_fin_prev = inv_fin

                ds = (inv_fin / vta) if vta > 0 else 0.0
                pct = (inv_fin / cap_max) * 100 if cap_max > 0 else 0.0

                inv_ini_row.append(f"{inv_ini:,.0f}")
                espacio_disp_row.append(f"{espacio_disp:,.0f}")
                carga_row.append(f"{carga:,.0f}" if carga > 0 else "-")
                vta_row.append(f"{vta:,.0f}")
                inv_fin_row.append(f"{inv_fin:,.0f}")
                ds_row.append(f"{ds:.1f} d")
                pct_row.append(f"{pct:.1f}%")

            df_matriz = pd.DataFrame(
                [
                    inv_ini_row,
                    espacio_disp_row,
                    carga_row,
                    vta_row,
                    inv_fin_row,
                    ds_row,
                    pct_row
                ],
                index=[
                    "Inventario Inicial",
                    "Espacio disponible",
                    "Programa (Carga)",
                    "Venta Proyectada",
                    "Inventario Final",
                    "D/S (Final)",
                    "% Tanque (Final)"
                ],
                columns=col_names_matrix
            )

            st.dataframe(df_matriz, width='stretch')
            st.markdown("")

        # 9. Sección Interactiva para Registrar / Actualizar Pedidos Masivos (con col_names_editor que usa solo dd-mmm)
        st.markdown("---")
        st.markdown("#### 📝 Editor de Programa de Carga (14 Días)")
        st.write("Modifica directamente los volúmenes de carga en la tabla inferior y haz clic en **Guardar Cambios**.")

        editor_data = {}
        for col_n in col_names_editor:
            f_obj = col_to_date[col_n]
            f_str_k = f_obj.strftime("%Y-%m-%d")
            editor_data[col_n] = [
                f"{cargas_guardadas.get((f_str_k, 'regular'), 0.0):,.0f}",
                f"{cargas_guardadas.get((f_str_k, 'premium'), 0.0):,.0f}",
                f"{cargas_guardadas.get((f_str_k, 'diesel'), 0.0):,.0f}"
            ]

        df_editor = pd.DataFrame(editor_data, index=["Regular", "Premium", "Diesel"])

        with st.form("form_editor_cargas"):
            edited_df = st.data_editor(
                df_editor, 
                width='stretch',
                key="editor_matriz_cargas"
            )
            
            submitted_editor = st.form_submit_button("💾 Guardar Todos los Cambios")
            
            if submitted_editor:
                user_actual = row_estacion['programador']
                cursor = conn.cursor()
                try:
                    for prod_name in ["Regular", "Premium", "Diesel"]:
                        p_str = prod_name.strip().lower()
                        for col_n in col_names_editor:
                            val_raw = edited_df.loc[prod_name, col_n]
                            
                            if isinstance(val_raw, str):
                                val_clean = val_raw.replace(',', '').strip()
                                volumen_val = float(val_clean) if val_clean and val_clean != '-' else 0.0
                            else:
                                volumen_val = float(val_raw) if pd.notna(val_raw) else 0.0

                            f_obj = col_to_date[col_n]
                            f_str = f_obj.strftime("%Y-%m-%d")
                            
                            check_query = f"""
                                SELECT id FROM programacion_cargas 
                                WHERE id_estacion = '{estacion_id_sel}' 
                                  AND fecha_programacion = '{f_str}' 
                                  AND LOWER(producto) = '{p_str}';
                            """
                            cursor.execute(check_query)
                            existing = cursor.fetchone()
                            
                            if existing:
                                update_query = f"""
                                    UPDATE programacion_cargas 
                                    SET volumen_programado = {volumen_val}, "user" = '{user_actual}'
                                    WHERE id_estacion = '{estacion_id_sel}' 
                                      AND fecha_programacion = '{f_str}' 
                                      AND LOWER(producto) = '{p_str}';
                                """
                                cursor.execute(update_query)
                            else:
                                if volumen_val > 0:
                                    insert_query = f"""
                                        INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado, "user")
                                        VALUES ('{estacion_id_sel}', '{prod_name}', '{f_str}', {volumen_val}, '{user_actual}');
                                    """
                                    cursor.execute(insert_query)
                                    
                    conn.commit()
                    cursor.close()
                    st.success("¡Programa de cargas actualizado correctamente en todas las fechas!")
                    st.rerun()
                except Exception as db_err:
                    conn.rollback()
                    cursor.close()
                    st.error(f"Error al guardar los pedidos en la base de datos: {db_err}")

    except Exception as e:
        st.error(f"Error al generar la matriz MRP: {e}")
