from datetime import datetime
import io
import re
import pandas as pd
import streamlit as st


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
  """Estandariza los nombres de productos en mayúsculas."""
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


def transformar_reporte_ancho(df_wide, anio_referencia=2026):
  """Transforma un reporte de programación en formato ancho (fechas en columnas)

  a formato tabular normalizado: fecha, id_estacion, producto, volumen.
  """
  # 1. Identificar columnas fijas hasta 'Inv Actual' o usar metadatos estándar
  if 'Inv Actual' in df_wide.columns:
    idx_inv = df_wide.columns.get_loc('Inv Actual')
    columnas_fijas = list(df_wide.columns[: idx_inv + 1])
    columnas_fechas = list(df_wide.columns[idx_inv + 1 :])
  else:
    columnas_fijas = [
        c
        for c in [
            'User',
            'ID',
            'Destino',
            'TAD',
            'Grupo',
            'Estacion',
            'Producto',
            'MRP',
            'Inv Actual',
        ]
        if c in df_wide.columns
    ]
    if not columnas_fijas:
      columnas_fijas = list(df_wide.columns[:9])
    columnas_fechas = [c for c in df_wide.columns if c not in columnas_fijas]

  # 2. Reestructurar de ancho a largo con pd.melt
  df_long = pd.melt(
      df_wide,
      id_vars=columnas_fijas,
      value_vars=columnas_fechas,
      var_name='fecha_raw',
      value_name='volumen_raw',
  )

  # 3. Extraer y limpiar ID de estación y producto
  col_id = (
      'ID'
      if 'ID' in df_long.columns
      else (df_long.columns[1] if len(df_long.columns) > 1 else None)
  )
  df_long['id_estacion'] = (
      df_long[col_id].astype(str).str.strip() if col_id else ''
  )

  col_prod = (
      'Producto'
      if 'Producto' in df_long.columns
      else (df_long.columns[6] if len(df_long.columns) > 6 else None)
  )
  df_long['producto'] = (
      df_long[col_prod].apply(normalizar_producto) if col_prod else ''
  )
  df_long['volumen'] = df_long['volumen_raw'].apply(
      limpiar_numero_preservando_ceros
  )

  # 4. Parsear fechas combinando el texto de la columna (ej. '19-oct') con el año
  def parsear_fecha(val):
    if pd.isna(val):
      return None
    val_str = str(val).strip()
    try:
      dt = pd.to_datetime(
          f'{val_str}-{anio_referencia}', format='%d-%b-%Y', errors='coerce'
      )
      if pd.isna(dt):
        dt = pd.to_datetime(val_str, errors='coerce')
      return dt.strftime('%Y-%m-%d') if pd.notna(dt) else None
    except Exception:
      return None

  df_long['fecha'] = df_long['fecha_raw'].apply(parsear_fecha)

  # 5. Filtrar registros válidos
  df_resultado = df_long[['fecha', 'id_estacion', 'producto', 'volumen']].copy()
  df_resultado = df_resultado[
      df_resultado['fecha'].notna()
      & (df_resultado['id_estacion'] != '')
      & df_resultado['volumen'].notna()
      & (df_resultado['volumen'] > 0)
  ]

  # Consolidar duplicados si los hubiera
  df_resultado = df_resultado.groupby(
      ['fecha', 'id_estacion', 'producto'], as_index=False
  )['volumen'].sum()

  return df_resultado


def dataframe_a_excel_bytes(df):
  output = io.BytesIO()
  with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name='Programa_Normalizado')
  return output.getvalue()


def render(conn):
  st.markdown('### 🛠️ Módulo de Herramientas de Datos (Pruebas)')
  st.write(
      'Herramientas auxiliares para sanitizar y transformar reportes'
      ' operativos complejos antes de cargarlos al sistema.'
  )
  st.markdown('---')

  st.subheader('📥 Transformador de Reporte Ancho (Programa de Cargas)')
  st.write(
      'Sube un archivo de Excel con fechas en columnas (ej. `19-oct`, `20-oct`,'
      ' etc.). La herramienta generará automáticamente la tabla limpia con las'
      ' columnas: `fecha`, `id_estacion`, `producto`, `volumen`.'
  )

  anio_sel = st.number_input(
      'Año de referencia para las fechas del reporte:',
      min_value=2024,
      max_value=2030,
      value=datetime.now().year,
  )

  archivo_ancho = st.file_uploader(
      'Selecciona el reporte Excel en formato ancho:',
      type=['xlsx', 'xls'],
      key='up_herramientas_ancho',
  )

  if archivo_ancho is not None:
    try:
      df_crudo = pd.read_excel(archivo_ancho)
      st.write('📊 **Vista previa del archivo original cargado:**')
      st.dataframe(df_crudo.head(5), use_container_width=True)

      # Aplicar transformación
      df_limpio = transformar_reporte_ancho(
          df_crudo, anio_referencia=int(anio_sel)
      )

      st.success(
          f'✨ ¡Transformación exitosa! Se obtuvieron {len(df_limpio)} registros'
          ' normalizados.'
      )
      st.write('📊 **Vista previa de la tabla resultante:**')
      st.dataframe(df_limpio.head(10), use_container_width=True)

      # Descargar resultado limpio
      st.download_button(
          label='📥 Descargar Tabla Normalizada (Excel)',
          data=dataframe_a_excel_bytes(df_limpio),
          file_name='programa_cargas_normalizado.xlsx',
          mime=(
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          ),
          key='btn_descargar_limpio',
      )

      st.markdown('---')
      st.subheader('🚀 Importación Opcional')
      st.write(
          'Si el resultado es correcto, puedes probar la importación directa a'
          " la tabla `programacion_cargas`."
      )

      if st.button(
          '💾 Importar Datos Transformados al Sistema',
          key='btn_importar_herramientas',
      ):
        if conn is None:
          st.error('No hay conexión activa a la base de datos.')
          return

        cursor = conn.cursor()
        sql_insert = """
                    INSERT INTO programacion_cargas (id_estacion, producto, fecha_programacion, volumen_programado)
                    VALUES (%s, %s, %s, %s);
                """
        count = 0
        for _, row in df_limpio.iterrows():
          cursor.execute(
              sql_insert,
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
            f'¡Se importaron exitosamente {count} registros a'
            " `programacion_cargas`!"
        )

    except Exception as e:
      st.error(f'Error al procesar el archivo en la herramienta: {e}')
