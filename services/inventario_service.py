import pandas as pd

PRODUCTOS_INVENTARIO = ("regular", "premium", "diesel")


def normalizar_producto_inventario(producto):
    valor = str(producto).strip().lower()
    if "regular" in valor or "magna" in valor:
        return "regular"
    if "premium" in valor:
        return "premium"
    if "diesel" in valor:
        return "diesel"
    return valor


def formatear_ids_estaciones(ids_estaciones):
    if not ids_estaciones:
        return "()"
    if len(ids_estaciones) == 1:
        return f"('{ids_estaciones[0]}')"
    return str(tuple(ids_estaciones))


def obtener_tanques_por_estaciones(conn, ids_estaciones):
    tanques_estaciones = {}
    if not ids_estaciones:
        return tanques_estaciones

    ids_str = formatear_ids_estaciones(ids_estaciones)
    try:
        query_tanques = f"""
            SELECT id_estacion, producto, capacidad_maxima
            FROM tanques
            WHERE id_estacion IN {ids_str};
        """
        df_tanques = pd.read_sql(query_tanques, conn)
        if not df_tanques.empty:
            for _, rt in df_tanques.iterrows():
                e_id = str(rt["id_estacion"]).strip()
                p_key = normalizar_producto_inventario(rt["producto"])
                cap = (
                    float(rt["capacidad_maxima"])
                    if pd.notna(rt["capacidad_maxima"])
                    else 0.0
                )
                if cap <= 0:
                    continue
                tanques_estaciones.setdefault(e_id, set()).add(p_key)
    except Exception:
        return tanques_estaciones

    return tanques_estaciones


def obtener_inventarios_existentes(conn, fecha_seleccionada, ids_estaciones):
    if not ids_estaciones:
        return pd.DataFrame(columns=["id_estacion", "producto", "volumen"])

    ids_str = formatear_ids_estaciones(ids_estaciones)
    query_inventarios_previos = f"""
        SELECT id_estacion, producto, volumen
        FROM inventarios
        WHERE fecha = '{fecha_seleccionada}'
          AND id_estacion IN {ids_str};
    """
    return pd.read_sql(query_inventarios_previos, conn)


def construir_matriz_inventario(df_estaciones, tanques_estaciones, df_existentes):
    df = df_estaciones.copy()
    for campo in ("Regular", "Premium", "Diesel"):
        df[campo] = None

    mapeo = {
        "Regular": "regular",
        "Premium": "premium",
        "Diesel": "diesel",
    }

    for idx, row in df.iterrows():
        e_id = row["ID"]
        prods_disp = tanques_estaciones.get(e_id, set(PRODUCTOS_INVENTARIO))
        for campo, producto_key in mapeo.items():
            if producto_key in prods_disp:
                df.loc[idx, campo] = 0

    if not df_existentes.empty:
        df_existentes = df_existentes.copy()
        df_existentes["producto_norm"] = df_existentes["producto"].map(
            normalizar_producto_inventario
        )

        for idx, row in df.iterrows():
            e_id = row["ID"]
            prods_disp = tanques_estaciones.get(e_id, set(PRODUCTOS_INVENTARIO))
            for campo, producto_key in mapeo.items():
                if producto_key not in prods_disp:
                    continue

                coincidencias = df_existentes[
                    (df_existentes["id_estacion"] == e_id)
                    & (df_existentes["producto_norm"] == producto_key)
                ]
                if coincidencias.empty:
                    df.loc[idx, campo] = 0
                    continue

                volumen = coincidencias.iloc[0].get("volumen")
                df.loc[idx, campo] = int(float(volumen)) if pd.notna(volumen) else 0

    return df


def guardar_inventarios(conn, df_editado, tanques_estaciones, fecha_seleccionada):
    cursor = conn.cursor()
    sql_upsert_inv = """
        INSERT INTO inventarios (fecha, id_estacion, producto, volumen)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (fecha, id_estacion, producto)
        DO UPDATE SET volumen = EXCLUDED.volumen;
    """
    count = 0
    fecha_str = str(fecha_seleccionada)

    for _, row in df_editado.iterrows():
        e_id = str(row["ID"])
        prods_disp = tanques_estaciones.get(e_id, set(PRODUCTOS_INVENTARIO))
        productos_data = [
            ("regular", row["Regular"]),
            ("premium", row["Premium"]),
            ("diesel", row["Diesel"]),
        ]

        for producto_key, vol_val in productos_data:
            if producto_key not in prods_disp:
                continue
            if pd.notna(vol_val) and float(vol_val) >= 0:
                cursor.execute(
                    sql_upsert_inv,
                    (fecha_str, e_id, producto_key, float(vol_val)),
                )
                count += 1

    conn.commit()
    cursor.close()
    return count


__all__ = [
    "normalizar_producto_inventario",
    "formatear_ids_estaciones",
    "obtener_tanques_por_estaciones",
    "obtener_inventarios_existentes",
    "construir_matriz_inventario",
    "guardar_inventarios",
]
