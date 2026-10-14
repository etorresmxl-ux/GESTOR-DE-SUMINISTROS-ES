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
        # 1. Consulta base de estaciones, plazas, proveedores/TAD y programadores si aplica
        # Ajustamos para obtener los datos necesarios para los filtros
        query_estaciones = """
            SELECT DISTINCT 
                id_estacion, 
                nombre, 
                tad as proveedor, 
                plaza,
                COALESCE(user_asignado, 'Yesenia') as programador
            FROM estaciones_detalle 
            ORDER BY id_estacion;
        """
        # Nota: Si tu columna de usuario tiene otro nombre en estaciones_detalle, la adaptamos. 
        # Como fallback por la imagen de referencia que usa 'Yesenia', manejamos un campo genérico o directo.
        
        # Vamos a hacer una consulta más segura trayendo las estaciones y uniendo con inventarios y vdp
        query_base = """
            SELECT 
                ed.id_estacion,
                ed.nombre as estacion_nombre,
                ed.plaza,
                ed.tad as proveedor,
                COALESCE(ed.usuario, 'Yesenia') as programador,
                ui.regular as inv_reg,
                ui.premium as inv_pre,
                ui.diesel as inv_die,
                COALESCE(vp.vdp_regular, 0) as vdp_reg,
                COALESCE(vp.vdp_premium, 0) as vdp_pre,
                COALESCE(vp.vdp_diesel, 0) as vdp_die
            FROM estaciones_detalle ed
            LEFT JOIN (
                SELECT estacion_id, regular, premium, diesel,
                       ROW_NUMBER() OVER(PARTITION BY estacion_id ORDER BY fecha DESC, turno DESC) as rn
                FROM inventarios_historico
            ) ui ON ed.id_estacion = ui.estacion_id AND ui.rn = 1
            LEFT JOIN vdp_ponderado_12w vp ON ed.id_estacion = vp.estacion_id;
        """
        
        df_base = pd.read_sql(query_base, conn)
        
        if df_base.empty:
            st.warning("No se encontraron registros en las tablas de estaciones e inventarios.")
            return

        # 2. Filtros Superiores: Programador y Nombre de Estación
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            programadores_disponibles = sorted(df_base['programador'].dropna().unique())
            selected_prog = st.selectbox("Selecciona el Programador:", programadores_disponibles)
            
        # Filtrar estaciones basadas en el programador seleccionado
        df_filtrado_prog = df_base[df_base['programador'] == selected_prog]
        
        with col_f2:
            estaciones_nombres = [f"{row['id_estacion']} - {row['estacion_nombre']}" for _, row in df_filtrado_prog.iterrows()]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este programador.")
                return
            selected_est_str = st.selectbox("Selecciona la Estación:", estaciones_nombres)
            
        # Obtener el ID de la estación seleccionada
        estacion_id_sel = selected_est_str.split(" - ")[0]
        row_estacion = df_base[df_base['id_estacion'] == estacion_id_sel].iloc[0]

        st.markdown("---")
        st.markdown(f"#### 🏢 Estación: {row_estacion['estacion_nombre']} (ID: {estacion_id_sel})")

        # Datos de cabecera comunes para las tablas de productos
        id_est = str(row_estacion['id_estacion'])
        nombre_est = str(row_estacion['estacion_nombre'])
        plaza_est = str(row_estacion['plaza'])
        prov_est = str(row_estacion['proveedor'])

        productos_config = [
            ("REGULAR", row_estacion['inv_reg'], row_estacion['vdp_reg']),
            ("PREMIUM", row_estacion['inv_pre'], row_estacion['vdp_pre']),
            ("DIESEL", row_estacion['inv_die'], row_estacion['vdp_die'])
        ]

        # 3. Renderizar una tabla por cada producto
        for prod_nombre, inv_inicial, vdp_val in productos_config:
            # Si el inventario o la vdp son nulos/cero, podemos omitir o mostrar con 0
            inv_ini = float(inv_inicial) if pd.notna(inv_inicial) else 0.0
            vdp = float(vdp_val) if pd.notna(vdp_val) else 0.0
            
            # Inventario final = Inventario Inicial - Venta Diaria Proyectada + Carga Programada (0)
            inv_final = inv_ini - vdp

            # Estructurar la tabla para este producto
            tabla_prod = pd.DataFrame({
                "id_estacion": [id_est],
                "Nombre": [nombre_est],
                "Plaza": [plaza_est],
                "Proveedor": [prov_est],
                "Inventario Inicial": [f"{inv_ini:,.0f} L"],
                "Venta Diaria Proyectada": [f"{vdp:,.0f} L"],
                "Carga Programada": ["-"],  # Vacío de momento para futura implementación
                "Inventario Final": [f"{inv_final:,.0f} L"]
            })

            st.markdown(f"##### ⛽ Producto: {prod_nombre}")
            st.dataframe(tabla_prod, width='stretch', hide_index=True)
            st.markdown("")

    except Exception as e:
        st.error(f"Error al generar el módulo de programación: {e}")
