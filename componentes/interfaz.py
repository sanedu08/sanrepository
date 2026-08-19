import streamlit as st


def aplicar_estilos_globales():
    """Aplica ajustes visuales compactos desde un único punto."""

    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1440px;
            padding-top: 1.1rem;
            padding-bottom: 1.75rem;
        }

        h1 {
            font-size: 1.55rem;
            letter-spacing: -0.025em;
            margin-bottom: 0.2rem;
        }

        h2, h3 {
            font-size: 1.15rem;
            letter-spacing: -0.015em;
            margin-top: 0.75rem;
            margin-bottom: 0.35rem;
        }

        div[data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 0.55rem;
            padding: 0.5rem 0.75rem;
        }

        div[data-testid="stMetric"] label {
            color: #667085;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.2rem;
        }

        div[data-testid="stExpander"] details summary {
            padding-top: 0.45rem;
            padding-bottom: 0.45rem;
        }

        div[data-testid="stAlert"] {
            padding-top: 0.55rem;
            padding-bottom: 0.55rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(49, 51, 63, 0.10);
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 0.55rem;
            font-weight: 500;
            min-height: 2.35rem;
        }

        [data-testid="stSidebar"] hr {
            margin: 0.75rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def encabezado_pagina(titulo, descripcion=None, icono=None):
    """Muestra el encabezado uniforme de una página."""

    titulo_visible = f"{icono} {titulo}" if icono else titulo
    st.title(titulo_visible)

    if descripcion:
        st.caption(descripcion)


def titulo_seccion(titulo, descripcion=None, numero=None):
    """Muestra un título de sección y una ayuda breve opcional."""

    prefijo = f"{numero}. " if numero is not None else ""
    st.subheader(f"{prefijo}{titulo}")

    if descripcion:
        st.caption(descripcion)


def resumen_compacto(metricas):
    """Presenta métricas homogéneas en una fila adaptable."""

    if not metricas:
        return

    columnas = st.columns(len(metricas))

    for columna, metrica in zip(columnas, metricas):
        columna.metric(
            label=metrica["etiqueta"],
            value=metrica["valor"],
            delta=metrica.get("variacion"),
            help=metrica.get("ayuda")
        )


def mensaje_estado(mensaje, tipo="info", icono=None):
    """Centraliza los mensajes nativos de estado de Streamlit."""

    componentes = {
        "info": st.info,
        "advertencia": st.warning,
        "error": st.error,
        "exito": st.success,
    }
    componente = componentes.get(tipo, st.info)
    componente(mensaje, icon=icono)


def mensaje_pagina_en_desarrollo(titulo, descripcion, icono=None):
    """Presenta de forma uniforme un módulo aún no implementado."""

    encabezado_pagina(
        titulo=titulo,
        descripcion=descripcion,
        icono=icono
    )
    mensaje_estado(
        "Este módulo se encuentra en desarrollo y estará disponible "
        "próximamente.",
        tipo="info",
        icono=":material/construction:"
    )
    pie_pagina()


def configuracion_plotly(nombre_archivo):
    """Devuelve la configuración interactiva común de Plotly."""

    return {
        "displaylogo": False,
        "scrollZoom": True,
        "responsive": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": nombre_archivo,
            "scale": 2
        }
    }


def pie_pagina():
    """Muestra el pie discreto compartido por las páginas."""

    st.divider()
    st.caption(
        "EAFV Data Explorer · Plataforma de análisis de datos"
    )
