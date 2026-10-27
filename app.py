import hashlib

import bcrypt


def _compare_passwords(password: str, stored_password: str) -> bool:
    """Valida contraseñas en entornos mixtos: texto plano, SHA256/SHA512 y bcrypt."""
    if not password or not stored_password:
        return False

    plain = str(stored_password).strip()
    supplied = str(password)

    if plain == supplied:
        return True

    try:
        if bcrypt.checkpw(supplied.encode("utf-8"), plain.encode("utf-8")):
            return True
    except Exception:
        pass

    hashes = {
        "sha256": hashlib.sha256(supplied.encode("utf-8")).hexdigest(),
        "sha512": hashlib.sha512(supplied.encode("utf-8")).hexdigest(),
    }

    return plain in hashes.values()


def authenticate_user(conn, usuario: str, password: str):
    """Valida un usuario contra la tabla usuarios_sistema."""
    if not usuario or not password:
        return None

    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT usuario, contrasena, rol, activo FROM usuarios_sistema WHERE usuario = %s LIMIT 1;",
                (usuario,),
            )
        except Exception:
            cursor.execute(
                "SELECT usuario, contrasena, rol FROM usuarios_sistema WHERE usuario = %s LIMIT 1;",
                (usuario,),
            )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        if len(row) >= 4 and row[3] is False:
            return None

        stored_password = str(row[1]) if row[1] is not None else ""
        rol = str(row[2]) if len(row) > 2 and row[2] is not None else "operador"

        if not _compare_passwords(password, stored_password):
            return None

        return {"usuario": row[0], "rol": rol}
    except Exception:
        return None


def get_menu_for_role(rol: str):
    """Devuelve la lista de módulos visibles según el rol."""
    role = (rol or "").strip().lower()

    if role == "admin":
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

    return [
        "Dashboard",
        "Programación (MRP)",
        "Inventarios",
        "Ventas",
        "Descargas",
    ]


def can_access_module(rol: str, modulo: str) -> bool:
    """Determina si el rol puede acceder a un módulo."""
    menu = get_menu_for_role(rol)
    return modulo in menu


__all__ = [
    "authenticate_user",
    "get_menu_for_role",
    "can_access_module",
]
