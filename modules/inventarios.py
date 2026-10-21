import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 📦 Módulo de Registro de Inventarios")
    st.write("Selecciona tu usuario y la fecha para consultar, ingresar o modificar los inventarios de tus estaciones asignadas.")
    st.markdown("---")

    try:
        # 1. Obtener la lista única de usuarias/programadoras desde 'usuarios_estaciones'
        query_usuarios = 'SELECT DISTINCT usuario FROM usuarios_estaciones WHERE usuario IS NOT NULL ORDER BY usuario;'
        df_usuarios = pd.read_sql(query_usuarios, conn)
        
        if df_usuarios.empty:
            st.warning("No se encontraron usuarios asignados en la tabla 'usuarios_estaciones'.")
            return

        lista_usuarios = df_usuarios["usuario"].tolist()

        # 2. Controles superiores: Selector de Usuario y Selector de Fecha (por defecto hoy)
        col1, col2 = st.columns(2)
        
        with col1:
            usuario_seleccionado = st.selectbox("👤 Selecciona el Usuario", lista_usuarios, key="inv_usuario_sel")
            
        with col2:
            fecha_seleccionada = st.date_input("📅 Selecciona la Fecha", date.today(), key="inv_fecha_sel")

        st.info(f"Mostrando estaciones asignadas a **{usuario_seleccionado}** para la fecha: **{fecha_seleccionada}**.")
        st.markdown("---")

        # 3. Obtener las estaciones correspondientes al usuario seleccionado (Uniendo estaciones y usuarios_estaciones)
        query_estaciones = f"""
            SELECT e.id_estacion AS "ID", e.nombre AS "Estacion", e.plaza AS "Plaza", e.tad AS "TAD"
            FROM estaciones e
            JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
            WHERE ue.usuario = '{usuario_seleccionado}'
            ORDER BY e.plaza, e.id_estacion;
        """
        df_estaciones = pd.read_sql(query_estaciones, conn)

        if df_estaciones.empty:
            st.warning(f"El usuario **{usuario_seleccionado}** no tiene estaciones asignadas actualmente.")
            return

        # 4. Validar si ya existen registros previos para esta fecha y estas estaciones en la tabla 'inventarios'
        ids_estaciones = tuple(df_estaciones["ID"].tolist())
        ids_str = f"('{ids_estaciones[0]}')" if len(ids_estaciones) == 1 else str(ids_estaciones)

        query_inventarios_previos = f"""
            SELECT id_estacion, producto, volumen 
            FROM inventarios 
            WHERE fecha = '{fecha_seleccionada}' 
              AND id_estacion IN {ids_str};
        """
        df_existentes = pd.read_sql(query_inventarios_previos, conn)

        # Inicializar columnas de productos en ceros
        df_estaciones["Regular"] = 0.0
        df_estaciones["Premium"] = 0.0
        df_estaciones["Diesel"] = 0.0

        # Si ya hay registros previos, cargarlos en la matriz
        if not df_existentes.empty:
            df_existentes["producto_norm"] = df_existentes["producto"].str.lower().str.strip()
            for idx, row in df_estaciones.iterrows():
                e_id = row["ID"]
                
                match_reg = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto_norm"].str.contains("regular|magna"))]
                match_pre = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto_norm"].str.contains("premium"))]
                match_die = df_existentes[(df_existentes["id_estacion"] == e_id) & (df_existentes["producto_norm"].str.contains("diesel"))]

                if not match_reg.empty and pd.notna(match_reg.iloc[0]["volumen"]):
                    df_estaciones.loc[idx, "Regular"] = float(match_reg.iloc[0]["volumen"])
                if not match_pre.empty and pd.notna(match_pre.iloc[0]["volumen"]):
                    df_estaciones.loc[idx, "Premium"] = float(match_pre.iloc[0]["volumen"])
                if not match_die.empty and pd.notna(match_die.iloc[0]["volumen"]):
                    df_estaciones.loc[idx, "Diesel"] = float(match_die.iloc[0]["volumen"])
            
            st.success(f"📂 Se encontraron registros previos guardados para el día {fecha_seleccionada}. Puedes modificarlos directamente.")
        else:
            st.info(f"ℹ️ No hay registros previos para el día {fecha_seleccionada}. Ingresa los volúmenes correspondientes.")

        # 5. Tabla Matriz Interactiva (Data Editor dentro de un Formulario)
        st.markdown(f"#### Matriz de Inventarios - `{usuario_seleccionado}` ({fecha_seleccionada})")

        with st.form("form_inventarios_matriz"):
            df_editado = st.data_editor(
                df_estaciones,
                column_config={
                    "ID": st.column_config.TextColumn("ID Estación", disabled=True),
                    "TAD": st.column_config.TextColumn("TAD", disabled=True),
                    "Plaza": st.column_config.TextColumn("Plaza", disabled=True),
                    "Estacion": st.column_config.TextColumn("Nombre Estación", disabled=True),
                    "Regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "Premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "Diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                },
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                height=500
            )

            st.markdown("")
            submitted = st.form_submit_button("💾 Guardar Inventarios", use_container_width=True)

            if submitted:
                cursor = conn.cursor()
                sql_upsert_inv = """
                    INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, id_estacion, producto) 
                    DO UPDATE SET volumen = EXCLUDED.volumen;
                """
                count = 0
                fecha_str = str(fecha_seleccionada)

                for _, row in df_editado.iterrows():
                    e_id = str(row["ID"])
                    
                    # Guardar cada producto si el valor es válido
                    productos_data = [
                        ("regular", float(row["Regular"])),
                        ("premium", float(row["Premium"])),
                        ("diesel", float(row["Diesel"]))
                    ]

                    for prod_nombre, vol_val in productos_data:
                        if vol_val >= 0:
                            cursor.execute(sql_upsert_inv, (fecha_str, e_id, prod_nombre, vol_val))
                            count += 1

                conn.commit()
                cursor.close()
                st.success(f"¡Se guardaron y actualizaron {count} registros de inventario exitosamente para el usuario {usuario_seleccionado}!")
                st.rerun()

    except Exception as e:
        st.error(f"Error al cargar o procesar el módulo de inventarios: {e}")
