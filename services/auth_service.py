import bcrypt


def normalize_role(role_value):
    if role_value is None:
        return "usuario"

    value = str(role_value).strip().lower()
    if value == "admin":
        return "admin"
    return "usuario"


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
    """Valida credenciales usando usuarios_sistema, con roles admin/usuario."""
    if conn is None:
        return False, "usuario", "No hay conexión a la base de datos."

    username_value = (username or "").strip()
    if not username_value:
        return False, "usuario", "Debes ingresar tu usuario."

    try:
        with conn.cursor() as cursor:
            queries = (
                "SELECT usuario, contrasena, rol FROM public.usuarios_sistema WHERE usuario = %s LIMIT 1",
                "SELECT usuario, contrasena, rol FROM usuarios_sistema WHERE usuario = %s LIMIT 1",
            )

            for query in queries:
                try:
                    cursor.execute(query, (username_value,))
                    row = cursor.fetchone()
                    if row is None:
                        continue

                    _, stored_password, stored_role = row
                    if not _password_matches(stored_password, password):
                        return False, "usuario", "Usuario o contraseña incorrectos."

                    return True, normalize_role(stored_role), ""
                except Exception:
                    continue

            return False, "usuario", "No se pudo validar el usuario en la base de datos."
    except Exception as exc:
        return False, "usuario", f"Error al autenticar: {exc}"


def get_rol_usuario(conn, username):
    if conn is None:
        return "usuario"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT rol FROM public.usuarios_sistema WHERE usuario = %s LIMIT 1",
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return "usuario"
            return normalize_role(row[0])
    except Exception:
        return "usuario"


def get_estaciones_usuario(conn, username):
    """Devuelve las estaciones permitidas para un usuario."""
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT id_estacion
                FROM public.usuarios_estaciones
                WHERE usuario = %s
                ORDER BY id_estacion
                """,
                (username,),
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception:
        return []


def usuario_tiene_permiso(conn, username, modulo):
    """Valida si el usuario tiene permiso para un módulo concreto."""
    if conn is None:
        return False

    rol = get_rol_usuario(conn, username)
    if rol == "admin":
        return True

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT permitido
                FROM public.permisos_modulo
                WHERE rol = %s AND modulo = %s
                LIMIT 1
                """,
                (rol, modulo),
            )
            row = cursor.fetchone()
            if not row:
                return False
            return bool(row[0])
    except Exception:
        return False


def usuario_puede_ver_estacion(conn, username, id_estacion):
    """Valida si el usuario tiene acceso a una estación concreta."""
    if conn is None:
        return False

    rol = get_rol_usuario(conn, username)
    if rol == "admin":
        return True

    estaciones = get_estaciones_usuario(conn, username)
    return str(id_estacion) in [str(e) for e in estaciones]


def get_modulos_habilitados(conn, username):
    """Devuelve los módulos visibles para un usuario."""
    if conn is None:
        return []

    rol = get_rol_usuario(conn, username)
    if rol == "admin":
        return [
            "dashboard",
            "programacion",
            "inventarios",
            "ventas",
            "descargas",
            "reportes",
            "importador",
            "herramientas",
            "administracion_usuarios",
        ]

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT modulo
                FROM public.permisos_modulo
                WHERE rol = %s AND permitido = TRUE
                ORDER BY modulo
                """,
                (rol,),
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception:
        return []


def get_menu_for_role(rol_or_conn, username=None):
    """Compatibilidad: acepta rol texto o conn + username para permisos centralizados."""
    labels = {
        "dashboard": "Dashboard",
        "programacion": "Programación (MRP)",
        "inventarios": "Inventarios",
        "ventas": "Ventas",
        "descargas": "Descargas",
        "reportes": "Reportes",
        "importador": "Importador de Datos",
        "herramientas": "Herramientas de Datos",
        "administracion_usuarios": "Administración de Usuarios",
    }

    if hasattr(rol_or_conn, "cursor") and username is not None:
        modulos = get_modulos_habilitados(rol_or_conn, username)
        return [labels.get(modulo, modulo.replace("_", " ").title()) for modulo in modulos]

    rol = normalize_role(rol_or_conn)
    if rol == "admin":
        modulos = [
            "dashboard",
            "programacion",
            "inventarios",
            "ventas",
            "descargas",
            "reportes",
            "importador",
            "herramientas",
            "administracion_usuarios",
        ]
    else:
        modulos = [
            "dashboard",
            "programacion",
            "inventarios",
            "ventas",
            "descargas",
        ]

    return [labels.get(modulo, modulo.replace("_", " ").title()) for modulo in modulos]


__all__ = [
    "authenticate_user",
    "normalize_role",
    "get_rol_usuario",
    "get_estaciones_usuario",
    "usuario_tiene_permiso",
    "usuario_puede_ver_estacion",
    "get_modulos_habilitados",
    "get_menu_for_role",
]
