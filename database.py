import streamlit as st
import psycopg2

def init_connection():
    """Establece y retorna la conexión a Supabase usando el Pooler."""
    try:
        db_url = st.secrets["postgres"]["url"]
        return psycopg2.connect(db_url)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None
