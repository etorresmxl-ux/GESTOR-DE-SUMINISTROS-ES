import streamlit as st
import pandas as pd
from datetime import date, timedelta

def render(conn):
    st.markdown("### 📊 Registro Semanal de Ventas")
    st.write("Captura o actualiza las ventas diarias (de lunes a domingo) para las estaciones asignadas al usuario.")
    
    try:
        # 1. Obtener la lista de programadores desde estaciones_detalle
        query_prog = 'SELECT DISTINCT "user" AS usuario FROM estaciones_detalle WHERE "user" IS NOT NULL ORDER BY usuario;'
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        # 2. Calcular la semana en curso (Lunes a Domingo)
        hoy = date.today()

        col1, col2 = st.columns(2)
        with col1:
            usuario_seleccionado = st.selectbox("👤 Selecciona tu Usuario (Programador)", df_prog["usuario"].tolist(), key="ventas_prog")
        with col2:
            lunes_seleccionado = st.date_input("Semana (Selecciona cualquier día de la semana deseada)", hoy)
            lunes_semana = lunes_seleccionado - timedelta(days=lunes_seleccionado.weekday())
            domingo_semana = lunes_semana + timedelta(days=6)

        st.info(f"Mostrando semana del **{lunes_semana}** al **{domingo_semana}** para el programador **{usuario_seleccionado}**.")
        st.markdown("---")

        # 3. Obtener estaciones del programador
        query_est = f"""
            SELECT DISTINCT id_estacion AS "ID", plaza AS "Plaza", nombre AS "Estacion"
            FROM estaciones_detalle
            WHERE "user" = '{usuario_seleccionado}'
            ORDER BY plaza, id_estacion;
        """
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning(f"El usuario {usuario_seleccionado} no tiene estaciones asignadas.")
            return

        lista_estaciones_opciones = [f"{row['ID']} - {row['Estacion']} ({row['Plaza']})" for _, row in df_estaciones.iterrows()]
        estacion_elegida_str = st.selectbox("Selecciona la Estación a Registrar", lista_estaciones_opciones)
        estacion_id = estacion_elegida_str.split(" - ")[0]

        # 4. Generar el rango de fechas de lunes a domingo
        fechas_semana = [lunes_semana + timedelta(days=i) for i in range(7)]
        nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        df_semanal = pd.DataFrame({
            "Fecha": fechas_semana,
            "Día": nombres_dias,
            "regular": [0.0] * 7,
            "premium": [0.0] * 7,
            "diesel": [0.0] * 7
        })

        # Consultar ventas existentes en la tabla normalizada 'ventas'
        query_ventas_norm = f"""
            SELECT fecha, producto, volumen 
            FROM ventas 
            WHERE id_estacion = '{estacion_id}' 
              AND fecha BETWEEN '{lunes_semana}' AND '{domingo_semana}';
        """
        df_existentes = pd.read_sql(query_ventas_norm, conn)

        if not df_existentes.empty:
            df_existentes["fecha"] = pd.to_datetime(df_existentes["fecha"]).dt.date
            for idx, row in df_semanal.iterrows():
                f_actual = row["Fecha"]
                match_reg = df_existentes[(df_existentes["fecha"] == f_actual) & (df_existentes["producto"] == "regular")]
                match_pre = df_existentes[(df_existentes["fecha"] == f_actual) & (df_existentes["producto"] == "premium")]
                match_die = df_existentes[(df_existentes["fecha"] == f_actual) & (df_existentes["producto"] == "diesel")]

                if not match_reg.empty:
                    df_semanal.loc[idx, "regular"] = float(match_reg.iloc[0]["volumen"])
                if not match_pre.empty:
                    df_semanal.loc[idx, "premium"] = float(match_pre.iloc[0]["volumen"])
                if not match_die.empty:
                    df_semanal.loc[idx, "diesel"] = float(match_die.iloc[0]["volumen"])

        # 5. Formulario y tabla interactiva
        with st.form(f"form_ventas_{estacion_id}"):
            st.markdown(f"#### Ventas Semanales para: `{estacion_elegida_str}`")
            
            df_editado = st.data_editor(
                df_semanal,
                column_config={
                    "Fecha": st.column_config.DateColumn("Fecha", disabled=True, format="YYYY-MM-DD"),
                    "Día": st.column_config.TextColumn("Día", disabled=True),
                    "regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed"
            )
            
            submitted = st.form_submit_button("💾 Guardar Ventas Semanales", use_container_width=True)
            
            if submitted:
                cursor = conn.cursor()
                sql_upsert_ventas = """
                    INSERT INTO ventas (fecha, id_estacion, producto, volumen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, id_estacion, producto) 
                    DO UPDATE SET volumen = EXCLUDED.volumen;
                """
                count = 0
                for _, row in df_editado.iterrows():
                    fecha_str = str(row["Fecha"])
                    for prod in ["regular", "premium", "diesel"]:
                        vol = float(row[prod])
                        if vol >= 0:
                            cursor.execute(sql_upsert_ventas, (fecha_str, str(estacion_id), prod, vol))
                            count += 1
                
                conn.commit()
                cursor.close()
                st.success(f"¡Se guardaron {count} registros de ventas exitosamente en la tabla 'ventas'!")
                st.rerun()

    except Exception as e:
        st.error(f"Error al cargar o guardar los datos de ventas: {e}")
