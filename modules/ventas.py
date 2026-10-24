from datetime import date, timedelta
import pandas as pd
import streamlit as st


def render(conn):
  st.markdown("### 📊 Registro Semanal de Ventas por Estación")
  st.write(
      "Selecciona una estación y una fecha para consultar o capturar la semana"
      " completa (de lunes a domingo)."
  )
  st.markdown("---")

  if conn is None:
    st.error("No hay conexión a la base de datos.")
    return

  usuario_actual = st.session_state.get("usuario_actual", "")
  rol_actual = st.session_state.get("rol_actual", "operador")

  try:
    # 1. Obtener la lista de estaciones disponibles según el rol del usuario
    if rol_actual == "admin":
      query_est = """
            SELECT DISTINCT id_estacion AS "ID", nombre AS "Estacion", plaza AS "Plaza"
            FROM estaciones
            ORDER BY plaza, id_estacion;
        """
    else:
      query_est = f"""
            SELECT DISTINCT e.id_estacion AS "ID", e.nombre AS "Estacion", e.plaza AS "Plaza"
            FROM estaciones e
            JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
            WHERE ue.usuario = '{usuario_actual}'
            ORDER BY e.plaza, e.id_estacion;
        """

    df_estaciones = pd.read_sql(query_est, conn)

    if df_estaciones.empty:
      st.warning(
          "No se encontraron estaciones registradas o asignadas a tu usuario."
      )
      return

    # 2. Controles superiores: Selector de Estación y Selector de Fecha
    col1, col2 = st.columns(2)

    with col1:
      lista_opciones = [
          f"{row['ID']} - {row['Estacion']} ({row['Plaza']})"
          for _, row in df_estaciones.iterrows()
      ]
      estacion_elegida = st.selectbox(
          "⛽ Selecciona la Estación", lista_opciones, key="ventas_estacion_sel"
      )
      estacion_id = estacion_elegida.split(" - ")[0]

    with col2:
      lunes_seleccionado = st.date_input(
          "📅 Semana (Selecciona cualquier día)",
          date.today(),
          key="ventas_fecha_sel",
      )
      # Calcular automáticamente el Lunes y Domingo de esa semana
      lunes_semana = lunes_seleccionado - timedelta(
          days=lunes_seleccionado.weekday()
      )
      domingo_semana = lunes_semana + timedelta(days=6)

    st.info(
        f"Mostrando semana del **{lunes_semana}** al **{domingo_semana}** para la"
        f" estación: **{estacion_elegida}**."
    )
    st.markdown("---")

    # 3. Validación: Consultar la tabla 'tanques' en Supabase[cite: 4] para determinar los productos válidos de la estación
    productos_validos = []
    nombres_prod_map = {
        "regular": "Regular",
        "premium": "Premium",
        "diesel": "Diesel",
    }

    try:
      query_tanques = f"""
            SELECT DISTINCT producto, capacidad_maxima 
            FROM tanques 
            WHERE id_estacion = '{estacion_id}';
        """
      df_tanques = pd.read_sql(query_tanques, conn)
      if not df_tanques.empty:
        for _, r_t in df_tanques.iterrows():
          p_raw = str(r_t["producto"]).strip().lower()
          cap = (
              float(r_t["capacidad_maxima"])
              if pd.notna(r_t["capacidad_maxima"])
              else 0.0
          )
          if cap > 0:
            if "regular" in p_raw or "magna" in p_raw:
              if "regular" not in productos_validos:
                productos_validos.append("regular")
            elif "premium" in p_raw:
              if "premium" not in productos_validos:
                productos_validos.append("premium")
            elif "diesel" in p_raw:
              if "diesel" not in productos_validos:
                productos_validos.append("diesel")
    except Exception as e_tanq:
      st.warning(f"Aviso al consultar tanques: {e_tanq}")

    # Ordenar productos válidos de forma estándar
    productos_validos = [
        p for p in ["regular", "premium", "diesel"] if p in productos_validos
    ]

    # Fallback de seguridad por si la tabla tanques estuviera vacía para esta estación
    if not productos_validos:
      productos_validos = ["regular", "premium"]
      st.caption(
          "ℹ️ No se encontraron registros de tanques específicos, habilitando"
          " productos estándar (Regular, Premium)."
      )
    else:
      prods_str = ", ".join([nombres_prod_map[p] for p in productos_validos])
      st.caption(
          f"ℹ️ Productos habilitados según registros de tanques: **{prods_str}**."
      )

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

    # 5. Validar y precargar registros existentes si ya fueron guardados previamente
    query_ventas_previas = f"""
        SELECT fecha, producto, volumen 
        FROM ventas 
        WHERE id_estacion = '{estacion_id}' 
          AND fecha BETWEEN '{lunes_semana}' AND '{domingo_semana}';
    """
    df_existentes = pd.read_sql(query_ventas_previas, conn)

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
              & (df_existentes["producto_norm"] == p)
          ]
          if not match.empty:
            val = match.iloc[0]["volumen"]
            if pd.notna(val):
              df_semanal.loc[idx, nombres_prod_map[p]] = float(val)

    # 6. Tabla Matriz Interactiva dentro de un formulario
    st.markdown(f"#### Matriz de Ventas Semanales")

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

    with st.form(f"form_ventas_semanal_{estacion_id}"):
      df_editado = st.data_editor(
          df_semanal,
          column_config=column_config,
          hide_index=True,
          use_container_width=True,
          num_rows="fixed",
          height=350,
      )

      st.markdown("")
      submitted = st.form_submit_button(
          "💾 Guardar Ventas Semanales", use_container_width=True
      )

      if submitted:
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
                  (fecha_str, estacion_id, p, float(volumen)),
              )
              count += 1

        conn.commit()
        cursor.close()
        st.success(
            f"¡Se guardaron y actualizaron {count} registros de ventas"
            " exitosamente!"
        )
        st.rerun()

  except Exception as e:
    st.error(f"Error al cargar o guardar el módulo de ventas: {e}")
