import streamlit as st
import pandas as pd
from datetime import date

def render(conn):
    st.markdown("### 🚛 Administrador de Cargas (Ejecución y Bitácora Real)")
    st.write("Control de autotanques: Vincula la **Orden de Carga** (plan) o registra **Descargas Extraordinarias** (sin orden), capturando Remisión Pemex (RP), Factura del Distribuidor, volúmenes físicos, temperaturas y fletes.")

    if conn is None:
        st.error("No hay conexión a la base de datos.")
        return

    try:
        # 1. Consultar estaciones y programadores correctamente asegurando el campo "user"
        query_base = """
            SELECT DISTINCT 
                id_estacion, 
                nombre AS estacion_nombre, 
                plaza,
                COALESCE(NULLIF("user", ''), 'Sin Asignar') AS programador
            FROM estaciones_detalle
            ORDER BY programador, plaza, id_estacion;
        """
        df_estaciones = pd.read_sql(query_base, conn)
        
        if df_estaciones.empty:
            st.warning("No hay estaciones registradas.")
            return

        # Filtros Superiores: Programador y Estación
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            programadores_disponibles = sorted(df_estaciones['programador'].unique())
            selected_prog = st.selectbox("Filtrar por Programador / Usuario:", programadores_disponibles)
            
        df_filtrado_prog = df_estaciones[df_estaciones['programador'] == selected_prog]
        
        with col_f2:
            estaciones_nombres = [f"{row['id_estacion']} - {row['estacion_nombre']} ({row['plaza']})" for _, row in df_filtrado_prog.iterrows()]
            if not estaciones_nombres:
                st.warning("No hay estaciones asignadas a este programador.")
                return
            sel_est = st.selectbox("Selecciona la Estación:", estaciones_nombres)
            
        estacion_id_sel = sel_est.split(" - ")[0]

        st.markdown("---")

        # 2. Pestañas del Módulo
        tab1, tab2 = st.tabs(["📥 Registrar Descarga (Con o Sin Orden)", "📋 Historial de Bitácora y Remisiones"])

        # ==========================================
        # PESTAÑA 1: REGISTRAR DESCARGA
        # ==========================================
        with tab1:
            st.markdown("#### 🔍 Seleccionar Orden de Carga o Registro Manual")
            st.write("Selecciona una Orden de Carga del programa o elige la opción manual para recibir una pipa imprevista.")

            # Consultar programa de cargas para esta estación
            query_prog = f"""
                SELECT id AS orden_carga, producto, fecha_programacion, volumen_programado
                FROM programacion_cargas
                WHERE id_estacion = '{estacion_id_sel}'
                ORDER BY fecha_programacion DESC
                LIMIT 30;
            """
            df_prog = pd.read_sql(query_prog, conn)

            # Opciones para el selector de Orden de Carga
            opciones_ordenes = ["-- Sin Orden de Carga (Descarga Extraordinaria / Imprevista) --"]
            if not df_prog.empty:
                for _, r in df_prog.iterrows():
                    f_str = str(r['fecha_programacion']).split("T")[0]
                    opciones_ordenes.append(f"Orden de Carga #{r['orden_carga']} | {r['producto']} | {f_str} | {r['volumen_programado']:,.0f} L")

            # Selector FUERA del formulario para permitir actualización dinámica inmediata
            sel_orden_str = st.selectbox("Vinculación con Orden de Carga (Plan):", opciones_ordenes)
            
            es_manual = sel_orden_str.startswith("--")
            
            producto_default = "REGULAR"
            vol_prog_val = 0.0
            sel_prog_id_val = "NULL"

            if not es_manual:
                orden_id_num = int(sel_orden_str.split("#")[1].split(" ")[0])
                sel_prog_id_val = str(orden_id_num)
                row_sel = df_prog[df_prog['orden_carga'] == orden_id_num].iloc[0]
                producto_default = str(row_sel['producto'])
                vol_prog_val = float(row_sel['volumen_programado']) if pd.notna(row_sel['volumen_programado']) else 0.0

            st.markdown("#### ✍️ Captura de Datos de la Orden de Carga y Factura")
            
            # Nota informativa FUERA del formulario para evitar que se meta a la caja azul desalineada
            if es_manual:
                st.info("ℹ️ **Modo Manual / Extraordinario:** Esta descarga no está atada a un plan previo en el MRP.")
            else:
                st.success(f"🔗 **Vinculado a Orden de Carga #{sel_prog_id_val}** (Volumen planificado: {vol_prog_val:,.0f} L)")

            with st.form("form_registrar_descarga_detallada"):
                col_prod, col_fec_desc = st.columns(2)
                
                if es_manual:
                    with col_prod:
                        producto_descarga = st.selectbox("Producto Descargado:", ["REGULAR", "PREMIUM", "DIESEL"])
                    with col_fec_desc:
                        fecha_descarga_real = st.date_input("Fecha de Descarga Real:", value=date.today())
                else:
                    with col_prod:
                        producto_descarga = st.text_input("Producto:", value=producto_default, disabled=True)
                    with col_fec_desc:
                        fecha_descarga_real = st.date_input("Fecha de Descarga Real:", value=date.today())

                st.markdown("---")
                st.markdown("##### ⛽ Datos del Autotanque y Documentos (Pemex / Distribuidor)")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    num_embarque = st.text_input("Número de Embarque:")
                with c2:
                    fecha_carga = st.date_input("Fecha de Carga (TAD):", value=date.today())
                with c3:
                    tad_origen = st.text_input("TAD de Origen:")
                with c4:
                    cliente_pemex = st.text_input("Cliente (Núm. Pemex):")

                c5, c6, c7, c8 = st.columns(4)
                with c5:
                    destino_num = st.text_input("Destino (3 dígitos):")
                with c6:
                    cant_natural = st.number_input("Cantidad al Natural (L):", min_value=0.0, step=100.0)
                with c7:
                    cant_20c = st.number_input("Cantidad a 20°C (L):", min_value=0.0, step=100.0)
                with c8:
                    temperatura = st.number_input("Temperatura (°C):", value=20.0, step=0.1)

                c9, c10, c11 = st.columns(3)
                with c9:
                    importe_flete = st.number_input("Importe Flete ($):", min_value=0.0, step=50.0)
                with c10:
                    remision_pemex = st.text_input("RP (Remisión Pemex) *Obligatoria*:")
                with c11:
                    factura_distribuidor = st.text_input("Folio Factura Distribuidor:")

                observaciones = st.text_area("Observaciones (Incidencias, mermas, imprevistos):", value="")

                submitted_descarga = st.form_submit_button("💾 Guardar Descarga Real en Bitácora")

                if submitted_descarga:
                    if not remision_pemex:
                        st.error("⚠️ El campo de Remisión Pemex (RP) es obligatorio para realizar el cruce operativo y fiscal.")
                    else:
                        cursor = conn.cursor()
                        try:
                            f_desc_str = fecha_descarga_real.strftime("%Y-%m-%d")
                            f_carga_str = fecha_carga.strftime("%Y-%m-%d")
                            
                            insert_bitacora = f"""
                                INSERT INTO bitacora_descargas 
                                (
                                    id_programacion, id_estacion, producto, fecha_descarga_real,
                                    numero_embarque, fecha_carga, tad_origen, cliente_pemex,
                                    destino_num, cantidad_natural, cantidad_20c, temperatura,
                                    importe_flete, remision_pemex, folio_factura_distribuidor,
                                    observaciones
                                )
                                VALUES 
                                (
                                    {sel_prog_id_val}, '{estacion_id_sel}', '{producto_descarga}', '{f_desc_str}',
                                    '{num_embarque}', '{f_carga_str}', '{tad_origen}', '{cliente_pemex}',
                                    '{destino_num}', {cant_natural}, {cant_20c}, {temperatura},
                                    {importe_flete}, '{remision_pemex}', '{factura_distribuidor}',
                                    '{observaciones}'
                                );
                            """
                            cursor.execute(insert_bitacora)
                            conn.commit()
                            cursor.close()
                            st.success("✅ ¡Descarga real registrada y guardada exitosamente en la bitácora!")
                            st.rerun()
                        except Exception as err:
                            conn.rollback()
                            cursor.close()
                            st.error(f"Error al registrar en la base de datos: {err}")

        # ==========================================
        # PESTAÑA 2: HISTORIAL DE BITÁCORA REAL
        # ==========================================
        with tab2:
            st.markdown(f"#### 📋 Bitácora Histórica de Descargas - Estación {estacion_id_sel}")
            
            try:
                query_bitacora = f"""
                    SELECT 
                        id AS id_bitacora,
                        COALESCE(CAST(id_programacion AS VARCHAR), 'EXTRAORDINARIA') AS orden_de_carga,
                        producto,
                        fecha_descarga_real AS f_descarga,
                        remision_pemex AS rp,
                        folio_factura_distribuidor AS factura,
                        cantidad_natural AS natural_l,
                        cantidad_20c AS a_20c_l,
                        temperatura AS temp,
                        importe_flete AS flete,
                        tad_origen AS tad,
                        numero_embarque AS embarque,
                        registrado_en
                    FROM bitacora_descargas
                    WHERE id_estacion = '{estacion_id_sel}'
                    ORDER BY fecha_descarga_real DESC, id DESC;
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
