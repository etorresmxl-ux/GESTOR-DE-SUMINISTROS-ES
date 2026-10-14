import streamlit as st
import pandas as pd

def render(conn):
    st.markdown("### 📊 Dashboard Operativo - Inventarios y Días de Suministro (D/S)")
    st.write("Resumen general por estación: Inventario actual de litros y días de cobertura según su VDP.")
    
    # Consulta SQL para unir estaciones, su inventario más reciente y su VDP
    query = """
        WITH ultimo_inventario AS (
            SELECT 
                estacion_id,
                regular AS inv_regular,
                premium AS inv_premium,
                diesel AS inv_diesel,
                ROW_NUMBER() OVER(PARTITION BY estacion_id ORDER BY fecha DESC, turno DESC) as rn
            FROM inventarios_historico
        )
        SELECT 
            e.id_estacion,
            e.proveedor,
            e.tad,
            e.plaza,
            e.nombre as estacion,
            -- Inventarios
            COALESCE(ui.inv_regular, 0) as reg_litros,
            COALESCE(ui.inv_premium, 0) as pre_litros,
            COALESCE(ui.inv_diesel, 0) as die_litros,
            -- VDP (Venta Diaria Promedio) por producto desde estaciones_detalle
            MAX(CASE WHEN e.producto = 'Regular' THEN e.vdp ELSE 0 END) as vdp_reg,
            MAX(CASE WHEN e.producto = 'Premium' THEN e.vdp ELSE 0 END) as vdp_pre,
            MAX(CASE WHEN e.producto = 'Diesel' THEN e.vdp ELSE 0 END) as vdp_die
        FROM estaciones_detalle e
        LEFT JOIN ultimo_inventario ui ON e.id_estacion = ui.estacion_id AND ui.rn = 1
        GROUP BY e.id_estacion, e.proveedor, e.tad, e.plaza, e.nombre, ui.inv_regular, ui.inv_premium, ui.inv_diesel
        ORDER BY e.id_estacion;
    """
    
    try:
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("No hay datos suficientes para generar el resumen.")
            return

        # Calcular los Días de Suministro (D/S) = Inventario / VDP
        # Evitamos división entre cero si VDP es 0 o NaN
        df['DS_Regular'] = df.apply(lambda r: round(r['reg_litros'] / r['vdp_reg'], 1) if r['vdp_reg'] > 0 else None, axis=1)
        df['DS_Premium'] = df.apply(lambda r: round(r['inv_premium'] / r['vdp_pre'], 1) if r['vdp_pre'] > 0 else None, axis=1) # Corrigiendo clave de inv
        
        # Ajustamos el cálculo limpio de la tabla final combinada
        tabla_final = pd.DataFrame({
            "Proveedor": df['proveedor'],
            "ID": df['id_estacion'],
            "TAD": df['tad'],
            "Plaza": df['plaza'],
            "Estacion": df['estacion'],
            "Regular": df['reg_litros'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Premium": df['inv_premium'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "Diesel": df['inv_diesel'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-"),
            "D/S R": df.apply(lambda r: round(r['reg_litros'] / r['vdp_reg'], 1) if r['vdp_reg'] > 0 else "", axis=1),
            "D/S P": df.apply(lambda r: round(r['inv_premium'] / r['vdp_pre'], 1) if r['vdp_pre'] > 0 else "", axis=1),
            "D/S D": df.apply(lambda r: round(r['inv_diesel'] / r['vdp_die'], 1) if r['vdp_die'] > 0 else "", axis=1),
        })

        # Mostrar tabla interactiva en Streamlit
        st.dataframe(tabla_final, use_container_width=True, height=550)
        
    except Exception as e:
        st.error(f"Error al generar el dashboard operativo: {e}")
