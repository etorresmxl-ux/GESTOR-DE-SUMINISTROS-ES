import streamlit as st
import pandas as pd
import numpy as np

def render(conn):
    st.markdown("### 📊 Dashboard Operativo - Inventarios, Espacio Disponible y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario actual, capacidad disponible y Días de Suministro calculados con VDP ponderada (12 semanas).")
    
    query = """
        WITH ultimo_inventario AS (
            SELECT 
                estacion_id,
                regular,
                premium,
                diesel,
                ROW_NUMBER() OVER(PARTITION BY estacion_id ORDER BY fecha DESC, turno DESC) as rn
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

        # Calcular días de suministro solo si la estación vende el producto (capacidad > 0 y vdp > 0)
        df['ds_r'] = df.apply(lambda r: round(r['reg_litros'] / r['vdp_reg'], 1) if r['cap_regular'] > 0 and r['vdp_reg'] > 0 else np.nan, axis=1)
        df['ds_p'] = df.apply(lambda r: round(r['pre_litros'] / r['vdp_pre'], 1) if r['cap_premium'] > 0 and r['vdp_pre'] > 0 else np.nan, axis=1)
        df['ds_d'] = df.apply(lambda r: round(r['die_litros'] / r['vdp_die'], 1) if r['cap_diesel'] > 0 and r['vdp_die'] > 0 else np.nan, axis=1)

        # Calcular espacio disponible para recibir producto al 90% de su capacidad máxima
        df['espacio_r'] = df.apply(lambda r: max(0, (r['cap_regular'] * 0.90) - r['reg_litros']) if r['cap_regular'] > 0 else np.nan, axis=1)
        df['espacio_p'] = df.apply(lambda r: max(0, (r['cap_premium'] * 0.90) - r['pre_litros']) if r['cap_premium'] > 0 else np.nan, axis=1)
        df['espacio_d'] = df.apply(lambda r: max(0, (r['cap_diesel'] * 0.90) - r['die_litros']) if r['cap_diesel'] > 0 else np.nan, axis=1)

        # ==========================================
        # 1. CENTRO DE ALERTAS PRIORIZADAS (PRIMERO)
        # ==========================================
        st.markdown("### 🚨 Centro de Alertas y Prioridades de Abastecimiento")
        
        alertas = []
        for _, r in df.iterrows():
            productos = [
                ('Regular', r['ds_r'], r['reg_litros'], r['cap_regular'], r['espacio_r']), 
                ('Premium', r['ds_p'], r['pre_litros'], r['cap_premium'], r['espacio_p']), 
                ('Diesel', r['ds_d'], r['die_litros'], r['cap_diesel'], r['espacio_d'])
            ]
            
            for prod, ds, litros, cap, espacio in productos:
                if cap > 0 and pd.notna(ds):
                    if ds < 1.0:
                        alertas.append({
                            "prioridad": 1, 
                            "nivel": "🔴 CRÍTICO (< 1 Día)",
                            "estacion": f"{r['id_estacion']} - {r['estacion']}",
                            "plaza": str(r['plaza']),
                            "producto": prod,
                            "ds": ds,
                            "litros": litros,
                            "espacio": espacio
                        })
                    elif ds < 2.0:
                        alertas.append({
                            "prioridad": 2, 
                            "nivel": "🟡 ADVERTENCIA (< 2 Días)",
                            "estacion": f"{r['id_estacion']} - {r['estacion']}",
                            "plaza": str(r['plaza']),
                            "producto": prod,
                            "ds": ds,
                            "litros": litros,
                            "espacio": espacio
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
                "Inventario Actual": df_alertas['litros'].apply(lambda x: f"{x:,.0f} L"),
                "Espacio Disponible": df_alertas['espacio'].apply(lambda x: f"{x:,.0f} L"),
                "Días de Suministro": df_alertas['ds'].apply(lambda x: f"{x:.1f} días")
            })
            
            st.dataframe(tabla_alertas_vis, width='stretch', height=300, hide_index=True)

        st.markdown("---")

        # ==========================================
        # 2. TABLA GENERAL DE INVENTARIOS CON SEMÁFORO
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

        # Construcción de la tabla visual integrando inventario, espacio disponible al 90% y D/S (con N/A si no aplica)
        tabla_vis = pd.DataFrame({
            "Semáforo": df['semaforo'],
            "ID": df['id_estacion'].astype(str),
            "TAD": df['tad'].astype(str),
            "Plaza": df['plaza'].astype(str),
            "Estación": df['estacion'].astype(str),
            
            # Inventarios actuales / Espacio al 90%
            "Reg (Inv / Cap.Max)": df.apply(lambda r: f"{r['reg_litros']:,.0f} L (Faltan {r['espacio_r']:,.0f} L)" if r['cap_regular'] > 0 else "N/A", axis=1),
            "Pre (Inv / Cap.Max)": df.apply(lambda r: f"{r['pre_litros']:,.0f} L (Faltan {r['espacio_p']:,.0f} L)" if r['cap_premium'] > 0 else "N/A", axis=1),
            "Die (Inv / Cap.Max)": df.apply(lambda r: f"{r['die_litros']:,.0f} L (Faltan {r['espacio_d']:,.0f} L)" if r['cap_diesel'] > 0 else "N/A", axis=1),
            
            # Días de Suministro
            "D/S R": df.apply(lambda r: f"{r['ds_r']:.1f}" if r['cap_regular'] > 0 and pd.notna(r['ds_r']) else "N/A", axis=1),
            "D/S P": df.apply(lambda r: f"{r['ds_p']:.1f}" if r['cap_premium'] > 0 and pd.notna(r['ds_p']) else "N/A", axis=1),
            "D/S D": df.apply(lambda r: f"{r['ds_d']:.1f}" if r['cap_diesel'] > 0 and pd.notna(r['ds_d']) else "N/A", axis=1),
        })

        st.dataframe(tabla_vis, width='stretch', height=450, hide_index=True)
        
    except Exception as e:
        st.error(f"Error al generar el dashboard operativo: {e}")
