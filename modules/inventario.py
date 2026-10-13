import streamlit as st
from datetime import datetime

def render(conn):
    st.header("📝 Registro de Inventarios Históricos")
    st.write("Captura los niveles diarios de combustible por estación.")
    
    with st.form("form_inventario"):
        estacion = st.selectbox("Estación / Ciudad", ["Mexicali", "SLRC", "Hermosillo"])
        combustible = st.selectbox("Tipo de Combustible", ["Magna", "Premium", "Diesel"])
        volumen_actual = st.number_input("Volumen Actual (Litros)", min_value=0.0, format="%.2f")
        fecha_registro = st.date_input("Fecha de Registro", datetime.now())
        
        submitted = st.form_submit_button("Guardar Registro")
        if submitted:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO inventarios_historico (estacion, combustible, volumen, fecha) VALUES (%s, %s, %s, %s)",
                    (estacion, combustible, volumen_actual, fecha_registro)
                )
                conn.commit()
                cursor.close()
                st.success("¡Registro de inventario guardado correctamente en Supabase!")
            except Exception as e:
                st.error(f"Error al insertar el registro: {e}")
