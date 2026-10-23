import io
import re
import pandas as pd
import streamlit as st


def limpiar_fecha(val):
    if pd.isna(val) or str(val).strip() == '':
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None


def limpiar_numero_preservando_ceros(val):
    """Limpia el número permitiendo ceros y descartando vacíos."""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str == '' or val_str.lower() in ['none', 'null', 'nan', '-']:
        return None
    val_limpio = re.sub(r'[^\d.-]', '', val_str)
    try:
        num = float(val_limpio)
        if pd.isna(num):
            return None
        return num
    except ValueError:
        return None


def normalizar_producto(producto_raw):
    """Estandariza los nombres de productos en mayúsculas para la programación de cargas."""
    if pd.isna(producto_raw):
        return ''
    p_str = str(producto_raw).strip().upper()
    if 'REGULAR' in p_str or 'MAGNA' in p_str:
        return 'REGULAR'
    elif 'PREMIUM' in p_str:
        return 'PREMIUM'
    elif 'DIESEL' in p_str:
        return 'DIESEL'
    else:
        return p_str


def normalizar_producto_inventario(producto_raw):
    """Estandariza los nombres de productos estrictamente en minúsculas para inventarios y ventas."""
    if pd.isna(producto_raw):
        return ''
    p_str = str(producto_raw).strip().lower()
    if 'regular' in p_str or 'magna' in p_str:
        return 'regular'
    elif 'premium' in p_str:
        return 'premium'
    elif 'diesel' in p_str:
        return 'diesel'
    else:
        return p_str


def dataframe_a_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()


def obtener_tanques_validos(conn, ids_estaciones, para_cargas=False):
    """
    Consulta la tabla 'tanques' en Supabase y retorna un set de tuplas (id_estacion, producto_normalizado)
    con capacidad > 0.
    """
    validos = set()
    if not ids_estaciones:
        return validos

    ids_lista = list(set(ids_estaciones))
    ids_str = f"('{ids_lista[0]}')" if len(ids_lista) == 1 else str(tuple(ids_lista))

    try:
        query_tanques = f"""
            SELECT id_estacion, producto, capacidad_maxima 
            FROM tanques 
            WHERE id_estacion IN {ids_str};
        """
        df_tanques = pd.read_sql(query_tanques, conn)
        if not df_tanques.empty:
            for _, r in df_tanques.iterrows():
                e_id = str(r['id_estacion']).strip()
                p_raw = str(r['producto']).strip()
                cap = float(r['capacidad_maxima']) if pd.notna(r['capacidad_maxima']) else 0.0

                if cap > 0:
                    if para_cargas:
                        p_norm = normalizar_producto(p_raw)
                    else:
                        p_norm = normalizar_producto_inventario(p_raw)
                    
                    if p_norm:
                        validos.add((e_id, p_norm))
    except Exception as e:
        st.warning(f"Aviso al consultar la tabla de tanques: {e}")

    return validos


def render(conn):
    st.markdown('### 📥 Módulo de Importación Masiva (Excel / CSV)')
    st.write(
        'Sube tus archivos de Excel (.xlsx) o CSV apegados a la estructura'
        ' normalizada (fecha, id_estacion, producto, volumen).'
    )

    tab_inv, tab_ventas, tab_cargas = st.tabs(
        ['📦 Inventarios', '📊 Ventas', '🚛 Programa de Cargas']
    )

    # ==========================================
    # 1. INVENTARIOS
    # ==========================================
    with tab_inv:
        st.subheader('Carga de Inventarios Históricos y Actuales')
        df_plantilla_inv = pd.DataFrame(
            columns=['fecha', 'id_estacion', 'producto', 'volumen']
        )
        st.download_button(
            label='📥 Descargar Plantilla Excel (Inventarios)',
            data=dataframe_a_excel_bytes(df_plantilla_inv),
            file_name='plantilla_inventarios.xlsx',
            mime=(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
            key='descargar_plantilla_inv_xlsx',
        )
        st.markdown('---')
        file_inv = st.file_uploader(
            'Selecciona el archivo de Inventarios:',
            type=['xlsx', 'xls', 'csv'],
            key='up_inv_file',
        )

        if file_inv is not None:
            try:
                df_inv = (
                    pd.read_csv(file_inv)
                    if file_inv.name.endswith('.csv')
                    else pd.read_excel(file_inv)
                )

                cols_requeridas = ['fecha', 'id_estacion', 'producto', 'volumen']
                if not all(col in df_inv.columns for col in cols_requeridas):
                    st.error(
                        f'El archivo debe contener las columnas exactas:'
                        f' {cols_requeridas}'
                    )
                    return

                df_inv['fecha'] = df_inv['fecha'].apply(limpiar_fecha)
                df_inv['id_estacion'] = df_inv['id_estacion'].astype(str).str.strip()
                df_inv['producto'] = df_inv['producto'].apply(
                    normalizar_producto_inventario
                )
                df_inv['volumen'] = df_inv['volumen'].apply(
                    limpiar_numero_preservando_ceros
                )

                # Validar registros según tanques registrados en Supabase
                ids_est = df_inv['id_estacion'].unique().tolist()
                tanques_validos = obtener_tanques_validos(conn, ids_est, para_cargas=False)

                if tanques_validos:
                    cant_orig = len(df_inv)
                    df_inv['es_valido'] = df_inv.apply(
                        lambda r: (str(r['id_estacion']), str(r['producto'])) in tanques_validos,
                        axis=1
                    )
                    df_inv_omitidos = df_inv[~df_inv['es_valido']]
                    df_inv = df_inv[df_inv['es_valido']].drop(columns=['es_valido'])

                    if not df_inv_omitidos.empty:
                        st.warning(
                            f'⚠️ Se omitieron {len(df_inv_omitidos)} registros por no contar con tanque registrado/activo en Supabase para ese producto.'
                        )

                df_inv = df_inv.groupby(
                    ['fecha', 'id_estacion', 'producto'], as_index=False
                )['volumen'].sum()

                st.info(
                    f'📊 Archivo cargado y sanitizado. Total de registros'
                    f' consolidados a importar: {len(df_inv)}'
                )
                st.dataframe(df_inv, use_container_width=True, height=250)

                if st.button('🚀 Procesar e Importar Inventarios', key='btn_imp_inv'):
                    cursor = conn.cursor()
                    sql_upsert_inv = """
                        INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (fecha, id_estacion, producto) 
                        DO UPDATE SET volumen = EXCLUDED.volumen;
                    """
                    count = 0
                    for _, row in df_inv.iterrows():
                        if pd.notna(row['fecha']) and row['id_estacion'] != '':
                            vol_val = (
                                float(row['volumen']) if pd.notna(row['volumen']) else None
                            )
                            cursor.execute(
                                sql_upsert_inv,
                                (
                                    str(row['fecha']),
                                    str(row['id_estacion']),
                                    str(row['producto']),
                                    vol_val,
                                ),
                            )
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(
                        f'¡Se procesaron e importaron {count} registros de inventarios'
                        " exitosamente en la tabla 'inventarios'!"
                    )
            except Exception as e:
                st.error(f'Error al procesar el archivo de inventarios: {e}')

    # ==========================================
    # 2. VENTAS
    # ==========================================
    with tab_ventas:
        st.subheader('Carga de Ventas Históricas')
        df_plantilla_ventas = pd.DataFrame(
            columns=['fecha', 'id_estacion', 'producto', 'volumen']
        )
        st.download_button(
            label='📥 Descargar Plantilla Excel (Ventas)',
            data=dataframe_a_excel_bytes(df_plantilla_ventas),
            file_name='plantilla_ventas.xlsx',
            mime=(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
            key='descargar_plantilla_ventas_xlsx',
        )
        st.markdown('---')
        file_ventas = st.file_uploader(
            'Selecciona el archivo de Ventas:',
            type=['xlsx', 'xls', 'csv'],
            key='up_ventas_file',
        )

        if file_ventas is not None:
            try:
                df_ventas = (
                    pd.read_csv(file_ventas)
                    if file_ventas.name.endswith('.csv')
                    else pd.read_excel(file_ventas)
                )

                cols_requeridas = ['fecha', 'id_estacion', 'producto', 'volumen']
                if not all(col in df_ventas.columns for col in cols_requeridas):
                    st.error(
                        f'El archivo debe contener las columnas exactas:'
                        f' {cols_requeridas}'
                    )
                    return

                df_ventas['fecha'] = df_ventas['fecha'].apply(limpiar_fecha)
                df_ventas['id_estacion'] = df_ventas['id_estacion'].astype(str).str.strip()
                df_ventas['producto'] = df_ventas['producto'].apply(
                    normalizar_producto_inventario
                )
                df_ventas['volumen'] = df_ventas['volumen'].apply(
                    limpiar_numero_preservando_ceros
                )

                # Validar registros según tanques registrados en Supabase
                ids_est = df_ventas['id_estacion'].unique().tolist()
                tanques_validos = obtener_tanques_validos(conn, ids_est, para_cargas=False)

                if tanques_validos:
                    df_ventas['es_valido'] = df_ventas.apply(
                        lambda r: (str(r['id_estacion']), str(r['producto'])) in tanques_validos,
                        axis=1
                    )
                    df_ventas_omitidos = df_ventas[~df_ventas['es_valido']]
                    df_ventas = df_ventas[df_ventas['es_valido']].drop(columns=['es_valido'])

                    if not df_ventas_omitidos.empty:
                        st.warning(
                            f'⚠️ Se omitieron {len(df_ventas_omitidos)} registros por no contar con tanque registrado/activo en Supabase para ese producto.'
                        )

                df_ventas = df_ventas.groupby(
                    ['fecha', 'id_estacion', 'producto'], as_index=False
                )['volumen'].sum()

                st.info(
                    f'📊 Archivo cargado y sanitizado. Total de registros'
                    f' consolidados a importar: {len(df_ventas)}'
                )
                st.dataframe(df_ventas, use_container_width=True, height=250)

                if st.button('🚀 Procesar e Importar Ventas', key='btn_imp_ventas'):
                    cursor = conn.cursor()
                    sql_upsert_ventas = """
                        INSERT INTO ventas (fecha, id_estacion, producto, volumen)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (fecha, id_estacion, producto) 
                        DO UPDATE SET volumen = EXCLUDED.volumen;
                    """
                    count = 0
                    for _, row in df_ventas.iterrows():
                        if pd.notna(row['fecha']) and row['id_estacion'] != '':
                            vol_val = (
                                float(row['volumen']) if pd.notna(row['volumen']) else None
                            )
                            cursor.execute(
                                sql_upsert_ventas,
                                (
                                    str(row['fecha']),
                                    str(row['id_estacion']),
                                    str(row['producto']),
                                    vol_val,
                                ),
                            )
                            count += 1
                    conn.commit()
                    cursor.close()
                    st.success(
                        f'¡Se procesaron e importaron {count} registros de ventas'
                        " exitosamente en la tabla 'ventas'!"
                    )
            except Exception as e:
                st.error(f'Error al procesar el archivo de ventas: {e}')

    # ==========================================
    # 3. PROGRAMA DE CARGAS
    # ==========================================
    with tab_cargas:
        st.subheader('Carga Masiva del Programa de Cargas')
        st.write(
            'Sube un archivo con el programa de cargas. Cada registro validado'
            ' generará una nueva Orden de Carga con su respectivo número de orden'
            ' asignado.'
        )

        df_plantilla_cargas = pd.DataFrame(
            columns=['fecha', 'id_estacion', 'producto', 'volumen']
        )
        st.download_button(
            label='📥 Descargar Plantilla Excel (Programa de Cargas)',
            data=dataframe_a_excel_bytes(df_plantilla_cargas),
            file_name='plantilla_programa_cargas.xlsx',
            mime=(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
            key='descargar_plantilla_cargas_xlsx',
        )
        st.markdown('---')
        file_cargas = st.file_uploader(
            'Selecciona el archivo del Programa de Cargas:',
            type=['xlsx', 'xls', 'csv'],
            key='up_cargas_file',
        )

        if file_cargas is not None:
            try:
                df_cargas = (
                    pd.read_csv(file_cargas)
                    if file_cargas.name.endswith('.csv')
                    else pd.read_excel(file_cargas)
                )

                cols_requeridas = ['fecha', 'id_estacion', 'producto', 'volumen']
                if not all(col in df_cargas.columns for col in cols_requeridas):
                    st.error(
                        f'El archivo debe contener las columnas exactas:'
                        f' {cols_requeridas}'
                    )
                    return

                df_cargas['fecha'] = df_cargas['fecha'].apply(limpiar_fecha)
                df_cargas['id_estacion'] = df_cargas['id_estacion'].astype(str).str.strip()
                df_cargas['producto'] = df_cargas['producto'].apply(normalizar_producto)
                df_cargas['volumen'] = df_cargas['volumen'].apply(
                    limpiar_numero_preservando_ceros
                )

                # Filtrar filas inválidas por datos básicos
                df_cargas_valido = df_cargas[
                    df_cargas['fecha'].notna()
                    & (df_cargas['id_estacion'] != '')
                    & df_cargas['volumen'].notna()
                    & (df_cargas['volumen'] > 0)
                ].copy()

                # Validar registros según tanques registrados en Supabase
                ids_est = df_cargas_valido['id_estacion'].unique().tolist()
                tanques_validos = obtener_tanques_validos(conn, ids_est, para_cargas=True)

                if tanques_validos:
                    df_cargas_valido['es_valido'] = df_cargas_valido.apply(
                        lambda r: (str(r['id_estacion']), str(r['producto'])) in tanques_validos,
                        axis=1
                    )
                    df_cargas_omitidos = df_cargas_valido[~df_cargas_valido['es_valido']]
                    df_cargas_valido = df_cargas_valido[df_cargas_valido['es_valido']].drop(columns=['es_valido'])

                    if not df_cargas_omitidos.empty:
                        st.warning(
                            f'⚠️ Se omitieron {len(df_cargas_omitidos)} órdenes por no contar con tanque registrado/activo en Supabase para ese producto.'
                        )

                st.info(
                    f'📊 Archivo cargado y validado. Total de órdenes listas para'
                    f' registrar: {len(df_cargas_valido)}'
                )
                if len(df_cargas) > len(df_cargas_valido):
                    st.warning(
                        f'⚠️ Se omitieron un total de {len(df_cargas) - len(df_cargas_valido)}'
                        ' registros por datos incompletos, volúmenes inválidos o sin tanque asignado.'
                    )

                st.dataframe(df_cargas_valido, use_container_width=True, height=250)

                if st.button(
                    '🚀 Procesar e Importar Programa de Cargas', key='btn_imp_cargas'
                ):
                    cursor = conn.cursor()
                    sql_insert_carga = """
                        INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado)
                        VALUES (%s, %s, %s, %s);
                    """
                    count = 0
                    for _, row in df_cargas_valido.iterrows():
                        cursor.execute(
                            sql_insert_carga,
                            (
                                str(row['id_estacion']),
                                str(row['producto']),
                                str(row['fecha']),
                                float(row['volumen']),
                            ),
                        )
                        count += 1
                    conn.commit()
                    cursor.close()
                    st.success(
                        f'¡Se registraron exitosamente {count} nuevas órdenes de carga en'
                        " la tabla 'programacion_cargas' con asignación de folio"
                        ' automático!'
                    )
            except Exception as e:
                st.error(f'Error al procesar el archivo del programa de cargas: {e}')
