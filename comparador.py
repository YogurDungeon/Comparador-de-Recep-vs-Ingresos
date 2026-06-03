"""
Módulo para comparar archivos de recepción e ingresos de medicamentos
"""

import pandas as pd
from rapidfuzz import fuzz
from typing import Dict, List, Tuple
import os
import json

SINONIMOS = {
    'LAPIZ': 'LAPICERO',
    'X30': 'CX30', 'X10': 'CX10', 'X2': 'CX2', 'X8': 'CX8',
    'X1': 'CX1', 'X28': 'CX28', 'X60': 'CX60', 'X90': 'CX90',
    'X100': 'CX100', 'X20': 'CX20', 'X14': 'CX14', 'X7': 'CX7',
    'X4': 'CX4', 'X3': 'CX3', 'XI': 'CXI',
}


class ComparadorMedicamentos:
    """Clase para comparar medicamentos entre recepción e ingresos"""
    
    def __init__(self, threshold: int = 70):
        """
        Inicializa el comparador
        
        Args:
            threshold: Porcentaje mínimo de similitud para considerar un match (0-100)
        """
        self.threshold = threshold
        self.recepcion_df = None
        self.ingresos_df = None
        self.matches = {}  # medicamento_recepcion -> medicamento_ingresos
        self.equivalencias = {}  # diccionario de equivalencias cargadas (normalizado)
        self.equivalencias_crudas = []  # lista de dicts de equivalencias sin normalizar (para guardar)
        self.modo_matching = 'hibrido'  # 'fuzzy', 'equivalencias' o 'hibrido'
        self.fuzzy_enabled = True  # Controla si se usa fuzzy matching como fallback
        self.rastreo_matching = {}  # para registrar qué método se usó
        self.resultados = {
            'coincidencias': [],
            'discrepancias_cantidad': [],
            'faltantes_en_ingresos': [],
            'faltantes_en_recepcion': [],
            'sugerencias': []  # sugerencias semiautomáticas de coincidencia
        }

        # Caché de normalización
        self._cache_recepcion_norm = {}  # nombre_original -> nombre_normalizado
        self._cache_ingresos_norm = {}   # nombre_original -> nombre_normalizado
    
    def cargar_recepcion(self, ruta: str) -> tuple:
        """
        Carga archivo de recepción (columnas: Medicamento, Cantidad)
        
        Args:
            ruta: Ruta al archivo Excel
            
        Returns:
            tuple: (bool: True si se cargó, str: mensaje de error o vacío)
        """
        try:
            self.recepcion_df = pd.read_excel(ruta)
            # Normalizar nombres de columnas (convertir a string primero)
            self.recepcion_df.columns = [str(col).strip() for col in self.recepcion_df.columns]
            
            # Validar que tenga las columnas requeridas
            columnas_requeridas = ['Medicamento', 'Cantidad']
            columnas_presentes = self.recepcion_df.columns.tolist()
            
            faltantes = [col for col in columnas_requeridas if col not in columnas_presentes]
            if faltantes:
                return False, f"Columnas faltantes: {', '.join(faltantes)}\nColumnas encontradas: {', '.join(columnas_presentes)}"

            # Construir caché de nombres normalizados
            self._cache_recepcion_norm = {}
            for nombre in self.recepcion_df['Medicamento'].unique():
                self._cache_recepcion_norm[nombre] = self._normalizar_nombre(nombre)

            return True, ""
        except FileNotFoundError:
            return False, f"Archivo no encontrado: {ruta}"
        except Exception as e:
            return False, f"Error al cargar archivo: {str(e)}"

    def cargar_ingresos(self, ruta: str) -> tuple:
        """
        Carga archivo de ingresos (debe tener columnas: Nombre del Medicamento, Cantidad)
        
        Args:
            ruta: Ruta al archivo Excel
            
        Returns:
            tuple: (bool: True si se cargó, str: mensaje de error o vacío)
        """
        try:
            self.ingresos_df = pd.read_excel(ruta)
            # Normalizar nombres de columnas (convertir a string primero)
            self.ingresos_df.columns = [str(col).strip() for col in self.ingresos_df.columns]
            
            # Validar que tenga las columnas requeridas
            columnas_requeridas = ['Nombre del Medicamento', 'Cantidad']
            columnas_presentes = self.ingresos_df.columns.tolist()
            
            faltantes = [col for col in columnas_requeridas if col not in columnas_presentes]
            if faltantes:
                return False, f"Columnas faltantes: {', '.join(faltantes)}\nColumnas encontradas: {', '.join(columnas_presentes)}"

            # Construir caché de nombres normalizados
            self._cache_ingresos_norm = {}
            for nombre in self.ingresos_df['Nombre del Medicamento'].unique():
                self._cache_ingresos_norm[nombre] = self._normalizar_nombre(nombre)

            return True, ""
        except FileNotFoundError:
            return False, f"Archivo no encontrado: {ruta}"
        except Exception as e:
            return False, f"Error al cargar archivo: {str(e)}"
    
    def _normalizar_nombre(self, nombre: str) -> str:
        """Normaliza nombres de medicamentos para mejor matching"""
        import re
        import unicodedata
        
        if not isinstance(nombre, str):
            nombre = str(nombre)
            
        # Convertir a mayúsculas
        nombre = nombre.upper()
        
        # Eliminar tildes/acentos
        nombre = "".join(c for c in unicodedata.normalize('NFD', nombre) if unicodedata.category(c) != 'Mn')
        
        # Eliminar símbolos especiales de marca y caracteres corruptos
        for char in ['®', '™', '©', '']:
            nombre = nombre.replace(char, '')
            
        # Reemplazar puntuación no esencial por espacios (paréntesis, guiones, etc.)
        nombre = re.sub(r'[^A-Z0-9\s/%,.]', ' ', nombre)
        
        # Colapsar múltiples espacios en uno solo
        nombre = re.sub(r'\s+', ' ', nombre).strip()
        
        return nombre
    
    def cargar_equivalencias(self, ruta: str) -> tuple:
        """
        Carga un archivo de equivalencias entre medicamentos
        
        Args:
            ruta: Ruta al archivo CSV o Excel con columnas: Medicamento_Recepcion, Nombre_Ingresos
            
        Returns:
            tuple: (bool: True si se cargó, str: mensaje)
        """
        try:
            if not os.path.exists(ruta):
                return False, f"Archivo no encontrado: {ruta}"
            
            # Limpiar equivalencias previas
            self.equivalencias = {}
            self.equivalencias_crudas = []
            
            # Cargar archivo según extensión (Excel o CSV)
            if ruta.lower().endswith(('.xlsx', '.xls')):
                df_equiv = pd.read_excel(ruta)
            else:
                # Cargar CSV con soporte para múltiples codificaciones
                try:
                    df_equiv = pd.read_csv(ruta, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df_equiv = pd.read_csv(ruta, encoding='latin-1')
                    except UnicodeDecodeError:
                        df_equiv = pd.read_csv(ruta, encoding='windows-1252')
            
            # Validar columnas
            if 'Medicamento_Recepcion' not in df_equiv.columns or 'Nombre_Ingresos' not in df_equiv.columns:
                return False, "El archivo debe tener columnas: 'Medicamento_Recepcion' y 'Nombre_Ingresos'"
            
            # Crear diccionario normalizado y lista cruda
            for _, row in df_equiv.iterrows():
                val_recep = str(row['Medicamento_Recepcion']).strip() if not pd.isna(row['Medicamento_Recepcion']) else ""
                val_ing = str(row['Nombre_Ingresos']).strip() if not pd.isna(row['Nombre_Ingresos']) else ""
                
                # Caso especial: delimitación rota (ej. "A,B" en la primera col y NaN en la segunda)
                if (not val_ing or val_ing.lower() == 'nan') and ',' in val_recep:
                    partes = val_recep.split(',', 1)
                    med_recep_raw = partes[0].strip()
                    nombre_ing_raw = partes[1].strip()
                else:
                    med_recep_raw = val_recep
                    nombre_ing_raw = val_ing
                
                # Quitar posibles comillas externas residuales
                if med_recep_raw.startswith('"') and med_recep_raw.endswith('"'):
                    med_recep_raw = med_recep_raw[1:-1].strip()
                if nombre_ing_raw.startswith('"') and nombre_ing_raw.endswith('"'):
                    nombre_ing_raw = nombre_ing_raw[1:-1].strip()
                    
                # Omitir si alguno queda vacío o es nan
                if not med_recep_raw or not nombre_ing_raw or med_recep_raw.lower() == 'nan' or nombre_ing_raw.lower() == 'nan':
                    continue
                
                # Guardar en la lista cruda manteniendo el formato del usuario
                self.equivalencias_crudas.append({
                    'Medicamento_Recepcion': med_recep_raw,
                    'Nombre_Ingresos': nombre_ing_raw
                })
                
                # Guardar en el diccionario normalizado de búsqueda rápida
                med_recep = self._normalizar_nombre(med_recep_raw)
                nombre_ing = self._normalizar_nombre(nombre_ing_raw)
                self.equivalencias[med_recep] = nombre_ing
            
            return True, f"Equivalencias cargadas: {len(self.equivalencias_crudas)} medicamentos"
            
        except Exception as e:
            return False, f"Error al cargar equivalencias: {str(e)}"

    def agregar_equivalencia_manual(self, med_recepcion_raw: str, med_ingresos_raw: str) -> bool:
        """
        Agrega una equivalencia manualmente en caliente
        """
        if not med_recepcion_raw.strip() or not med_ingresos_raw.strip():
            return False
            
        # Limpiar espacios
        rec_raw = med_recepcion_raw.strip()
        ing_raw = med_ingresos_raw.strip()
        
        # Eliminar si ya existe el de recepción en las crudas
        self.equivalencias_crudas = [item for item in self.equivalencias_crudas if item['Medicamento_Recepcion'].upper() != rec_raw.upper()]
        
        # Agregar a crudas
        self.equivalencias_crudas.append({
            'Medicamento_Recepcion': rec_raw,
            'Nombre_Ingresos': ing_raw
        })
        
        # Agregar a normalizadas
        med_recep_norm = self._normalizar_nombre(rec_raw)
        nombre_ing_norm = self._normalizar_nombre(ing_raw)
        self.equivalencias[med_recep_norm] = nombre_ing_norm
        return True

    def eliminar_equivalencia_manual(self, med_recepcion_raw: str) -> bool:
        """
        Elimina una equivalencia en caliente
        """
        rec_raw = med_recepcion_raw.strip()
        
        # Eliminar de crudas
        len_antes = len(self.equivalencias_crudas)
        self.equivalencias_crudas = [item for item in self.equivalencias_crudas if item['Medicamento_Recepcion'].upper() != rec_raw.upper()]
        
        # Eliminar de normalizadas
        med_recep_norm = self._normalizar_nombre(rec_raw)
        if med_recep_norm in self.equivalencias:
            del self.equivalencias[med_recep_norm]
            
        return len(self.equivalencias_crudas) < len_antes

    def guardar_equivalencias(self, ruta: str) -> Tuple[bool, str]:
        """
        Guarda el diccionario actual en un archivo CSV o Excel
        """
        try:
            if not self.equivalencias_crudas:
                return False, "No hay equivalencias cargadas para guardar."
                
            df_save = pd.DataFrame(self.equivalencias_crudas)
            df_save = df_save[['Medicamento_Recepcion', 'Nombre_Ingresos']]
            
            if ruta.lower().endswith(('.xlsx', '.xls')):
                df_save.to_excel(ruta, index=False)
            else:
                # Guardar en CSV con latin-1 para compatibilidad perfecta con Excel en español
                df_save.to_csv(ruta, index=False, encoding='latin-1')
                
            return True, f"Diccionario guardado exitosamente en: {os.path.basename(ruta)}"
        except Exception as e:
            return False, f"Error al guardar el diccionario: {str(e)}"
    
    def _expandir_sinonimos(self, nombre: str) -> str:
        """Expande sinónimos comunes y extrae valores numéricos sin unidad"""
        import re
        tokens = nombre.split()
        tokens_expandidos = []

        UNIDADES = r'(?:MCG|MG|UI|ML|G|DOSIS|PULS|MCG/DOSIS|MG/ML|UI/ML|%)'

        for t in tokens:
            # Dividir tokens compuestos por separadores
            partes = re.split(r'[/+\-]', t)
            for p in partes:
                p = p.strip()
                if not p:
                    continue
                tokens_expandidos.append(p)
                if p in SINONIMOS:
                    tokens_expandidos.append(SINONIMOS[p])
                # Extraer número sin unidad: ej 250MCG → 250
                m = re.match(r'^(\d+(?:[.,]\d+)?)' + UNIDADES + r'$', p, re.IGNORECASE)
                if m:
                    tokens_expandidos.append(m.group(1))

        return ' '.join(tokens_expandidos)

    def _calcular_score_compuesto(self, a: str, b: str) -> int:
        """Calcula similitud usando token_set_ratio con expansión de sinónimos"""
        return int(fuzz.token_set_ratio(a, b))

    def _encontrar_match_con_equivalencias(self, medicamento_recepcion: str) -> Tuple[str, int, str]:
        """
        Encuentra match primero en equivalencias, luego en fuzzy matching

        Args:
            medicamento_recepcion: Nombre del medicamento en recepción

        Returns:
            Tuple: (medicamento_ingresos, score, metodo_usado)
        """
        if self.ingresos_df is None or 'Nombre del Medicamento' not in self.ingresos_df.columns:
            return None, 0, "ninguno"

        # Usar caché si está disponible, sino normalizar
        med_norm = self._cache_recepcion_norm.get(medicamento_recepcion) or self._normalizar_nombre(medicamento_recepcion)
        med_norm_exp = self._expandir_sinonimos(med_norm)

        # 1. Buscar en equivalencias primero
        if med_norm in self.equivalencias:
            equiv_buscada = self.equivalencias[med_norm]

            for med_ingreso, med_ing_norm in self._cache_ingresos_norm.items():
                if equiv_buscada in med_ing_norm or med_ing_norm in equiv_buscada:
                    return med_ingreso, 100, "equivalencia"

            mejor_equiv_match = None
            mejor_equiv_score = 0
            for med_ingreso, med_ing_norm in self._cache_ingresos_norm.items():
                score = self._calcular_score_compuesto(equiv_buscada, med_ing_norm)
                if score > mejor_equiv_score:
                    mejor_equiv_score = score
                    mejor_equiv_match = med_ingreso

            if mejor_equiv_score >= 85 and mejor_equiv_match:
                return mejor_equiv_match, mejor_equiv_score, "equivalencia"

        # 2. Fallback a fuzzy matching
        if self.fuzzy_enabled:
            mejor_match = None
            mejor_score = 0

            for med_ingreso, med_ing_norm in self._cache_ingresos_norm.items():
                med_ing_norm_exp = self._expandir_sinonimos(med_ing_norm)
                score = self._calcular_score_compuesto(med_norm_exp, med_ing_norm_exp)

                if score > mejor_score:
                    mejor_score = score
                    mejor_match = med_ingreso

            if mejor_match:
                return mejor_match, mejor_score, "fuzzy_matching"

        return None, 0, "ninguno"
    
    def comparar(self) -> Dict:
        """
        Compara los dos archivos y retorna los resultados
        
        Returns:
            Dict: Resultados de la comparación
        """
        if self.recepcion_df is None or self.ingresos_df is None:
            return {
                'error': 'Debe cargar ambos archivos antes de comparar',
                'resultados': self.resultados
            }
        
        # Limpiar resultados previos
        self.resultados = {
            'coincidencias': [],
            'discrepancias_cantidad': [],
            'faltantes_en_ingresos': [],
            'faltantes_en_recepcion': [],
            'sugerencias': []
        }
        self.matches = {}
        self.rastreo_matching = {}
        
        # Crear diccionario de medicamentos en ingresos
        ingresos_dict = {}
        if 'Nombre del Medicamento' in self.ingresos_df.columns and 'Cantidad' in self.ingresos_df.columns:
            for _, row in self.ingresos_df.iterrows():
                med = row['Nombre del Medicamento']
                cantidad = row['Cantidad']
                # Agrupar por medicamento (sumar cantidades si hay duplicados)
                ingresos_dict[med] = ingresos_dict.get(med, 0) + cantidad
        
        # Procesar medicamentos de recepción
        if 'Medicamento' not in self.recepcion_df.columns or 'Cantidad' not in self.recepcion_df.columns:
            return {
                'error': 'Archivo de recepción debe tener columnas "Medicamento" y "Cantidad"',
                'resultados': self.resultados
            }
        
        # Agrupar recepción por medicamento (sumar cantidades si hay duplicados)
        recepcion_dict = {}
        for _, row in self.recepcion_df.iterrows():
            med = row['Medicamento']
            cantidad = row['Cantidad']
            recepcion_dict[med] = recepcion_dict.get(med, 0) + cantidad
        
        medicamentos_procesados = set()
        
        for med_recepcion, cant_recepcion in recepcion_dict.items():
            
            # Buscar match con nueva lógica
            med_ingreso, score, metodo = self._encontrar_match_con_equivalencias(med_recepcion)
            
            if score >= self.threshold and med_ingreso:
                self.matches[med_recepcion] = med_ingreso
                self.rastreo_matching[med_recepcion] = metodo
                cant_ingreso = ingresos_dict.get(med_ingreso, 0)
                medicamentos_procesados.add(med_ingreso)
                
                if cant_recepcion == cant_ingreso:
                    self.resultados['coincidencias'].append({
                        'medicamento_recepcion': med_recepcion,
                        'medicamento_ingresos': med_ingreso,
                        'cantidad': cant_recepcion,
                        'similitud': score,
                        'metodo': metodo
                    })
                else:
                    self.resultados['discrepancias_cantidad'].append({
                        'medicamento_recepcion': med_recepcion,
                        'medicamento_ingresos': med_ingreso,
                        'cantidad_recepcion': cant_recepcion,
                        'cantidad_ingresos': cant_ingreso,
                        'diferencia': cant_ingreso - cant_recepcion,
                        'similitud': score,
                        'metodo': metodo
                    })
            else:
                self.resultados['faltantes_en_ingresos'].append({
                    'medicamento': med_recepcion,
                    'cantidad': cant_recepcion,
                    'ubicacion': 'Solo en Recepción',
                    'medicamento_origen': ''
                })
        
        # Encontrar medicamentos en ingresos que no tienen match
        for med_ingreso, cantidad in ingresos_dict.items():
            if med_ingreso not in medicamentos_procesados:
                self.resultados['faltantes_en_recepcion'].append({
                    'medicamento': med_ingreso,
                    'cantidad': cantidad,
                    'ubicacion': 'Solo en Ingresos',
                    'medicamento_origen': ''
                })
        
        # Agregar diferencias de cantidad de las discrepancias a los faltantes correspondientes
        for disc in self.resultados['discrepancias_cantidad']:
            cant_rec = disc['cantidad_recepcion']
            cant_ing = disc['cantidad_ingresos']
            med_rec = disc['medicamento_recepcion']
            med_ing = disc['medicamento_ingresos']
            
            if cant_rec > cant_ing:
                self.resultados['faltantes_en_ingresos'].append({
                    'medicamento': med_rec,
                    'cantidad': cant_rec - cant_ing,
                    'ubicacion': 'Diferencia en Ingresos',
                    'medicamento_origen': med_ing
                })
            elif cant_ing > cant_rec:
                self.resultados['faltantes_en_recepcion'].append({
                    'medicamento': med_rec,
                    'cantidad': cant_ing - cant_rec,
                    'ubicacion': 'Diferencia en Recepción',
                    'medicamento_origen': med_ing
                })
        
        # Calcular sugerencias de coincidencia para los medicamentos faltantes en ingresos
        for faltante in self.resultados['faltantes_en_ingresos']:
            if faltante.get('ubicacion') == 'Diferencia en Ingresos':
                continue
            med_rec = faltante['medicamento']
            med_rec_norm = self._cache_recepcion_norm.get(med_rec) or self._normalizar_nombre(med_rec)
            med_rec_norm_exp = self._expandir_sinonimos(med_rec_norm)

            mejor_sug_match = None
            mejor_sug_score = 0

            # Comparar contra los medicamentos que quedaron huérfanos en ingresos
            for faltante_ing in self.resultados['faltantes_en_recepcion']:
                med_ing = faltante_ing.get('medicamento_origen') or faltante_ing['medicamento']
                med_ing_norm = self._cache_ingresos_norm.get(med_ing) or self._normalizar_nombre(med_ing)
                med_ing_norm_exp = self._expandir_sinonimos(med_ing_norm)

                score = self._calcular_score_compuesto(med_rec_norm_exp, med_ing_norm_exp)
                if score > mejor_sug_score:
                    mejor_sug_score = score
                    mejor_sug_match = med_ing

            # Si no hay huérfanos suficientes, comparar contra todo el catálogo de ingresos
            if mejor_sug_score < 45:
                for med_ing in ingresos_dict.keys():
                    med_ing_norm = self._cache_ingresos_norm.get(med_ing) or self._normalizar_nombre(med_ing)
                    med_ing_norm_exp = self._expandir_sinonimos(med_ing_norm)
                    score = self._calcular_score_compuesto(med_rec_norm_exp, med_ing_norm_exp)
                    if score > mejor_sug_score:
                        mejor_sug_score = score
                        mejor_sug_match = med_ing

            # Si la similitud está en rango intermedio (45% a threshold-1), sugerirla
            if 45 <= mejor_sug_score < self.threshold:
                self.resultados['sugerencias'].append({
                    'medicamento_recepcion': med_rec,
                    'medicamento_ingresos': mejor_sug_match,
                    'similitud': mejor_sug_score
                })
        
        return {
            'error': None,
            'resultados': self.resultados,
            'total_medicamentos_recepcion': len(recepcion_dict),
            'total_medicamentos_ingresos': len(ingresos_dict)
        }
    
    def guardar_perfil(self, ruta: str) -> tuple:
        """Guarda la configuración actual como perfil JSON"""
        try:
            perfil = {
                'threshold': self.threshold,
                'fuzzy_enabled': self.fuzzy_enabled,
                'modo_matching': self.modo_matching
            }
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(perfil, f, indent=2, ensure_ascii=False)
            return True, f"Perfil guardado: {os.path.basename(ruta)}"
        except Exception as e:
            return False, f"Error al guardar perfil: {str(e)}"

    def cargar_perfil(self, ruta: str) -> tuple:
        """Carga configuración desde un archivo JSON"""
        try:
            if not os.path.exists(ruta):
                return False, f"Archivo no encontrado: {ruta}"
            with open(ruta, 'r', encoding='utf-8') as f:
                perfil = json.load(f)
            self.threshold = perfil.get('threshold', self.threshold)
            self.fuzzy_enabled = perfil.get('fuzzy_enabled', self.fuzzy_enabled)
            self.modo_matching = perfil.get('modo_matching', self.modo_matching)
            return True, perfil
        except Exception as e:
            return False, f"Error al cargar perfil: {str(e)}"

    def obtener_resumen(self) -> Dict:
        """Retorna un resumen de los resultados"""
        return {
            'coincidencias': len(self.resultados['coincidencias']),
            'discrepancias_cantidad': len(self.resultados['discrepancias_cantidad']),
            'faltantes_en_ingresos': len(self.resultados['faltantes_en_ingresos']),
            'faltantes_en_recepcion': len(self.resultados['faltantes_en_recepcion']),
            'total_recepcion': len(self.recepcion_df['Medicamento'].unique()) if self.recepcion_df is not None else 0,
            'total_ingresos': len(self.ingresos_df['Nombre del Medicamento'].unique()) if self.ingresos_df is not None else 0,
            'total_cantidad_recepcion': self.recepcion_df['Cantidad'].sum() if self.recepcion_df is not None else 0,
            'total_cantidad_ingresos': self.ingresos_df['Cantidad'].sum() if self.ingresos_df is not None else 0,
        }
