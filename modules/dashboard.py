import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📊 Dashboard Operativo - Inventarios y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario actual y Días de Suministro calculados con VDP ponderada (12 semanas).")
    
    # Consulta optimizada que une el catálogo, el último inventario y la nueva vista de VDP ponderado
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
            -- Inventarios más recientes
            COALESCE(ui.regular, 0) as reg_litros,
            COALESCE(ui.premium, 0) as pre_litros,
            COALESCE(ui.diesel, 0) as die_litros,
            -- VDP Ponderado obtenido desde la vista que creamos
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

        # Construcción de la tabla final
        tabla_final = pd.DataFrame({
            "Proveedor": df['proveedor'],
            "ID": df['id_estacion'],
            "TAD": df['tad'],
            "Plaza": df['plaza'],
            "Estacion": df['estacion'],
            "Regular": df['reg_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Premium": df['pre_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Diesel": df['die_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "D/S R": df.apply(lambda r: round(r['reg_litros'] / r['vdp_reg'], 1) if r['vdp_reg'] > 0 else "", axis=1),
            "D/S P": df.apply(lambda r: round(r['pre_litros'] / r['vdp_pre'], 1) if r['vdp_pre'] > 0 else "", axis=1),
            "D/S D": df.apply(lambda r: round(r['die_litros'] / r['vdp_die'], 1) if r['vdp_die'] > 0 else "", axis=1),
        })

        # Mostrar tabla interactiva en Streamlit
        st.dataframe(tabla_final, use_container_width=True, height=550)
        
    except Exception as e:
        st.error(f"Error al generar el dashboard operativo: {e}")
