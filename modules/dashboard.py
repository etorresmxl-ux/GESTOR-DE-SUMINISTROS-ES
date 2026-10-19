import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime

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

        hoy = date.today()
        hoy_str = hoy.strftime("%Y-%m-%d")

        # 1. Consultar descargas reales en bitacora_descargas para ajustar el inventario histórico al día de hoy
        descargas_reales = {} # {(estacion_id, producto_key, fecha_str): volumen_total_descargado}
        try:
            query_bitacora_hist = """
                SELECT id_estacion, producto, fecha_descarga_real, cantidad_natural 
                FROM bitacora_descargas;
            """
            df_bit_hist = pd.read_sql(query_bitacora_hist, conn)
            if not df_bit_hist.empty:
                for _, rb in df_bit_hist.iterrows():
                    e_id = str(rb['id_estacion']).strip()
                    pk = normalizar_producto(rb['producto'])
                    
                    f_desc = pd.to_datetime(rb['fecha_descarga_real']).strftime("%Y-%m-%d")
                    vol_real = float(rb['cantidad_natural']) if pd.notna(rb['cantidad_natural']) else 0.0
                    
                    key = (e_id, pk, f_desc)
                    descargas_reales[key] = descargas_reales.get(key, 0.0) + vol_real
        except Exception as e:
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
            
            # Si la fecha del inventario es hoy o futura, se queda igual; si es pasada, proyectamos día por día
            dias_transcurridos = (hoy - f_inv_date).days
            
            # Valores base
            inv_r = float(r['reg_litros'])
            inv_p = float(r['pre_litros'])
            inv_d = float(r['die_litros'])
            
            vdp_r = float(r['vdp_reg'])
            vdp_p = float(r['vdp_pre'])
            vdp_d = float(r['vdp_die'])

            # Simular el desgaste y entradas día por día desde el día posterior al inventario hasta hoy
            if dias_transcurridos > 0:
                current_date = f_inv_date
                for _ in range(dias_transcurridos):
                    current_date = current_date + pd.Timedelta(days=1)
                    curr_str = current_date.strftime("%Y-%m-%d")
                    
                    # Descontar VDP y sumar descargas reales de ese día específico
                    inv_r = inv_r - vdp_r + descargas_reales.get((est_id, 'regular', curr_str), 0.0)
                    inv_p = inv_p - vdp_p + descargas_reales.get((est_id, 'premium', curr_str), 0.0)
                    inv_d = inv_d - vdp_d + descargas_reales.get((est_id, 'diesel', curr_str), 0.0)
            
            # Evitar negativos lógicos
            inventarios_actualizados_reg.append(max(0.0, inv_r))
            inventarios_actualizados_pre.append(max(0.0, inv_p))
            inventarios_actualizados_die.append(max(0.0, inv_d))

        df['reg_litros_calc'] = inventarios_actualizados_reg
        df['pre_litros_calc'] = inventarios_actualizados_pre
        df['die_litros_calc'] = inventarios_actualizados_die

        # Función auxiliar para determinar si el inventario es teórico (si el último registro físico no es de hoy)
        def formato_inv(litros, fecha_inv):
            if pd.isna(fecha_inv):
                return "N/A", True
            f_str = pd.to_datetime(fecha_inv).strftime("%Y-%m-%d")
            es_teorico = f_str < hoy_str
            prefijo = "*" if es_teorico else ""
            return f"{prefijo}{litros:,.0f} L", es_teorico

        # Consultar únicamente las cargas programadas para el DÍA DE HOY (acumulando múltiples folios)
        cargas_hoy = {} # {(estacion_id, producto_key): volumen_total_programado_hoy}
        try:
            query_cargas = f"""
                SELECT id_estacion, producto, volumen_programado
                FROM programacion_cargas
                WHERE fecha_programacion = '{hoy_str}';
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
            pass

        # Calcular días de suministro actuales utilizando el inventario proyectado a hoy
        df['ds_r'] = df.apply(lambda r: round(r['reg_litros_calc'] / r['vdp_reg'], 1) if r['cap_regular'] > 0 and r['vdp_reg'] > 0 else np.nan, axis=1)
        df['ds_p'] = df.apply(lambda r: round(r['pre_litros_calc'] / r['vdp_pre'], 1) if r['cap_premium'] > 0 and r['vdp_pre'] > 0 else np.nan, axis=1)
        df['ds_d'] = df.apply(lambda r: round(r['die_litros_calc'] / r['vdp_die'], 1) if r['cap_diesel'] > 0 and r['vdp_die'] > 0 else np.nan, axis=1)

        # Calcular espacio disponible
        df['espacio_r'] = df.apply(lambda r: max(0, r['cap_regular'] - r['reg_litros_calc']) if r['cap_regular'] > 0 else np.nan, axis=1)
        df['espacio_p'] = df.apply(lambda r: max(0, r['cap_premium'] - r['pre_litros_calc']) if r['cap_premium'] > 0 else np.nan, axis=1)
        df['espacio_d'] = df.apply(lambda r: max(0, r['cap_diesel'] - r['die_litros_calc']) if r['cap_diesel'] > 0 else np.nan, axis=1)

        # ==========================================
        # 1. CENTRO DE ALERTAS PRIORIZADAS
        # ==========================================
        st.markdown("### 🚨 Centro de Alertas y Prioridades de Abastecimiento")
        
        alertas = []
        for _, r in df.iterrows():
            est_id = str(r['id_estacion']).strip()
            f_inv = r['fecha_inventario']
            
            productos = [
                ('Regular', r['ds_r'], r['reg_litros_calc'], r['cap_regular'], r['espacio_r'], r['vdp_reg'], 'regular'), 
                ('Premium', r['ds_p'], r['pre_litros_calc'], r['cap_premium'], r['espacio_p'], r['vdp_pre'], 'premium'), 
                ('Diesel', r['ds_d'], r['die_litros_calc'], r['cap_diesel'], r['espacio_d'], r['vdp_die'], 'diesel')
            ]
            
            for prod, ds, litros, cap, espacio, vdp, p_key in productos:
                if cap > 0 and pd.notna(ds):
                    if ds < 2.0: # Menor a 2 días (Crítico o Advertencia)
                        prioridad = 1 if ds < 1.0 else 2
                        nivel = "🔴 CRÍTICO (< 1 Día)" if ds < 1.0 else "🟡 ADVERTENCIA (< 2 Días)"
                        
                        str_inv_actual, _ = formato_inv(litros, f_inv)
                        
                        vol_carga_hoy = cargas_hoy.get((est_id, p_key), 0.0)
                        
                        if vol_carga_hoy > 0:
                            litros_post = litros + vol_carga_hoy - vdp
                            ds_post = round(litros_post / vdp, 1) if vdp > 0 else ds
                            programa_status = f"🚛 Sí ({vol_carga_hoy:,.0f} L) ➔ Post: *{litros_post:,.0f} L ({ds_post:.1f} d)"
                        else:
                            programa_status = "❌ Sin Carga Hoy"

                        alertas.append({
                            "prioridad": prioridad, 
                            "nivel": nivel,
                            "estacion": f"{r['id_estacion']} - {r['estacion']}",
                            "plaza": str(r['plaza']),
                            "producto": prod,
                            "ds": ds,
                            "litros_val": str_inv_actual,
                            "espacio": espacio,
                            "programa": programa_status
                        })

        if not alertas:
            st.success("✅ ¡Excelente noticia! No hay estaciones con niveles críticos o de advertencia en este momento.")
        else:
            alertas_ordenadas = sorted(alertas, key=lambda x: (x['prioridad'], x['ds']))
            df_alertas = pd.DataFrame(alertas_ordenadas)
            
            tabla_alertas_vis = pd.DataFrame({
                "Estatus": df_alertas['nivel'],
                "Estación": df_alertas['estacion'],
                "Plaza": df_alertas['plaza'],
                "Producto": df_alertas['producto'],
                "Inventario Actual": df_alertas['litros_val'],
                "D/S Actual": df_alertas['ds'].apply(lambda x: f"{x:.1f} días"),
                "Programa Hoy / Post-Entrega": df_alertas['programa']
            })
            
            st.dataframe(tabla_alertas_vis, width='stretch', height=300, hide_index=True)

        st.markdown("---")

        # ==========================================
        # 2. TABLA GENERAL DE INVENTARIOS COMBINADA (INV + D/S)
        # ==========================================
        st.markdown("### 📋 Detalle General de Inventarios y Suministro")

        def calcular_semaforo(r):
            ds_vals = [r['ds_r'], r['ds_p'], r['ds_d']]
            ds_validos = [v for v in ds_vals if pd.notna(v)]
            if not ds_validos:
                return "🟢"
            min_ds = min(ds_validos)
            if min_ds < 1.0:
                return "🔴"
            elif min_ds < 2.0:
                return "🟡"
            else:
                return "🟢"

        df['semaforo'] = df.apply(calcular_semaforo, axis=1)

        def formatear_celda_general(litros, ds, cap, fecha_inv):
            if cap <= 0 or pd.isna(ds):
                return "N/A"
            txt_inv, _ = formato_inv(litros, fecha_inv)
            return f"{txt_inv} ({ds:.1f} d)"

        tabla_vis = pd.DataFrame({
            "Semáforo": df['semaforo'],
            "ID": df['id_estacion'].astype(str),
            "TAD": df['tad'].astype(str),
            "Plaza": df['plaza'].astype(str),
            "Estación": df['estacion'].astype(str),
            
            "REGULAR (Inv / D/S)": df.apply(lambda r: formatear_celda_general(r['reg_litros_calc'], r['ds_r'], r['cap_regular'], r['fecha_inventario']), axis=1),
            "PREMIUM (Inv / D/S)": df.apply(lambda r: formatear_celda_general(r['pre_litros_calc'], r['ds_p'], r['cap_premium'], r['fecha_inventario']), axis=1),
            "DIESEL (Inv / D/S)": df.apply(lambda r: formatear_celda_general(r['die_litros_calc'], r['ds_d'], r['cap_diesel'], r['fecha_inventario']), axis=1),
        })

        st.dataframe(tabla_vis, width='stretch', height=450, hide_index=True)
        
    except Exception as e:
        st.error(f"Error al generar el dashboard operativo: {e}")
