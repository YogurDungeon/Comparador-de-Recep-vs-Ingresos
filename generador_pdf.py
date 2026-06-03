"""
Generador de informe PDF para comparador de medicamentos usando reportlab
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os


def _crear_estilos():
    """Crea y devuelve los estilos de parrafo necesarios"""
    estilos = {}
    estilos['titulo_seccion'] = ParagraphStyle(
        'TituloSeccion',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    estilos['subtitulo'] = ParagraphStyle(
        'Subtitulo',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    estilos['normal'] = ParagraphStyle(
        'NormalCustom',
        fontSize=10,
        leading=12,
        textColor=colors.black
    )
    estilos['observaciones'] = ParagraphStyle(
        'Observaciones',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#333333'),
        borderColor=colors.HexColor('#bdc3c7'),
        borderWidth=1,
        borderPadding=8,
        leftIndent=4,
        rightIndent=4
    )
    estilos['celda_wrap'] = ParagraphStyle(
        'CeldaWrap',
        fontSize=9,
        leading=11,
        wordWrap='CJK'
    )
    estilos['encabezado_wrap'] = ParagraphStyle(
        'EncabezadoWrap',
        fontSize=10,
        leading=12,
        wordWrap='CJK',
        textColor=colors.whitesmoke
    )
    return estilos


def _crear_tabla_encabezados(headers, colWidths=None):
    """Crea una tabla de reportlab con estilo profesional para encabezados"""
    data = [headers]
    table = Table(data, colWidths=colWidths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
    ]))
    return table


def _aplicar_estilo_filas(tabla, tipo='coincidencias'):
    """Aplica estilos de filas alternadas segun el tipo de seccion"""
    estilos = []
    # Obtener numero de filas de datos (sin encabezado)
    num_filas = len(tabla._cellvalues) - 1  # -1 por el encabezado
    
    if tipo == 'coincidencias':
        color_fondo = colors.HexColor('#eafaf1')  # verde claro
    elif tipo == 'discrepancias':
        color_fondo = colors.HexColor('#fef9e7')  # amarillo claro
    elif tipo in ('faltantes_ingresos', 'faltantes_recepcion'):
        color_fondo = colors.HexColor('#fdedec')  # rojo claro
    else:
        color_fondo = colors.HexColor('#f8f9f9')  # gris muy claro
    
    for i in range(1, num_filas + 1):
        if i % 2 == 0:
            estilos.append(('BACKGROUND', (0, i), (-1, i), color_fondo))
    
    # Aplicar estilos
    for estilo in estilos:
        tabla._style.add(*estilo)
    
    return tabla


def _datos_a_tabla(datos_list, headers, colWidths=None, tipo='coincidencias'):
    """
    Convierte una lista de diccionarios en una tabla de reportlab.
    
    Args:
        datos_list: lista de diccionarios
        headers: lista de tuplas (clave_diccionario, titulo_visible)
        colWidths: lista de anchos de columna
        tipo: tipo de seccion para coloreo alternado
    """
    if not datos_list:
        return Paragraph("<i>No hay datos para esta seccion.</i>", _crear_estilos()['normal']), None
    
    # Construir datos de la tabla
    data = []
    # Encabezados visibles - usar Paragraph para wrap automático
    titulos = []
    estilos = _crear_estilos()
    for j, (_, titulo) in enumerate(headers):
        ancho_max = colWidths[j] if colWidths and j < len(colWidths) else 100
        titulos.append(Paragraph(titulo, estilos['encabezado_wrap']))
    data.append(titulos)
    
    # Filas de datos
    estilos = _crear_estilos()
    for item in datos_list:
        fila = []
        for j, (key, _) in enumerate(headers):
            val = item.get(key, '')
            # Formatear numeros
            if isinstance(val, (int, float)):
                if key in ('diferencia',):
                    # Mostrar con signo
                    val_str = f"{val:+d}" if isinstance(val, int) else f"{val:+.2f}"
                else:
                    val_str = str(val)
                fila.append(val_str)
            else:
                val_str = str(val) if val is not None else ''
                ancho_max = colWidths[j] if colWidths and j < len(colWidths) else 100
                fila.append(Paragraph(val_str, estilos['celda_wrap']))
        data.append(fila)
    
    table = Table(data, colWidths=colWidths, repeatRows=1)
    
    # Estilo base
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
    ]
    
    # Color de fondo alternado segun tipo
    if tipo == 'coincidencias':
        color_fondo = colors.HexColor('#eafaf1')
    elif tipo == 'discrepancias':
        color_fondo = colors.HexColor('#fef9e7')
    elif tipo in ('faltantes_ingresos', 'faltantes_recepcion'):
        color_fondo = colors.HexColor('#fdedec')
    else:
        color_fondo = colors.HexColor('#f8f9f9')
    
    num_filas = len(data) - 1  # sin encabezado
    for i in range(1, num_filas + 1):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), color_fondo))
    
    table.setStyle(TableStyle(style_commands))
    
    return table, len(data) - 1


def generar_informe_pdf(ruta_salida: str, comparador, observaciones: str = ""):
    """
    Genera un informe PDF completo con los resultados de la comparacion.
    
    Args:
        ruta_salida: ruta completa donde guardar el PDF
        comparador: instancia de ComparadorMedicamentos (con resultados)
        observaciones: texto libre de observaciones del usuario
    """
    if comparador is None or not comparador.resultados:
        return False, "No hay resultados de comparacion para generar el informe."
    
    try:
        doc = SimpleDocTemplate(
            ruta_salida,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        estilos = _crear_estilos()
        elementos = []
        
        # ==========================================
        # TITULO PRINCIPAL
        # ==========================================
        titulo_style = ParagraphStyle(
            'TituloPrincipal',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        elementos.append(Paragraph("INFORME DE COMPARACION DE MEDICAMENTOS", titulo_style))
        
        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        elementos.append(Paragraph(f"Fecha de generacion: {fecha_str}", estilos['subtitulo']))
        elementos.append(Spacer(1, 12))
        
        # ==========================================
        # SECCION 1: RESUMEN EJECUTIVO
        # ==========================================
        elementos.append(Paragraph("1. RESUMEN EJECUTIVO", estilos['titulo_seccion']))
        
        # Tabla de resumen
        resumen = comparador.obtener_resumen()
        data_resumen = [
            ['Concepto', 'Cantidad'],
            ['Coincidencias Totales', str(resumen.get('coincidencias', 0))],
            ['Discrepancias de Cantidad', str(resumen.get('discrepancias_cantidad', 0))],
            ['Faltantes en Ingresos', str(resumen.get('faltantes_en_ingresos', 0))],
            ['Faltantes en Recepcion', str(resumen.get('faltantes_en_recepcion', 0))],
        ]
        
        tabla_resumen = Table(data_resumen, colWidths=[8*cm, 4*cm])
        tabla_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ]))
        elementos.append(tabla_resumen)
        elementos.append(Spacer(1, 16))
        
        # ==========================================
        # SECCION 2: COINCIDENCIAS
        # ==========================================
        elementos.append(Paragraph("2. DETALLE DE COINCIDENCIAS", estilos['titulo_seccion']))
        
        coincidencias = comparador.resultados.get('coincidencias', [])
        if coincidencias:
            headers_coin = [
                ('medicamento_recepcion', 'Medicamento Recepcion'),
                ('medicamento_ingresos', 'Medicamento Ingresos'),
                ('cantidad', 'Cantidad'),
            ]
            tabla, _ = _datos_a_tabla(coincidencias, headers_coin, 
                                      colWidths=[7*cm, 7*cm, 3*cm], 
                                      tipo='coincidencias')
            elementos.append(tabla)
        else:
            elementos.append(Paragraph("<i>No hay coincidencias para mostrar.</i>", estilos['normal']))
        
        elementos.append(Spacer(1, 16))
        
        # ==========================================
        # SECCION 3: DISCREPANCIAS
        # ==========================================
        elementos.append(Paragraph("3. DETALLE DE DISCREPANCIAS", estilos['titulo_seccion']))
        
        discrepancias = comparador.resultados.get('discrepancias_cantidad', [])
        if discrepancias:
            headers_disc = [
                ('medicamento_recepcion', 'Medicamento Recepcion'),
                ('medicamento_ingresos', 'Medicamento Ingresos'),
                ('cantidad_recepcion', 'Cant. Recepcion'),
                ('cantidad_ingresos', 'Cant. Ingresos'),
                ('diferencia', 'Diferencia'),
            ]
            tabla, _ = _datos_a_tabla(discrepancias, headers_disc,
                                      colWidths=[6*cm, 6*cm, 2.5*cm, 2.5*cm, 2*cm],
                                      tipo='discrepancias')
            elementos.append(tabla)
        else:
            elementos.append(Paragraph("<i>No hay discrepancias para mostrar.</i>", estilos['normal']))
        
        elementos.append(Spacer(1, 16))
        
        # ==========================================
        # SECCION 4: FALTANTES EN INGRESOS
        # ==========================================
        elementos.append(Paragraph("4. FALTANTES EN INGRESOS", estilos['titulo_seccion']))
        elementos.append(Paragraph(
            "Medicamentos que se recepcionaron pero NO se ingresaron al sistema:",
            estilos['subtitulo']
        ))
        
        faltantes_ing = comparador.resultados.get('faltantes_en_ingresos', [])
        if faltantes_ing:
            headers_falt_ing = [
                ('medicamento', 'Medicamento'),
                ('cantidad', 'Cantidad'),
                ('medicamento_origen', 'Medicamento Origen'),
            ]
            tabla, _ = _datos_a_tabla(faltantes_ing, headers_falt_ing,
                                      colWidths=[6*cm, 2.5*cm, 7.5*cm],
                                      tipo='faltantes_ingresos')
            elementos.append(tabla)
        else:
            elementos.append(Paragraph("<i>No hay faltantes en ingresos.</i>", estilos['normal']))
        
        elementos.append(Spacer(1, 16))
        
        # ==========================================
        # SECCION 5: FALTANTES EN RECEPCION
        # ==========================================
        elementos.append(Paragraph("5. FALTANTES EN RECEPCION", estilos['titulo_seccion']))
        elemento = Paragraph(
            "Medicamentos que estan cargados en el sistema pero NO aparecen en recepcion:",
            estilos['subtitulo']
        )
        elementos.append(elemento)
        
        faltantes_rec = comparador.resultados.get('faltantes_en_recepcion', [])
        if faltantes_rec:
            headers_falt_rec = [
                ('medicamento', 'Medicamento'),
                ('cantidad', 'Cantidad'),
                ('medicamento_origen', 'Medicamento Origen'),
            ]
            tabla, _ = _datos_a_tabla(faltantes_rec, headers_falt_rec,
                                      colWidths=[6*cm, 2.5*cm, 7.5*cm],
                                      tipo='faltantes_recepcion')
            elementos.append(tabla)
        else:
            elementos.append(Paragraph("<i>No hay faltantes en recepcion.</i>", estilos['normal']))
        
        elementos.append(Spacer(1, 16))
        
        # ==========================================
        # SECCION 6: OBSERVACIONES
        # ==========================================
        elementos.append(Paragraph("6. OBSERVACIONES", estilos['titulo_seccion']))
        
        if observaciones and observaciones.strip():
            elementos.append(Paragraph(observaciones.strip(), estilos['observaciones']))
        else:
            elementos.append(Paragraph("<i>Sin observaciones.</i>", estilos['normal']))
        
        # ==========================================
        # GENERAR PDF
        # ==========================================
        doc.build(elementos)
        
        return True, f"Informe PDF generado exitosamente en: {ruta_salida}"
        
    except Exception as e:
        return False, f"Error al generar el PDF: {str(e)}"
