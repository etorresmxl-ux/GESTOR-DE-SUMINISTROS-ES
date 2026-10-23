from datetime import date
import pandas as pd
import streamlit as st


def normalizar_producto(producto_raw):
  """Estandariza los nombres de productos para la bitácora de descargas."""
  if pd.isna(producto_raw):
    return ""
  p_str = str(producto_raw).strip().upper()
  if "REGULAR" in p_str or "MAGNA" in p_str:
    return "REGULAR"
  elif "PREMIUM" in p_str:
    return "PREMIUM"
  elif "DIESEL" in p_str:
    return "DIESEL"
  return p_str


def render(conn):
  st.markdown("### 🚛 Módulo de Registro de Descargas (Bitácora)")
  st.write(
      "Registra la información detallada de las descargas físicas de combustible"
      " basándote en la orden de carga / remisión del pipero."
  )
  st.markdown("---")

  try:
    # 1. Consultar estaciones disponibles para los selectores
    query_est = """
            SELECT DISTINCT id_estacion, nombre, plaza 
            FROM estaciones 
            ORDER BY plaza, id_estacion;
        """
    df_estaciones = pd.read_sql(query_est, conn)

    if df_estaciones.empty:
      st.warning("No se encontraron estaciones registradas en el sistema.")
      return

    # 2. Formulario de Captura de Descarga
    with st.form("form_bitacora_descarga", clear_on_submit=True):
      st.markdown("##### ➕ Registrar Nueva Descarga Física")

      col1, col2, col3 = st.columns(3)
      with col1:
        num_embarque = st.number_input(
            "Número de Embarque:",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 123456",
        )
      with col2:
        fecha_carga = st.date_input(
            "Fecha de Carga:", value=date.today()
        )
      with col3:
        tad_origen = st.number_input(
            "TAD Origen (Número):",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 638",
        )

      col4, col5, col6 = st.columns(3)
      with col4:
        cliente_num = st.number_input(
            "Cliente (Proveedor - Número):",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 1",
        )
      with col5:
        lista_est_opciones = [
            f"{r['id_estacion']} - {r['nombre']} ({r['plaza']})"
            for _, r in df_estaciones.iterrows()
        ]
        estacion_sel_str = st.selectbox("Destino (Estación):", lista_est_opciones)
        estacion_id = estacion_sel_str.split(" - ")[0]
      with col6:
        producto_sel = st.selectbox(
            "Producto:", ["REGULAR", "PREMIUM", "DIESEL"]
        )

      col7, col8, col9 = st.columns(3)
      with col7:
        volumen_nat = st.number_input(
            "Volumen al Natural (Litros):",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 20000",
        )
      with col8:
        volumen_20c = st.number_input(
            "Volumen a 20°C (Litros):",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 19850",
        )
      with col9:
        temperatura = st.number_input(
            "Temperatura (°C):",
            value=20.0,
            step=0.1,
            format="%.2f",
            placeholder="Ej. 24.5",
        )

      col10, col11 = st.columns(2)
      with col10:
        flete = st.number_input(
            "Costo del Flete ($):",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
        )
      with col11:
        remision_pemex = st.number_input(
            "Remisión PEMEX (RP - Número):",
            min_value=1,
            step=1,
            format="%d",
            placeholder="Ej. 987654",
        )

      submitted = st.form_submit_button(
          "💾 Guardar Descarga en Bitácora", use_container_width=True
      )

      if submitted:
        if (
            num_embarque is None
            or volumen_nat is None
            or volumen_20c is None
            or remision_pemex is None
        ):
          st.warning(
              "⚠️ Por favor completa los campos obligatorios numéricos."
          )
        else:
          cursor = conn.cursor()
          try:
            sql_insert = """
                            INSERT INTO bitacora_descargas 
                            (num_embarque, fecha_carga, tad_origen, cliente, id_estacion, producto, volumen_nat, volumen_20c, temperatura, flete, remision_pemex)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
            cursor.execute(
                sql_insert,
                (
                    int(num_embarque),
                    str(fecha_carga),
                    int(tad_origen),
                    int(cliente_num),
                    str(estacion_id),
                    str(producto_sel),
                    int(volumen_nat),
                    int(volumen_20c),
                    float(temperatura),
                    float(flete),
                    int(remision_pemex),
                ),
            )
            conn.commit()
            cursor.close()
            st.success(
                f"✅ ¡Descarga del embarque #{num_embarque} registrada"
                " exitosamente en la bitácora!"
            )
            st.rerun()
          except Exception as err:
            conn.rollback()
            cursor.close()
            st.error(f"Error al guardar la descarga: {err}")

    st.markdown("---")
    st.markdown("##### 🔍 Historial de Descargas Registradas")

    query_historial = """
            SELECT 
                id,
                num_embarque AS "Embarque",
                fecha_carga AS "Fecha Carga",
                tad_origen AS "TAD",
                cliente AS "Cliente",
                id_estacion AS "Estación",
                producto AS "Producto",
                vol_nat AS "Vol. Natural",
                vol_20c AS "Vol. 20°C",
                temperatura AS "Temp (°C)",
                flete AS "Flete ($)",
                remision_pemex AS "RP"
            FROM bitacora_descargas
            ORDER BY fecha_carga DESC, id DESC
            LIMIT 50;
        """
    # Ajustamos la consulta adaptándonos a los nombres reales de las columnas creadas
    query_historial_real = """
            SELECT 
                num_embarque AS "Embarque",
                fecha_carga AS "Fecha",
                tad_origen AS "TAD",
                cliente AS "Cliente",
                id_estacion AS "Estación",
                producto AS "Producto",
                volumen_nat AS "Vol. Natural (L)",
                volumen_20c AS "Vol. 20°C (L)",
                temperatura AS "Temp (°C)",
                flete AS "Flete ($)",
                remision_pemex AS "RP"
            FROM bitacora_descargas
            ORDER BY fecha_carga DESC, id DESC
            LIMIT 50;
        """
    df_hist = pd.read_sql(query_historial_real, conn)

    if df_hist.empty:
      st.info("No hay registros en la bitácora de descargas aún.")
    else:
      st.dataframe(df_hist, use_container_width=True, hide_index=True)

  except Exception as e:
    st.error(f"Error al cargar el módulo de descargas: {e}")
