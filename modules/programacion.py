import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 🚛 Programación y Suministro de Combustible")
    st.write("Planifica y visualiza el balance diario por producto y estación.")

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
                COALESCE(NULLIF("user", ''), 'Sin Asignar') AS programador
            FROM estaciones_detalle
            ORDER BY programador, plaza, id_estacion;
        """
        df_estaciones = pd.read_sql(query_base, conn)
        
        if df_estaciones.empty:
            st.warning("No se encontraron registros en estaciones_detalle.")
            return

        # 2. Filtros Superiores: Fecha, Programador y Estación
        col_f0, col_f1, col_f2 = st.columns(3)
        
        with col_f0:
            fecha_prog = st.date_input("Fecha de Programación", date.today())
            
        with col_f1:
            programadores_disponibles = sorted(df_estaciones['programador'].unique())
            selected_prog = st.selectbox("Programador / Usuario:", programadores_disponibles)
            
        # Filtrar estaciones según el programador seleccionado
        df_filtrado_prog = df_estaciones[df_estaciones['programador'] == selected_prog]
        
        with col_f2:
            estaciones_nombres = [f"{row['id_estacion']} - {row['estacion_nombre']}" for _, row in df_filtrado_prog.iterrows()]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este programador.")
                return
            selected_est_str = st.selectbox("Selecciona la Estación:", estaciones_nombres)
            
        estacion_id_sel = selected_est_str.split(" - ")[0]
        row_estacion = df_filtrado_prog[df_filtrado_prog['id_estacion'] == estacion_id_sel].iloc[0]

        # 3. Consultar Inventarios Actuales de la estación
        inv_reg, inv_pre, inv_die = 0.0, 0.0, 0.0
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
                inv_reg = float(df_inv['regular'].iloc[0]) if pd.notna(df_inv['regular'].iloc[0]) else 0.0
                inv_pre = float(df_inv['premium'].iloc[0]) if pd.notna(df_inv['premium'].iloc[0]) else 0.0
                inv_die = float(df_inv['diesel'].iloc[0]) if pd.notna(df_inv['diesel'].iloc[0]) else 0.0
        except Exception:
            pass

        # 4. Consultar VDP Ponderada (Venta Estimada del Día)
        vdp_reg, vdp_pre, vdp_die = 0.0, 0.0, 0.0
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
                        vdp_reg = val
                    elif 'premium' in p_name:
                        vdp_pre = val
                    elif 'diesel' in p_name:
                        vdp_die = val
        except Exception:
            pass

        # 5. Consultar Cargas Programadas para esta estación y fecha
        cargas_reg, cargas_pre, cargas_die = 0.0, 0.0, 0.0
        try:
            query_cargas = f"""
                SELECT producto, volumen_programado 
                FROM programacion_cargas 
                WHERE id_estacion = '{estacion_id_sel}' 
                  AND fecha_programacion = '{fecha_prog}';
            """
            df_cargas = pd.read_sql(query_cargas, conn)
            if not df_cargas.empty:
                for _, r in df_cargas.iterrows():
                    p_name = str(r['producto']).lower()
                    vol = float(r['volumen_programado']) if pd.notna(r['volumen_programado']) else 0.0
                    if 'regular' in p_name or 'magna' in p_name:
                        cargas_reg += vol
                    elif 'premium' in p_name:
                        cargas_pre += vol
                    elif 'diesel' in p_name:
                        cargas_die += vol
        except Exception:
            pass

        st.markdown("---")
        st.markdown(f"#### 🏢 Estación: {row_estacion['estacion_nombre']} (ID: {estacion_id_sel}) | Plaza: {row_estacion['plaza']}")

        id_est = str(row_estacion['id_estacion'])
        nombre_est = str(row_estacion['estacion_nombre'])
        plaza_est = str(row_estacion['plaza'])
        prov_est = str(row_estacion['proveedor'])

        # Configuración de productos: (Nombre, Inventario Actual, Venta Estimada, Carga Programada)
        productos_config = [
            ("REGULAR", inv_reg, vdp_reg, cargas_reg),
            ("PREMIUM", inv_pre, vdp_pre, cargas_pre),
            ("DIESEL", inv_die, vdp_die, cargas_die)
        ]

        # 6. Renderizar las tablas independientes por cada producto
        for prod_nombre, inv_inicial, vdp_val, carga_val in productos_config:
            inv_ini = float(inv_inicial)
            vdp = float(vdp_val)
            carga = float(carga_val)
            
            # Inventario Final = Inventario Actual - Venta Estimada + Carga Programada
            inv_final = inv_ini - vdp + carga

            tabla_prod = pd.DataFrame({
                "id_estacion": [id_est],
                "Nombre": [nombre_est],
                "Plaza": [plaza_est],
                "Proveedor": [prov_est],
                "Inventario Actual": [f"{inv_ini:,.0f} L"],
                "Venta Estimada Día": [f"{vdp:,.0f} L"],
                "Carga Programada": [f"{carga:,.0f} L"],
                "Inventario Final": [f"{inv_final:,.0f} L"]
            })

            st.markdown(f"##### ⛽ Producto: {prod_nombre}")
            st.dataframe(tabla_prod, width='stretch', hide_index=True)
            st.markdown("")

    except Exception as e:
        st.error(f"Error al generar el módulo de programación de cargas: {e}")
