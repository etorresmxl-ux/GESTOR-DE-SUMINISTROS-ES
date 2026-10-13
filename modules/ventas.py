import streamlit as st
import pandas as pd
from datetime import date, timedelta

def render(conn):
    st.markdown("### 📊 Registro Semanal de Ventas")
    st.write("Captura o actualiza las ventas diarias (de lunes a domingo) para las estaciones asignadas a tu usuario.")
    
    try:
        # 1. Obtener la lista de programadores
        query_prog = "SELECT DISTINCT usuario FROM estaciones WHERE usuario IS NOT NULL ORDER BY usuario;"
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        # 2. Calcular la semana en curso (Lunes a Domingo)
        hoy = date.today()
        # Ajustar para que el lunes sea el inicio de semana (0 = Lunes, 6 = Domingo)
        inicio_semana_actual = hoy - timedelta(days=hoy.weekday())
        fin_semana_actual = inicio_semana_actual + timedelta(days=6)

        # Controles superiores
        col1, col2 = st.columns(2)
        with col1:
            usuario_seleccionado = st.selectbox("👤 Selecciona tu Usuario (Programador)", df_prog["usuario"].tolist(), key="ventas_prog")
        with col2:
            # Selector de semana (permitiendo elegir el lunes de la semana a consultar)
            lunes_seleccionado = st.date_input("Semana (Selecciona cualquier día de la semana deseada)", hoy)
            # Normalizar al lunes de esa semana
            lunes_semana = lunes_seleccionado - timedelta(days=lunes_seleccionado.weekday())
            domingo_semana = lunes_semana + timedelta(days=6)

        st.info(f"Mostrando semana del **{lunes_semana}** al **{domingo_semana}** para el programador **{usuario_seleccionado}**.")
        st.markdown("---")

        # 3. Obtener estaciones del programador
        query_est = f"""
            SELECT id AS "ID", plaza AS "Plaza", nombre AS "Estacion"
            FROM estaciones
            WHERE usuario = '{usuario_seleccionado}'
            ORDER BY plaza, id;
        """
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning(f"El usuario {usuario_seleccionado} no tiene estaciones asignadas.")
            return

        # Selector para elegir qué estación consultar/registrar en detalle semanal
        lista_estaciones_opciones = [f"{row['ID']} - {row['Estacion']} ({row['Plaza']})" for _, row in df_estaciones.iterrows()]
        estacion_elegida_str = st.selectbox("Selecciona la Estación a Registrar", lista_estaciones_opciones)
        
        estacion_id = estacion_elegida_str.split(" - ")[0]

        # 4. Generar el rango de fechas de lunes a domingo para la estación seleccionada
        fechas_semana = [lunes_semana + timedelta(days=i) for i in range(7)]
        nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        df_semanal = pd.DataFrame({
            "Fecha": fechas_semana,
            "Día": nombres_dias,
            "Regular": [0] * 7,
            "Premium": [0] * 7,
            "Diesel": [0] * 7
        })

        # Consultar ventas existentes en ese rango de fechas para esta estación
        query_ventas = f"""
            SELECT fecha, regular, premium, diesel 
            FROM ventas_historico 
            WHERE estacion_id = '{estacion_id}' 
              AND fecha BETWEEN '{lunes_semana}' AND '{domingo_semana}';
        """
        df_existentes = pd.read_sql(query_ventas, conn)

        if not df_existentes.empty:
            # Asegurar formato date para comparar
            df_existentes["fecha"] = pd.to_datetime(df_existentes["fecha"]).dt.date
            for idx, row in df_semanal.iterrows():
                match = df_existentes[df_existentes["fecha"] == row["Fecha"]]
                if not match.empty:
                    df_semanal.loc[idx, "Regular"] = int(match.iloc[0]["regular"])
                    df_semanal.loc[idx, "Premium"] = int(match.iloc[0]["premium"])
                    df_semanal.loc[idx, "Diesel"] = int(match.iloc[0]["diesel"])

        # 5. Formulario y tabla interactiva para los 7 días de la semana
        with st.form(f"form_ventas_{estacion_id}"):
            st.markdown(f"#### Ventas Semanales para: `{estacion_elegida_str}`")
            
            df_editado = st.data_editor(
                df_semanal,
                column_config={
                    "Fecha": st.column_config.DateColumn("Fecha", disabled=True, format="YYYY-MM-DD"),
                    "Día": st.column_config.TextColumn("Día", disabled=True),
                    "Regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0, format="%,d", step=100),
                    "Premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0, format="%,d", step=100),
                    "Diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0, format="%,d", step=100),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed"
            )
            
            submitted = st.form_submit_button("💾 Guardar / Actualizar Ventas Semanales", use_container_width=True)
            
            if submitted:
                try:
                    cursor = conn.cursor()
                    for _, row in df_editado.iterrows():
                        cursor.execute(
                            """
                            INSERT INTO ventas_historico (estacion_id, fecha, regular, premium, diesel)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (estacion_id, fecha) 
                            DO UPDATE SET regular = EXCLUDED.regular, 
                                          premium = EXCLUDED.premium, 
                                          diesel = EXCLUDED.diesel;
                            """,
                            (estacion_id, row["Fecha"], row["Regular"], row["Premium"], row["Diesel"])
                        )
                    conn.commit()
                    cursor.close()
                    st.success(f"¡Ventas semanales guardadas exitosamente para la estación {estacion_id}!")
                except Exception as e:
                    st.error(f"Error al guardar las ventas en la base de datos: {e}")

    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
