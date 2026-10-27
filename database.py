import logging

import streamlit as st
import psycopg2

from config import get_database_url

logger = logging.getLogger(__name__)


def init_connection():
    """Establece y retorna la conexión a la base de datos desde configuración centralizada."""
    db_url = get_database_url()

    if not db_url:
        message = (
            "No se configuró la conexión a la base de datos. "
            "Define DATABASE_URL/SUPABASE_DB_URL/POSTGRES_URL o agrega "
            "st.secrets['postgres']['url']."
        )
        logger.error(message)
        st.error(message)
        return None

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    except Exception as exc:
        message = f"Error al conectar con la base de datos: {exc}"
        logger.exception(message)
        st.error(message)
        return None


def close_connection(conn):
    """Cierra la conexión si existe."""
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
