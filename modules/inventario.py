import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 📝 Captura Masiva de Inventarios")
    
    # CSS personalizado para compactar filas y aplicar diseño cebra
    st.markdown("""
        <style>
        div[data-testid="stDataEditor"] tr {
            height: 32px !important;
        }
        div[data-testid="stDataEditor"] td {
            padding-top: 2px !important;
            padding-bottom: 2px !important;
        }
        div[data-testid="stDataEditor"] tbody tr:nth-child(odd) {
            background-color: #1a1a1a !important;
        }
        div[data-testid="stDataEditor"] tbody tr:nth-child(even) {
            background-color: #262626 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    try:
        # 1. Obtener la lista de programadores
        query_prog = 'SELECT DISTINCT "user" AS usuario FROM estaciones_detalle WHERE "user" IS NOT NULL ORDER BY usuario;'
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        # Controles superiores compactos (Solo Fecha y Programador)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_registro = st.date_input("Fecha de Inventario", date.today())
        with col_f2:
            usuario_seleccionado = st.selectbox("Programador", df_prog["usuario"].tolist())
        
        st.markdown("---")

        # 2. Consultar las estaciones asignadas a este usuario desde estaciones_detalle
        query_est = f"""
            SELECT DISTINCT id_estacion AS "ID", tad AS "TAD", plaza AS "Plaza", nombre AS "Estacion"
            FROM estaciones_detalle
            WHERE "user" = '{usuario_seleccionado}'
            ORDER BY plaza, id_estacion;
        """
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning(f"El usuario {usuario_seleccionado} no tiene estaciones asignadas.")
            return

        # 3. Buscar si ya existen registros previos para esta fecha
        ids_estaciones = tuple(df_estaciones["ID"].tolist())
        if len(ids_estaciones) == 1:
            ids_str = f"('{ids_estaciones[0]}')"
        else:
            ids_str = str(ids_estaciones)
        
        query_exist = f"""
            SELECT estacion_id, regular, premium, diesel 
            FROM inventarios_historico 
            WHERE fecha = '{fecha_registro}' 
              AND estacion_id IN {ids_str};
        """
        df_existentes = pd.read_sql(query_exist, conn)

        # Preparar columnas de litros inicializadas en 0
        df_estaciones["Regular"] = 0
        df_estaciones["Premium"] = 0
        df_estaciones["Diesel"] = 0

        # Precargar valores existentes de forma segura
        if not df_existentes.empty:
            for idx, row in df_estaciones.iterrows():
                match = df_existentes[df_existentes["estacion_id"] == row["ID"]]
                if not match.empty:
                    reg_val = match.iloc[0]["regular"]
                    pre_val = match.iloc[0]["premium"]
                    die_val = match.iloc[0]["diesel"]
                    
                    df_estaciones.loc[idx, "Regular"] = int(reg_val) if pd.notna(reg_val) else 0
                    df_estaciones.loc[idx, "Premium"] = int(pre_val) if pd.notna(pre_val) else 0
                    df_estaciones.loc[idx, "Diesel"] = int(die_val) if pd.notna(die_val) else 0

        st.caption(f"Mostrando **{len(df_estaciones)} estaciones** asignadas a **{usuario_seleccionado}** (Fecha: **{fecha_registro}**).")

        # 4. Tabla interactiva
        with st.form("form_captura_masiva_inventario"):
            df_editado = st.data_editor(
                df_estaciones,
                column_config={
                    "ID": st.column_config.TextColumn("ID", disabled=True),
                    "TAD": st.column_config.TextColumn("TAD", disabled=True),
                    "Plaza": st.column_config.TextColumn("Plaza", disabled=True),
                    "Estacion": st.column_config.TextColumn("Estacion", disabled=True),
                    "Regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0, format="%,d", step=100),
                    "Premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0, format="%,d", step=100),
                    "Diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0, format="%,d", step=100),
                },
                hide_index=True,
                width='stretch',
                num_rows="fixed",
                height=550
            )
            
            submitted = st.form_submit_button("💾 Guardar / Actualizar Inventarios")
            
            if submitted:
                try:
                    cursor = conn.cursor()
                    for _, row in df_editado.iterrows():
                        cursor.execute(
                            """
                            INSERT INTO inventarios_historico (estacion_id, fecha, regular, premium, diesel)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (estacion_id, fecha) 
                            DO UPDATE SET regular = EXCLUDED.regular, 
                                          premium = EXCLUDED.premium, 
                                          diesel = EXCLUDED.diesel;
                            """,
                            (row["ID"], fecha_registro, row["Regular"], row["Premium"], row["Diesel"])
                        )
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Inventarios guardados correctamente para la fecha {fecha_registro}!")
                    # Forzar recarga inmediata para liberar el estado del formulario de forma limpia
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar los registros en la base de datos: {e}")

    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
