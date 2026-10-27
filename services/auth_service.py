def get_menu_for_role(rol: str):
    rol_normalizado = (rol or "").strip().lower()

    if rol_normalizado == "admin":
        return [
            "Dashboard",
            "Programación (MRP)",
            "Inventarios",
            "Ventas",
            "Descargas",
            "Reportes",
            "Importador de Datos",
            "Herramientas de Datos",
        ]

    if rol_normalizado in {"supervisor", "operador", "analista"}:
        return [
            "Dashboard",
            "Programación (MRP)",
            "Inventarios",
            "Ventas",
            "Descargas",
        ]

    return ["Dashboard"]
