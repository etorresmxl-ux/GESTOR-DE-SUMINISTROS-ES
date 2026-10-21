from datetime import date, timedelta
import pandas as pd
import streamlit as st


def render(conn):
  st.markdown("### 📊 Registro Simplificado de Ventas Semanales")
  st.write(
      "Selecciona la semana y la estación para registrar o actualizar las"
      " ventas diarias de forma directa."
  )
  st.markdown("---")

  # 1. Obtener la lista de estaciones disponibles
  try:
    query_est = (
        'SELECT id AS "ID", nombre AS "Estacion", plaza AS "Plaza" FROM'
        " estaciones ORDER BY plaza, id;"
    )
    df_estaciones = pd.read_sql(query_est, conn)
  except Exception:
    try:
      query_est = (
          "SELECT DISTINCT id_estacion AS \"ID\", nombre AS \"Estacion\","
          " plaza AS \"Plaza\" FROM estaciones_detalle ORDER BY plaza,"
          " id_estacion;"
      )
      df_estaciones = pd.read_sql(query_est, conn)
    except Exception as e:
      st.error(f"Error al cargar el catálogo de estaciones: {e}")
      return

  if df_estaciones.empty:
    st.warning("No se encontraron estaciones registradas en el sistema.")
    return

  # 2. Controles superiores: Selector de Fecha (Semanal) y Estación
  col1, col2 = st.columns(2)

  with col1:
    lunes_seleccionado = st.date_input(
        "📅 Selecciona cualquier día de la semana deseada", date.today()
    )
    # Calcular automáticamente el Lunes y Domingo de esa semana
    lunes_semana = lunes_seleccionado - timedelta(
        days=lunes_seleccionado.weekday()
    )
    domingo_semana = lunes_semana + timedelta(days=6)

  with col2:
    lista_opciones = [
        f"{row['ID']} - {row['Estacion']} ({row['Plaza']})"
        for _, row in df_estaciones.iterrows()
    ]
    estacion_elegida = st.selectbox(
        "⛽ Selecciona la Estación", lista_opciones
    )

  estacion_id = estacion_elegida.split(" - ")[0]

  st.info(
      f"Trabajando con la semana del **{lunes_semana}** al"
      f" **{domingo_semana}** para la estación: **{estacion_elegida}**."
  )
  st.markdown("---")

  # 3. Validar con qué productos cuenta la estación (consultando historial previo)
  try:
    query_prod = f"""
            SELECT DISTINCT LOWER(producto) as producto 
            FROM ventas 
            WHERE id_estacion = '{estacion_id}'
            UNION
            SELECT DISTINCT LOWER(producto) as producto 
            FROM inventarios 
            WHERE id_estacion = '{estacion_id}';
        """
    df_prods = pd.read_sql(query_prod, conn)
    productos_encontrados = (
        df_prods["producto"].dropna().str.lower().tolist()
    )
  except Exception:
    productos_encontrados = []

  # Filtrar cuáles de los 3 productos principales aplican
  productos_validos = []
  for p in ["regular", "premium", "diesel"]:
    if any(p in prod for prod in productos_encontrados):
      productos_validos.append(p)

  # Si la estación es nueva o no tiene historial, habilitamos los 3 por defecto
  if not productos_validos:
    productos_validos = ["regular", "premium", "diesel"]

  nombres_prod_map = {
      "regular": "Regular",
      "premium": "Premium",
      "diesel": "Diesel",
  }

  # 4. Generar la estructura de la matriz (Lunes a Domingo = 7 filas)
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

  data_matriz = {"Fecha": fechas_semana, "Día": nombres_dias}
  for p in productos_validos:
    data_matriz[nombres_prod_map[p]] = [0.0] * 7

  df_semanal = pd.DataFrame(data_matriz)

  # 5. Precargar ventas existentes si ya fueron capturadas previamente
  try:
    query_ventas = f"""
            SELECT fecha, producto, volumen 
            FROM ventas 
            WHERE id_estacion = '{estacion_id}' 
              AND fecha BETWEEN '{lunes_semana}' AND '{domingo_semana}';
        """
    df_existentes = pd.read_sql(query_ventas, conn)

    if not df_existentes.empty:
      df_existentes["fecha"] = pd.to_datetime(df_existentes["fecha"]).dt.date
      df_existentes["producto_norm"] = (
          df_existentes["producto"].str.lower().str.strip()
      )

      for idx, row in df_semanal.iterrows():
        f_row = row["Fecha"]
        for p in productos_validos:
          match = df_existentes[
              (df_existentes["fecha"] == f_row)
              & (df_existentes["producto_norm"].str.contains(p))
          ]
          if not match.empty:
            val = match.iloc[0]["volumen"]
            if pd.notna(val):
              df_semanal.loc[idx, nombres_prod_map[p]] = float(val)
  except Exception as e:
    st.warning(
        "No se pudieron precargar registros previos (iniciando en ceros):"
        f" {str(e)}"
    )

  # 6. Tabla interactiva (Data Editor) y botón de guardado al fondo
  st.markdown(f"#### Matriz de Registro: `{estacion_elegida}`")

  column_config = {
      "Fecha": st.column_config.DateColumn(
          "Fecha", disabled=True, format="YYYY-MM-DD"
      ),
      "Día": st.column_config.TextColumn("Día", disabled=True),
  }

  for p in productos_validos:
    col_nombre = nombres_prod_map[p]
    column_config[col_nombre] = st.column_config.NumberColumn(
        f"{col_nombre} (Lts)", min_value=0.0, format="%,.2f", step=100.0
    )

  with st.form(f"form_ventas_simple_{estacion_id}"):
    df_editado = st.data_editor(
        df_semanal,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
    )

    st.markdown("")
    submitted = st.form_submit_button(
        "💾 Guardar Cambios de Ventas", use_container_width=True
    )

    if submitted:
      try:
        cursor = conn.cursor()
        sql_upsert = """
                    INSERT INTO ventas (fecha, id_estacion, producto, volumen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fecha, id_estacion, producto) 
                    DO UPDATE SET volumen = EXCLUDED.volumen;
                """
        count = 0
        for _, row in df_editado.iterrows():
          fecha_str = str(row["Fecha"])
          for p in productos_validos:
            col_nombre = nombres_prod_map[p]
            volumen = row[col_nombre]
            if pd.notna(volumen) and volumen >= 0:
              cursor.execute(
                  sql_upsert,
                  (fecha_str, estacion_id, col_nombre.capitalize(), float(volumen)),
              )
              count += 1

        conn.commit()
        cursor.close()
        st.success(
            f"¡Se guardaron {count} registros correctamente para la semana del"
            f" {lunes_semana} al {domingo_semana}!"
        )
        st.rerun()
      except Exception as e:
        conn.rollback()
        st.error(f"Error al guardar los registros en la base de datos: {e}")
