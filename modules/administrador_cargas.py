import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 🚛 Administrador de Cargas (Ejecución y Cruce de Remisiones)")
    st.write("Registra y audita las descargas reales cruzando la Remisión Pemex (RP) contra la planeación y el folio de factura del distribuidor.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    try:
        # 1. Selector de Estación
        query_estaciones = """
            SELECT DISTINCT id_estacion, nombre, plaza 
            FROM estaciones_detalle 
            ORDER BY id_estacion;
        """
        df_est = pd.read_sql(query_estaciones, conn)
        if df_est.empty:
            st.warning("No hay estaciones registradas.")
            return

        estaciones_lista = [f"{r['id_estacion']} - {r['nombre']} ({r['plaza']})" for _, r in df_est.iterrows()]
        sel_est = st.selectbox("Selecciona la Estación:", estaciones_lista)
        estacion_id_sel = sel_est.split(" - ")[0]

        st.markdown("---")

        # 2. Pestañas de Navegación del Módulo
        tab1, tab2 = st.tabs(["📥 Registrar Descarga Real (Orden de Carga)", "📋 Historial y Auditoría de Bitácora"])

        # ==========================================
        # PESTAÑA 1: REGISTRAR DESCARGA DESDE LA ORDEN
        # ==========================================
        with tab1:
            st.markdown("#### 🔍 Órdenes Programadas Recientes")
            st.write("Selecciona la orden planeada para vincularla con los datos reales de la orden de carga de Pemex.")

            query_prog = f"""
                SELECT id, id_estacion, producto, fecha_programacion, volumen_programado, "user"
                FROM programacion_cargas
                WHERE id_estacion = '{estacion_id_sel}'
                ORDER BY fecha_programacion DESC
                LIMIT 30;
            """
            df_prog = pd.read_sql(query_prog, conn)

            if df_prog.empty:
                st.info("No hay cargas programadas registradas para esta estación.")
            else:
                st.dataframe(df_prog, width='stretch', hide_index=True)

                st.markdown("#### ✍️ Captura de Datos de la Orden de Carga y Recepción")
                
                with st.form("form_registrar_descarga_detallada"):
                    col_id, col_prod = st.columns(2)
                    with col_id:
                        prog_ids = df_prog['id'].tolist()
                        sel_prog_id = st.selectbox("ID de Orden Programada (Plan):", prog_ids)
                    
                    row_sel = df_prog[df_prog['id'] == sel_prog_id].iloc[0]
                    
                    with col_prod:
                        producto_fijo = st.text_input("Producto:", value=str(row_sel['producto']), disabled=True)

                    st.markdown("##### 📄 Datos de Embarque y Pemex")
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        num_embarque = st.text_input("Núm. de Embarque:")
                    with c2:
                        fecha_carga = st.date_input("Fecha de Carga:", value=date.today())
                    with c3:
                        tad_origen = st.text_input("TAD de Origen:")
                    with c4:
                        remision_pemex = st.text_input("RP (Remisión Pemex):")

                    c5, c6, c7, c8 = st.columns(4)
                    with c5:
                        cliente_pemex = st.text_input("Cliente (Núm. Distribuidor):")
                    with c6:
                        destino_codigo = st.text_input("Destino (3 dígitos):")
                    with c7:
                        temperatura = st.number_input("Temperatura (°C):", value=20.0, step=0.1)
                    with c8:
                        importe_flete = st.number_input("Importe Flete ($):", min_value=0.0, value=0.0, step=100.0, format="%.2f")

                    st.markdown("##### 📊 Volúmenes y Facturación del Distribuidor")
                    c9, c10, c11, c12 = st.columns(4)
                    with c9:
                        vol_sugerido = float(row_sel['volumen_programado']) if pd.notna(row_sel['volumen_programado']) else 0.0
                        cant_natural = st.number_input("Cantidad al Natural (L):", min_value=0.0, value=vol_sugerido, step=100.0)
                    with c10:
                        cant_20c = st.number_input("Cantidad a 20°C (L):", min_value=0.0, value=vol_sugerido, step=100.0)
                    with c11:
                        folio_factura = st.text_input("Folio Factura (Distribuidor):")
                    with c12:
                        orden_remision = st.text_input("Orden Remisión Interna:")

                    observaciones = st.text_area("Observaciones (Incidencias, mermas o diferencias):", value="")

                    submitted_descarga = st.form_submit_button("💾 Guardar y Auditar en Bitácora Real")

                    if submitted_descarga:
                        cursor = conn.cursor()
                        try:
                            f_carga_str = fecha_carga.strftime("%Y-%m-%d")
                            insert_bitacora = f"""
                                INSERT INTO bitacora_descargas 
                                (id_programacion, id_estacion, producto, numero_embarque, fecha_carga, tad_origen, cliente_pemex, destino_codigo, cantidad_natural, cantidad_20c, temperatura, importe_flete, remision_pemex, folio_factura, orden_remision, observaciones, usuario)
                                VALUES 
                                ({sel_prog_id}, '{estacion_id_sel}', '{row_sel['producto']}', '{num_embarque}', '{f_carga_str}', '{tad_origen}', '{cliente_pemex}', '{destino_codigo}', {cant_natural}, {cant_20c}, {temperatura}, {importe_flete}, '{remision_pemex}', '{folio_factura}', '{orden_remision}', '{observaciones}', '{row_sel["user"]}')
                            """
                            cursor.execute(insert_bitacora)
                            conn.commit()
                            cursor.close()
                            st.success("✅ ¡Descarga registrada y cruzada correctamente con la Remisión Pemex (RP)!")
                            st.rerun()
                        except Exception as err:
                            conn.rollback()
                            cursor.close()
                            st.error(f"Error al registrar en la base de datos: {err}")

        # ==========================================
        # PESTAÑA 2: HISTORIAL DE BITÁCORA REAL
        # ==========================================
        with tab2:
            st.markdown(f"#### 📋 Bitácora de Descargas y Cruce de RP - Estación {estacion_id_sel}")
            
            try:
                query_bitacora = f"""
                    SELECT 
                        b.id,
                        b.remision_pemex AS "RP",
                        b.folio_factura AS "Factura Dist.",
                        b.fecha_carga AS "F. Carga",
                        b.producto AS "Producto",
                        b.cantidad_20c AS "Litros @20°C",
                        b.importe_flete AS "Flete ($)",
                        b.tad_origen AS "TAD",
                        b.numero_embarque AS "Embarque",
                        b.usuario AS "Usuario",
                        b.registrado_en AS "Registrado"
                    FROM bitacora_descargas b
                    WHERE b.id_estacion = '{estacion_id_sel}'
                    ORDER BY b.fecha_carga DESC;
                """
                df_bitacora = pd.read_sql(query_bitacora, conn)
                
                if df_bitacora.empty:
                    st.info("No hay registros de descargas reales para esta estación todavía.")
                else:
                    st.dataframe(df_bitacora, width='stretch', hide_index=True)
            except Exception as e:
                st.warning(f"Aviso al consultar la bitácora: {e}")

    except Exception as e:
        st.error(f"Error en el Administrador de Cargas: {e}")
