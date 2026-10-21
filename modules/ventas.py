from datetime import date, timedelta
import pandas as pd
import streamlit as st


def render(conn):
  st.markdown("### 📊 Módulo de Gestión y Control de Ventas")
  st.write(
      "Administra, consulta y registra los volúmenes de venta diarios por"
      " estación y producto."
  )
  st.markdown("---")

  # Pestañas de navegación interna del módulo
  tab_consulta, tab_registro = st.tabs(
      ["📈 Consulta de Ventas", "📝 Registro y Captura"]
  )

  # ==========================================
  # 1. PESTAÑA DE CONSULTA DE VENTAS
  # ==========================================
  with tab_consulta:
    st.subheader("Historial de Ventas Registradas")

    col1, col2 = st.columns(2)
    with col1:
      fecha_inicio = st.date_input(
          "Fecha Inicial", date.today() - timedelta(days=7)
      )
    with col2:
      fecha_fin = st.date_input("Fecha Final", date.today())

    try:
      query_historial = f"""
                SELECT fecha, id_estacion, producto, volumen 
                FROM ventas 
                WHERE fecha BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
                ORDER BY fecha DESC, id_estacion ASC;
            """
      df_ventas_hist = pd.read_sql(query_historial, conn)

      if df_ventas_hist.empty:
        st.info("No hay registros de ventas para el rango de fechas seleccionado.")
      else:
        st.dataframe(
            df_ventas_hist,
            column_config={
                "fecha": st.column_config.DateColumn(
                    "Fecha", format="YYYY-MM-DD"
                ),
                "id_estacion": st.column_config.TextColumn("Estación ID"),
                "producto": st.column_config.TextColumn("Producto"),
                "volumen": st.column_config.NumberColumn(
                    "Volumen (Lts)", format="%,.2f"
                ),
            },
            hide_index=True,
            use_container_width=True,
            height=400,
        )
    except Exception as e:
      st.error(f"Error al consultar el historial de ventas: {e}")

  # ==========================================
  # 2. PESTAÑA DE REGISTRO Y CAPTURA
  # ==========================================
  with tab_registro:
    st.subheader("Captura Directa de Ventas por Estación")

    # Obtener listado de estaciones
    try:
      query_est = (
          "SELECT id_estacion, nombre, plaza FROM estaciones ORDER BY plaza,"
          " id_estacion;"
      )
      df_estaciones = pd.read_sql(query_est, conn)

      if df_estaciones.empty:
        st.warning(
            "No se encontraron estaciones registradas en la base de datos."
        )
        return

      opciones_estaciones = (
          df_estaciones["id_estacion"]
          + " - "
          + df_estaciones["nombre"]
          + " ("
          + df_estaciones["plaza"]
          + ")"
      ).tolist()

      estacion_seleccionada = st.selectbox(
          "Selecciona la Estación:", opciones_estaciones
      )
      estacion_id = estacion_seleccionada.split(" - ")[0]

      fecha_venta = st.date_input("Fecha de Venta", date.today(), key="f_venta")

      st.markdown("---")
      st.markdown(
          f"##### Ingresa los volúmenes para la estación: **{estacion_seleccionada}**"
      )

      # Formulario de captura rápida para los 3 productos principales
      with st.form("form_nuevo_registro_ventas"):
        col_r, col_p, col_d = st.columns(3)

        with col_r:
          vol_regular = st.number_input(
              "Regular (Lts)", min_value=0.0, format="%,.2f", step=100.0
          )
        with col_p:
          vol_premium = st.number_input(
              "Premium (Lts)", min_value=0.0, format="%,.2f", step=100.0
          )
        with col_d:
          vol_diesel = st.number_input(
              "Diesel (Lts)", min_value=0.0, format="%,.2f", step=100.0
          )

        submitted_ventas = st.form_submit_button(
            "💾 Guardar / Actualizar Ventas", use_container_width=True
        )

        if submitted_ventas:
          try:
            cursor = conn.cursor()
            sql_upsert = """
                            INSERT INTO ventas (fecha, id_estacion, producto, volumen)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (fecha, id_estacion, producto) 
                            DO UPDATE SET volumen = EXCLUDED.volumen;
                        """

            # Insertar o actualizar cada producto
            productos_a_guardar = [
                ("Regular", float(vol_regular)),
                ("Premium", float(vol_premium)),
                ("Diesel", float(vol_diesel)),
            ]

            for producto, volumen in productos_a_guardar:
              cursor.execute(
                  sql_upsert,
                  (str(fecha_venta), estacion_id, producto, volumen),
              )

            conn.commit()
            cursor.close()
            st.success(
                "¡Ventas registradas y actualizadas correctamente para el"
                f" {fecha_venta}!"
            )
            st.rerun()
          except Exception as e:
            conn.rollback()
            st.error(f"Error al guardar los volúmenes de venta: {e}")

    except Exception as e:
      st.error(f"Error al cargar las configuraciones del módulo: {e}")
