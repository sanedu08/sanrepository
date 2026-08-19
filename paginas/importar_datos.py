import csv
import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from componentes.interfaz import (
    encabezado_pagina,
    pie_pagina,
    resumen_compacto,
    titulo_seccion,
)

encabezado_pagina(
    titulo="Importar datos",
    descripcion=(
        "Carga y prepara una fuente antes de utilizarla en los "
        "módulos de análisis."
    )
)

st.session_state.setdefault("datos", None)
st.session_state.setdefault("datos_originales", None)
st.session_state.setdefault("nombre_archivo", None)
st.session_state.setdefault("metadatos_importacion", None)
st.session_state.setdefault("importacion_temporal", None)
st.session_state.setdefault("archivo_temporal_id", None)
st.session_state.setdefault("configuraciones_csv_detectadas", {})


# -------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------

def formatear_tamano(numero_bytes):
    """Convierte bytes a una unidad más fácil de leer."""

    unidades = ["B", "KB", "MB", "GB"]
    tamano = float(numero_bytes)

    for unidad in unidades:
        if tamano < 1024 or unidad == unidades[-1]:
            return f"{tamano:.2f} {unidad}"

        tamano /= 1024

    return f"{numero_bytes} B"


def nombres_columnas_unicos(columnas):
    """Evita nombres de columnas repetidos."""

    resultado = []
    repeticiones = {}

    for columna in columnas:
        nombre = str(columna)

        if nombre not in repeticiones:
            repeticiones[nombre] = 0
            resultado.append(nombre)
        else:
            repeticiones[nombre] += 1
            resultado.append(
                f"{nombre}_{repeticiones[nombre]}"
            )

    return resultado


def limpiar_nombres_columnas(columnas):
    """
    Limpia espacios, saltos de línea y caracteres especiales
    presentes en los nombres de las columnas.
    """

    columnas_limpias = []

    for columna in columnas:
        nombre = str(columna).strip()

        nombre = re.sub(r"\s+", "_", nombre)
        nombre = re.sub(r"[^\w.-]", "_", nombre)
        nombre = re.sub(r"_+", "_", nombre)

        if not nombre:
            nombre = "columna"

        columnas_limpias.append(nombre)

    return nombres_columnas_unicos(columnas_limpias)


def crear_identificador_archivo(contenido, tamano_muestra=65_536):
    """Identifica el archivo mediante su tamaño y una muestra binaria."""

    muestra = contenido[:tamano_muestra]
    firma = hashlib.sha256()
    firma.update(str(len(contenido)).encode("ascii"))
    firma.update(b":")
    firma.update(muestra)
    return firma.hexdigest()


def detectar_codificacion_csv(muestra):
    """Prueba las codificaciones admitidas en un orden controlado."""

    tiene_bom_utf8 = muestra.startswith(b"\xef\xbb\xbf")

    for codificacion in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1"
    ):
        # UTF-8-SIG también decodifica UTF-8 sin BOM. Se reserva para
        # archivos que realmente incluyen la marca para distinguirlos.
        if codificacion == "utf-8-sig" and not tiene_bom_utf8:
            continue

        try:
            texto = muestra.decode(codificacion, errors="strict")
            confiable = codificacion != "latin-1"
            return codificacion, texto, confiable
        except UnicodeDecodeError:
            continue

    # Latin-1 puede representar cualquier byte, por lo que esta rama es
    # solamente una protección adicional.
    return "latin-1", muestra.decode("latin-1"), False


def detectar_separador_csv(texto, extension):
    """Detecta un delimitador permitido y evalúa su consistencia."""

    separadores_permitidos = [",", ";", "\t", "|"]
    predeterminados = {
        ".csv": ",",
        ".tsv": "\t",
        ".txt": "|"
    }

    try:
        dialecto = csv.Sniffer().sniff(
            texto,
            delimiters="".join(separadores_permitidos)
        )
        separador = dialecto.delimiter
    except csv.Error:
        return predeterminados.get(extension, ","), False

    lineas = [
        linea
        for linea in texto.splitlines()
        if linea.strip()
    ][:50]

    if len(lineas) < 2:
        return separador, False

    cantidades = []
    for linea in lineas:
        try:
            cantidades.append(
                len(next(csv.reader([linea], delimiter=separador)))
            )
        except (csv.Error, StopIteration):
            continue

    if not cantidades:
        return separador, False

    cantidad_frecuente = max(
        set(cantidades),
        key=cantidades.count
    )
    proporcion_consistente = (
        cantidades.count(cantidad_frecuente) / len(cantidades)
    )
    confiable = (
        cantidad_frecuente > 1
        and proporcion_consistente >= 0.8
    )

    return separador, confiable


def detectar_decimal_csv(texto, separador):
    """Infiere punto o coma decimal desde valores numéricos simples."""

    conteos = {".": 0, ",": 0}

    try:
        filas = csv.reader(io.StringIO(texto), delimiter=separador)

        for indice, fila in enumerate(filas):
            if indice >= 100:
                break

            for valor in fila:
                valor = valor.strip()

                if re.fullmatch(r"[+-]?\d+\.\d+", valor):
                    conteos["."] += 1
                elif re.fullmatch(r"[+-]?\d+,\d+", valor):
                    conteos[","] += 1
    except csv.Error:
        return ".", False

    if conteos["."] > conteos[","]:
        return ".", True

    if conteos[","] > conteos["."]:
        return ",", True

    return ".", False


def detectar_configuracion_csv(contenido, extension):
    """Detecta la configuración usando una sola muestra de 64 KiB."""

    muestra = contenido[:65_536]
    codificacion, texto, codificacion_confiable = (
        detectar_codificacion_csv(muestra)
    )
    separador, separador_confiable = detectar_separador_csv(
        texto,
        extension
    )
    decimal, decimal_confiable = detectar_decimal_csv(
        texto,
        separador
    )

    return {
        "separador": separador,
        "decimal": decimal,
        "codificacion": codificacion,
        "valores_vacios": [
            "",
            "NA",
            "N/A",
            "null",
            "NULL",
            "NaN"
        ],
        "separador_confiable": separador_confiable,
        "decimal_confiable": decimal_confiable,
        "codificacion_confiable": codificacion_confiable,
    }


def interpretar_valores_vacios(texto):
    """Convierte la configuración manual en valores para pandas."""

    valores = []

    for valor in texto.split(","):
        valor = valor.strip()

        if valor == "(vacío)":
            valores.append("")
        elif valor:
            valores.append(valor)

    return valores


@st.cache_data(show_spinner=False)
def obtener_hojas_excel(contenido):
    """Obtiene las hojas disponibles en un archivo Excel."""

    archivo = io.BytesIO(contenido)

    with pd.ExcelFile(archivo) as libro:
        return libro.sheet_names


@st.cache_data(show_spinner=False)
def obtener_raices_json(contenido, codificacion):
    """
    Obtiene las claves principales de un JSON para permitir
    seleccionar dónde están los registros.
    """

    texto = contenido.decode(codificacion)
    objeto = json.loads(texto)

    if not isinstance(objeto, dict):
        return []

    return [
        clave
        for clave, valor in objeto.items()
        if isinstance(valor, (list, dict))
    ]


def convertir_json_a_dataframe(objeto, aplanar):
    """Transforma una lista o diccionario JSON en DataFrame."""

    if aplanar:
        return pd.json_normalize(objeto)

    if isinstance(objeto, list):
        return pd.DataFrame(objeto)

    if isinstance(objeto, dict):
        try:
            return pd.DataFrame(objeto)
        except ValueError:
            return pd.DataFrame([objeto])

    return pd.DataFrame({"valor": [objeto]})


@st.cache_data(show_spinner=False)
def leer_archivo(
    contenido,
    nombre_archivo,
    configuracion_json
):
    """Lee el archivo según su extensión y configuración."""

    configuracion = json.loads(configuracion_json)
    extension = Path(nombre_archivo).suffix.lower()
    archivo = io.BytesIO(contenido)

    # CSV, TXT y TSV
    if extension in {".csv", ".txt", ".tsv"}:

        separador = configuracion["separador"]

        argumentos = {
            "sep": separador,
            "decimal": configuracion["decimal"],
            "encoding": configuracion["codificacion"],
            "header": configuracion["encabezado"],
            "skiprows": configuracion["filas_omitidas"],
        }

        if configuracion["valores_vacios"]:
            argumentos["na_values"] = configuracion[
                "valores_vacios"
            ]

        if configuracion["limite_filas"] is not None:
            argumentos["nrows"] = configuracion[
                "limite_filas"
            ]

    # La detección automática requiere el motor Python
        if separador is None:
            argumentos["engine"] = "python"

    # Con un separador definido se puede usar el motor C
        else:
            argumentos["engine"] = "c"
            argumentos["low_memory"] = True

        return pd.read_csv(archivo, **argumentos)

    # Excel y ODS
    if extension in {
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
        ".ods"
    }:

        argumentos = {
            "sheet_name": configuracion["hoja"],
            "header": configuracion["encabezado"],
            "skiprows": configuracion["filas_omitidas"],
        }

        if configuracion["limite_filas"] is not None:
            argumentos["nrows"] = configuracion[
                "limite_filas"
            ]

        return pd.read_excel(archivo, **argumentos)

    # JSON, JSONL y NDJSON
    if extension in {".json", ".jsonl", ".ndjson"}:

        codificacion = configuracion["codificacion"]
        json_lines = configuracion["json_lines"]

        if json_lines:
            return pd.read_json(
                archivo,
                lines=True,
                encoding=codificacion
            )

        texto = contenido.decode(codificacion)
        objeto = json.loads(texto)

        raiz = configuracion["raiz_json"]

        if raiz != "__documento_completo__":
            objeto = objeto[raiz]

        return convertir_json_a_dataframe(
            objeto,
            configuracion["aplanar_json"]
        )

    # Parquet
    if extension == ".parquet":
        return pd.read_parquet(archivo)

    # Feather
    if extension == ".feather":
        return pd.read_feather(archivo)

    # XML
    if extension == ".xml":
        return pd.read_xml(archivo)

    raise ValueError(
        f"El formato {extension} todavía no está soportado."
    )


def preparar_dataframe(
    dataframe,
    columnas_seleccionadas,
    columna_tiempo,
    convertir_fecha,
    dia_primero,
    ordenar_tiempo,
    eliminar_filas_vacias,
    eliminar_columnas_vacias,
    eliminar_duplicados,
    limpiar_columnas
):
    """Aplica la preparación seleccionada por el usuario."""

    datos_preparados = dataframe[
        columnas_seleccionadas
    ].copy()

    # Convertir fecha y hora antes de renombrar columnas
    if (
        convertir_fecha
        and columna_tiempo
        and columna_tiempo in datos_preparados.columns
    ):
        datos_preparados[columna_tiempo] = pd.to_datetime(
            datos_preparados[columna_tiempo],
            errors="coerce",
            dayfirst=dia_primero
        )

        if ordenar_tiempo:
            datos_preparados = datos_preparados.sort_values(
                columna_tiempo
            )

    if eliminar_filas_vacias:
        datos_preparados = datos_preparados.dropna(
            how="all"
        )

    if eliminar_columnas_vacias:
        datos_preparados = datos_preparados.dropna(
            axis=1,
            how="all"
        )

    if eliminar_duplicados:
        datos_preparados = datos_preparados.drop_duplicates()

    if limpiar_columnas:
        datos_preparados.columns = limpiar_nombres_columnas(
            datos_preparados.columns
        )

    return datos_preparados.reset_index(drop=True)


# -------------------------------------------------
# MENSAJE DESPUÉS DE CONFIRMAR
# -------------------------------------------------

if st.session_state.pop(
    "mostrar_importacion_confirmada",
    False
):
    st.success(
        "Los datos fueron importados correctamente y ya están "
        "disponibles en los módulos de análisis."
    )


# -------------------------------------------------
# FUENTE DE DATOS
# -------------------------------------------------

tab_archivo, tab_bd, tab_api = st.tabs(
    [
        "📁 Archivo local",
        "🗄️ Base de datos",
        "🔗 API o URL"
    ]
)


# =================================================
# ARCHIVO LOCAL
# =================================================

with tab_archivo:

    titulo_seccion("Seleccionar archivo", numero=1)

    archivo_subido = st.file_uploader(
        "Arrastra un archivo o selecciónalo desde tu equipo",
        type=[
            "csv",
            "txt",
            "tsv",
            "xlsx",
            "xls",
            "xlsm",
            "xlsb",
            "ods",
            "json",
            "jsonl",
            "ndjson",
            "parquet",
            "feather",
            "xml"
        ],
        accept_multiple_files=False,
        help=(
            "Formatos permitidos: CSV, TXT, TSV, Excel, JSON, "
            "Parquet, Feather y XML."
        )
    )

    st.caption(
        "Formatos: CSV, TXT, TSV, Excel, ODS, JSON, Parquet, "
        "Feather y XML."
    )

    if archivo_subido is None:
        st.caption("Selecciona un archivo para continuar.")

    else:

        contenido = archivo_subido.getvalue()
        extension = Path(
            archivo_subido.name
        ).suffix.lower()

        if extension in {".csv", ".txt", ".tsv"}:
            identificador_archivo = crear_identificador_archivo(
                contenido
            )
        else:
            identificador_archivo = (
                f"{archivo_subido.name}:"
                f"{archivo_subido.size}"
            )

        # Limpiar la vista temporal al seleccionar otro archivo
        if (
            st.session_state.archivo_temporal_id
            != identificador_archivo
        ):
            st.session_state.importacion_temporal = None
            st.session_state.archivo_temporal_id = (
                identificador_archivo
            )

        # Información del archivo
        st.caption(
            f"{archivo_subido.name} · "
            f"{extension.replace('.', '').upper()} · "
            f"{formatear_tamano(archivo_subido.size)}"
        )

        # -----------------------------------------
        # CONFIGURACIÓN DE LECTURA
        # -----------------------------------------

        titulo_seccion("Configurar lectura", numero=2)

        configuracion = {
            "encabezado": 0,
            "filas_omitidas": 0,
            "limite_filas": None
        }

        es_archivo_delimitado = extension in {
            ".csv",
            ".txt",
            ".tsv"
        }

        configuracion_detectada = None

        if es_archivo_delimitado:
            cache_deteccion = st.session_state[
                "configuraciones_csv_detectadas"
            ]

            if identificador_archivo not in cache_deteccion:
                cache_deteccion[identificador_archivo] = (
                    detectar_configuracion_csv(
                        contenido,
                        extension
                    )
                )

            configuracion_detectada = cache_deteccion[
                identificador_archivo
            ]

            nombres_separadores = {
                ",": "coma (,)",
                ";": "punto y coma (;)",
                "\t": "tabulación",
                "|": "barra vertical (|)"
            }
            nombres_codificaciones = {
                "utf-8-sig": "UTF-8-SIG",
                "utf-8": "UTF-8",
                "cp1252": "CP1252",
                "latin-1": "Latin-1"
            }

            st.caption(
                "Separador: "
                f"{nombres_separadores[configuracion_detectada['separador']]}"
                " · Decimal: "
                f"{configuracion_detectada['decimal']}"
                " · Codificación: "
                f"{nombres_codificaciones[configuracion_detectada['codificacion']]}"
            )

            advertencias_deteccion = []

            if not configuracion_detectada["separador_confiable"]:
                advertencias_deteccion.append(
                    "el separador de columnas"
                )

            if not configuracion_detectada["decimal_confiable"]:
                advertencias_deteccion.append(
                    "el separador decimal (se usará punto)"
                )

            if not configuracion_detectada["codificacion_confiable"]:
                advertencias_deteccion.append(
                    "la codificación"
                )

            if advertencias_deteccion:
                st.warning(
                    "La detección no fue concluyente para "
                    + ", ".join(advertencias_deteccion)
                    + ". Revisa y corrige estos valores en "
                    "Configuración avanzada si es necesario."
                )

        with st.expander(
            (
                "Configuración avanzada"
                if es_archivo_delimitado
                else "Configuración del archivo"
            ),
            expanded=not es_archivo_delimitado
        ):

            columna_encabezado = None
            columna_omitidas = None
            columna_limite = None

            # Configuración CSV, TXT y TSV
            if es_archivo_delimitado:

                separadores = {
                    "Coma (,)": ",",
                    "Punto y coma (;)": ";",
                    "Tabulación": "\t",
                    "Barra vertical (|)": "|"
                }

                separadores_opciones = list(
                    separadores.values()
                )

                col_separador, col_decimal, col_codificacion = (
                    st.columns([1.4, 0.8, 1])
                )

                with col_separador:
                    separador = st.selectbox(
                        "Separador de columnas",
                        separadores_opciones,
                        index=separadores_opciones.index(
                            configuracion_detectada["separador"]
                        ),
                        format_func=lambda valor: next(
                            nombre
                            for nombre, separador_opcion
                            in separadores.items()
                            if separador_opcion == valor
                        ),
                        key=(
                            "csv_separador_"
                            f"{identificador_archivo}"
                        )
                    )

                decimales = [".", ","]
                with col_decimal:
                    decimal = st.selectbox(
                        "Decimal",
                        decimales,
                        index=decimales.index(
                            configuracion_detectada["decimal"]
                        ),
                        key=(
                            "csv_decimal_"
                            f"{identificador_archivo}"
                        )
                    )

                codificaciones = [
                    "utf-8-sig",
                    "utf-8",
                    "cp1252",
                    "latin-1"
                ]
                with col_codificacion:
                    codificacion = st.selectbox(
                        "Codificación",
                        codificaciones,
                        index=codificaciones.index(
                            configuracion_detectada["codificacion"]
                        ),
                        format_func=lambda valor: nombres_codificaciones[
                            valor
                        ],
                        key=(
                            "csv_codificacion_"
                            f"{identificador_archivo}"
                        )
                    )

                valores_vacios_texto = st.text_input(
                    "Valores considerados vacíos",
                    value="(vacío),NA,N/A,null,NULL,NaN",
                    help=(
                        "Separa los valores utilizando comas. Usa "
                        "(vacío) para representar campos vacíos."
                    ),
                    key=(
                        "csv_vacios_"
                        f"{identificador_archivo}"
                    )
                )

                valores_vacios = interpretar_valores_vacios(
                    valores_vacios_texto
                )

                configuracion.update(
                    {
                        "separador": separador,
                        "decimal": decimal,
                        "codificacion": codificacion,
                        "valores_vacios": valores_vacios,
                    }
                )

                (
                    columna_encabezado,
                    columna_omitidas,
                    columna_limite
                ) = st.columns([1.7, 1, 1.2])

            # Configuración Excel
            elif extension in {
                ".xlsx",
                ".xls",
                ".xlsm",
                ".xlsb",
                ".ods"
            }:

                (
                    columna_hoja,
                    columna_encabezado,
                    columna_omitidas,
                    columna_limite
                ) = st.columns([1.3, 1.7, 1, 1.2])

                try:
                    hojas = obtener_hojas_excel(contenido)

                    with columna_hoja:
                        hoja = st.selectbox(
                            "Hoja",
                            hojas
                        )

                    configuracion["hoja"] = hoja

                except Exception as error:
                    st.error(
                        f"No fue posible obtener las hojas: {error}"
                    )
                    configuracion["hoja"] = 0

            # Configuración JSON
            elif extension in {
                ".json",
                ".jsonl",
                ".ndjson"
            }:

                codificacion = st.selectbox(
                    "Codificación JSON",
                    [
                        "utf-8",
                        "utf-8-sig",
                        "latin-1",
                        "cp1252"
                    ]
                )

                json_lines_default = extension in {
                    ".jsonl",
                    ".ndjson"
                }

                json_lines = st.checkbox(
                    "El archivo utiliza JSON Lines",
                    value=json_lines_default,
                    help=(
                        "Actívalo cuando cada línea del archivo "
                        "contenga un registro JSON independiente."
                    )
                )

                aplanar_json = st.checkbox(
                    "Aplanar estructuras anidadas",
                    value=True
                )

                raiz_json = "__documento_completo__"

                if not json_lines:
                    try:
                        raices = obtener_raices_json(
                            contenido,
                            codificacion
                        )

                        opciones_raiz = [
                            "__documento_completo__"
                        ] + raices

                        raiz_json = st.selectbox(
                            "Ubicación de los registros",
                            opciones_raiz,
                            format_func=lambda valor: (
                                "Documento completo"
                                if valor
                                == "__documento_completo__"
                                else valor
                            )
                        )

                    except Exception as error:
                        st.warning(
                            "No fue posible detectar automáticamente "
                            f"la estructura del JSON: {error}"
                        )

                configuracion.update(
                    {
                        "codificacion": codificacion,
                        "json_lines": json_lines,
                        "aplanar_json": aplanar_json,
                        "raiz_json": raiz_json,
                    }
                )

            # Encabezados para archivos tabulares
            if extension in {
                ".csv",
                ".txt",
                ".tsv",
                ".xlsx",
                ".xls",
                ".xlsm",
                ".xlsb",
                ".ods"
            }:

                with columna_encabezado:
                    opcion_encabezado = st.selectbox(
                        "Encabezados",
                        [
                            "La primera fila contiene los nombres",
                            "El archivo no tiene encabezados"
                        ]
                    )

                configuracion["encabezado"] = (
                    0
                    if opcion_encabezado
                    == "La primera fila contiene los nombres"
                    else None
                )

                with columna_omitidas:
                    configuracion["filas_omitidas"] = int(
                        st.number_input(
                            "Filas omitidas",
                            min_value=0,
                            value=0,
                            step=1
                        )
                    )

            if columna_limite is not None:
                with columna_limite:
                    limitar_filas = st.checkbox(
                        "Limitar filas",
                        value=False,
                        help=(
                            "Puede ser útil para probar archivos grandes."
                        )
                    )

                    if limitar_filas:
                        configuracion["limite_filas"] = int(
                            st.number_input(
                                "Máximo",
                                min_value=100,
                                value=10000,
                                step=1000
                            )
                        )
            else:
                limitar_filas = st.checkbox(
                    "Importar solamente una cantidad limitada de filas",
                    value=False,
                    help=(
                        "Puede ser útil para probar archivos muy grandes."
                    )
                )

                if limitar_filas:
                    configuracion["limite_filas"] = int(
                        st.number_input(
                            "Cantidad máxima de filas",
                            min_value=100,
                            value=10000,
                            step=1000
                        )
                    )

        # -----------------------------------------
        # LEER ARCHIVO
        # -----------------------------------------

        boton_leer = st.button(
            "Leer archivo y generar vista previa",
            type="primary",
            width="content"
        )

        if boton_leer:

            try:
                with st.spinner(
                    "Leyendo y validando el archivo..."
                ):
                    configuracion_json = json.dumps(
                        configuracion,
                        sort_keys=True
                    )

                    datos_temporales = leer_archivo(
                        contenido,
                        archivo_subido.name,
                        configuracion_json
                    )

                    if datos_temporales.empty:
                        st.warning(
                            "El archivo fue leído, pero no contiene registros."
                        )
                    else:
                        st.session_state.importacion_temporal = (
                            datos_temporales
                        )

                        st.success(
                            "Archivo leído correctamente. "
                            "Revisa la información antes de confirmar."
                        )

            except ImportError as error:
                st.error(
                    "Falta instalar una dependencia necesaria "
                    f"para leer este formato: {error}"
                )

            except UnicodeDecodeError:
                st.error(
                    "No fue posible interpretar la codificación. "
                    "Prueba con Latin-1 o CP1252."
                )

            except Exception as error:
                st.error(
                    f"No fue posible leer el archivo: {error}"
                )

        # -----------------------------------------
        # REVISIÓN Y PREPARACIÓN
        # -----------------------------------------

        datos_temporales = (
            st.session_state.importacion_temporal
        )

        if datos_temporales is not None:

            st.divider()
            titulo_seccion("Revisar los datos", numero=3)

            filas = datos_temporales.shape[0]
            columnas = datos_temporales.shape[1]
            vacios = int(
                datos_temporales.isna().sum().sum()
            )
            duplicados = int(
                datos_temporales.duplicated().sum()
            )

            numericas = datos_temporales.select_dtypes(
                include="number"
            )

            infinitos = (
                int(np.isinf(numericas).sum().sum())
                if not numericas.empty
                else 0
            )

            st.caption(
                f"{filas:,} filas · {columnas:,} columnas · "
                f"{vacios:,} vacíos · {duplicados:,} duplicados"
            )

            # Validación inicial
            if vacios == 0 and duplicados == 0 and infinitos == 0:
                st.caption(
                    "Validación inicial sin problemas relevantes."
                )
            else:
                mensajes = []

                if vacios > 0:
                    mensajes.append(
                        f"{vacios:,} celdas vacías"
                    )

                if duplicados > 0:
                    mensajes.append(
                        f"{duplicados:,} filas duplicadas"
                    )

                if infinitos > 0:
                    mensajes.append(
                        f"{infinitos:,} valores infinitos"
                    )

                st.warning(
                    "Se detectaron: " + ", ".join(mensajes) + "."
                )

            detalle_vista, control_vista = st.columns(
                [2, 1],
                vertical_alignment="bottom"
            )

            with detalle_vista:
                st.caption("Vista previa del archivo")

            with control_vista:
                filas_vista = st.slider(
                    "Filas visibles",
                    min_value=5,
                    max_value=100,
                    value=20,
                    step=5
                )

            st.dataframe(
                datos_temporales.head(filas_vista),
                width="stretch",
                hide_index=True
            )

            # Tipos de datos
            with st.expander(
                "Validación detallada de columnas",
                expanded=False
            ):
                resumen_columnas = pd.DataFrame(
                    {
                        "Columna": [
                            str(columna)
                            for columna
                            in datos_temporales.columns
                        ],
                        "Tipo detectado": [
                            str(tipo)
                            for tipo
                            in datos_temporales.dtypes
                        ],
                        "Datos no vacíos": [
                            int(
                                datos_temporales[
                                    columna
                                ].notna().sum()
                            )
                            for columna
                            in datos_temporales.columns
                        ],
                        "Datos vacíos": [
                            int(
                                datos_temporales[
                                    columna
                                ].isna().sum()
                            )
                            for columna
                            in datos_temporales.columns
                        ],
                    }
                )

                st.dataframe(
                    resumen_columnas,
                    width="stretch",
                    hide_index=True
                )

            # -------------------------------------
            # PREPARACIÓN
            # -------------------------------------

            titulo_seccion("Preparar la importación", numero=4)

            columnas_disponibles = list(
                datos_temporales.columns
            )

            columnas_seleccionadas = st.multiselect(
                "Columnas que deseas importar",
                options=columnas_disponibles,
                default=columnas_disponibles
            )

            opciones_tiempo = [
                "No definir columna temporal"
            ] + columnas_disponibles

            columna_tiempo_seleccionada = st.selectbox(
                "Columna de fecha y hora",
                opciones_tiempo
            )

            columna_tiempo = (
                None
                if columna_tiempo_seleccionada
                == "No definir columna temporal"
                else columna_tiempo_seleccionada
            )

            convertir_fecha = False
            dia_primero = True
            ordenar_tiempo = False

            if columna_tiempo:

                convertir_fecha = st.checkbox(
                    "Convertir esta columna a fecha y hora",
                    value=True
                )

                dia_primero = st.checkbox(
                    "La fecha utiliza formato día/mes/año",
                    value=True
                )

                ordenar_tiempo = st.checkbox(
                    "Ordenar los registros cronológicamente",
                    value=True
                )

            opcion1, opcion2 = st.columns(2)

            with opcion1:

                limpiar_columnas = st.checkbox(
                    "Limpiar nombres de columnas",
                    value=True
                )

                eliminar_filas_vacias = st.checkbox(
                    "Eliminar filas completamente vacías",
                    value=True
                )

            with opcion2:

                eliminar_columnas_vacias = st.checkbox(
                    "Eliminar columnas completamente vacías",
                    value=True
                )

                eliminar_duplicados = st.checkbox(
                    "Eliminar filas duplicadas",
                    value=False
                )

            if not columnas_seleccionadas:
                st.error(
                    "Debes seleccionar al menos una columna."
                )

            else:

                try:
                    datos_preparados = preparar_dataframe(
                        dataframe=datos_temporales,
                        columnas_seleccionadas=columnas_seleccionadas,
                        columna_tiempo=columna_tiempo,
                        convertir_fecha=convertir_fecha,
                        dia_primero=dia_primero,
                        ordenar_tiempo=ordenar_tiempo,
                        eliminar_filas_vacias=eliminar_filas_vacias,
                        eliminar_columnas_vacias=eliminar_columnas_vacias,
                        eliminar_duplicados=eliminar_duplicados,
                        limpiar_columnas=limpiar_columnas
                    )

                    st.caption("Resultado de la preparación")

                    resumen_compacto(
                        [
                            {
                                "etiqueta": "Filas finales",
                                "valor": f"{datos_preparados.shape[0]:,}"
                            },
                            {
                                "etiqueta": "Columnas finales",
                                "valor": datos_preparados.shape[1]
                            },
                            {
                                "etiqueta": "Datos vacíos finales",
                                "valor": (
                                    f"{int(datos_preparados.isna().sum().sum()):,}"
                                )
                            }
                        ]
                    )

                    with st.expander(
                        "Vista previa de los datos preparados"
                    ):
                        st.dataframe(
                            datos_preparados.head(20),
                            width="stretch",
                            hide_index=True
                        )

                    st.divider()
                    titulo_seccion("Confirmar importación", numero=5)

                    st.caption(
                        "Los datos originales se conservarán; las "
                        "transformaciones se aplicarán sobre una copia."
                    )

                    confirmar = st.button(
                        "Confirmar importación",
                        type="primary",
                        width="content"
                    )

                    if confirmar:

                        st.session_state.datos_originales = (
                            datos_temporales.copy(deep=True)
                        )

                        st.session_state.datos = (
                            datos_preparados.copy(deep=True)
                        )

                        st.session_state.nombre_archivo = (
                            archivo_subido.name
                        )

                        st.session_state.metadatos_importacion = {
                            "nombre_archivo": archivo_subido.name,
                            "formato": extension.replace(
                                ".",
                                ""
                            ).upper(),
                            "tamano_bytes": archivo_subido.size,
                            "fecha_importacion": datetime.now().strftime(
                                "%d-%m-%Y %H:%M:%S"
                            ),
                            "filas_originales": (
                                datos_temporales.shape[0]
                            ),
                            "columnas_originales": (
                                datos_temporales.shape[1]
                            ),
                            "filas_importadas": (
                                datos_preparados.shape[0]
                            ),
                            "columnas_importadas": (
                                datos_preparados.shape[1]
                            ),
                            "columna_tiempo": columna_tiempo,
                            "configuracion_lectura": configuracion,
                        }

                        st.session_state[
                            "mostrar_importacion_confirmada"
                        ] = True

                        st.rerun()

                except Exception as error:
                    st.error(
                        "No fue posible preparar los datos: "
                        f"{error}"
                    )

        # -----------------------------------------
        # DATOS YA ACTIVOS
        # -----------------------------------------

        if st.session_state.datos is not None:

            st.divider()
            titulo_seccion("Datos activos")

            st.success(
                f"Archivo activo: "
                f"{st.session_state.nombre_archivo}"
            )

            enlace1, enlace2 = st.columns(2)

            with enlace1:
                st.page_link(
                    "paginas/asistente_datos.py",
                    label="Consultar al asistente",
                    icon=":material/chat:"
                )

            with enlace2:
                st.page_link(
                    "paginas/tendencias.py",
                    label="Analizar tendencias",
                    icon=":material/monitoring:"
                )


# =================================================
# BASE DE DATOS
# =================================================

with tab_bd:

    titulo_seccion("Conectar una base de datos")

    st.info(
        """
        Esta sección permitirá conectarse posteriormente a
        SQLite, SQL Server, PostgreSQL, MySQL y otras fuentes SQL.
        """
    )

    st.write(
        """
        La conexión incluirá selección de servidor, base de datos,
        tabla, consulta y vista previa antes de confirmar.
        """
    )


# =================================================
# API O URL
# =================================================

with tab_api:

    titulo_seccion("Conectar una API o URL")

    st.info(
        """
        Esta sección permitirá importar información desde una API
        REST o desde la URL de un archivo.
        """
    )

    st.write(
        """
        Incluirá configuración de método, parámetros, encabezados,
        autenticación y revisión de la respuesta recibida.
        """
    )


# -------------------------------------------------
# PIE DE PÁGINA
# -------------------------------------------------

pie_pagina()
