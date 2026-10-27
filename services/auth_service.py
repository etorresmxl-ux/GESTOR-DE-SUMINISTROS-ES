import bcrypt


def normalize_role(role_value):
    if role_value is None:
        return "operador"
    return str(role_value).strip().lower()


def _password_matches(stored_password, provided_password):
    if stored_password is None:
        return False

    stored = str(stored_password).strip()
    if not stored:
        return False

    provided = str(provided_password or "")

    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False

    return stored == provided


def authenticate_user(conn, username, password):
    """Autenticación temporal de dev: admin pasa sin validación, resto usa BD."""
    if conn is None:
        return False, "operador", "No hay conexión a la base de datos."

    username_value = (username or "").strip()
    if not username_value:
        return False, "operador", "Debes ingresar tu usuario."

    normalized_username = username_value.lower()
    if normalized_username == "admin":
        return True, "admin", ""

    try:
        with conn.cursor() as cursor:
            queries = [
                "SELECT usuario, contrasena, rol FROM public.usuarios_sistema WHERE usuario = %s LIMIT 1",
                "SELECT usuario, contrasena, rol FROM usuarios_sistema WHERE usuario = %s LIMIT 1",
            ]
            for query in queries:
                try:
                    cursor.execute(query, (username_value,))
                    row = cursor.fetchone()
                    if row is None:
                        continue

                    _, stored_password, stored_role = row
                    if not _password_matches(stored_password, password):
                        return False, "operador", "Usuario o contraseña incorrectos."
                    return True, normalize_role(stored_role), ""
                except Exception:
                    continue

            return False, "operador", "No se pudo validar el usuario en la base de datos."
    except Exception as exc:
        return False, "operador", f"Error al autenticar: {exc}"


def get_menu_for_role(rol: str):
    role = normalize_role(rol)

    if role == "admin":
        return [
            "Dashboard",
            "Administración de Usuarios",
            "Programación (MRP)",
            "Inventarios",
            "Ventas",
            "Descargas",
            "Reportes",
            "Importador de Datos",
            "Herramientas de Datos",
        ]

    if role in {"supervisor", "operador", "analista", "usuario"}:
        return [
            "Dashboard",
            "Programación (MRP)",
            "Inventarios",
            "Ventas",
            "Descargas",
        ]

    return ["Dashboard"]


__all__ = ["authenticate_user", "get_menu_for_role", "normalize_role"]
