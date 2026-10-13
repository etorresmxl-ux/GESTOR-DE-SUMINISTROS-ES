import streamlit as st
import psycopg2

st.set_page_config(page_title="Gestión de Suministro", page_icon="⛽")
st.title("⛽ Sistema de Gestión de Suministro de Gasolineras")

# Intentar conectar a la base de datos usando los secretos configurados
try:
    # Leemos la URL desde st.secrets
    db_url = st.secrets["postgres"]["url"]
    
    # Establecemos la conexión
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Hacemos una consulta rápida para verificar las tablas existentes
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    tablas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Si todo sale bien, mostramos éxito
    st.success("¡Conexión exitosa con la base de datos de Supabase! 🚀")
    
    if tablas:
        st.write("**Tablas detectadas en tu base de datos:**")
        for tabla in tablas:
            st.write(f"- 📁 {tabla[0]}")
    else:
        st.info("La conexión es correcta, pero aún no se detectan tablas creadas.")

except Exception as e:
    st.error("Hubo un error al conectar con la base de datos:")
    st.exception(e)
