import streamlit as st
import pandas as pd
import numpy as np

def render(conn):
    st.markdown("### 🚛 Módulo de Programación y Control de Inventarios")
    st.write("Filtra por Programador y Estación para visualizar el balance diario por producto.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    try:
        # 1. Consultar todo directamente desde estaciones_detalle agrupando por usuario
        query_base = """
            SELECT DISTINCT 
                id_estacion, 
                nombre AS estacion_nombre, 
                tad AS proveedor, 
                plaza,
                "user" AS programador
            FROM estaciones_detalle
            WHERE "user" IS NOT NULL
            ORDER BY "user", id_estacion;
        """
        df_estaciones = pd.read_sql(query_base, conn)
        
        if df_estaciones.empty:
            st.warning("No se encontraron registros de estaciones o programadores en estaciones_detalle.")
            return

        # 2. Filtros Superiores: Programador y Nombre de Estación
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            programadores_disponibles = sorted(df_estaciones['programador'].dropna().unique())
            selected_prog = st.selectbox("Selecciona el Programador:", programadores_disponibles)
            
        # Filtrar estaciones basadas en el programador seleccionado
        df_filtrado_prog = df_estaciones[df_estaciones['programador'] == selected_prog]
        
        with col_f2:
            estaciones_nombres = [f"{row['id_estacion']} - {row['estacion_nombre']}" for _, row in df_filtrado_prog.iterrows()]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este programador.")
                return
            selected_est_str = st.selectbox("Selecciona la Estación:", estaciones_nombres)
            
        # Obtener el ID de la estación seleccionada
        estacion_id_sel = selected_est_str.split(" - ")[0]
        row_estacion = df_estaciones[df_estaciones['id_estacion'] == estacion_id_sel].iloc[0]

        # 3. Consultar Inventarios Actuales de la estación
        query_inv = f"""
            SELECT regular, premium, diesel 
            FROM inventarios_historico 
            WHERE estacion_id = '{estacion_id_sel}' 
            ORDER BY fecha DESC, turno DESC 
            LIMIT 1;
        """
        df_inv = pd.read_sql(query_inv, conn)
        inv_reg = df_inv['regular'].iloc[0] if not df_inv.empty and pd.notna(df_inv['regular'].iloc[0]) else 0.0
        inv_pre = df_inv['premium'].iloc[0] if not df_inv.empty and pd.notna(df_inv['premium'].iloc[0]) else 0.0
        inv_die = df_inv['diesel'].iloc[0] if not df_inv.empty and pd.notna(df_inv['diesel'].iloc[0]) else 0.0

        # 4. Consultar VDP Ponderada de la estación
        query_vdp = f"""
            SELECT producto, vdp_ponderada 
            FROM vw_factor_real_vdp_ponderada 
            WHERE estacion_id = '{estacion_id_sel}';
        """
        df_vdp = pd.read_sql(query_vdp, conn)
        
        vdp_reg, vdp_pre, vdp_die = 0.0, 0.0, 0.0
        if not df_vdp.empty:
            for _, r in df_vdp.iterrows():
                p_name = str(r['producto']).lower()
                val = r['vdp_ponderada'] if pd.notna(r['vdp_ponderada']) else 0.0
                if 'regular' in p_name or 'magna' in p_name:
                    vdp_reg = val
                elif 'premium' in p_name:
                    vdp_pre = val
                elif 'diesel' in p_name:
                    vdp_die = val

        st.markdown("---")
        st.markdown(f"#### 🏢 Estación: {row_estacion['estacion_nombre']} (ID: {estacion_id_sel})")

        id_est = str(row_estacion['id_estacion'])
        nombre_est = str(row_estacion['estacion_nombre'])
        plaza_est = str(row_estacion['plaza'])
        prov_est = str(row_estacion['proveedor'])

        productos_config = [
            ("REGULAR", inv_reg, vdp_reg),
            ("PREMIUM", inv_pre, vdp_pre),
            ("DIESEL", inv_die, vdp_die)
        ]

        # 5. Renderizar una tabla independiente por cada producto
        for prod_nombre, inv_inicial, vdp_val in productos_config:
            inv_ini = float(inv_inicial)
            vdp = float(vdp_val)
            inv_final = inv_ini - vdp

            tabla_prod = pd.DataFrame({
                "id_estacion": [id_est],
                "Nombre": [nombre_est],
                "Plaza": [plaza_est],
                "Proveedor": [prov_est],
                "Inventario Inicial": [f"{inv_ini:,.0f} L"],
                "Venta Diaria Proyectada": [f"{vdp:,.0f} L"],
                "Carga Programada": ["-"],
                "Inventario Final": [f"{inv_final:,.0f} L"]
            })

            st.markdown(f"##### ⛽ Producto: {prod_nombre}")
            st.dataframe(tabla_prod, width='stretch', hide_index=True)
            st.markdown("")

    except Exception as e:
        st.error(f"Error al generar el módulo de programación: {e}")
