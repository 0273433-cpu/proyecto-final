import streamlit as st
from lxml import etree
from dataclasses import dataclass, asdict
import pandas as pd
from io import BytesIO

# ReportLab para PDF con tablas bonitas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


# ───────────────────────────
# MODELO
# ───────────────────────────
@dataclass
class Factura:
    nombre: str
    rfc_emisor: str
    nombre_emisor: str
    concepto: tuple          # puede traer varios conceptos
    total: float
    fecha: str               # string ISO del CFDI
    impuestos_trasladados: float
    impuestos_retenidos: float
    uso_cfdi: str

    def __eq__(self, other):
        return (
            isinstance(other, Factura)
            and self.nombre == other.nombre
            and self.total == other.total
        )

    def __hash__(self):
        return hash((self.nombre, self.total))


# ───────────────────────────
# FUNCIÓN: GENERAR PDF CON TABLAS
# ───────────────────────────
def generar_pdf(resumenes: dict) -> bytes:
    """
    Construye un PDF con tablas usando reportlab.platypus.
    'resumenes' = {"Título sección": DataFrame}
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()
    style_title = styles["Heading1"]
    style_section = styles["Heading2"]
    style_normal = styles["Normal"]

    elements = []

    # Título principal
    elements.append(Paragraph("Reporte de facturas", style_title))
    elements.append(Spacer(1, 12))

    for titulo, df in resumenes.items():
        # Título de sección
        elements.append(Paragraph(titulo, style_section))
        elements.append(Spacer(1, 6))

        if df is None or df.empty:
            elements.append(Paragraph("Sin datos para mostrar.", style_normal))
            elements.append(Spacer(1, 12))
            continue

        # Convertir DataFrame a lista de listas (para Table)
        table_data = [list(df.columns)]
        for _, row in df.iterrows():
            table_data.append([str(row[col]) for col in df.columns])

        # Crear tabla
        tabla = Table(table_data, repeatRows=1)

        # Estilo de la tabla
        tabla.setStyle(
            TableStyle(
                [
                    # Encabezado
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

                    # Cuerpo
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 1), (-1, -1), "LEFT"),

                    # Líneas de tabla
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),

                    # Relleno de celdas
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),

                    # Fondo alternado para filas de datos
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ]
            )
        )

        elements.append(tabla)
        elements.append(Spacer(1, 16))

    # Construir documento
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ───────────────────────────
# CONFIG STREAMLIT
# ───────────────────────────
st.set_page_config(
    page_title="Mi App",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("Reporte de gastos")
uploaded_files = st.sidebar.file_uploader(
    "Sube facturas XML",
    type="xml",
    accept_multiple_files=True,
)

filtro_rfc = st.sidebar.text_input("Filtrar por RFC emisor:")

st.title("Reporte de facturas")

if "facturas" not in st.session_state:
    st.session_state.facturas = []


# ───────────────────────────
# LECTURA DE XML
# ───────────────────────────
if uploaded_files:
    lista_facturas = []

    for uploaded_file in uploaded_files:
        xml_bytes = uploaded_file.read()

        try:
            tree = etree.fromstring(xml_bytes)
            ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}

            total = tree.xpath("//cfdi:Comprobante/@Total", namespaces=ns)
            rfc_emisor = tree.xpath(
                "//cfdi:Comprobante/cfdi:Emisor/@Rfc", namespaces=ns
            )
            nombre_emisor = tree.xpath(
                "//cfdi:Comprobante/cfdi:Emisor/@Nombre", namespaces=ns
            )
            fecha = tree.xpath("//cfdi:Comprobante/@Fecha", namespaces=ns)
            concepto = tree.xpath(
                "//cfdi:Comprobante/cfdi:Conceptos/cfdi:Concepto/@Descripcion",
                namespaces=ns,
            )

            # impuestos a nivel comprobante
            imp_tras = tree.xpath(
                "//cfdi:Comprobante/cfdi:Impuestos/@TotalImpuestosTrasladados",
                namespaces=ns,
            )
            imp_ret = tree.xpath(
                "//cfdi:Comprobante/cfdi:Impuestos/@TotalImpuestosRetenidos",
                namespaces=ns,
            )

            uso_cfdi = tree.xpath(
                "//cfdi:Comprobante/cfdi:Receptor/@UsoCFDI",
                namespaces=ns,
            )

            st.write(f"Archivo leído correctamente: {uploaded_file.name}")

            lista_facturas.append(
                Factura(
                    nombre=uploaded_file.name,
                    rfc_emisor=rfc_emisor[0] if rfc_emisor else "",
                    nombre_emisor=nombre_emisor[0] if nombre_emisor else "",
                    concepto=tuple(concepto),
                    total=float(total[0]) if total else 0.0,
                    fecha=fecha[0] if fecha else "",
                    impuestos_trasladados=float(imp_tras[0]) if imp_tras else 0.0,
                    impuestos_retenidos=float(imp_ret[0]) if imp_ret else 0.0,
                    uso_cfdi=uso_cfdi[0] if uso_cfdi else "",
                )
            )

        except Exception as e:
            st.error(f"Error al leer {uploaded_file.name}: {e}")

    # quitar duplicados
    st.session_state.facturas = list(set(lista_facturas))

else:
    st.write("Selecciona tus facturas XML.")
    st.session_state.facturas = []


# ───────────────────────────
# DATAFRAME BASE
# ───────────────────────────
if len(st.session_state.facturas) > 0:
    df = pd.DataFrame([asdict(f) for f in st.session_state.facturas])

    # convertir fecha y crear columnas de año y mes
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month

    # impuestos efectivos (puedes ajustar la fórmula si quieres otro criterio)
    df["impuestos"] = df["impuestos_trasladados"] - df["impuestos_retenidos"]

    # filtro por RFC
    if filtro_rfc:
        df = df[df["rfc_emisor"].str.contains(filtro_rfc, case=False, na=False)]

    st.subheader("Facturas cargadas")
    st.dataframe(df)

    # ───────────────────────
    # CÁLCULOS SOLICITADOS
    # ───────────────────────
    st.subheader("Calcular totales por año")
    totales_anio = (
        df.groupby("anio", as_index=False)["total"].sum().rename(columns={"total": "total_anual"})
    )
    st.dataframe(totales_anio)

    st.subheader("Calcular totales por mes")
    totales_mes = (
        df.groupby(["anio", "mes"], as_index=False)["total"]
        .sum()
        .rename(columns={"total": "total_mensual"})
    )
    st.dataframe(totales_mes)

    st.subheader("Calcular impuestos pagados por año")
    impuestos_anio = (
        df.groupby("anio", as_index=False)["impuestos"]
        .sum()
        .rename(columns={"impuestos": "impuestos_anual"})
    )
    st.dataframe(impuestos_anio)

    st.subheader("Calcular impuestos pagados por mes")
    impuestos_mes = (
        df.groupby(["anio", "mes"], as_index=False)["impuestos"]
        .sum()
        .rename(columns={"impuestos": "impuestos_mensual"})
    )
    st.dataframe(impuestos_mes)

    st.subheader("Totales e impuestos por año y mes por RFC emisor")
    resumen_rfc = (
        df.groupby(["anio", "mes", "rfc_emisor"], as_index=False)[["total", "impuestos"]]
        .sum()
        .rename(columns={"total": "total", "impuestos": "impuestos"})
    )
    st.dataframe(resumen_rfc)

    st.subheader("Totales e impuestos por año y mes por concepto")
    resumen_concepto = (
        df.groupby(["anio", "mes", "concepto"], as_index=False)[["total", "impuestos"]]
        .sum()
    )
    st.dataframe(resumen_concepto)

    st.subheader("Totales e impuestos por año y mes por Uso de CFDI")
    resumen_uso_cfdi = (
        df.groupby(["anio", "mes", "uso_cfdi"], as_index=False)[["total", "impuestos"]]
        .sum()
    )
    st.dataframe(resumen_uso_cfdi)

    # ───────────────────────
    # GRÁFICO DE GASTOS POR MES
    # ───────────────────────
    st.title("Gráfico de gastos por mes")
    totales_mes_chart = totales_mes.copy()
    totales_mes_chart["periodo"] = (
        totales_mes_chart["anio"].astype(str)
        + "-"
        + totales_mes_chart["mes"].astype(str).str.zfill(2)
    )
    totales_mes_chart = totales_mes_chart.set_index("periodo")["total_mensual"]
    st.line_chart(totales_mes_chart)

    # ───────────────────────
    # PDF DE REPORTE (CON TABLAS)
    # ───────────────────────
    resumenes_para_pdf = {
        "Totales por año": totales_anio,
        "Totales por mes": totales_mes,
        "Impuestos por año": impuestos_anio,
        "Impuestos por mes": impuestos_mes,
        "Por RFC emisor (año/mes)": resumen_rfc,
        "Por concepto (año/mes)": resumen_concepto,
        "Por Uso CFDI (año/mes)": resumen_uso_cfdi,
    }

    pdf_bytes = generar_pdf(resumenes_para_pdf)

    st.sidebar.download_button(
        label="Descargar reporte PDF",
        data=pdf_bytes,
        file_name="reporte_facturas.pdf",
        mime="application/pdf",
    )

else:
    st.info("Todavía no hay facturas válidas para mostrar.")