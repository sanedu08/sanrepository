# EAFV Data Explorer

Aplicación multipágina de Streamlit para importar, explorar y analizar datos.

## Ejecución local

1. Crea y activa un entorno virtual de Python.
2. Instala las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copia `.streamlit/secrets.toml.example` como
   `.streamlit/secrets.toml` y agrega una clave nueva de Groq.
4. Ejecuta la aplicación desde la raíz del repositorio:

   ```powershell
   streamlit run app.py
   ```

## Despliegue en Streamlit Community Cloud

- Archivo principal: `app.py`
- Dependencias: `requirements.txt`
- Configuración visual: `.streamlit/config.toml`
- En **Advanced settings > Secrets**, agrega:

  ```toml
  [groq]
  API_KEY = "tu_clave_de_groq"
  MODEL = "llama-3.3-70b-versatile"
  ```

El archivo `.streamlit/secrets.toml` está excluido de Git y nunca debe
publicarse.

## Seguridad

El asistente de datos utiliza un agente capaz de ejecutar código Python para
analizar el DataFrame cargado. Antes de ofrecer la aplicación a usuarios no
confiables, esa ejecución debe aislarse en un entorno restringido.
