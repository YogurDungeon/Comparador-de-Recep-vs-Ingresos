"""
Archivo de configuración para la aplicación
"""

# Configuración de interfaz gráfica
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800
WINDOW_TITLE = "Comparador de Medicamentos - Recepción vs Ingresos"

# Configuración de matching
FUZZY_THRESHOLD_MIN = 60
FUZZY_THRESHOLD_MAX = 100
FUZZY_THRESHOLD_DEFAULT = 80

# Configuración de columnas esperadas
COLUMNAS_RECEPCION = ['Medicamento', 'Cantidad']
COLUMNAS_INGRESOS = ['Nombre del Medicamento', 'Cantidad']

# Configuración de interfaz
FONT_RESUMEN = ("Courier", 10)
FONT_DETALLES = ("Courier", 9)
FONT_NORMAL = ("Arial", 10)

# Colores
COLOR_EXITO = "green"
COLOR_ERROR = "red"
COLOR_ADVERTENCIA = "orange"

# Rutas
RUTA_EJEMPLOS = "./ejemplo_*.xlsx"

# Formato de exportación
EXPORTAR_ENCODING = 'utf-8'
