import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📊 Dashboard Operativo - Inventarios y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario actual de litros y días de cobertura según su VDP.")
    
    # Consulta SQL optimizada para obtener estación, último inventario por producto y su VDP
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
            -- VDP por producto desde estaciones_detalle
            MAX(CASE WHEN e.producto = 'Regular' THEN e.vdp ELSE 0 END) as vdp_reg,
            MAX(CASE WHEN e.producto = 'Premium' THEN e.vdp ELSE 0 END) as vdp_pre,
            MAX(CASE WHEN e.producto = 'Diesel' THEN e.vdp ELSE 0 END) as vdp_die
        FROM estaciones_detalle e
        LEFT JOIN ultimo_inventario ui ON e.id_estacion = ui.estacion_id AND ui.rn = 1
        GROUP BY e.id_estacion, e.proveedor, e.tad, e.plaza, e.nombre, ui.regular, ui.premium, ui.diesel
        ORDER BY e.id_estacion;
    """
    
    try:
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("No hay datos suficientes para generar el resumen.")
            return

        # Construcción de la tabla final con formato idéntico al solicitado
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
