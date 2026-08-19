import streamlit as st

from componentes.interfaz import (
    encabezado_pagina,
    pie_pagina,
    resumen_compacto,
    titulo_seccion,
)

encabezado_pagina(
    titulo="Data Explorer",
    descripcion=(
        "analisa y visualiza datos de procesos "

    )
)


# -------------------------------------------------
# RECUPERAR INFORMACIÓN DE LA SESIÓN
# -------------------------------------------------

datos = st.session_state.get("datos")
nombre_archivo = st.session_state.get("nombre_archivo")
proyecto_activo = st.session_state.get(
    "proyecto_activo",
    "Sin proyecto"
)

# -------------------------------------------------
# ESTADO GENERAL
# -------------------------------------------------

titulo_seccion("Estado actual")

resumen_compacto(
    [
        {
            "etiqueta": "Proyecto activo",
            "valor": proyecto_activo
        },
        {
            "etiqueta": "Archivo",
            "valor": nombre_archivo or "Sin archivo"
        },
        {
            "etiqueta": "Registros",
            "valor": f"{len(datos):,}" if datos is not None else "—"
        },
        {
            "etiqueta": "Columnas",
            "valor": datos.shape[1] if datos is not None else "—"
        }
    ]
)


# -------------------------------------------------
# CUANDO NO EXISTEN DATOS
# -------------------------------------------------

if datos is None:

    st.info(
        """
        Para comenzar un análisis, crea o selecciona un proyecto
        y luego importa o conecta una fuente de datos.
        """
    )

    titulo_seccion("Comenzar un nuevo análisis")

    col1, col2 = st.columns(2)

    with col1:
        st.page_link(
            "paginas/proyectos.py",
            label="Administrar proyectos",
            icon=":material/folder:"
        )

    with col2:
        st.page_link(
            "paginas/importar_datos.py",
            label="Importar datos",
            icon=":material/upload_file:"
        )

    with st.expander("Ver flujo de trabajo", expanded=False):
        st.markdown(
            """
            1. **Crear o seleccionar un proyecto.**
            2. **Importar o conectar una fuente de datos.**
            3. **Consultar los datos con el asistente.**
            4. **Analizar tendencias.**
            """
        )


# -------------------------------------------------
# CUANDO EXISTEN DATOS
# -------------------------------------------------

else:

    cantidad_filas = datos.shape[0]
    cantidad_columnas = datos.shape[1]

    datos_vacios = int(
        datos.isna().sum().sum()
    )

    columnas_numericas = datos.select_dtypes(
        include="number"
    ).columns

    cantidad_numericas = len(columnas_numericas)

    # Indicadores principales

    titulo_seccion("Resumen de los datos")

    resumen_compacto(
        [
            {
                "etiqueta": "Registros",
                "valor": f"{cantidad_filas:,}"
            },
            {
                "etiqueta": "Columnas",
                "valor": cantidad_columnas
            },
            {
                "etiqueta": "Datos vacíos",
                "valor": f"{datos_vacios:,}"
            },
            {
                "etiqueta": "Variables numéricas",
                "valor": cantidad_numericas
            }
        ]
    )

    st.divider()

    # Estado de calidad

    titulo_seccion("Estado general")

    if datos_vacios == 0:
        st.success(
            "No se detectaron datos vacíos."
        )
    else:
        porcentaje_vacios = (
            datos_vacios
            / datos.size
            * 100
        )

        st.warning(
            f"""
            Se detectaron {datos_vacios:,} datos vacíos,
            equivalentes al {porcentaje_vacios:.2f}% del archivo.
            """
        )

    # Vista previa

    titulo_seccion("Vista previa")

    st.dataframe(
        datos.head(10),
        use_container_width=True,
        hide_index=True
    )

    # Accesos rápidos

    titulo_seccion("Accesos rápidos")

    acceso1, acceso2 = st.columns(2)

    with acceso1:
        st.page_link(
            "paginas/asistente_datos.py",
            label="Consultar al asistente",
            icon=":material/chat:"
        )

    with acceso2:
        st.page_link(
            "paginas/tendencias.py",
            label="Analizar tendencias",
            icon=":material/monitoring:"
        )


# -------------------------------------------------
# PIE DE PÁGINA
# -------------------------------------------------

pie_pagina()
