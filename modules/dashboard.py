import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def normalizar_producto(producto_raw):
    """
    Normaliza cualquier variante de producto a una llave estándar:
    'regular', 'premium', 'diesel' o el texto original limpio si no coincide.
    """
    if pd.isna(producto_raw):
        return ""
    
    p_str = str(producto_raw).strip().lower()
    
    if 'regular' in p_str or 'magna' in p_str:
        return 'regular'
    elif 'premium' in p_str:
        return 'premium'
    elif 'diesel' in p_str:
        return 'diesel'
    else:
        return p_str

def render(conn):
    # Definir fecha y hora local (UTC-7 / Noroeste / Mexicali) para los cálculos
    tz_local = timezone(timedelta(hours=-7))
    ahora_local = datetime.now(tz_local)
    hoy = ahora_local.date()
    hoy_str = hoy.strftime("%Y-%m-%d")

    # Indicador de fecha y hora local en el menú lateral (inferior)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='text-align: center; color: #aaa; font-size: 0.85em; padding: 10px;'>"
        f"🕒 <b>Reloj del Sistema</b><br>"
        f"📅 {ahora_local.strftime('%Y-%m-%d')}<br>"
        f"⏱️ {ahora_local.strftime('%H:%M:%S')} (UTC-7)"
        f"</div>",
        unsafe_allow_html=True
    )

    st.markdown("### 📊 Dashboard Operativo - Inventarios, Espacio Disponible y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario teórico/actualizado al día de hoy (con indicador * si es arrastrado), capacidad máxima, cargas del día y Días de Suministro (VDP 12 semanas).")
    
    query = """
        WITH ultimo_inventario AS (
            SELECT 
                estacion_id,
                fecha,
                regular,
                premium,
                diesel,
                ROW_NUMBER() OVER(PARTITION BY estacion_id ORDER BY fecha DESC) as rn
            FROM inventarios_historico
        ),
        capacidades_productos AS (
            SELECT 
                id_estacion,
                SUM(CASE WHEN producto ILIKE '%regular%' OR producto ILIKE '%magna%' THEN capacidad_maxima ELSE 0 END) as cap_regular,
                SUM(CASE WHEN producto ILIKE '%premium%' THEN capacidad_maxima ELSE 0 END) as cap_premium,
                SUM(CASE WHEN producto ILIKE '%diesel%' THEN capacidad_maxima ELSE 0 END) as cap_diesel
            FROM estaciones_detalle
            GROUP BY id_estacion
        ),
        info_base AS (
            SELECT DISTINCT 
                id_estacion,
                tad,
                plaza,
                nombre as estacion
            FROM estaciones_detalle
        )
        SELECT 
            ib.id_estacion,
            ib.tad,
            ib.plaza,
            ib.estacion,
            COALESCE(cp.cap_regular, 0) as cap_regular,
            COALESCE(cp.cap_premium, 0) as cap_premium,
            COALESCE(cp.cap_diesel, 0) as cap_diesel,
            COALESCE(ui.regular, 0) as reg_litros,
            COALESCE(ui.premium, 0) as pre_litros,
            COALESCE(ui.diesel, 0) as die_litros,
            ui.fecha as fecha_inventario,
            COALESCE(vp.vdp_regular, 0) as vdp_reg,
            COALESCE(vp.vdp_premium, 0) as vdp_pre,
            COALESCE(vp.vdp_diesel, 0) as vdp_die
        FROM info_base ib
        LEFT JOIN ultimo_inventario ui ON ib.id_estacion = ui.estacion_id AND ui.rn = 1
        LEFT JOIN capacidades_productos cp ON ib.id_estacion = cp.id_estacion
        LEFT JOIN vdp_ponderado_12w vp ON ib.id_estacion = vp.estacion_id
        ORDER BY ib.id_estacion;
    """
    
    try:
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("No hay datos suficientes para generar el resumen.")
            return

        # 1. Consultar descargas reales de forma segura y flexible
        descargas_reales = {} # {(estacion_id, producto_key, fecha_str): volumen_total_descargado}
        try:
            df_bit_hist = pd.read_sql("SELECT * FROM bitacora_descargas;", conn)
            if not df_bit_hist.empty:
                col_est = next((c for c in df_bit_hist.columns if 'estacion' in c.lower()), None)
                col_prod = next((c for c in df_bit_hist.columns if 'producto' in c.lower()), None)
                col_fecha = next((c for c in df_bit_hist.columns if 'fecha' in c.lower()), None)
                col_cant = next((c for c in df_bit_hist.columns if 'cant' in c.lower() or 'vol' in c.lower() or 'natural' in c.lower()), None)
                
                if col_est and col_prod and col_fecha and col_cant:
                    for _, rb in df_bit_hist.iterrows():
                        e_id = str(rb[col_est]).strip()
                        pk = normalizar_producto(rb[col_prod])
                        f_desc = pd.to_datetime(rb[col_fecha]).strftime("%Y-%m-%d")
                        vol_real = float(rb[col_cant]) if pd.notna(rb[col_cant]) else 0.0
                        
                        key = (e_id, pk, f_desc)
                        descargas_reales[key] = descargas_reales.get(key, 0.0) + vol_real
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass

        # 2. Ajustar el inventario de cada estación descontando ventas y sumando descargas reales transcurridas
        inventarios_actualizados_reg = []
        inventarios_actualizados_pre = []
        inventarios_actualizados_die = []

        for _, r in df.iterrows():
            est_id = str(r['id_estacion']).strip()
            f_inv = r['fecha_inventario']
            
            if pd.isna(f_inv):
                inventarios_actualizados_reg.append(0.0)
                inventarios_actualizados_pre.append(0.0)
                inventarios_actualizados_die.append(0.0)
                continue
                
            f_inv_date = pd.to_datetime(f_inv).date()
            dias_transcurridos = (hoy - f_inv_date).days
            
            inv_r = float(r['reg_litros'])
            inv_p = float(r['pre_litros'])
            inv_d = float(r['die_litros'])
            
            vdp_r = float(r['vdp_reg'])
            vdp_p = float(r['vdp_pre'])
            vdp_d = float(r['vdp_die'])

            if dias_transcurridos > 0:
                current_date = f_inv_date
                for _ in range(dias_transcurridos):
                    current_date = current_date + timedelta(days=1)
                    curr_str = current_date.strftime("%Y-%m-%d")
                    
                    inv_r = inv_r - vdp_r + descargas_reales.get((est_id, 'regular', curr_str), 0.0)
                    inv_p = inv_p - vdp_p + descargas_reales.get((est_id, 'premium', curr_str), 0.0)
                    inv_d = inv_d - vdp_d + descargas_reales.get((est_id, 'diesel', curr_str), 0.0)
            
            inventarios_actualizados_reg.append(max(0.0, inv_r))
            inventarios_actualizados_pre.append(max(0.0, inv_p))
            inventarios_actualizados_die.append(max(0.0, inv_d))

        df['reg_litros_calc'] = inventarios_actualizados_reg
        df['pre_litros_calc'] = inventarios_actualizados_pre
        df['die_litros_calc'] = inventarios_actualizados_die

        def formato_inv(litros, fecha_inv):
            if pd.isna(fecha_inv):
                return "N/A", True
            f_str = pd.to_datetime(fecha_inv).strftime("%Y-%m-%d")
            es_teorico = f_str < hoy_str
            prefijo = "*" if es_teorico else ""
            return f"{prefijo}{litros:,.0f} L", es_teorico

        # Consultar cargas programadas para el DÍA DE HOY de forma segura
        cargas_hoy = {} # {(estacion_id, producto_key): volumen_total_programado_hoy}
        try:
            query_cargas = f"""
                SELECT id_estacion, producto, volumen_programado
                FROM programacion_cargas
                WHERE CAST(fecha_programacion AS TEXT) LIKE '{hoy_str}%';
            """
            df_cargas = pd.read_sql(query_cargas, conn)
            if not df_cargas.empty:
                for _, rc in df_cargas.iterrows():
                    est_id = str(rc['id_estacion']).strip()
                    pk = normalizar_producto(rc['producto'])
                    vol = float(rc['volumen_programado']) if pd.notna(rc['volumen_programado']) else 0.0
                    
                    key_carga = (est_id, pk)
                    cargas_hoy[key_carga] = cargas_hoy.get(key_carga, 0.0) + vol
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass

        # Calcular días de suministro actuales utilizando el inventario proyectado a hoy
        df['ds_r'] = df.apply(lambda r: round(r['reg_litros_calc'] / r['vdp_reg'], 1) if r['cap_regular'] > 0 and r['vdp_reg'] > 0 else np.nan, axis=1)
        df['ds_p'] = df.apply(lambda r: round(r['pre_litros_calc'] / r['vdp_pre'], 1) if r['cap_premium'] > 0 and r['vdp_pre'] > 0 else np.nan, axis=1)
        df['ds_d'] = df.apply(lambda r: round(r['die_litros_calc'] / r['vdp_die'], 1) if r['cap_diesel'] > 0 and r['vdp_die'] > 0 else np.nan, axis=1)

        # Calcular espacio disponible
        df['espacio_r'] = df.apply(lambda r: max(0, r['cap_regular'] - r['reg_litros_calc']) if r['cap_regular'] > 0 else np.nan, axis=1)
        df['espacio_p'] = df.
