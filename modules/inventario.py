import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.header("📝 Captura Masiva de Inventarios por Programador")
    st.write("Registra los volúmenes de combustible de forma rápida en formato de tabla para tus estaciones asignadas.")
    
    try:
        # 1. Obtener la lista de programadores
        query_prog = "SELECT DISTINCT usuario FROM estaciones WHERE usuario IS NOT NULL ORDER BY usuario;"
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        # Controles superiores: Fecha, Turno y Usuario
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            fecha_registro = st.date_input("Fecha de Inventario", date.today())
        with col_f2:
            turno_seleccionado = st.selectbox("Turno / Hora", ["06:00 AM", "02:00 PM", "10:00 PM"])
        with col_f3:
            usuario_seleccionado = st.selectbox("👤 Programador", df_prog["usuario"].tolist())
        
        st.markdown("---")

        # 2. Consultar las estaciones asignadas a este usuario
        query_est = f"""
            SELECT id AS "ID", tad AS "TAD", plaza AS "Plaza", nombre AS "Estacion"
            FROM estaciones
            WHERE usuario = '{usuario_seleccionado}'
            ORDER BY plaza, id;
        """
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning(f"El usuario {usuario_seleccionado} no tiene estaciones asignadas.")
            return

        # 3. Buscar si ya existen registros previos para esta fecha y turno para precargarlos
        placeholders = tuple(df_estaciones["ID"].tolist())
        placeholders_str = f"('{I}'" + "".join([f", '{I}'" for I in placeholders[1:]]) + ")" if len(placeholders) > 1 else f"('{placeholders[0]}')"
        
        query_exist = f"""
            SELECT estacion_id, regular, premium, diesel 
            FROM inventarios_historico 
            WHERE fecha = '{fecha_registro}' 
              AND turno = '{turno_seleccionado}'
              AND estacion_id IN {placeholders_str};
        """
        df_existentes = pd.read_sql(query_exist, conn)

        # Preparar el DataFrame combinando las estaciones con sus valores (si ya existen) o en 0.0
        df_estaciones["Regular"] = 0.0
        df_estaciones["Premium"] = 0.0
        df_estaciones["Diesel"] = 0.0

        if not df_existentes.empty:
            for idx, row in df_estaciones.iterrows():
                match = df_existentes[df_existentes["estacion_id"] == row["ID"]]
                if not match.empty:
                    df_estaciones.loc[idx, "Regular"] = float(match.iloc[0]["regular"])
                    df_estaciones.loc[idx, "Premium"] = float(match.iloc[0]["premium"])
                    df_estaciones.loc[idx, "Diesel"] = float(match.iloc[0]["diesel"])

        st.info(f"Mostrando **{len(df_estaciones)} estaciones** asignadas a **{usuario_seleccionado}** para el turno de las **{turno_seleccionado}** del día **{fecha_registro}**.")

        # 4. Tabla interactiva editable estilo Excel
        with st.form("form_captura_masiva"):
            df_editado = st.data_editor(
                df_estaciones,
                column_config={
                    "ID": st.column_config.TextColumn("ID", disabled=True),
                    "TAD": st.column_config.TextColumn("TAD", disabled=True),
                    "Plaza": st.column_config.TextColumn("Plaza", disabled=True),
                    "Estacion": st.column_config.TextColumn("Estacion", disabled=True),
                    "Regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0.0, format="%.2f", step=100.0),
                    "Premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0.0, format="%.2f", step=100.0),
                    "Diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0.0, format="%.2f", step=100.0),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed"
            )
            
            submitted = st.form_submit_button("💾 Guardar / Actualizar Inventarios")
            
            if submitted:
                try:
                    cursor = conn.cursor()
                    for _, row in df_editado.iterrows():
                        cursor.execute(
                            """
                            INSERT INTO inventarios_historico (estacion_id, fecha, turno, regular, premium, diesel)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (estacion_id, fecha, turno) 
                            DO UPDATE SET regular = EXCLUDED.regular, 
                                          premium = EXCLUDED.premium, 
                                          diesel = EXCLUDED.diesel;
                            """,
                            (row["ID"], fecha_registro, turno_seleccionado, row["Regular"], row["Premium"], row["Diesel"])
                        )
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Inventarios actualizados exitosamente para el turno {turno_seleccionado} ({usuario_seleccionado})!")
                except Exception as e:
                    st.error(f"Error al guardar los registros en la base de datos: {e}")

    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
