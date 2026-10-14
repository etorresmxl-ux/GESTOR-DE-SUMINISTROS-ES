import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def render(conn):
    st.markdown("### 🚛 Módulo de Programación y Proyección de Inventarios (MRP)")
    st.write("Matriz de proyección operativa: Venta estimada, Compras, Inventario Final, Días de Suministro (D/S) y Capacidad %.")

    # 1. Selector de Estación
    query_estaciones = "SELECT DISTINCT id_estacion, nombre, tad, plaza FROM estaciones_detalle ORDER BY id_estacion;"
    try:
        df_estaciones = pd.read_sql(query_estaciones, conn)
        if df_estaciones.empty:
            st.warning("No hay estaciones registradas.")
            return

         estaciones_list = [f"{row['id_estacion']} - {row['nombre']}" for _, row in df_estaciones.iterrows()]
        selected_estacion_str = st.selectbox("Selecciona la Estación a Programar:", estaciones_list)
        estacion_id = selected_estacion_str.split(" - ")[0]

        # Obtener datos base de la estación seleccionada
        info_estacion = df_estaciones[df_estaciones['id_estacion'] == estacion_id].iloc[0]

        # 2. Consultar Inventarios Actuales de la estación
        query_inv = f"""
            SELECT regular, premium, diesel 
            FROM inventarios_historico 
            WHERE estacion_id = '{estacion_id}' 
            ORDER BY fecha DESC, turno DESC 
            LIMIT 1;
        """
        df_inv = pd.read_sql(query_inv, conn)
        inv_reg = df_inv['regular'].iloc[0] if not df_inv.empty and pd.notna(df_inv['regular'].iloc[0]) else 0.0
        inv_pre = df_inv['premium'].iloc[0] if not df_inv.empty and pd.notna(df_inv['premium'].iloc[0]) else 0.0
        inv_die = df_inv['diesel'].iloc[0] if not df_inv.empty and pd.notna(df_inv['diesel'].iloc[0]) else 0.0

        # 3. Consultar Capacidades Máximas
        query_cap = f"""
            SELECT 
                SUM(CASE WHEN producto ILIKE '%regular%' OR producto ILIKE '%magna%' THEN capacidad_maxima ELSE 0 END) as cap_regular,
                SUM(CASE WHEN producto ILIKE '%premium%' THEN capacidad_maxima ELSE 0 END) as cap_premium,
                SUM(CASE WHEN producto ILIKE '%diesel%' THEN capacidad_maxima ELSE 0 END) as cap_diesel
            FROM estaciones_detalle
            WHERE id_estacion = '{estacion_id}';
        """
        df_cap = pd.read_sql(query_cap, conn)
        cap_reg = df_cap['cap_regular'].iloc[0] if not df_cap.empty and pd.notna(df_cap['cap_regular'].iloc[0]) else 1.0
        cap_pre = df_cap['cap_premium'].iloc[0] if not df_cap.empty and pd.notna(df_cap['cap_premium'].iloc[0]) else 1.0
        cap_die = df_cap['cap_diesel'].iloc[0] if not df_cap.empty and pd.notna(df_cap['cap_diesel'].iloc[0]) else 1.0

        # 4. Consultar VDP Ponderada y Factores Reales de la estación
        query_factores = f"""
            SELECT producto, vdp_ponderada, 
                   fact_real_lun, fact_real_mar, fact_real_mie, fact_real_jue, 
                   fact_real_vie, fact_real_sab, fact_real_dom
            FROM vw_factor_real_vdp_ponderada
            WHERE estacion_id = '{estacion_id}';
        """
        df_factores = pd.read_sql(query_factores, conn)

        if df_factores.empty:
            st.warning("No se encontraron factores calculados para esta estación. Revisa la vista vw_factor_real_vdp_ponderada.")
            return

        # 5. Generar Línea de Tiempo (Próximos 8 días a partir de hoy)
        hoy = datetime.now().date()
        fechas = [hoy + timedelta(days=i) for i in range(8)]
        columnas_fechas = [f.strftime('%d-%b') for f in fechas]

        # Estructura para armar la tabla final tipo MRP
        filas_matriz = []
        productos = [('Regular', inv_reg, cap_reg, 'regular'), 
                     ('Premium', inv_pre, cap_pre, 'premium'), 
                     ('Diesel', inv_die, cap_die, 'diesel')]

        for prod_nombre, inv_actual, cap_max, prod_key in productos:
            # Buscar datos del producto
            prod_row = df_factores[df_factores['producto'] == prod_key]
            if prod_row.empty or prod_row['vdp_ponderada'].iloc[0] == 0:
                continue # Si no vende este producto, lo saltamos

            vdp = prod_row['vdp_ponderada'].iloc[0]
            factores = [
                prod_row['fact_real_lun'].iloc[0],
                prod_row['fact_real_mar'].iloc[0],
                prod_row['fact_real_mie'].iloc[0],
                prod_row['fact_real_jue'].iloc[0],
                prod_row['fact_real_vie'].iloc[0],
                prod_row['fact_real_sab'].iloc[0],
                prod_row['fact_real_dom'].iloc[0]
            ]

            # Calcular ventas estimadas para la línea de tiempo
            ventas_dia = []
            inventarios_dia = []
            ds_dia = []
            cap_pct_dia = []
            
            inv_rolling = inv_actual
            for idx, f_date in enumerate(fechas):
                # Determinar índice de día de la semana (0=Lunes ... 6=Domingo)
                isodow = f_date.isoweekday() - 1 # 0 a 6
                factor_hoy = factores[isodow]
                venta_est = round(vdp * factor_hoy, 0)
                ventas_dia.append(venta_est)

                # Compra programada por defecto en 0 (puedes enlazarla a tu tabla de pedidos despues)
                compra_est = 0.0 

                # Inventario final del día
                inv_rolling = inv_rolling + compra_est - venta_est
                inventarios_dia.append(round(inv_rolling, 0))

                # Días de Suministro (D/S)
                ds = round(inv_rolling / vdp, 1) if vdp > 0 else 0.0
                ds_dia.append(ds)

                # Capacidad %
                cap_p = round((inv_rolling / cap_max) * 100, 0) if cap_max > 0 else 0.0
                cap_pct_dia.append(f"{cap_p:.0f}%")

            # Crear las filas estilo MRP para este producto
            base_meta = {
                "User": "Sistema",
                "ID": estacion_id,
                "Destino": str(info_estacion.get('tad', '')),
                "TAD": str(info_estacion.get('tad', '')),
                "Grupo": str(info_estacion.get('plaza', '')),
                "Estacion": info_estacion['nombre'],
                "Producto": prod_nombre
            }

            # Fila Venta
            f_venta = base_meta.copy()
            f_venta["MRP"] = "Venta"
            f_venta["Inv Actual"] = f"{inv_actual:,.0f}"
            for c_name, val in zip(columnas_fechas, ventas_dia):
                f_venta[c_name] = f"{val:,.0f}"
            filas_matriz.append(f_venta)

            # Fila Compra
            f_compra = base_meta.copy()
            f_compra["MRP"] = "Compra"
            f_compra["Inv Actual"] = f"{inv_actual:,.0f}"
            for c_name in columnas_fechas:
                f_compra[c_name] = "0"
            filas_matriz.append(f_compra)

            # Fila Inventario
            f_inv = base_meta.copy()
            f_inv["MRP"] = "Inventario"
            f_inv["Inv Actual"] = f"{inv_actual:,.0f}"
            for c_name, val in zip(columnas_fechas, inventarios_dia):
                f_inv[c_name] = f"{val:,.0f}"
            filas_matriz.append(f_inv)

            # Fila D/S
            f_ds = base_meta.copy()
            f_ds["MRP"] = "D/S"
            f_ds["Inv Actual"] = f"{inv_actual:,.0f}"
            for c_name, val in zip(columnas_fechas, ds_dia):
                f_ds[c_name] = f"{val:.1f}"
            filas_matriz.append(f_ds)

            # Fila Capacidad %
            f_cap = base_meta.copy()
            f_cap["MRP"] = "Capacidad %"
            f_cap["Inv Actual"] = f"{inv_actual:,.0f}"
            for c_name, val in zip(columnas_fechas, cap_pct_dia):
                f_cap[c_name] = val
            filas_matriz.append(f_cap)

        # Renderizar la tabla final en Streamlit
        df_matriz = pd.DataFrame(filas_matriz)
        st.dataframe(df_matriz, width='stretch', height=500, hide_index=True)

    except Exception as e:
        st.error(f"Error al generar la matriz de programación: {e}")
