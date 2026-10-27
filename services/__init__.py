import pandas as pd

DIAS_SEMANA = ["lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom."]
MESES = [
    "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
    "jul.", "ago.", "sep.", "oct.", "nov.", "dic.",
]
PRODUCTOS_ORDEN = ["REGULAR", "PREMIUM", "DIESEL"]
COLOR_PRODUCTO = {
    "REGULAR": "#1e8449",
    "PREMIUM": "#d35400",
    "DIESEL": "#5d6d7e",
}


def _clave_producto(texto):
    p = str(texto).strip().lower()
    if "regular" in p or "magna" in p:
        return "REGULAR"
    if "premium" in p:
        return "PREMIUM"
    if "diesel" in p:
        return "DIESEL"
    return str(texto).strip().upper()


def _etiqueta_fecha(f):
    return f"{DIAS_SEMANA[f.weekday()]} {f.day:02d}-{MESES[f.month - 1]}"


def construir_calendario(df_ordenes, productos_estacion, hoy):
    """Calendario de cargas registradas: una fila por producto, una columna por día."""
    o = df_ordenes.copy()
    o["fecha"] = pd.to_datetime(o["fecha_programacion"]).dt.date
    o["prod"] = o["producto"].map(_clave_producto)
    o["vol"] = pd.to_numeric(o["volumen_programado"], errors="coerce").fillna(0.0)

    lunes_actual = hoy - pd.Timedelta(days=hoy.weekday())
    fechas = [lunes_actual + pd.Timedelta(days=i) for i in range(14)]

    fuera = int((o["fecha"] > fechas[-1]).sum()) + int((o["fecha"] < fechas[0]).sum())
    con_ordenes = set(o["prod"])
    productos = [p for p in PRODUCTOS_ORDEN if p in productos_estacion or p in con_ordenes] or PRODUCTOS_ORDEN
    totales = o.groupby(["prod", "fecha"])["vol"].sum()

    tabla = pd.DataFrame(
        "",
        index=[p.capitalize() for p in productos],
        columns=[_etiqueta_fecha(f) for f in fechas],
    )
    for p in productos:
        for f in fechas:
            v = totales.get((p, f), 0.0)
            if v > 0:
                tabla.loc[p.capitalize(), _etiqueta_fecha(f)] = f"{v:,.0f}"
    return tabla, fuera


def estilo_calendario(tabla):
    """Pinta solo las celdas con carga, con el color de cada producto."""

    def pintar(_):
        css = pd.DataFrame("", index=tabla.index, columns=tabla.columns)
        for etiqueta in tabla.index:
            color = COLOR_PRODUCTO.get(etiqueta.upper(), "#5d6d7e")
            for col in tabla.columns:
                if tabla.loc[etiqueta, col]:
                    css.loc[etiqueta, col] = (
                        f"background-color: {color}; color: #ffffff; font-weight: 600;"
                    )
        return css

    return tabla.style.apply(pintar, axis=None)


def obtener_capacidades_por_estacion(conn, estacion_id):
    capacidades = {}
    productos_disponibles_estacion = set()
    try:
        query_tanques = f"""
            SELECT producto, capacidad_maxima
            FROM tanques
            WHERE id_estacion = '{estacion_id}';
        """
        df_tanques = pd.read_sql(query_tanques, conn)
        if not df_tanques.empty:
            for _, r_t in df_tanques.iterrows():
                p_raw = str(r_t["producto"]).strip().lower()
                cap = float(r_t["capacidad_maxima"]) if pd.notna(r_t["capacidad_maxima"]) else 0.0

                if "regular" in p_raw or "magna" in p_raw:
                    p_key = "regular"
                elif "premium" in p_raw:
                    p_key = "premium"
                elif "diesel" in p_raw:
                    p_key = "diesel"
                else:
                    p_key = p_raw

                capacidades[p_key] = cap
                if cap > 0:
                    productos_disponibles_estacion.add(p_key)
    except Exception:
        pass

    return capacidades, productos_disponibles_estacion


def obtener_cargas_guardadas(conn, estacion_id):
    cargas_guardadas = {}
    try:
        query_cargas_db = f"""
            SELECT fecha_programacion, producto, SUM(volumen_programado) as total_vol
            FROM programacion_cargas
            WHERE id_estacion = '{estacion_id}'
            GROUP BY fecha_programacion, producto;
        """
        df_cargas_db = pd.read_sql(query_cargas_db, conn)
        if not df_cargas_db.empty:
            for _, r in df_cargas_db.iterrows():
                f_str = str(r["fecha_programacion"]).split("T")[0]
                p_str = str(r["producto"]).strip().lower()
                vol = float(r["total_vol"]) if pd.notna(r["total_vol"]) else 0.0
                cargas_guardadas[(f_str, p_str)] = vol
    except Exception:
        pass

    return cargas_guardadas


def obtener_inventario_actual(conn, estacion_id):
    inv_actuales = {"regular": 0.0, "premium": 0.0, "diesel": 0.0}
    fecha_inventario = None
    try:
        query_inv = f"""
            SELECT fecha, producto, volumen
            FROM inventarios
            WHERE id_estacion = '{estacion_id}'
            ORDER BY fecha DESC;
        """
        df_inv = pd.read_sql(query_inv, conn)
        if not df_inv.empty:
            fecha_inventario = df_inv["fecha"].iloc[0]
            df_inv_reciente = df_inv[df_inv["fecha"] == fecha_inventario]
            for _, row_i in df_inv_reciente.iterrows():
                p_norm = str(row_i["producto"]).strip().lower()
                vol_val = float(row_i["volumen"]) if pd.notna(row_i["volumen"]) else 0.0
                if "regular" in p_norm or "magna" in p_norm:
                    inv_actuales["regular"] = vol_val
                elif "premium" in p_norm:
                    inv_actuales["premium"] = vol_val
                elif "diesel" in p_norm:
                    inv_actuales["diesel"] = vol_val
    except Exception:
        pass

    return inv_actuales, fecha_inventario


__all__ = [
    "DIAS_SEMANA",
    "MESES",
    "PRODUCTOS_ORDEN",
    "COLOR_PRODUCTO",
    "_clave_producto",
    "_etiqueta_fecha",
    "construir_calendario",
    "estilo_calendario",
    "obtener_capacidades_por_estacion",
    "obtener_cargas_guardadas",
    "obtener_inventario_actual",
]
