import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 📝 Captura Masiva de Inventarios")
    
    try:
        # 1. Obtener la lista de programadores
        query_prog = 'SELECT DISTINCT "user" AS usuario FROM estaciones_detalle WHERE "user" IS NOT NULL ORDER BY usuario;'
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_registro = st.date_input("Fecha de Inventario", date.today())
        with col_f2:
            usuario_seleccionado = st.selectbox("Programador", df_prog["usuario"].tolist())
        
        st.markdown("---")

        # 2. Consultar las estaciones asignadas a este usuario
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

        # 3. Buscar registros previos para esta fecha en la tabla normalizada 'inventarios'
        ids_estaciones = tuple(df_estaciones["ID"].tolist())
        ids_str = f"('{ids_estaciones[0]}')" if len(ids_estaciones) == 1 else str(ids_estaciones)
        
        query_exist = f"""
            SELECT id_estacion, producto, volumen 
            FROM inventarios 
            WHERE fecha = '{fecha_registro}' 
              AND id_estacion IN {ids_str};
        """
        df_existentes = pd.read_sql(query_exist, conn)

        df_estaciones["regular"] = 0.0
        df_estaciones["premium"] = 0.0
        df_estaciones["diesel"] = 0.0

        if not df_existentes.empty:
            for idx, row in df_estaciones.iterrows():
                e_id = row["ID"]
                match_reg = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto"] == "regular")]
                match_pre = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto"] == "premium")]
                match_die = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto"] == "diesel")]

                if not match_reg.empty:
                    df_estaciones.loc[idx, "regular"] = float(match_reg.iloc[0]["volumen"])
                if not match_pre.empty:
                    df_estaciones.loc[idx, "premium"] = float(match_pre.iloc[0]["volumen"])
                if not match_die.empty:
                    df_estaciones.loc[idx, "diesel"] = float(match_die.iloc[0]["volumen"])

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
                    "regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                height=550
            )
            
            submitted = st.form_submit_button("💾 Guardar Inventarios en Supabase")
            
            if submitted:
                cursor = conn.cursor()
                sql_upsert_inv = """
                    INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, id_estacion, producto) 
                    DO UPDATE SET volumen = EXCLUDED.volumen;
                """
                count = 0
                for _, row in df_editado.iterrows():
                    e_id = str(row["ID"])
                    for prod in ["regular", "premium", "diesel"]:
                        vol = float(row[prod])
                        if vol >= 0:
                            cursor.execute(sql_upsert_inv, (str(fecha_registro), e_id, prod, vol))
                            count += 1
                            
                conn.commit()
                cursor.close()
                st.success(f"¡Inventarios guardados y actualizados correctamente en la tabla 'inventarios' ({count} registros)!")
                st.rerun()

    except Exception as e:
        st.error(f"Error al cargar o guardar los inventarios: {e}")
