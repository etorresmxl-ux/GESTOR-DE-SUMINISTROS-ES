import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Umbral Z global para evitar cualquier problema de alcance de variable
UMBRAL_Z = 2.5

def evaluar_y_gestionar_venta(conn, estacion_id, fecha_str, producto, volumen, metodo_carga):
    """
    Evalúa una venta usando Z-Score basado en las columnas horizontales (regular, premium, diesel) 
    de la misma estación y el mismo día de la semana (últimas 12 semanas).
    """
    cursor = conn.cursor()
    prod_col = producto.lower().strip()
    if prod_col not in ['regular', 'premium', 'diesel']:
        cursor.close()
        return "IGNORADO"
    
    try:
        # Obtener el día de la semana de la fecha ingresada (0 = Lunes, 6 = Domingo)
        dt_obj = pd.to_datetime(fecha_str)
        dia_semana = dt_obj.dayofweek
        
        # Consultar datos históricos para la misma estación y el mismo día de la semana
        query_hist = f"""
            SELECT fecha, {prod_col} 
            FROM ventas_historico 
            WHERE estacion_id = %s 
              AND EXTRACT(DOW FROM fecha) = %s 
              AND fecha < %s 
              AND ignorar_en_promedio = FALSE
            ORDER BY fecha DESC
            LIMIT 12;
        """
        cursor.execute(query_hist, (estacion_id, dia_semana, fecha_str))
        filas = cursor.fetchall()
        
        # Extraer valores numéricos válidos
        valores = [float(row[1]) for row in filas if row[1] is not None]
        
        # Si no hay suficientes datos históricos, se acepta la venta directamente
        if len(valores) < 3:
            _insertar_venta_oficial(cursor, estacion_id, fecha_str, prod_col, volumen)
            cursor.close()
            return "NORMAL"
            
        media = np.mean(valores)
        desv_est = np.std(valores)
        
        # Si la desviación estándar es cero, se compara directamente con la media
        if desv_est == 0:
            if volumen == media:
                _insertar_venta_oficial(cursor, estacion_id, fecha_str, prod_col, volumen)
                cursor.close()
                return "NORMAL"
            else:
                z_score = 99.9  # Desviación alta respecto a una media constante
        else:
            z_score = abs((volumen - media) / desv_est)
            
        # Evaluar contra el umbral Z global
        if z_score <= UMBRAL_Z:
            _insertar_venta_oficial(cursor, estacion_id, fecha_str, prod_col, volumen)
            cursor.close()
            return "NORMAL"
        else:
            _enviar_a_cuarentena(cursor, estacion_id, fecha_str, prod_col, volumen, float(media), float(desv_est), float(z_score), metodo_carga)
            cursor.close()
            return "ANOMALIA"
            
    except Exception as e:
        cursor.close()
        raise e

def _insertar_venta_oficial(cursor, estacion_id, fecha_str, producto, volumen):
    prod_col = producto.lower().strip()
    if prod_col not in ['regular', 'premium', 'diesel']:
        return
    
    sql_upsert = f"""
        INSERT INTO ventas_historico (estacion_id, fecha, {prod_col}, ignorar_en_promedio)
        VALUES (%s, %s, %s, FALSE)
        ON CONFLICT (estacion_id, fecha) 
        DO UPDATE SET 
            {prod_col} = COALESCE(EXCLUDED.{prod_col}, ventas_historico.{prod_col});
    """
    cursor.execute(sql_upsert, (estacion_id, fecha_str, volumen))

def _enviar_a_cuarentena(cursor, estacion_id, fecha_str, producto, volumen, media, desv_est, z_score, metodo_carga):
    sql_cuarentena = """
        INSERT INTO ventas_anomalias (estacion_id, fecha, producto, volumen_capturado, media_historica, desviacion_estandar, z_score, metodo_carga, estatus)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE');
    """
    cursor.execute(sql_cuarentena, (estacion_id, fecha_str, producto, volumen, media, desv_est, z_score, metodo_carga))

def render(conn):
    st.markdown("### 📊 Registro Semanal de Ventas (Con Auditoría de Anomalías)")
    st.write("Captura o actualiza las ventas diarias (de lunes a domingo) para las estaciones asignadas al usuario.")
    
    try:
        # 1. Obtener la lista de programadores
        query_prog = "SELECT DISTINCT usuario FROM estaciones WHERE usuario IS NOT NULL ORDER BY usuario;"
        df_prog = pd.read_sql(query_prog, conn)
        
        if df_prog.empty:
            st.warning("No hay programadores asignados en las estaciones.")
            return

        # 2. Calcular la semana en curso (Lunes a Domingo)
        hoy = date.today()

        # Controles superiores
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
            SELECT id AS "ID", plaza AS "Plaza", nombre AS "Estacion"
            FROM estaciones
            WHERE usuario = '{usuario_seleccionado}'
            ORDER BY plaza, id;
        """
        df_estaciones = pd.read_sql(query_est, conn)
        
        if df_estaciones.empty:
            st.warning(f"El usuario {usuario_seleccionado} no tiene estaciones asignadas.")
            return

        lista_estaciones_opciones = [f"{row['ID']} - {row['Estacion']} ({row['Plaza']})" for _, row in df_estaciones.iterrows()]
        estacion_elegida_str = st.selectbox("Selecciona la Estación a Registrar", lista_estaciones_opciones)
        
        estacion_id = estacion_elegida_str.split(" - ")[0]

        # 4. Generar el rango de fechas de lunes a domingo para la estación seleccionada
        fechas_semana = [lunes_semana + timedelta(days=i) for i in range(7)]
        nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        df_semanal = pd.DataFrame({
            "Fecha": fechas_semana,
            "Día": nombres_dias,
            "Regular": [0.0] * 7,
            "Premium": [0.0] * 7,
            "Diesel": [0.0] * 7
        })

        # Consulta adaptada a columnas separadas (regular, premium, diesel)
        query_ventas_cols = f"""
            SELECT fecha, regular, premium, diesel 
            FROM ventas_historico 
            WHERE estacion_id = '{estacion_id}' 
              AND fecha BETWEEN '{lunes_semana}' AND '{domingo_semana}';
        """
        df_existentes = pd.read_sql(query_ventas_cols, conn)

        if not df_existentes.empty:
            df_existentes["fecha"] = pd.to_datetime(df_existentes["fecha"]).dt.date
            for idx, row in df_semanal.iterrows():
                match = df_existentes[df_existentes["fecha"] == row["Fecha"]]
                if not match.empty:
                    df_semanal.loc[idx, "Regular"] = float(match.iloc[0]["regular"]) if pd.notna(match.iloc[0]["regular"]) else 0.0
                    df_semanal.loc[idx, "Premium"] = float(match.iloc[0]["premium"]) if pd.notna(match.iloc[0]["premium"]) else 0.0
                    df_semanal.loc[idx, "Diesel"] = float(match.iloc[0]["diesel"]) if pd.notna(match.iloc[0]["diesel"]) else 0.0

        # 5. Formulario y tabla interactiva para los 7 días de la semana
        with st.form(f"form_ventas_{estacion_id}"):
            st.markdown(f"#### Ventas Semanales para: `{estacion_elegida_str}`")
            
            df_editado = st.data_editor(
                df_semanal,
                column_config={
                    "Fecha": st.column_config.DateColumn("Fecha", disabled=True, format="YYYY-MM-DD"),
                    "Día": st.column_config.TextColumn("Día", disabled=True),
                    "Regular": st.column_config.NumberColumn("Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "Premium": st.column_config.NumberColumn("Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                    "Diesel": st.column_config.NumberColumn("Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed"
            )
            
            submitted = st.form_submit_button("💾 Guardar / Evaluar Ventas Semanales", use_container_width=True)
            
            if submitted:
                try:
                    normales_count = 0
                    anomalias_count = 0
                    
                    for _, row in df_editado.iterrows():
                        fecha_str = str(row["Fecha"])
                        
                        # Evaluamos cada producto individualmente con el motor de Z-Score
                        for prod in ["regular", "premium", "diesel"]:
                            vol = float(row[prod.capitalize()])
                            if vol > 0: # Solo evaluamos si hay volumen registrado
                                resultado = evaluar_y_gestionar_venta(
                                    conn, estacion_id, fecha_str, prod, vol, "Registro Manual"
                                )
                                if resultado == "ANOMALIA":
                                    anomalias_count += 1
                                elif resultado == "NORMAL":
                                    normales_count += 1

                    conn.commit()
                    st.success(f"¡Proceso completado! Registros guardados con éxito: {normales_count}.")
                    if anomalias_count > 0:
                        st.warning(f"⚠️ Se detectaron y enviaron **{anomalias_count} registros a Cuarentena (`ventas_anomalias`)** por superar el umbral estadístico de desviación.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al guardar las ventas en la base de datos: {e}")

    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
