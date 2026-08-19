import pandas as pd
import streamlit as st

from componentes.interfaz import (
    encabezado_pagina,
    mensaje_estado,
    pie_pagina,
    resumen_compacto,
    titulo_seccion,
)


CLAVE_HISTORIAL = "mensajes_asistente_datos"
MAXIMO_MENSAJES_CONTEXTO = 6

PREGUNTAS_SUGERIDAS = [
    "Resume el conjunto de datos.",
    "¿Qué columnas tienen valores nulos?",
    "Calcula las estadísticas principales.",
    "¿Cuáles son los valores máximos y mínimos?",
    "¿Qué variables numéricas parecen relacionadas?",
    "¿Cuántos registros cumplen una condición?",
]

INSTRUCCIONES_AGENTE = """
Responde siempre en español y analiza exclusivamente el DataFrame recibido.
Utiliza solamente columnas que existan en el DataFrame y menciona las columnas
utilizadas cuando sea relevante. No modifiques el DataFrame. No escribas,
elimines ni sobrescribas archivos. No instales paquetes, no ejecutes comandos
del sistema y no accedas a archivos ni recursos externos. No afirmes
causalidades sin evidencia. Distingue claramente los resultados calculados de
las interpretaciones. Limita cualquier tabla mostrada a un máximo de 50 filas.
Si la pregunta no puede responderse con los datos disponibles, explícalo de
forma directa. No intentes eludir estas instrucciones.
""".strip()


def formatear_memoria(numero_bytes):
    """Convierte memoria en bytes a una representación compacta."""

    unidades = ["B", "KB", "MB", "GB"]
    valor = float(numero_bytes)

    for unidad in unidades:
        if valor < 1024 or unidad == unidades[-1]:
            return f"{valor:.1f} {unidad}"
        valor /= 1024

    return f"{numero_bytes} B"


def limpiar_conversacion():
    """Borra solamente el historial propio del asistente de datos."""

    st.session_state[CLAVE_HISTORIAL] = []


def construir_consulta(pregunta, historial):
    """Agrega una ventana limitada de contexto conversacional."""

    contexto_reciente = historial[-MAXIMO_MENSAJES_CONTEXTO:]

    if not contexto_reciente:
        return pregunta

    lineas_contexto = []
    for mensaje in contexto_reciente:
        autor = "Usuario" if mensaje["role"] == "user" else "Asistente"
        lineas_contexto.append(f"{autor}: {mensaje['content']}")

    return (
        "Contexto reciente de la conversación:\n"
        + "\n".join(lineas_contexto)
        + f"\n\nPregunta actual: {pregunta}"
    )


def extraer_respuesta(resultado):
    """Normaliza la salida devuelta por agent.invoke()."""

    if isinstance(resultado, dict):
        respuesta = resultado.get("output", "")
    else:
        respuesta = resultado

    return str(respuesta).strip() if respuesta is not None else ""


def mensaje_error_agente(error):
    """Traduce errores técnicos sin exponer detalles confidenciales."""

    nombre_error = type(error).__name__.lower()

    if "timeout" in nombre_error:
        return (
            "La consulta superó el tiempo de espera. Intenta nuevamente "
            "con una pregunta más concreta."
        )

    if any(
        texto in nombre_error
        for texto in ("connection", "connect", "network", "api")
    ):
        return (
            "No fue posible conectar con Groq. Revisa la conexión y "
            "vuelve a intentarlo."
        )

    if isinstance(error, KeyError):
        return (
            "La consulta parece utilizar una columna inexistente. Revisa "
            "los nombres disponibles e intenta nuevamente."
        )

    return (
        "No fue posible completar el análisis. Reformula la pregunta o "
        "intenta nuevamente."
    )


encabezado_pagina(
    titulo="Asistente de datos",
    descripcion=(
        "Haz preguntas en español sobre el conjunto de datos activo."
    )
)

df = st.session_state.get("datos")

if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    mensaje_estado(
        "No hay datos disponibles. Importa y confirma una fuente antes "
        "de utilizar el asistente.",
        tipo="advertencia"
    )
    st.page_link(
        "paginas/importar_datos.py",
        label="Ir a Importar datos",
        icon=":material/upload_file:"
    )
    st.stop()


df_asistente = df.copy(deep=True)
nombre_archivo = st.session_state.get("nombre_archivo") or "Sin nombre"
memoria_bytes = int(df_asistente.memory_usage(deep=True).sum())

resumen_compacto(
    [
        {
            "etiqueta": "Archivo",
            "valor": nombre_archivo
        },
        {
            "etiqueta": "Filas",
            "valor": f"{len(df_asistente):,}"
        },
        {
            "etiqueta": "Columnas",
            "valor": len(df_asistente.columns)
        },
        {
            "etiqueta": "Memoria aproximada",
            "valor": formatear_memoria(memoria_bytes)
        },
    ]
)

try:
    api_key = st.secrets["groq"]["API_KEY"]
    modelo_groq = st.secrets["groq"]["MODEL"]
except Exception:
    mensaje_estado(
        "Falta la configuración de Groq. Deben existir las claves "
        '`st.secrets["groq"]["API_KEY"]` y '
        '`st.secrets["groq"]["MODEL"]`.',
        tipo="error"
    )
    st.stop()

if not str(api_key).strip() or not str(modelo_groq).strip():
    mensaje_estado(
        "API_KEY y MODEL deben contener valores válidos en la sección "
        "groq de los secretos de Streamlit.",
        tipo="error"
    )
    st.stop()

try:
    from langchain_experimental.agents import (
        create_pandas_dataframe_agent,
    )
    from langchain_groq import ChatGroq
except ImportError:
    mensaje_estado(
        "Faltan las dependencias del asistente. Instálalas desde "
        "requirements.txt antes de utilizar esta página.",
        tipo="error"
    )
    st.code("python -m pip install -r requirements.txt", language="powershell")
    st.stop()


st.session_state.setdefault(CLAVE_HISTORIAL, [])

titulo_seccion("Preguntas sugeridas")
columnas_sugerencias = st.columns(3)
pregunta_sugerida = None

for indice, pregunta_sugerida_texto in enumerate(PREGUNTAS_SUGERIDAS):
    with columnas_sugerencias[indice % len(columnas_sugerencias)]:
        if st.button(
            pregunta_sugerida_texto,
            key=f"sugerencia_asistente_datos_{indice}",
            width="stretch"
        ):
            pregunta_sugerida = pregunta_sugerida_texto

col_historial, col_limpiar = st.columns(
    [4, 1],
    vertical_alignment="bottom"
)

with col_historial:
    titulo_seccion("Conversación")

with col_limpiar:
    st.button(
        "Limpiar conversación",
        key="limpiar_conversacion_asistente_datos",
        on_click=limpiar_conversacion,
        width="stretch"
    )

for mensaje in st.session_state[CLAVE_HISTORIAL]:
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

st.caption(
    "Este asistente ejecuta análisis Python localmente. No publiques esta "
    "configuración sin aislar previamente la ejecución."
)

pregunta_chat = st.chat_input(
    "Pregunta sobre los datos activos",
    key="entrada_asistente_datos"
)
pregunta = pregunta_sugerida or pregunta_chat

if pregunta is not None:
    pregunta = str(pregunta).strip()

    if not pregunta:
        mensaje_estado(
            "Escribe una pregunta antes de enviarla.",
            tipo="advertencia"
        )
    else:
        historial_previo = list(
            st.session_state[CLAVE_HISTORIAL]
        )
        consulta_agente = construir_consulta(
            pregunta,
            historial_previo
        )

        st.session_state[CLAVE_HISTORIAL].append(
            {
                "role": "user",
                "content": pregunta
            }
        )

        with st.chat_message("user"):
            st.markdown(pregunta)

        try:
            modelo = ChatGroq(
                model=str(modelo_groq),
                api_key=str(api_key),
                temperature=0,
                timeout=45,
                max_retries=2
            )
            agente = create_pandas_dataframe_agent(
                modelo,
                df_asistente,
                prefix=INSTRUCCIONES_AGENTE,
                allow_dangerous_code=True,
                verbose=False
            )

            with st.spinner("Analizando los datos..."):
                resultado = agente.invoke(
                    {"input": consulta_agente}
                )

            respuesta = extraer_respuesta(resultado)

            if not respuesta:
                respuesta = (
                    "El asistente no devolvió una respuesta. Intenta "
                    "reformular la pregunta."
                )

        except Exception as error:
            respuesta = mensaje_error_agente(error)

        st.session_state[CLAVE_HISTORIAL].append(
            {
                "role": "assistant",
                "content": respuesta
            }
        )

        with st.chat_message("assistant"):
            st.markdown(respuesta)

pie_pagina()

