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


def _read_columns(cursor):
    try:
        columns = [col[0].lower() for col in cursor.description or []]
        return columns
    except Exception:
        return []


def authenticate_user(conn, username, password):
    """Valida credenciales del usuario usando la BD y devuelve rol normalizado.

    Busca filas en la tabla `usuarios` con nombres de columna comunes.
    Si la tabla o columnas difieren, intenta detectar el esquema dinámicamente.
    """
    if conn is None:
        return False, "operador", "No hay conexión a la base de datos."

    username_value = (username or "").strip()
    if not username_value:
        return False, "operador", "Debes ingresar tu usuario."

    try:
        with conn.cursor() as cursor:
            candidate_queries = [
                "SELECT usuario, password, rol FROM usuarios WHERE usuario = %s LIMIT 1",
                "SELECT usuario, contrasena, rol FROM usuarios WHERE usuario = %s LIMIT 1",
                "SELECT usuario, password_hash, rol FROM usuarios WHERE usuario = %s LIMIT 1",
                "SELECT username, password, role FROM usuarios WHERE username = %s LIMIT 1",
                "SELECT username, password_hash, role FROM usuarios WHERE username = %s LIMIT 1",
            ]

            for query in candidate_queries:
                try:
                    cursor.execute(query, (username_value,))
                    row = cursor.fetchone()
                    if row:
                        user_col = "usuario"
                        pass_col = "password"
                        role_col = "rol"

                        if len(row) >= 3:
                            user_value, password_value, role_value = row[0], row[1], row[2]
                            if _password_matches(password_value, password):
                                return True, normalize_role(role_value), ""
                            return False, "operador", "Usuario o contraseña incorrectos."
                except Exception:
                    continue

            try:
                cursor.execute("SELECT * FROM usuarios LIMIT 1")
                cols = _read_columns(cursor)
                if not cols:
                    return False, "operador", "No se encontró una tabla de usuarios válida."

                user_col = next((c for c in ["usuario", "username", "email", "login"] if c in cols), None)
                pass_col = next((c for c in ["password", "contrasena", "password_hash", "pass_hash", "pwd"] if c in cols), None)
                role_col = next((c for c in ["rol", "role", "tipo_usuario", "perfil", "cargo"] if c in cols), None)

                if not (user_col and pass_col and role_col):
                    return False, "operador", "La tabla de usuarios no tiene columnas de autenticación válidas."

                cursor.execute(
                    f"SELECT {user_col}, {pass_col}, {role_col} FROM usuarios WHERE {user_col} = %s LIMIT 1",
                    (username_value,),
                )
                row = cursor.fetchone()
                if not row:
                    return False, "operador", "Usuario o contraseña incorrectos."

                user_value, password_value, role_value = row[0], row[1], row[2]
                if not _password_matches(password_value, password):
                    return False, "operador", "Usuario o contraseña incorrectos."

                return True, normalize_role(role_value), ""
            except Exception:
                return False, "operador", "No se pudo validar el usuario en la base de datos."
    except Exception as exc:
        return False, "operador", f"Error al autenticar: {exc}"


def get_menu_for_role(rol: str):
    rol_normalizado = normalize_role(rol)

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

    if rol_normalizado in {"supervisor", "operador", "analista", "usuario"}:
        return [
            "Dashboard",
            "Programación (MRP)",
            "Inventarios",
            "Ventas",
            "Descargas",
        ]

    return ["Dashboard"]


__all__ = ["authenticate_user", "get_menu_for_role", "normalize_role"]
