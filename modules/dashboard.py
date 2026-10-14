import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📊 Dashboard Operativo - Inventarios y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario actual y Días de Suministro calculados con VDP ponderada (12 semanas).")
    
    query = """
        WITH ultimo_inventario AS (
            SELECT 
                estacion_id,
                regular,
                premium,
                diesel,
                ROW_NUMBER() OVER(PARTITION BY estacion_id ORDER BY fecha DESC, turno DESC) as rn
            FROM inventarios_historico
        )
        SELECT 
            e.id_estacion,
            e.proveedor,
            e.tad,
            e.plaza,
            e.nombre as estacion,
            COALESCE(ui.regular, 0) as reg_litros,
            COALESCE(ui.premium, 0) as pre_litros,
            COALESCE(ui.diesel, 0) as die_litros,
            COALESCE(vp.vdp_regular, 0) as vdp_reg,
            COALESCE(vp.vdp_premium, 0) as vdp_pre,
            COALESCE(vp.vdp_diesel, 0) as vdp_die
        FROM estaciones_detalle e
        LEFT JOIN ultimo_inventario ui ON e.id_estacion = ui.estacion_id AND ui.rn = 1
        LEFT JOIN vdp_ponderado_12w vp ON e.id_estacion = vp.estacion_id
        GROUP BY e.id_estacion, e.proveedor, e.tad, e.plaza, e.nombre, ui.regular, ui.premium, ui.diesel, vp.vdp_regular, vp.vdp_premium, vp.vdp_diesel
        ORDER BY e.id_estacion;
    """
    
    try:
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("No hay datos suficientes para generar el resumen.")
            return

        # Calcular los días de suministro numéricos internamente para las reglas y alertas
        df['ds_r'] = df.apply(lambda r: r['reg_litros'] / r['vdp_reg'] if r['vdp_reg'] > 0 else None, axis=1)
        df['ds_p'] = df.apply(lambda r: r['pre_litros'] / r['vdp_pre'] if r['vdp_pre'] > 0 else None, axis=1)
        df['ds_d'] = df.apply(lambda r: r['die_litros'] / r['vdp_die'] if r['vdp_die'] > 0 else None, axis=1)

        # Construcción de la tabla base para visualización
        tabla_vis = pd.DataFrame({
            "Proveedor": df['proveedor'],
            "ID": df['id_estacion'],
            "TAD": df['tad'],
            "Plaza": df['plaza'],
            "Estacion": df['estacion'],
            "Regular": df['reg_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Premium": df['pre_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Diesel": df['die_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "D/S R": df['ds_r'].apply(lambda x: round(x, 1) if x is not None else ""),
            "D/S P": df['ds_p'].apply(lambda x: round(x, 1) if x is not None else ""),
            "D/S D": df['ds_d'].apply(lambda x: round(x, 1) if x is not None else ""),
        })

        # Función de estilo para pintar celdas de D/S y Litros según los días de inventario
        def aplicar_semaforo(row_idx):
            estilos = [''] * len(tabla_vis.columns)
            r = df.iloc[row_idx]
            
            # Mapeo de columnas de inventario/litros y sus respectivos D/S
            mapeo = [
                ('Regular', 'D/S R', r['ds_r']),
                ('Premium', 'D/S P', r['ds_p']),
                ('Diesel', 'D/S D', r['ds_d'])
            ]
            
            for col_litro, col_ds, ds_val in mapeo:
                if ds_val is not None:
                    if ds_val < 1.0:
                        color = 'background-color: #ffcccc; color: #990000; font-weight: bold;' # Rojo crítico
                    elif ds_val < 2.0:
                        color = 'background-color: #fff2cc; color: #b26b00; font-weight: bold;' # Amarillo advertencia
                    else:
                        continue
                    
                    # Pintar tanto la columna de litros como la de D/S
                    if col_litro in tabla_vis.columns:
                        estilos[tabla_vis.columns.get_loc(col_litro)] = color
                    if col_ds in tabla_vis.columns:
                        estilos[tabla_vis.columns.get_loc(col_ds)] = color
            return estilos

        tabla_estilizada = tabla_vis.style.apply(aplicar_semaforo, axis=1)

        # Mostrar tabla interactiva en Streamlit
        st.dataframe(tabla_estilizada, use_container_width=True, height=450, hide_index=True)

        # ==========================================
        # CENTRO DE ALERTAS PRIORIZADAS
        # ==========================================
        st.markdown("---")
        st.markdown("### 🚨 Centro de Alertas y Prioridades de Abastecimiento")
        
        alertas = []
        for _, r in df.iterrows():
            productos = [('Regular', r['ds_r'], r['reg_litros']), 
                         ('Premium', r['ds_p'], r['pre_litros']), 
                         ('Diesel', r['ds_d'], r['die_litros'])]
            
            for prod, ds, litros in productos:
                if ds is not None:
                    if ds < 1.0:
                        alertas.append({
                            "prioridad": 1, # Rojo (Más crítico)
                            "nivel": "🔴 CRÍTICO (< 1 Día)",
                            "estacion": f"{r['id_estacion']} - {r['estacion']}",
                            "plaza": r['plaza'],
                            "producto": prod,
                            "ds": ds,
                            "litros": litros
                        })
                    elif ds < 2.0:
                        alertas.append({
                            "prioridad": 2, # Amarillo (Advertencia)
                            "nivel": "🟡 ADVERTENCIA (< 2 Días)",
                            "estacion": f"{r['id_estacion']} - {r['estacion']}",
                            "plaza": r['plaza'],
                            "producto": prod,
                            "ds": ds,
                            "litros": litros
                        })

        if not alertas:
            st.success("✅ ¡Excelente noticia! No hay estaciones con niveles críticos o de advertencia en este momento.")
        else:
            # Ordenar alertas: primero prioridad 1 (rojas) y luego prioridad 2 (amarillas)
            alertas_ordenadas = sorted(alertas, key=lambda x: (x['prioridad'], x['ds']))
            
            df_alertas = pd.DataFrame(alertas_ordenadas)
            
            # Formato visual para el resumen de alertas
            tabla_alertas_vis = pd.DataFrame({
                "Estatus": df_alertas['nivel'],
                "Estación": df_alertas['estacion'],
                "Plaza": df_alertas['plaza'],
                "Producto": df_alertas['producto'],
                "Inventario Actual": df_alertas['litros'].apply(lambda x: f"{x:,.0f} L"),
                "Días de Suministro": df_alertas['ds'].apply(lambda x: f"{x:.1f} días")
            })
            
            st.dataframe(tabla_alertas_vis, use_container_width=True, height=300, hide_index=True)
        
    except Exception as e:
        st.error(f"Error al generar el dashboard operativo: {e}")
