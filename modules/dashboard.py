from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import streamlit as st


def normalizar_producto(producto_raw):
  """Normaliza cualquier variante de producto a una llave estándar: 'regular', 'premium', 'diesel' o el texto original limpio si no coincide."""
  if pd.isna(producto_raw):
    return ""
  p_str = str(producto_raw).strip().lower()
  if "regular" in p_str or "magna" in p_str:
    return "regular"
  elif "premium" in p_str:
    return "premium"
  elif "diesel" in p_str:
    return "diesel"
  else:
    return p_str


def render(conn):
  # Definir fecha y hora local (UTC-7 / Noroeste / Mexicali) para los cálculos
  tz_local = timezone(timedelta(hours=-7))
  ahora_local = datetime.now(tz_local)
  hoy = ahora_local.date()
  hoy_str = hoy.strftime("%Y-%m-%d")

  st.markdown(
      "### 📊 Dashboard Operativo - Inventarios, Espacio Disponible y Días de"
      " Suministro (D/S)"
  )
  st.write(
      "Resumen general por estación: Inventario teórico/actualizado al día de"
      " hoy (con indicador * si es arrastrado), capacidad máxima real de"
      " tanques, cargas del día y Días de Suministro (VDP Ponderada)."
  )

  usuario_actual = st.session_state.get("usuario_actual", "")
  rol_actual = st.session_state.get("rol_actual", "operador")

  # Construir filtros dinámicos según el rol del usuario logueado
  if rol_actual == "admin":
    filtro_estaciones_cte = """
        info_base AS (
            SELECT DISTINCT id_estacion, tad, plaza, nombre as estacion
            FROM estaciones
        ),
    """
    where_cargas_hoy = f"WHERE fecha_programacion = '{hoy_str}'"
    where_cargas_det = f"WHERE pc.fecha_programacion = '{hoy_str}'"
  else:
    filtro_estaciones_cte = f"""
        info_base AS (
            SELECT DISTINCT e.id_estacion, e.tad, e.plaza, e.nombre as estacion
            FROM estaciones e
            JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
            WHERE ue.usuario = '{usuario_actual}'
        ),
    """
    where_cargas_hoy = f"""
        WHERE fecha_programacion = '{hoy_str}' 
        AND id_estacion IN (
            SELECT id_estacion FROM usuarios_estaciones WHERE usuario = '{usuario_actual}'
        )
    """
    where_cargas_det = f"""
        WHERE pc.fecha_programacion = '{hoy_str}' 
        AND pc.id_estacion IN (
            SELECT id_estacion FROM usuarios_estaciones WHERE usuario = '{usuario_actual}'
        )
    """

  # Consulta utilizando inventarios, VDP y la tabla real de tanques filtrada por usuario[cite: 3, 4, 8]
  query = f""" 
    WITH ultimo_inventario AS ( 
        SELECT id_estacion, fecha, 
               SUM(CASE WHEN producto ILIKE '%regular%' OR producto ILIKE '%magna%' THEN volumen ELSE 0 END) as regular,
               SUM(CASE WHEN producto ILIKE '%premium%' THEN volumen ELSE 0 END) as premium,
               SUM(CASE WHEN producto ILIKE '%diesel%' THEN volumen ELSE 0 END) as diesel,
               ROW_NUMBER() OVER(PARTITION BY id_estacion ORDER BY fecha DESC) as rn 
        FROM inventarios 
        GROUP BY id_estacion, fecha 
    ), 
    {filtro_estaciones_cte}
    vdp_resumen AS ( 
        SELECT id_estacion, 
               SUM(CASE WHEN producto ILIKE '%regular%' OR producto ILIKE '%magna%' THEN vdp_ponderada ELSE 0 END) as vdp_reg,
               SUM(CASE WHEN producto ILIKE '%premium%' THEN vdp_ponderada ELSE 0 END) as vdp_pre,
               SUM(CASE WHEN producto ILIKE '%diesel%' THEN vdp_ponderada ELSE 0 END) as vdp_die 
        FROM v_vdp_analisis 
        GROUP BY id_estacion 
    ), 
    capacidades_tanques AS ( 
        SELECT id_estacion, 
               SUM(CASE WHEN producto ILIKE '%regular%' OR producto ILIKE '%magna%' THEN capacidad_maxima ELSE 0 END) as cap_reg,
               SUM(CASE WHEN producto ILIKE '%premium%' THEN capacidad_maxima ELSE 0 END) as cap_pre,
               SUM(CASE WHEN producto ILIKE '%diesel%' THEN capacidad_maxima ELSE 0 END) as cap_die 
        FROM tanques 
        GROUP BY id_estacion 
    ) 
    SELECT ib.id_estacion, ib.tad, ib.plaza, ib.estacion, 
           COALESCE(ct.cap_reg, 0) as cap_regular, 
           COALESCE(ct.cap_pre, 0) as cap_premium, 
           COALESCE(ct.cap_die, 0) as cap_diesel, 
           COALESCE(ui.regular, 0) as reg_litros, 
           COALESCE(ui.premium, 0) as pre_litros, 
           COALESCE(ui.diesel, 0) as die_litros, 
           ui.fecha as fecha_inventario, 
           COALESCE(vp.vdp_reg, 0) as vdp_reg, 
           COALESCE(vp.vdp_pre, 0) as vdp_pre, 
           COALESCE(vp.vdp_die, 0) as vdp_die 
    FROM info_base ib 
    LEFT JOIN ultimo_inventario ui ON ib.id_estacion = ui.id_estacion AND ui.rn = 1 
    LEFT JOIN vdp_resumen vp ON ib.id_estacion = vp.id_estacion 
    LEFT JOIN capacidades_tanques ct ON ib.id_estacion = ct.id_estacion 
    ORDER BY ib.id_estacion; 
    """
  try:
    df = pd.read_sql(query, conn)

    if df.empty:
      st.warning(
          "No hay datos suficientes para generar el resumen o no tienes"
          " estaciones asignadas."
      )
      return

    # 1. Consultar descargas reales de forma segura
    descargas_reales = {}
    try:
      df_bit_hist = pd.read_sql("SELECT * FROM bitacora_descargas;", conn)
      if not df_bit_hist.empty:
        col_est = next(
            (c for c in df_bit_hist.columns if "estacion" in c.lower()), None
        )
        col_prod = next(
            (c for c in df_bit_hist.columns if "producto" in c.lower()), None
        )
        col_fecha = next(
            (c for c in df_bit_hist.columns if "fecha" in c.lower()), None
        )
        col_cant = next(
            (
                c
                for c in df_bit_hist.columns
                if "cant" in c.lower()
                or "vol" in c.lower()
                or "natural" in c.lower()
            ),
            None,
        )

        if col_est and col_prod and col_fecha and col_cant:
          for _, rb in df_bit_hist.iterrows():
            e_id = str(rb[col_est]).strip()
            pk = normalizar_producto(rb[col_prod])
            f_desc = pd.to_datetime(rb[col_fecha]).strftime("%Y-%m-%d")
            vol_real = (
                float(rb[col_cant]) if pd.notna(rb[col_cant]) else 0.0
            )

            key = (e_id, pk, f_desc)
            descargas_reales[key] = descargas_reales.get(key, 0.0) + vol_real
    except Exception:
      try:
        conn.rollback()
      except:
        pass

    # 2. Ajustar el inventario descontando ventas y sumando descargas
    inventarios_actualizados_reg = []
    inventarios_actualizados_pre = []
    inventarios_actualizados_die = []

    for _, r in df.iterrows():
      est_id = str(r["id_estacion"]).strip()
      f_inv = r["fecha_inventario"]

      if pd.isna(f_inv):
        inventarios_actualizados_reg.append(0.0)
        inventarios_actualizados_pre.append(0.0)
        inventarios_actualizados_die.append(0.0)
        continue

      f_inv_date = pd.to_datetime(f_inv).date()
      dias_transcurridos = (hoy - f_inv_date).days

      inv_r = float(r["reg_litros"])
      inv_p = float(r["pre_litros"])
      inv_d = float(r["die_litros"])

      vdp_r = float(r["vdp_reg"])
      vdp_p = float(r["vdp_pre"])
      vdp_d = float(r["vdp_die"])

      if dias_transcurridos > 0:
        current_date = f_inv_date
        for _ in range(dias_transcurridos):
          current_date = current_date + timedelta(days=1)
          curr_str = current_date.strftime("%Y-%m-%d")

          inv_r = (
              inv_r
              - vdp_r
              + descargas_reales.get((est_id, "regular", curr_str), 0.0)
          )
          inv_p = (
              inv_p
              - vdp_p
              + descargas_reales.get((est_id, "premium", curr_str), 0.0)
          )
          inv_d = (
              inv_d
              - vdp_d
              + descargas_reales.get((est_id, "diesel", curr_str), 0.0)
          )

      inventarios_actualizados_reg.append(max(0.0, inv_r))
      inventarios_actualizados_pre.append(max(0.0, inv_p))
      inventarios_actualizados_die.append(max(0.0, inv_d))

    df["reg_litros_calc"] = inventarios_actualizados_reg
    df["pre_litros_calc"] = inventarios_actualizados_pre
    df["die_litros_calc"] = inventarios_actualizados_die

    def formato_inv(litros, fecha_inv):
      if pd.isna(fecha_inv):
        return "N/A", True
      f_str = pd.to_datetime(fecha_inv).strftime("%Y-%m-%d")
      es_teorico = f_str < hoy_str
      prefijo = "*" if es_teorico else ""
      return f"{prefijo}{litros:,.0f} L", es_teorico

    # Consultar cargas programadas específicamente para HOY (filtrado por usuario)
    cargas_hoy = {}
    try:
      query_cargas = f"""
            SELECT id_estacion, producto, fecha_programacion, volumen_programado
            FROM programacion_cargas
            {where_cargas_hoy};
        """
      df_cargas = pd.read_sql(query_cargas, conn)
      if not df_cargas.empty:
        for _, rc in df_cargas.iterrows():
          est_id = str(rc["id_estacion"]).strip()
          pk = normalizar_producto(rc["producto"])
          f_prog = str(rc["fecha_programacion"]).split("T")[0]
          vol = (
              float(rc["volumen_programado"])
              if pd.notna(rc["volumen_programado"])
              else 0.0
          )

          key_carga = (est_id, pk, f_prog)
          cargas_hoy[key_carga] = cargas_hoy.get(key_carga, 0.0) + vol
    except Exception:
      try:
        conn.rollback()
      except:
        pass

    # Calcular Días de Suministro (D/S)
    df["ds_r"] = df.apply(
        lambda r: (
            round(r["reg_litros_calc"] / r["vdp_reg"], 1)
            if r["cap_regular"] > 0 and r["vdp_reg"] > 0
            else np.nan
        ),
        axis=1,
    )
    df["ds_p"] = df.apply(
        lambda r: (
            round(r["pre_litros_calc"] / r["vdp_pre"], 1)
            if r["cap_premium"] > 0 and r["vdp_pre"] > 0
            else np.nan
        ),
        axis=1,
    )
    df["ds_d"] = df.apply(
        lambda r: (
            round(r["die_litros_calc"] / r["vdp_die"], 1)
            if r["cap_diesel"] > 0 and r["vdp_die"] > 0
            else np.nan
        ),
        axis=1,
    )

    # Calcular espacio disponible actual basado en la capacidad máxima real de tanques
    df["espacio_r"] = df.apply(
        lambda r: (
            max(0, r["cap_regular"] - r["reg_litros_calc"])
            if r["cap_regular"] > 0
            else np.nan
        ),
        axis=1,
    )
    df["espacio_p"] = df.apply(
        lambda r: (
            max(0, r["cap_premium"] - r["pre_litros_calc"])
            if r["cap_premium"] > 0
            else np.nan
        ),
        axis=1,
    )
    df["espacio_d"] = df.apply(
        lambda r: (
            max(0, r["cap_diesel"] - r["die_litros_calc"])
            if r["cap_diesel"] > 0
            else np.nan
        ),
        axis=1,
    )

    # ==========================================
    # 1. CENTRO DE ALERTAS: INVENTARIOS BAJOS Y SOBRE-CARGAS SEPARADOS
    # ==========================================
    st.markdown("### 🚨 Alertas de Inventario (Días de Suministro Bajos)")

    alertas_inventario = []
    alertas_sobrecarga = []

    for _, r in df.iterrows():
      est_id = str(r["id_estacion"]).strip()
      f_inv = r["fecha_inventario"]

      productos = [
          (
              "Regular",
              r["ds_r"],
              r["reg_litros_calc"],
              r["cap_regular"],
              r["espacio_r"],
              r["vdp_reg"],
              "regular",
          ),
          (
              "Premium",
              r["ds_p"],
              r["pre_litros_calc"],
              r["cap_premium"],
              r["espacio_p"],
              r["vdp_pre"],
              "premium",
          ),
          (
              "Diesel",
              r["ds_d"],
              r["die_litros_calc"],
              r["cap_diesel"],
              r["espacio_d"],
              r["vdp_die"],
              "diesel",
          ),
      ]

      for prod, ds, litros, cap, espacio, vdp, p_key in productos:
        if cap > 0:
          str_inv_actual, _ = formato_inv(litros, f_inv)
          vol_carga_hoy = cargas_hoy.get((est_id, p_key, hoy_str), 0.0)

          # 1. Alerta por Días de Suministro bajos (< 2 días)
          if pd.notna(ds) and ds < 2.0:
            prioridad = 1 if ds < 1.0 else 2
            nivel = (
                "🔴 CRÍTICO (< 1 Día)"
                if ds < 1.0
                else "🟡 ADVERTENCIA (< 2 Días)"
            )

            if vol_carga_hoy > 0:
              litros_post = litros + vol_carga_hoy - vdp
              ds_post = round(litros_post / vdp, 1) if vdp > 0 else ds
              programa_status = f"🚛 Sí ({vol_carga_hoy:,.0f} L) ➔ Post: *{litros_post:,.0f} L ({ds_post:.1f} d)"
            else:
              programa_status = "❌ Sin Carga Hoy"

            alertas_inventario.append({
                "prioridad": prioridad,
                "nivel": nivel,
                "estacion": f"{r['id_estacion']} - {r['estacion']}",
                "plaza": str(r["plaza"]),
                "producto": prod,
                "litros_val": str_inv_actual,
                "vta_hoy": f"{vdp:,.0f} L",
                "ds": ds if pd.notna(ds) else 999.0,
                "espacio": espacio,
                "programa": programa_status,
            })

          # 2. Alertas de Sobre-carga diferenciadas
          espacio_post_venta = cap - (litros - vdp)

          if (
              vol_carga_hoy > 0
              and pd.notna(espacio)
              and pd.notna(espacio_post_venta)
          ):
            if vol_carga_hoy > espacio_post_venta:
              exceso = vol_carga_hoy - espacio_post_venta
              programa_status = f"⚠️ SOBRE-CARGA: {vol_carga_hoy:,.0f} L (Espacio Post-Venta: {espacio_post_venta:,.0f} L, Exceso: {exceso:,.0f} L)"

              alertas_sobrecarga.append({
                  "prioridad": 1,
                  "nivel": "🔴 SOBRE-CARGA",
                  "estacion": f"{r['id_estacion']} - {r['estacion']}",
                  "plaza": str(r["plaza"]),
                  "producto": prod,
                  "litros_val": str_inv_actual,
                  "vta_hoy": f"{vdp:,.0f} L",
                  "ds": ds if pd.notna(ds) else 999.0,
                  "espacio": espacio,
                  "programa": programa_status,
              })
            elif vol_carga_hoy > espacio:
              exceso = vol_carga_hoy - espacio
              programa_status = f"⚠️ POSIBLE-SOBRECARGA: {vol_carga_hoy:,.0f} L (Espacio Actual: {espacio:,.0f} L, Exceso: {exceso:,.0f} L)"

              alertas_sobrecarga.append({
                  "prioridad": 2,
                  "nivel": "🟡 POSIBLE-SOBRECARGA",
                  "estacion": f"{r['id_estacion']} - {r['estacion']}",
                  "plaza": str(r["plaza"]),
                  "producto": prod,
                  "litros_val": str_inv_actual,
                  "vta_hoy": f"{vdp:,.0f} L",
                  "ds": ds if pd.notna(ds) else 999.0,
                  "espacio": espacio,
                  "programa": programa_status,
              })

    def estilizar_producto(val):
      v_lower = str(val).strip().lower()
      if "regular" in v_lower:
        return "color: #27ae60; font-weight: bold; text-align: center;"
      elif "premium" in v_lower:
        return "color: #e67e22; font-weight: bold; text-align: center;"
      elif "diesel" in v_lower:
        return "color: #7f8c8d; font-weight: bold; text-align: center;"
      return ""

    # Desplegar Alertas de Inventario
    if not alertas_inventario:
      st.success(
          "✅ ¡Excelente noticia! No hay estaciones con niveles críticos o de"
          " advertencia en inventarios."
      )
    else:
      inv_ordenadas = sorted(
          alertas_inventario,
          key=lambda x: (
              x["prioridad"],
              x["ds"] if pd.notna(x["ds"]) else 999.0,
          ),
      )
      df_inv_alertas = pd.DataFrame(inv_ordenadas)

      tabla_inv_vis = pd.DataFrame({
          "Estatus": df_inv_alertas["nivel"],
          "Estación": df_inv_alertas["estacion"],
          "Plaza": df_inv_alertas["plaza"],
          "Producto": df_inv_alertas["producto"],
          "Inventario Actual": df_inv_alertas["litros_val"],
          "Venta Proyectada Hoy": df_inv_alertas["vta_hoy"],
          "D/S Actual": df_inv_alertas["ds"].apply(
              lambda x: f"{x:.1f} días" if x < 999 else "N/A"
          ),
          "Programa Hoy / Post-Entrega": df_inv_alertas["programa"],
      })
      st.dataframe(
          tabla_inv_vis.style.map(estilizar_producto, subset=["Producto"]),
          use_container_width=True,
          height=250,
          hide_index=True,
      )

    st.markdown("---")

    # Desplegar Alertas de Sobre-carga
    st.markdown("### ⚠️ Alertas de Sobre-Carga de Tanques")
    if not alertas_sobrecarga:
      st.success(
          "✅ ¡Sin riesgo de sobre-cargas! Todas las entregas programadas"
          " caben de forma segura en los tanques considerando la operación del"
          " día."
      )
    else:
      sobre_ordenadas = sorted(
          alertas_sobrecarga, key=lambda x: x["prioridad"]
      )
      df_sobre_alertas = pd.DataFrame(sobre_ordenadas)

      tabla_sobre_vis = pd.DataFrame({
          "Estatus": df_sobre_alertas["nivel"],
          "Estación": df_sobre_alertas["estacion"],
          "Plaza": df_sobre_alertas["plaza"],
          "Producto": df_sobre_alertas["producto"],
          "Inventario Actual": df_sobre_alertas["litros_val"],
          "Espacio Disponible": df_sobre_alertas["espacio"].apply(
              lambda x: f"{x:,.0f} L" if pd.notna(x) else "N/A"
          ),
          "Detalle de Sobre-Carga": df_sobre_alertas["programa"],
      })
      st.dataframe(
          tabla_sobre_vis.style.map(estilizar_producto, subset=["Producto"]),
          use_container_width=True,
          height=250,
          hide_index=True,
      )

    st.markdown("---")

    # ==========================================
    # 2. RESUMEN DEL PROGRAMA DE CARGAS DEL DÍA EN CURSO
    # ==========================================
    st.markdown(f"### 🚛 Resumen del Programa de Cargas ({hoy_str})")
    st.write(
        "Listado consolidado de las órdenes de carga programadas para hoy con"
        " su asignación de usuario, estación, plaza y TAD."
    )

    try:
      query_cargas_hoy_det = f"""
            SELECT 
                COALESCE(ue.usuario, 'Sin Asignar') AS usuario,
                e.id_estacion,
                e.nombre AS estacion_nombre,
                e.plaza,
                e.tad,
                pc.producto,
                pc.volumen_programado
            FROM programacion_cargas pc
            JOIN estaciones e ON pc.id_estacion = e.id_estacion
            LEFT JOIN (
                SELECT id_estacion, MIN(usuario) as usuario 
                FROM usuarios_estaciones 
                GROUP BY id_estacion
            ) ue ON e.id_estacion = ue.id_estacion
            {where_cargas_det}
            ORDER BY usuario, e.plaza, e.id_estacion, pc.producto;
        """
      df_prog_hoy = pd.read_sql(query_cargas_hoy_det, conn)

      if df_prog_hoy.empty:
        st.info(
            f"📅 No hay cargas programadas para el día de hoy ({hoy_str}) en"
            " tus estaciones asignadas."
        )
      else:
        tad_dict = {
            "636": "Rosarito",
            "637": "Hermosillo",
            "638": "Mexicali",
            "639": "Ensenada",
            "640": "Magdalena",
            "641": "Nogales",
            "646": "Obregón",
        }

        def formatear_tad(tad_val):
          t_str = str(tad_val).strip()
          nombre = tad_dict.get(t_str, "Terminal")
          return f"{t_str} - {nombre}"

        def formatear_producto(prod_val):
          p_str = str(prod_val).strip().lower()
          if "regular" in p_str or "magna" in p_str:
            return "Regular"
          elif "premium" in p_str:
            return "Premium"
          elif "diesel" in p_str:
            return "Diesel"
          return str(prod_val).capitalize()

        df_prog_hoy["TAD_fmt"] = df_prog_hoy["tad"].apply(formatear_tad)
        df_prog_hoy["Estacion_fmt"] = (
            df_prog_hoy["id_estacion"].astype(str)
            + " - "
            + df_prog_hoy["estacion_nombre"].astype(str)
        )
        df_prog_hoy["Producto_fmt"] = df_prog_hoy["producto"].apply(
            formatear_producto
        )

        tabla_cargas_vis = pd.DataFrame({
            "Usuario": df_prog_hoy["usuario"],
            "Estación": df_prog_hoy["Estacion_fmt"],
            "Plaza": df_prog_hoy["plaza"],
            "TAD": df_prog_hoy["TAD_fmt"],
            "Producto": df_prog_hoy["Producto_fmt"],
            "Volumen (Litros Programados)": df_prog_hoy[
                "volumen_programado"
            ].apply(
                lambda x: f"{float(x):,.0f} L" if pd.notna(x) else "0 L"
            ),
        })

        def estilizar_producto_cargas(val):
          v_lower = str(val).strip().lower()
          if "regular" in v_lower:
            return "color: #27ae60; font-weight: bold; text-align: center;"
          elif "premium" in v_lower:
            return "color: #e67e22; font-weight: bold; text-align: center;"
          elif "diesel" in v_lower:
            return "color: #7f8c8d; font-weight: bold; text-align: center;"
          return ""

        tabla_cargas_estilizada = tabla_cargas_vis.style.map(
            estilizar_producto_cargas, subset=["Producto"]
        )
        st.dataframe(
            tabla_cargas_estilizada,
            use_container_width=True,
            height=450,
            hide_index=True,
        )

    except Exception as e_prog_hoy:
      st.error(
          f"Error al consultar el programa de cargas del día: {e_prog_hoy}"
      )

  except Exception as e:
    st.error(f"Error al generar el dashboard operativo: {e}")
