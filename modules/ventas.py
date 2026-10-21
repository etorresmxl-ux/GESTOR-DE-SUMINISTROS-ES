from datetime import date, timedelta
import pandas as pd
import streamlit as st


def render(conn):
  st.markdown(
      "### 📊 Registro Semanal de Ventas (Captura Directa de Ventas)"
  )
  st.write(
      "Captura o actualiza las ventas diarias (de lunes a domingo) para las"
      " estaciones asignadas al usuario."
  )

  # CSS personalizado para compactar filas y aplicar diseño cebra
  st.markdown(
      """
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
  """,
      unsafe_allow_html=True,
  )

  try:
    # 1. Obtener la lista de programadores utilizando la tabla/vista estandarizada
    query_prog = (
        'SELECT DISTINCT "user" AS usuario FROM estaciones_detalle WHERE "user"'
        " IS NOT NULL ORDER BY usuario;"
    )
    df_prog = pd.read_sql(query_prog, conn)

    if df_prog.empty:
      st.warning("No hay programadores asignados en las estaciones.")
      return

    # 2. Calcular la semana en curso (Lunes a Domingo)
    hoy = date.today()

    # Controles superiores
    col1, col2 = st.columns(2)
    with col1:
      usuario_seleccionado = st.selectbox(
          "👤 Selecciona tu Usuario (Programador)",
          df_prog["usuario"].tolist(),
          key="ventas_prog",
      )
    with col2:
      lunes_seleccionado = st.date_input(
          "Semana (Selecciona cualquier día de la semana deseada)", hoy
      )
      lunes_semana = lunes_seleccionado - timedelta(
          days=lunes_seleccionado.weekday()
      )
      domingo_semana = lunes_semana + timedelta(days=6)

    st.info(
        f"Mostrando semana del **{lunes_semana}** al **{domingo_semana}** para"
        f" el programador **{usuario_seleccionado}**."
    )
    st.markdown("---")

    # 3. Obtener estaciones del programador desde estaciones_detalle
    query_est = f"""
        SELECT DISTINCT id_estacion AS "ID", tad AS "TAD", plaza AS "Plaza", nombre AS "Estacion"
        FROM estaciones_detalle
        WHERE "user" = '{usuario_seleccionado}'
        ORDER BY plaza, id_estacion;
    """
    df_estaciones = pd.read_sql(query_est, conn)

    if df_estaciones.empty:
      st.warning(
          f"El usuario {usuario_seleccionado} no tiene estaciones asignadas."
      )
      return

    lista_estaciones_opciones = [
        f"{row['ID']} - {row['Estacion']} ({row['Plaza']})"
        for _, row in df_estaciones.iterrows()
    ]
    estacion_elegida_str = st.selectbox(
        "Selecciona la Estación a Registrar", lista_estaciones_opciones
    )

    estacion_id = estacion_elegida_str.split(" - ")[0]

    # 4. Generar el rango de fechas de lunes a domingo para la estación seleccionada
    fechas_semana = [lunes_semana + timedelta(days=i) for i in range(7)]
    nombres_dias = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    df_semanal = pd.DataFrame({
        "Fecha": fechas_semana,
        "Día": nombres_dias,
        "Regular": [0.0] * 7,
        "Premium": [0.0] * 7,
        "Diesel": [0.0] * 7,
    })

    # Consulta adaptada a la tabla de histórico de inventarios/ventas o ventas general
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
          df_semanal.loc[idx, "Regular"] = (
              float(match.iloc[0]["regular"])
              if pd.notna(match.iloc[0]["regular"])
              else 0.0
          )
          df_semanal.loc[idx, "Premium"] = (
              float(match.iloc[0]["premium"])
              if pd.notna(match.iloc[0]["premium"])
              else 0.0
          )
          df_semanal.loc[idx, "Diesel"] = (
              float(match.iloc[0]["diesel"])
              if pd.notna(match.iloc[0]["diesel"])
              else 0.0
          )

    # 5. Formulario y tabla interactiva para los 7 días de la semana
    with st.form(f"form_ventas_{estacion_id}"):
      st.markdown(f"#### Ventas Semanales para: `{estacion_elegida_str}`")

      df_editado = st.data_editor(
          df_semanal,
          column_config={
              "Fecha": st.column_config.DateColumn(
                  "Fecha", disabled=True, format="YYYY-MM-DD"
              ),
              "Día": st.column_config.TextColumn("Día", disabled=True),
              "Regular": st.column_config.NumberColumn(
                  "Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0
              ),
              "Premium": st.column_config.NumberColumn(
                  "Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0
              ),
              "Diesel": st.column_config.NumberColumn(
                  "Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0
              ),
          },
          hide_index=True,
          width="stretch",
          num_rows="fixed",
      )

      submitted = st.form_submit_button(
          "💾 Guardar Ventas Semanales", use_container_width=True
      )

      if submitted:
        try:
          cursor = conn.cursor()
          registros_guardados = 0

          for _, row in df_editado.iterrows():
            fecha_str = str(row["Fecha"])
            reg_val = float(row["Regular"])
            pre_val = float(row["Premium"])
            die_val = float(row["Diesel"])

            # Inserción o actualización directa por cada día de la semana
            sql_upsert = """
                INSERT INTO ventas_historico (estacion_id, fecha, regular, premium, diesel, ignorar_en_promedio)
                VALUES (%s, %s, %s, %s, %s, FALSE)
                ON CONFLICT (estacion_id, fecha) 
                DO UPDATE SET 
                    regular = EXCLUDED.regular,
                    premium = EXCLUDED.premium,
                    diesel = EXCLUDED.diesel;
            """
            cursor.execute(
                sql_upsert,
                (estacion_id, fecha_str, reg_val, pre_val, die_val),
            )
            registros_guardados += 1

          conn.commit()
          cursor.close()
          st.success(
              f"¡Proceso completado! Se guardaron {registros_guardados} días"
              " de ventas exitosamente en la base de datos."
          )
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error al guardar las ventas en la base de datos: {e}")

except Exception as e:
  st.error(f"Error al cargar los datos: {e}")
