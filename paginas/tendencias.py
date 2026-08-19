import hashlib
import math
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from componentes.interfaz import (
    configuracion_plotly as crear_configuracion_plotly,
    encabezado_pagina,
    pie_pagina,
    resumen_compacto,
    titulo_seccion,
)

encabezado_pagina(
    titulo="Tendencias"
)


# -------------------------------------------------
# RECUPERAR DATOS
# -------------------------------------------------

datos_sesion = st.session_state.get("datos")

if datos_sesion is None:
    st.warning(
        "No hay datos disponibles. Primero debes importar "
        "y confirmar una fuente de datos."
    )

    st.page_link(
        "paginas/importar_datos.py",
        label="Ir a Importar datos",
        icon=":material/upload_file:"
    )

    st.stop()


# Copia para no modificar el DataFrame guardado en la sesión.
datos = datos_sesion.copy()


# -------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------

def convertir_fechas(serie: pd.Series) -> pd.Series:
    """
    Convierte una columna a datetime.

    Prioriza el formato del archivo TAG.csv:
    2026-03-01 00:00:09.999999823
    """

    texto = serie.astype("string").str.strip()

    fechas = pd.to_datetime(
        texto,
        format="%Y-%m-%d %H:%M:%S.%f",
        errors="coerce"
    )

    pendientes = fechas.isna() & texto.notna()

    if pendientes.any():
        fechas_mixtas = pd.to_datetime(
            texto.loc[pendientes],
            format="mixed",
            errors="coerce",
            dayfirst=False
        )

        fechas.loc[pendientes] = fechas_mixtas

    return fechas


def combinar_fecha_hora(fecha, hora) -> datetime:
    """Combina los valores entregados por date_input y time_input."""

    return datetime.combine(fecha, hora)


def restaurar_periodo_completo(
    clave_fecha_inicio,
    clave_hora_inicio,
    clave_fecha_fin,
    clave_hora_fin,
    fecha_minima,
    fecha_maxima
):
    """Restaura el periodo antes de reconstruir sus widgets."""

    st.session_state[clave_fecha_inicio] = fecha_minima.date()
    st.session_state[clave_hora_inicio] = fecha_minima.time()
    st.session_state[clave_fecha_fin] = fecha_maxima.date()
    st.session_state[clave_hora_fin] = fecha_maxima.time()


def crear_firma_datos(
    nombre_archivo: str,
    cantidad: int,
    fecha_minima: pd.Timestamp,
    fecha_maxima: pd.Timestamp,
    columna_tiempo: str
) -> str:
    """Crea claves únicas para los widgets de cada archivo importado."""

    texto = (
        f"{nombre_archivo}|{cantidad}|"
        f"{fecha_minima.isoformat()}|"
        f"{fecha_maxima.isoformat()}|"
        f"{columna_tiempo}"
    )

    return hashlib.sha1(
        texto.encode("utf-8")
    ).hexdigest()[:12]


def crear_histograma(
    serie: pd.Series,
    variable: str,
    numero_intervalos: int,
    color: str
):
    """Crea un histograma con media y mediana para una variable."""

    valores = pd.to_numeric(
        serie,
        errors="coerce"
    ).to_numpy(dtype=float)
    valores = valores[np.isfinite(valores)]

    if valores.size < 2:
        return None

    cantidades, limites = np.histogram(
        valores,
        bins=numero_intervalos
    )
    centros = (limites[:-1] + limites[1:]) / 2
    anchos = np.diff(limites)
    rangos = np.column_stack(
        (limites[:-1], limites[1:])
    )
    altura_maxima = max(int(cantidades.max()), 1)
    media = float(np.mean(valores))
    mediana = float(np.median(valores))

    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            x=centros,
            y=cantidades,
            width=anchos,
            customdata=rangos,
            marker_color=color,
            name="Distribución",
            hovertemplate=(
                "Rango: %{customdata[0]:.6g} – "
                "%{customdata[1]:.6g}<br>"
                "Cantidad: %{y:,}<extra></extra>"
            )
        )
    )
    figura.add_trace(
        go.Scatter(
            x=[media, media],
            y=[0, altura_maxima],
            mode="lines",
            name=f"Media: {media:.4g}",
            line=dict(
                color="#D62728",
                width=3,
                dash="dash"
            ),
            hovertemplate=(
                f"Media: {media:.6g}<extra></extra>"
            )
        )
    )
    figura.add_trace(
        go.Scatter(
            x=[mediana, mediana],
            y=[0, altura_maxima],
            mode="lines",
            name=f"Mediana: {mediana:.4g}",
            line=dict(
                color="#2CA02C",
                width=3,
                dash="dot"
            ),
            hovertemplate=(
                f"Mediana: {mediana:.6g}<extra></extra>"
            )
        )
    )
    figura.update_layout(
        title=f"Distribución de {variable}",
        xaxis_title=variable,
        yaxis_title="Cantidad de registros",
        bargap=0.03,
        height=500,
        legend_title_text="Referencias",
        margin=dict(
            l=40,
            r=30,
            t=60,
            b=40
        )
    )

    return figura


# -------------------------------------------------
# IDENTIFICAR COLUMNAS
# -------------------------------------------------

columnas = datos.columns.tolist()

columnas_numericas = datos.select_dtypes(
    include="number"
).columns.tolist()

if not columnas_numericas:
    st.error(
        "El conjunto de datos no contiene variables numéricas."
    )
    st.stop()


columnas_temporales = [
    columna
    for columna in columnas
    if pd.api.types.is_datetime64_any_dtype(datos[columna])
]

nombres_temporales = (
    "timestamp",
    "fecha",
    "hora",
    "datetime",
    "date",
    "time"
)

indice_sugerido = next(
    (
        indice
        for indice, columna in enumerate(columnas)
        if any(
            palabra in str(columna).lower()
            for palabra in nombres_temporales
        )
    ),
    0
)


# -------------------------------------------------
# CONFIGURAR COLUMNA TEMPORAL
# -------------------------------------------------

titulo_seccion("Periodo de análisis")

if columnas_temporales:
    opciones_tiempo = columnas_temporales
    indice_temporal = 0
else:
    opciones_tiempo = columnas
    indice_temporal = indice_sugerido



columna_periodo, detalle_periodo = st.columns([1.2, 2])

with columna_periodo:
    columna_tiempo = st.selectbox(
        "Columna de fecha y hora",
        options=opciones_tiempo,
        index=indice_temporal
    )


datos[columna_tiempo] = convertir_fechas(
    datos[columna_tiempo]
)

cantidad_total = len(datos)

cantidad_fechas_invalidas = int(
    datos[columna_tiempo].isna().sum()
)

datos = (
    datos
    .dropna(subset=[columna_tiempo])
    .sort_values(columna_tiempo)
    .reset_index(drop=True)
)

if datos.empty:
    st.error(
        "La columna seleccionada no contiene fechas válidas."
    )
    st.stop()


fecha_minima = pd.Timestamp(
    datos[columna_tiempo].min()
)

fecha_maxima = pd.Timestamp(
    datos[columna_tiempo].max()
)

with detalle_periodo:
    st.caption(
        "Disponible: "
        f"{fecha_minima.strftime('%d-%m-%Y %H:%M')} → "
        f"{fecha_maxima.strftime('%d-%m-%Y %H:%M')}"
    )

if cantidad_fechas_invalidas > 0:
    porcentaje_invalidas = (
        cantidad_fechas_invalidas
        / cantidad_total
        * 100
    )

    st.warning(
        f"""
        Se excluyeron {cantidad_fechas_invalidas:,} registros
        ({porcentaje_invalidas:.2f} %) porque no contenían una fecha válida.
        """
    )


# -------------------------------------------------
# SELECTOR DE PERIODO PERSONALIZADO
# -------------------------------------------------

nombre_archivo = st.session_state.get(
    "nombre_archivo",
    "sin_archivo"
)

firma_datos = crear_firma_datos(
    nombre_archivo=nombre_archivo,
    cantidad=len(datos),
    fecha_minima=fecha_minima,
    fecha_maxima=fecha_maxima,
    columna_tiempo=columna_tiempo
)

clave_fecha_inicio = f"tendencias_fecha_inicio_{firma_datos}"
clave_hora_inicio = f"tendencias_hora_inicio_{firma_datos}"
clave_fecha_fin = f"tendencias_fecha_fin_{firma_datos}"
clave_hora_fin = f"tendencias_hora_fin_{firma_datos}"


# Valores iniciales siempre válidos para el archivo actual.
if clave_fecha_inicio not in st.session_state:
    st.session_state[clave_fecha_inicio] = fecha_minima.date()

if clave_hora_inicio not in st.session_state:
    st.session_state[clave_hora_inicio] = fecha_minima.time()

if clave_fecha_fin not in st.session_state:
    st.session_state[clave_fecha_fin] = fecha_maxima.date()

if clave_hora_fin not in st.session_state:
    st.session_state[clave_hora_fin] = fecha_maxima.time()


(
    col_fecha_inicio,
    col_hora_inicio,
    col_fecha_fin,
    col_hora_fin,
    col_restaurar
) = st.columns(
    [1.35, 0.75, 1.35, 0.75, 0.8],
    vertical_alignment="bottom"
)

with col_fecha_inicio:
    fecha_inicio_input = st.date_input(
        "Fecha inicial",
        min_value=fecha_minima.date(),
        max_value=fecha_maxima.date(),
        format="DD/MM/YYYY",
        key=clave_fecha_inicio
    )

with col_hora_inicio:
    hora_inicio_input = st.time_input(
        "Hora inicial",
        step=60,
        key=clave_hora_inicio
    )
with col_fecha_fin:
    fecha_fin_input = st.date_input(
        "Fecha final",
        min_value=fecha_minima.date(),
        max_value=fecha_maxima.date(),
        format="DD/MM/YYYY",
        key=clave_fecha_fin
    )

with col_hora_fin:
    hora_fin_input = st.time_input(
        "Hora final",
        step=60,
        key=clave_hora_fin
    )

with col_restaurar:
    st.button(
        "Periodo completo",
        key=f"periodo_completo_{firma_datos}",
        on_click=restaurar_periodo_completo,
        args=(
            clave_fecha_inicio,
            clave_hora_inicio,
            clave_fecha_fin,
            clave_hora_fin,
            fecha_minima,
            fecha_maxima
        )
    )


fecha_inicio = pd.Timestamp(
    combinar_fecha_hora(
        fecha_inicio_input,
        hora_inicio_input
    )
)

fecha_fin = pd.Timestamp(
    combinar_fecha_hora(
        fecha_fin_input,
        hora_fin_input
    )
)


if fecha_inicio < fecha_minima:
    fecha_inicio = fecha_minima

if fecha_fin > fecha_maxima:
    fecha_fin = fecha_maxima

if fecha_inicio >= fecha_fin:
    st.error(
        "La fecha y hora inicial deben ser anteriores a la fecha y hora final."
    )
    st.stop()


# -------------------------------------------------
# FILTRAR PERIODO
# -------------------------------------------------

datos_periodo = datos.loc[
    (datos[columna_tiempo] >= fecha_inicio)
    & (datos[columna_tiempo] <= fecha_fin)
].copy()

if datos_periodo.empty:
    st.warning(
        "No existen registros dentro del periodo seleccionado."
    )
    st.stop()


# -------------------------------------------------
# CONFIGURAR VISUALIZACIÓN
# -------------------------------------------------

titulo_seccion("Visualización")

col_variables, col_modo, col_tipo = st.columns([2, 1, 1])

with col_variables:
    variables = st.multiselect(
        "Variables que deseas graficar",
        options=columnas_numericas,
        default=columnas_numericas[:1],
        max_selections=8,
        help=(
            "Puedes seleccionar hasta ocho variables. "
            "Usa paneles separados cuando sus escalas sean diferentes."
        )
    )

with col_modo:
    modo_visualizacion = st.selectbox(
        "Modo de visualización",
        options=[
            "Paneles separados",
            "Gráfico superpuesto"
        ],
        help=(
            "El gráfico superpuesto es recomendable cuando las variables "
            "tienen unidades y escalas similares."
        )
    )

with col_tipo:
    tipo_visualizacion = st.selectbox(
        "Tipo de visualización",
        options=[
            "Gráfico de líneas",
            "Histograma",
            "Ambos"
        ],
        index=0,
        key=f"tipo_visualizacion_{firma_datos}"
    )


if not variables:
    st.info(
        "Selecciona al menos una variable para generar el gráfico."
    )
    st.stop()


# -------------------------------------------------
# RESOLUCIÓN
# -------------------------------------------------

with st.expander("Opciones de resolución", expanded=False):
    col_resolucion, col_estadistica = st.columns(2)

    with col_resolucion:
        resolucion = st.selectbox(
            "Resolución",
            options=[
                "Automática",
                "Datos originales",
                "1 minuto",
                "5 minutos",
                "15 minutos",
                "30 minutos",
                "1 hora"
            ],
            index=0,
            key=f"resolucion_tendencias_{firma_datos}"
        )

    with col_estadistica:
        estadistica_agregacion = st.selectbox(
            "Valor representativo por intervalo",
            options=[
                "Promedio",
                "Mínimo",
                "Máximo",
                "Primer valor",
                "Último valor"
            ],
            index=0,
            disabled=(resolucion == "Datos originales"),
            key=f"agregacion_tendencias_{firma_datos}"
        )


duracion_periodo = (
    datos_periodo[columna_tiempo].max()
    - datos_periodo[columna_tiempo].min()
)

if resolucion == "Automática":
    if duracion_periodo <= pd.Timedelta(hours=12):
        regla_resample = None
        resolucion_utilizada = "Datos originales"
    elif duracion_periodo <= pd.Timedelta(days=3):
        regla_resample = "1min"
        resolucion_utilizada = "1 minuto"
    elif duracion_periodo <= pd.Timedelta(days=21):
        regla_resample = "5min"
        resolucion_utilizada = "5 minutos"
    elif duracion_periodo <= pd.Timedelta(days=90):
        regla_resample = "15min"
        resolucion_utilizada = "15 minutos"
    elif duracion_periodo <= pd.Timedelta(days=180):
        regla_resample = "30min"
        resolucion_utilizada = "30 minutos"
    else:
        regla_resample = "1h"
        resolucion_utilizada = "1 hora"
else:
    mapa_resoluciones = {
        "Datos originales": None,
        "1 minuto": "1min",
        "5 minutos": "5min",
        "15 minutos": "15min",
        "30 minutos": "30min",
        "1 hora": "1h"
    }

    regla_resample = mapa_resoluciones[resolucion]
    resolucion_utilizada = resolucion


# -------------------------------------------------
# PREPARAR DATOS DEL GRÁFICO
# -------------------------------------------------

columnas_grafico = [columna_tiempo] + variables

datos_grafico = (
    datos_periodo[columnas_grafico]
    .dropna(subset=[columna_tiempo])
    .copy()
)

if regla_resample is not None:
    mapa_agregaciones = {
        "Promedio": "mean",
        "Mínimo": "min",
        "Máximo": "max",
        "Primer valor": "first",
        "Último valor": "last"
    }

    datos_grafico = (
        datos_grafico
        .set_index(columna_tiempo)
        .resample(regla_resample)[variables]
        .agg(mapa_agregaciones[estadistica_agregacion])
        .dropna(how="all")
        .reset_index()
    )


# Protección del navegador.
limite_visual = 100_000

if len(datos_grafico) > limite_visual:
    salto = math.ceil(
        len(datos_grafico) / limite_visual
    )

    datos_grafico = datos_grafico.iloc[::salto].copy()

    st.warning(
        f"""
        El periodo contiene demasiados puntos para el navegador.
        Se muestra una representación de {len(datos_grafico):,} puntos.
        Selecciona un periodo más corto o una resolución agregada
        para observar mayor detalle.
        """
    )


st.caption(
    f"{len(datos_periodo):,} registros · "
    f"{len(datos_grafico):,} puntos mostrados · "
    f"Resolución: {resolucion_utilizada}"
)


# -------------------------------------------------
# GRÁFICO INTERACTIVO
# -------------------------------------------------

configuracion_plotly = crear_configuracion_plotly(
    "tendencias_EAFV"
)


if modo_visualizacion == "Gráfico superpuesto":
    figura = go.Figure()

    for variable in variables:
        figura.add_trace(
            go.Scattergl(
                x=datos_grafico[columna_tiempo],
                y=datos_grafico[variable],
                mode="lines",
                name=variable,
                hovertemplate=(
                    f"<b>{variable}</b><br>"
                    "%{x|%d-%m-%Y %H:%M:%S}<br>"
                    "Valor: %{y}<extra></extra>"
                )
            )
        )

    figura.update_layout(
        height=620,
        hovermode="x unified",
        legend_title_text="Variables",
        margin=dict(
            l=30,
            r=30,
            t=30,
            b=30
        ),
        xaxis_title="Fecha y hora",
        yaxis_title="Valor"
    )

    figura.update_xaxes(
        rangeslider_visible=True,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor"
    )

    figura.update_yaxes(
        showspikes=True,
        spikesnap="cursor"
    )

else:
    figura = make_subplots(
        rows=len(variables),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=variables
    )

    for indice, variable in enumerate(
        variables,
        start=1
    ):
        figura.add_trace(
            go.Scattergl(
                x=datos_grafico[columna_tiempo],
                y=datos_grafico[variable],
                mode="lines",
                name=variable,
                showlegend=False,
                hovertemplate=(
                    f"<b>{variable}</b><br>"
                    "%{x|%d-%m-%Y %H:%M:%S}<br>"
                    "Valor: %{y}<extra></extra>"
                )
            ),
            row=indice,
            col=1
        )

        figura.update_yaxes(
            title_text=variable,
            showspikes=True,
            spikesnap="cursor",
            row=indice,
            col=1
        )

    figura.update_layout(
        height=max(500, 280 * len(variables)),
        hovermode="x unified",
        margin=dict(
            l=40,
            r=30,
            t=40,
            b=40
        )
    )

    figura.update_xaxes(
        title_text="Fecha y hora",
        rangeslider_visible=True,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        row=len(variables),
        col=1
    )


if tipo_visualizacion in {"Gráfico de líneas", "Ambos"}:
    titulo_seccion("Gráfico de tendencias")

    st.plotly_chart(
        figura,
        width="stretch",
        config=configuracion_plotly,
        key=f"grafico_tendencias_{firma_datos}"
    )


if tipo_visualizacion in {"Histograma", "Ambos"}:
    titulo_seccion("Distribución de las variables")

    numero_intervalos = st.slider(
        "Número de intervalos",
        min_value=5,
        max_value=100,
        value=30,
        step=1,
        key=f"intervalos_histograma_{firma_datos}"
    )

    colores_plotly = [
        "#636EFA",
        "#EF553B",
        "#00CC96",
        "#AB63FA",
        "#FFA15A",
        "#19D3F3",
        "#FF6692",
        "#B6E880"
    ]

    for indice, variable in enumerate(variables):
        figura_histograma = crear_histograma(
            serie=datos_periodo[variable],
            variable=str(variable),
            numero_intervalos=numero_intervalos,
            color=colores_plotly[
                indice % len(colores_plotly)
            ]
        )

        if figura_histograma is None:
            st.warning(
                f"La variable '{variable}' no contiene al menos "
                "dos valores numéricos finitos dentro del periodo "
                "seleccionado. Se omitió su histograma."
            )
            continue

        configuracion_histograma = {
            **configuracion_plotly,
            "toImageButtonOptions": {
                **configuracion_plotly["toImageButtonOptions"],
                "filename": f"histograma_{indice + 1}_EAFV"
            }
        }

        st.plotly_chart(
            figura_histograma,
            width="stretch",
            config=configuracion_histograma,
            key=(
                f"histograma_{firma_datos}_{indice}_"
                f"{numero_intervalos}"
            )
        )


# -------------------------------------------------
# RESUMEN DEL PERIODO
# -------------------------------------------------

titulo_seccion("Resumen del periodo")

fecha_inicial_real = datos_periodo[columna_tiempo].min()
fecha_final_real = datos_periodo[columna_tiempo].max()

resumen_compacto(
    [
        {
            "etiqueta": "Registros",
            "valor": f"{len(datos_periodo):,}"
        },
        {
            "etiqueta": "Variables",
            "valor": len(variables)
        },
        {
            "etiqueta": "Inicio",
            "valor": fecha_inicial_real.strftime("%d-%m-%Y %H:%M")
        },
        {
            "etiqueta": "Fin",
            "valor": fecha_final_real.strftime("%d-%m-%Y %H:%M")
        }
    ]
)


resumen = (
    datos_periodo[variables]
    .describe()
    .T
    .rename(
        columns={
            "count": "Registros",
            "mean": "Promedio",
            "std": "Desviación estándar",
            "min": "Mínimo",
            "25%": "Percentil 25",
            "50%": "Mediana",
            "75%": "Percentil 75",
            "max": "Máximo"
        }
    )
)

with st.expander("Ver estadísticas detalladas", expanded=False):
    st.dataframe(
        resumen,
        width="stretch"
    )


# -------------------------------------------------
# DESCARGA
# -------------------------------------------------

st.caption("Exportación")

datos_descarga = datos_periodo[
    [columna_tiempo] + variables
].to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    label="Descargar datos filtrados",
    data=datos_descarga,
    file_name="datos_periodo_tendencias.csv",
    mime="text/csv",
    icon=":material/download:",
    width="content"
)

pie_pagina()

