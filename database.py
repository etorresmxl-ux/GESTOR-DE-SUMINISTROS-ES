import streamlit as st
import psycopg2


def init_connection():
    """Establece y retorna la conexión a Supabase usando la URL de secrets."""
    try:
        db_url = st.secrets["postgres"]["url"]
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None


def close_connection(conn):
    """Cierra la conexión si existe."""
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
