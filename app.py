import streamlit as st

from componentes.interfaz import aplicar_estilos_globales


# -------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------

st.set_page_config(
    page_title="EAFV Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

aplicar_estilos_globales()


# -------------------------------------------------
# VARIABLES COMPARTIDAS ENTRE LAS PÁGINAS
# -------------------------------------------------

if "datos" not in st.session_state:
    st.session_state.datos = None

if "nombre_archivo" not in st.session_state:
    st.session_state.nombre_archivo = None

if "proyecto_activo" not in st.session_state:
    st.session_state.proyecto_activo = "Sin proyecto"


# -------------------------------------------------
# INFORMACIÓN DE LA BARRA LATERAL
# -------------------------------------------------

st.sidebar.title("EAFV Data Explorer")
st.sidebar.caption("Análisis de datos")

st.sidebar.divider()

st.sidebar.caption("PROYECTO ACTIVO")
st.sidebar.write(f"**{st.session_state.proyecto_activo}**")

if st.session_state.nombre_archivo:
    st.sidebar.caption("ARCHIVO ACTIVO")
    st.sidebar.write(st.session_state.nombre_archivo)
else:
    st.sidebar.caption("Sin archivo cargado")


# -------------------------------------------------
# DEFINICIÓN DE LAS PÁGINAS
# -------------------------------------------------

paginas = {

    "General": [

        st.Page(
            "paginas/inicio.py",
            title="Inicio",
            icon=":material/home:",
            default=True
        ),

        st.Page(
            "paginas/proyectos.py",
            title="Proyectos",
            icon=":material/folder:"
        ),

        st.Page(
            "paginas/importar_datos.py",
            title="Importar datos",
            icon=":material/upload_file:"
        ),
    ],

    "Análisis": [

        st.Page(
            "paginas/asistente_datos.py",
            title="Asistente de datos",
            icon=":material/chat:"
        ),

        st.Page(
            "paginas/tendencias.py",
            title="Tendencias",
            icon=":material/monitoring:"
        ),
    ],
}


# -------------------------------------------------
# CREACIÓN Y EJECUCIÓN DE LA NAVEGACIÓN
# -------------------------------------------------

pagina_seleccionada = st.navigation(
    paginas,
    position="sidebar",
    expanded=True
)

pagina_seleccionada.run()
