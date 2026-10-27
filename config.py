import os

import streamlit as st


def get_database_url():
    """Obtiene la URL de conexión priorizando variables de entorno."""
    candidates = [
        os.getenv("DATABASE_URL"),
        os.getenv("SUPABASE_DB_URL"),
        os.getenv("POSTGRES_URL"),
    ]

    for value in candidates:
        if value and value.strip():
            return value.strip()

    try:
        return st.secrets["postgres"]["url"]
    except Exception:
        return None


def has_database_config():
    return bool(get_database_url())
