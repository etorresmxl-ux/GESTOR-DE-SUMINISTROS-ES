import streamlit as st
import pandas as pd
from datetime import date, timedelta

def render(conn):
    st.markdown("### 🚛 Matriz de Programación y Suministro (MRP)")
    st.write("Planificación multicierre a 14 días por estación y producto.")

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

        # 3. Cabecera de Información de la Estación (Estilo de la imagen)
        st.markdown("---")
        st.markdown(f"""
        | User | ID Estación | Destino (TAD) | Proveedor | Estación | Plaza |
        | :--- | :--- | :--- | :--- | :--- | :--- |
        | **{row_estacion['programador']}** | **{estacion_id_sel}** | **{row_estacion['proveedor']}** | **{row_estacion.get('tad', 'N/A')}** | **{row_estacion['estacion_nombre']}** | **{row_estacion['plaza']}** |
        """)
        st.markdown("---")

        # 4. Definir rango de fechas (14 días a partir de hoy)
        dias_proyeccion = 14
        hoy = date.today()
        fechas = [hoy + timedelta(days=i) for i in range(dias_proyeccion)]
        
        # Generar nombres de columnas formateados (ej. "lun. 12-oct")
        dias_semana = ['lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.']
        meses = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']
        col_names = [f"{dias_semana[f.weekday()]} {f.day:02d}-{meses[f.month-1]}" for f in fechas]

        # 5. Obtener Inventario Inicial actual del producto
        inv_actuales = {"regular": 0.0, "premium": 0.0, "diesel": 0.0}
        try:
            query_inv = f"""
                SELECT regular, premium, diesel 
                FROM inventarios_historico 
                WHERE estacion_id = '{estacion_id_sel}' 
                ORDER BY fecha DESC, turno DESC 
                LIMIT 1;
            """
            df_inv = pd.read_sql(query_inv, conn)
            if not df_inv.empty:
                inv_actuales['regular'] = float(df_inv['regular'].iloc[0]) if pd.notna(df_inv['regular'].iloc[0]) else 0.0
                inv_actuales['premium'] = float(df_inv['premium'].iloc[0]) if pd.notna(df_inv['premium'].iloc[0]) else 0.0
                inv_actuales['diesel'] = float(df_inv['diesel'].iloc[0]) if pd.notna(df_inv['diesel'].iloc[0]) else 0.0
        except Exception:
            pass

        # 6. Obtener VDP Ponderada (Venta Proyectada Diaria)
        vdp_dict = {"regular": 0.0, "premium": 0.0, "diesel": 0.0}
        try:
            query_vdp = f"""
                SELECT producto, vdp_ponderada 
                FROM vw_factor_real_vdp_ponderada 
                WHERE estacion_id = '{estacion_id_sel}';
            """
            df_vdp = pd.read_sql(query_vdp, conn)
            if not df_vdp.empty:
                for _, r in df_vdp.iterrows():
                    p_name = str(r['producto']).lower()
                    val = float(r['vdp_ponderada']) if pd.notna(r['vdp_ponderada']) else 0.0
                    if 'regular' in p_name or 'magna' in p_name:
                        vdp_dict['regular'] = val
                    elif 'premium' in p_name:
                        vdp_dict['premium'] = val
                    elif 'diesel' in p_name:
                        vdp_dict['diesel'] = val
        except Exception:
            pass

        # 7. Renderizar Matriz por Producto
        productos = [("REGULAR", "regular"), ("PREMIUM", "premium"), ("DIESEL", "diesel")]

        for prod_label, prod_key in productos:
            st.markdown(f"#### ⛽ {prod_label}")
            
            # Construir filas para los 14 días
            inv_ini_row = []
            carga_row = []
            vta_row = []
            inv_fin_row = []
            ds_row = []
            pct_row = []

            inv_actual = inv_actuales.get(prod_key, 0.0)
            vdp_val = vdp_dict.get(prod_key, 0.0)
            cap_max = capacidades.get(prod_key, 100000.0)

            for i, f_date in enumerate(fechas):
                # Inventario inicial del día (el primer día usa el real, los siguientes usan el final del día anterior)
                if i == 0:
                    inv_ini = inv_actual
                else:
                    inv_ini = inv_fin_prev

                # Carga programada (por defecto 0 o consultada de la BD)
                carga = 0.0 
                
                # Venta proyectada
                vta = vdp_val

                # Inventario final
                inv_fin = inv_ini + carga - vta
                inv_fin_prev = inv_fin

                # D/S (Days of Supply) = Inventario Final / Venta Proyectada
                ds = (inv_fin / vta) if vta > 0 else 0.0

                # % Tanque (Final) = Inventario Final / Capacidad Máxima
                pct = (inv_fin / cap_max) * 100 if cap_max > 0 else 0.0

                # Formato de valores
                inv_ini_row.append(f"{inv_ini:,.0f}")
                carga_row.append(f"{carga:,.0f}")
                vta_row.append(f"{vta:,.0f}")
                inv_fin_row.append(f"{inv_fin:,.0f}")
                ds_row.append(f"{ds:.1f} d")
                pct_row.append(f"{pct:.1f}%")

            # Crear DataFrame con el layout exacto de la matriz
            df_matriz = pd.DataFrame(
                [
                    inv_ini_row,
                    carga_row,
                    vta_row,
                    inv_fin_row,
                    ds_row,
                    pct_row
                ],
                index=[
                    "Inventario Inicial",
                    "Programa (Carga)",
                    "Venta Proyectada",
                    "Inventario Final",
                    "D/S (Final)",
                    "% Tanque (Final)"
                ],
                columns=col_names
            )

            st.dataframe(df_matriz, width='stretch')
            st.markdown("")

    except Exception as e:
        st.error(f"Error al generar la matriz MRP: {e}")
