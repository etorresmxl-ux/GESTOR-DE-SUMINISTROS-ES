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
  # Estilo CSS para ocultar los botones (+ / -) en los campos numéricos
  st.markdown(
      """
        <style>
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        input[type="number"] {
            -moz-appearance: textfield;
        }
        </style>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("### 🚛 Módulo de Registro de Descargas (Bitácora)")
  st.write(
      "Registra la información detallada de las descargas físicas de combustible"
      " basándote en la orden de carga / remisión del pipero."
  )
  st.markdown("---")

  if conn is None:
    st.error("No hay conexión a la base de datos.")
    return

  try:
    # 1. Consultar usuarios disponibles desde 'usuarios_estaciones'
    query_usuarios = """
            SELECT DISTINCT usuario 
            FROM usuarios_estaciones 
            WHERE usuario IS NOT NULL 
            ORDER BY usuario;
        """
    df_usuarios = pd.read_sql(query_usuarios, conn)

    if df_usuarios.empty:
      st.warning(
          "No se encontraron usuarios asignados en la tabla"
          " 'usuarios_estaciones'."
      )
      return

    lista_usuarios = df_usuarios["usuario"].tolist()

    # Controles superiores: Filtro de Usuario y Estación
    col_f1, col_f2 = st.columns(2)
    with col_f1:
      usuario_seleccionado = st.selectbox(
          "👤 Selecciona el Usuario:",
          lista_usuarios,
          key="descarga_usuario_sel",
      )

    query_estaciones = f"""
            SELECT e.id_estacion, e.nombre, e.plaza, e.tad 
            FROM estaciones e
            JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
            WHERE ue.usuario = '{usuario_seleccionado}'
            ORDER BY e.plaza, e.id_estacion;
        """
    df_estaciones = pd.read_sql(query_estaciones, conn)

    if df_estaciones.empty:
      st.warning(
          f"El usuario **{usuario_seleccionado}** no tiene estaciones"
          " asignadas."
      )
      return

    with col_f2:
      lista_est_opciones = [
          f"{r['id_estacion']} - {r['nombre']} ({r['plaza']})"
          for _, r in df_estaciones.iterrows()
      ]
      estacion_sel_str = st.selectbox(
          "⛽ Selecciona la Estación:",
          lista_est_opciones,
          key="descarga_estacion_sel",
      )
      estacion_id = estacion_sel_str.split(" - ")[0]

    # Obtener la TAD asociada por defecto a la estación seleccionada
    row_estacion_sel = df_estaciones[
        df_estaciones["id_estacion"] == estacion_id
    ].iloc[0]
    tad_asociada = 1
    if pd.notna(row_estacion_sel["tad"]):
      try:
        tad_asociada = int(str(row_estacion_sel["tad"]).strip())
      except ValueError:
        tad_asociada = 1

    st.markdown("---")

    # 2. Selector de Órdenes de Carga según la estación seleccionada
    query_ordenes = f"""
            SELECT id, producto, fecha_programacion, volumen_programado
            FROM programacion_cargas
            WHERE id_estacion = '{estacion_id}'
            ORDER BY fecha_programacion DESC;
        """
    df_ordenes_prog = pd.read_sql(query_ordenes, conn)

    orden_seleccionada_info = None
    if not df_ordenes_prog.empty:
      st.markdown("##### 🔍 Selector de Órdenes de Carga Programadas")
      opciones_ordenes = ["(Ninguna / Captura manual libre)"] + [
          f"Folio #{r['id']} - {r['producto']} - {r['fecha_programacion']} - {float(r['volumen_programado']):,.0f} L"
          for _, r in df_ordenes_prog.iterrows()
      ]
      sel_orden_prog = st.selectbox(
          "Selecciona una Orden de Carga para autocompletar el formulario:",
          opciones_ordenes,
          key="sel_orden_prog_descarga",
      )

      if sel_orden_prog != "(Ninguna / Captura manual libre)":
        orden_id_sel = int(sel_orden_prog.split(" - ")[0].replace("Folio #", ""))
        orden_seleccionada_info = df_ordenes_prog[
            df_ordenes_prog["id"] == orden_id_sel
        ].iloc[0]
    else:
      st.info(
          "ℹ️ No hay órdenes de carga programadas para esta estación. Puedes"
          " realizar un registro manual."
      )

    st.markdown("---")

    # Valores por defecto basados en la orden seleccionada si existe
    def_fecha = (
        pd.to_datetime(orden_seleccionada_info["fecha_programacion"]).date()
        if orden_seleccionada_info is not None
        else date.today()
    )
    def_prod = (
        normalizar_producto(orden_seleccionada_info["producto"])
        if orden_seleccionada_info is not None
        else "REGULAR"
    )
    def_vol = (
        int(float(orden_seleccionada_info["volumen_programado"]))
        if orden_seleccionada_info is not None
        else 0
    )
    prod_indices = {"REGULAR": 0, "PREMIUM": 1, "DIESEL": 2}
    def_prod_idx = prod_indices.get(def_prod, 0)

    # 3. Formulario de Captura de Descarga
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
        fecha_carga = st.date_input("Fecha de Carga:", value=def_fecha)
      with col3:
        tad_origen = st.number_input(
            "TAD Origen (Número):",
            min_value=1,
            value=tad_asociada,
            step=1,
            format="%d",
            placeholder="Ej. 638",
        )

      col4, col5, col6 = st.columns(3)
      with col4:
        cliente_opciones = ["1501350 - GAZPRO", "201549 - DAGAL"]
        cliente_sel = st.selectbox("Cliente:", cliente_opciones)
        cliente_num = int(cliente_sel.split(" - ")[0])
      with col5:
        st.text_input(
            "Destino (Estación):", value=estacion_sel_str, disabled=True
        )
      with col6:
        producto_sel = st.selectbox(
            "Producto:",
            ["REGULAR", "PREMIUM", "DIESEL"],
            index=def_prod_idx,
        )

      col7, col8, col9 = st.columns(3)
      with col7:
        volumen_nat = st.number_input(
            "Volumen al Natural (Litros):",
            min_value=1,
            value=def_vol if def_vol > 0 else None,
            step=1,
            format="%d",
            placeholder="Ej. 20000",
        )
      with col8:
        volumen_20c = st.number_input(
            "Volumen a 20°C (Litros):",
            min_value=1,
            value=def_vol if def_vol > 0 else None,
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

    query_historial_real = f"""
            SELECT 
                bd.num_embarque AS "Embarque",
                bd.fecha_carga AS "Fecha",
                bd.tad_origen AS "TAD",
                bd.cliente AS "Cliente",
                CONCAT(e.id_estacion, ' - ', e.nombre) AS "Estación",
                bd.producto AS "Producto",
                bd.volumen_nat AS "Vol. Natural (L)",
                bd.volumen_20c AS "Vol. 20°C (L)",
                bd.temperatura AS "Temp (°C)",
                bd.flete AS "Flete ($)",
                bd.remision_pemex AS "RP"
            FROM bitacora_descargas bd
            JOIN estaciones e ON bd.id_estacion = e.id_estacion
            WHERE bd.id_estacion = '{estacion_id}'
            ORDER BY bd.fecha_carga DESC, bd.id DESC
            LIMIT 50;
        """
    df_hist = pd.read_sql(query_historial_real, conn)

    if df_hist.empty:
      st.info("No hay registros en la bitácora de descargas para esta estación.")
    else:
      st.dataframe(df_hist, use_container_width=True, hide_index=True)

  except Exception as e:
    st.error(f"Error al cargar el módulo de descargas: {e}")
