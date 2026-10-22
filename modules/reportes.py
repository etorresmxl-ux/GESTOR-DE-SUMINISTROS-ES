from datetime import date, timedelta
import pandas as pd
import streamlit as st


def render(conn):
  st.markdown("### 📋 Módulo de Reportes Operativos")
  st.write(
      "Consulta la información consolidada de inventarios, ventas y"
      " programación de cargas."
  )

  tab_inv, tab_vta, tab_prog = st.tabs([
      "📦 Reporte de Inventarios",
      "📊 Reporte de Ventas",
      "🚛 Reporte de Programación de Cargas",
  ])

  # ==========================================
  # 1. REPORTE DE INVENTARIOS
  # ==========================================
  with tab_inv:
    st.markdown("#### 📦 Reporte de Inventarios Registrados")
    fecha_inv_sel = st.date_input(
        "Selecciona el día de consulta:",
        value=date.today(),
        key="rep_inv_fecha",
    )

    if conn is not None:
      try:
        query_inv_rep = f"""
                    SELECT 
                        COALESCE(ue.usuario, 'Sin Asignar') AS usuario,
                        e.plaza,
                        CONCAT(e.id_estacion, ' - ', e.nombre) AS estacion,
                        i.producto,
                        i.volumen
                    FROM estaciones e
                    LEFT JOIN (
                        SELECT id_estacion, MIN(usuario) as usuario 
                        FROM usuarios_estaciones 
                        GROUP BY id_estacion
                    ) ue ON e.id_estacion = ue.id_estacion
                    LEFT JOIN inventarios i ON e.id_estacion = i.id_estacion AND i.fecha = '{fecha_inv_sel}'
                    ORDER BY ue.usuario, e.plaza, e.id_estacion;
                """
        df_raw_inv = pd.read_sql(query_inv_rep, conn)

        if df_raw_inv.empty:
          st.info("No se encontraron estaciones en el sistema.")
        else:
          df_raw_inv["prod_norm"] = df_raw_inv["producto"].apply(
              lambda p: (
                  "regular"
                  if pd.notna(p) and ("regular" in str(p).lower() or "magna" in str(p).lower())
                  else (
                      "premium"
                      if pd.notna(p) and "premium" in str(p).lower()
                      else ("diesel" if pd.notna(p) and "diesel" in str(p).lower() else "otro")
                  )
              )
          )

          df_pivot_inv = df_raw_inv.pivot_table(
              index=["usuario", "plaza", "estacion"],
              columns="prod_norm",
              values="volumen",
              aggfunc="sum",
              fill_value=0,
          ).reset_index()

          for col_p in ["regular", "premium", "diesel"]:
            if col_p not in df_pivot_inv.columns:
              df_pivot_inv[col_p] = 0.0

          tabla_inv_vis = pd.DataFrame({
              "Usuario": df_pivot_inv["usuario"],
              "Plaza": df_pivot_inv["plaza"],
              "Estación": df_pivot_inv["estacion"],
              "Regular (Lts)": df_pivot_inv["regular"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
              "Premium (Lts)": df_pivot_inv["premium"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
              "Diesel (Lts)": df_pivot_inv["diesel"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
          })

          st.dataframe(tabla_inv_vis, use_container_width=True, hide_index=True)
      except Exception as e:
        st.error(f"Error al obtener reporte de inventarios: {e}")

  # ==========================================
  # 2. REPORTE DE VENTAS
  # ==========================================
  with tab_vta:
    st.markdown("#### 📊 Reporte de Ventas Registradas")
    fecha_vta_sel = st.date_input(
        "Selecciona el día de consulta:",
        value=date.today(),
        key="rep_vta_fecha",
    )

    if conn is not None:
      try:
        query_vta_rep = f"""
                    SELECT 
                        COALESCE(ue.usuario, 'Sin Asignar') AS usuario,
                        e.plaza,
                        CONCAT(e.id_estacion, ' - ', e.nombre) AS estacion,
                        v.producto,
                        v.volumen
                    FROM estaciones e
                    LEFT JOIN (
                        SELECT id_estacion, MIN(usuario) as usuario 
                        FROM usuarios_estaciones 
                        GROUP BY id_estacion
                    ) ue ON e.id_estacion = ue.id_estacion
                    LEFT JOIN ventas v ON e.id_estacion = v.id_estacion AND v.fecha = '{fecha_vta_sel}'
                    ORDER BY ue.usuario, e.plaza, e.id_estacion;
                """
        df_raw_vta = pd.read_sql(query_vta_rep, conn)

        if df_raw_vta.empty:
          st.info("No se encontraron estaciones en el sistema.")
        else:
          df_raw_vta["prod_norm"] = df_raw_vta["producto"].apply(
              lambda p: (
                  "regular"
                  if pd.notna(p) and ("regular" in str(p).lower() or "magna" in str(p).lower())
                  else (
                      "premium"
                      if pd.notna(p) and "premium" in str(p).lower()
                      else ("diesel" if pd.notna(p) and "diesel" in str(p).lower() else "otro")
                  )
              )
          )

          df_pivot_vta = df_raw_vta.pivot_table(
              index=["usuario", "plaza", "estacion"],
              columns="prod_norm",
              values="volumen",
              aggfunc="sum",
              fill_value=0,
          ).reset_index()

          for col_p in ["regular", "premium", "diesel"]:
            if col_p not in df_pivot_vta.columns:
              df_pivot_vta[col_p] = 0.0

          tabla_vta_vis = pd.DataFrame({
              "Usuario": df_pivot_vta["usuario"],
              "Plaza": df_pivot_vta["plaza"],
              "Estación": df_pivot_vta["estacion"],
              "Regular (Lts)": df_pivot_vta["regular"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
              "Premium (Lts)": df_pivot_vta["premium"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
              "Diesel (Lts)": df_pivot_vta["diesel"].apply(
                  lambda x: f"{x:,.0f} L" if x > 0 else "-"
              ),
          })

          st.dataframe(tabla_vta_vis, use_container_width=True, hide_index=True)
      except Exception as e:
        st.error(f"Error al obtener reporte de ventas: {e}")

  # ==========================================
  # 3. REPORTE DE PROGRAMACIÓN DE CARGAS
  # ==========================================
  with tab_prog:
    st.markdown("#### 🚛 Reporte Semanal de Cargas Programadas")

    if conn is not None:
      try:
        query_usr = (
            "SELECT DISTINCT usuario FROM usuarios_estaciones WHERE usuario IS"
            " NOT NULL ORDER BY usuario;"
        )
        df_usr = pd.read_sql(query_usr, conn)
        usuarios_list = df_usr["usuario"].tolist() if not df_usr.empty else []

        c1, c2 = st.columns(2)
        with c1:
          usr_prog_sel = st.selectbox(
              "Selecciona el Usuario:", usuarios_list, key="rep_prog_usr"
          )
        with c2:
          fecha_ref_sel = st.date_input(
              "Selecciona una fecha (calcula semana de lun. a dom.):",
              value=date.today(),
              key="rep_prog_fecha",
          )

        lunes = fecha_ref_sel - timedelta(days=fecha_ref_sel.weekday())
        dias_semana_fechas = [lunes + timedelta(days=i) for i in range(7)]
        nombres_columnas_dias = [
            f"{f.strftime('%A')[:3].lower()}. {f.strftime('%d-%b')}"
            for f in dias_semana_fechas
        ]

        st.caption(
            f"Mostrando semana del **{lunes}** al **{lunes + timedelta(days=6)}**"
            f" para el usuario **{usr_prog_sel}**."
        )

        query_cargas_sem = f"""
                    SELECT 
                        e.id_estacion,
                        CONCAT(e.id_estacion, ' - ', e.nombre) AS estacion,
                        pc.producto,
                        pc.fecha_programacion,
                        SUM(pc.volumen_programado) AS volumen
                    FROM estaciones e
                    JOIN usuarios_estaciones ue ON e.id_estacion = ue.id_estacion
                    LEFT JOIN programacion_cargas pc ON e.id_estacion = pc.id_estacion 
                        AND pc.fecha_programacion BETWEEN '{lunes}' AND '{lunes + timedelta(days=6)}'
                    WHERE ue.usuario = '{usr_prog_sel}'
                    GROUP BY e.id_estacion, e.nombre, pc.producto, pc.fecha_programacion
                    ORDER BY e.id_estacion;
                """
        df_cargas_sem = pd.read_sql(query_cargas_sem, conn)

        if df_cargas_sem.empty:
          st.info(
              f"No hay estaciones asignadas o registradas para {usr_prog_sel}."
          )
        else:
          # Construir combinación base de Estación x Producto para mostrar todas las combinaciones registrables
          estaciones_unicas = df_cargas_sem[
              ["id_estacion", "estacion"]
          ].drop_duplicates()
          productos_base = ["REGULAR", "PREMIUM", "DIESEL"]

          filas_base = []
          for _, row_e in estaciones_unicas.iterrows():
            for p in productos_base:
              filas_base.append({
                  "estacion": row_e["estacion"],
                  "producto": p,
              })

          df_plantilla_prog = pd.DataFrame(filas_base)

          # Mapear volumen por fecha
          for i, f in enumerate(dias_semana_fechas):
            f_str = f.strftime("%Y-%m-%d")
            col_name = nombres_columnas_dias[i]

            sub_f = df_cargas_sem[
                df_cargas_sem["fecha_programacion"].astype(str) == f_str
            ]

            def obtener_vol(row, sub_df):
              est = row["estacion"]
              prod = row["producto"]
              match = sub_df[
                  (sub_df["estacion"] == est)
                  & (
                      sub_df["producto"].str.upper()
                      == prod
                  )
              ]
              if not match.empty:
                v = match.iloc[0]["volumen"]
                return f"{v:,.0f} L" if pd.notna(v) and v > 0 else "-"
              return "-"

            df_plantilla_prog[col_name] = df_plantilla_prog.apply(
                lambda r: obtener_vol(r, sub_f), axis=1
            )

          st.dataframe(
              df_plantilla_prog, use_container_width=True, hide_index=True
          )

      except Exception as e:
        st.error(f"Error al obtener reporte de programación de cargas: {e}")
