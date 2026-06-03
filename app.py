import os
import json
import uuid
import tempfile
from flask import Flask, render_template, request, send_file, session
from comparador import ComparadorMedicamentos
from generador_pdf import generar_informe_pdf
import pandas as pd

app = Flask(__name__)
app.secret_key = os.urandom(24)

RUTA_DICCIONARIO_BASE = os.path.join(os.path.dirname(__file__), 'diccionario_equivalencias.xlsx')


def cargar_diccionario_base():
    if not os.path.exists(RUTA_DICCIONARIO_BASE):
        return []
    comp = ComparadorMedicamentos()
    comp.cargar_equivalencias(RUTA_DICCIONARIO_BASE)
    return comp.equivalencias_crudas


@app.route('/')
def index():
    dicc_base = cargar_diccionario_base()
    return render_template('index.html', diccionario_base=json.dumps(dicc_base, ensure_ascii=False))


@app.route('/comparar', methods=['POST'])
def comparar():
    archivo_rec = request.files.get('recepcion')
    archivo_ing = request.files.get('ingresos')

    if not archivo_rec or not archivo_ing:
        return render_template('resultados.html', error="Debes subir ambos archivos")

    session_id = str(uuid.uuid4())
    tmp = tempfile.gettempdir()
    ruta_rec = os.path.join(tmp, f'rec_{session_id}.xlsx')
    ruta_ing = os.path.join(tmp, f'ing_{session_id}.xlsx')
    archivo_rec.save(ruta_rec)
    archivo_ing.save(ruta_ing)

    threshold = int(request.form.get('threshold', 70))
    comparador = ComparadorMedicamentos(threshold=threshold)

    if os.path.exists(RUTA_DICCIONARIO_BASE):
        comparador.cargar_equivalencias(RUTA_DICCIONARIO_BASE)

    equivalencias_usuario = request.form.get('equivalencias_usuario', '[]')
    try:
        for eq in json.loads(equivalencias_usuario):
            comparador.agregar_equivalencia_manual(eq['rec'], eq['ing'])
    except Exception:
        pass

    ok_rec, err_rec = comparador.cargar_recepcion(ruta_rec)
    if not ok_rec:
        return render_template('resultados.html', error=err_rec)

    ok_ing, err_ing = comparador.cargar_ingresos(ruta_ing)
    if not ok_ing:
        return render_template('resultados.html', error=err_ing)

    resultado = comparador.comparar()
    if resultado.get('error'):
        return render_template('resultados.html', error=resultado['error'])

    resumen = comparador.obtener_resumen()

    session['session_id'] = session_id
    session['threshold'] = threshold

    return render_template('resultados.html',
                           session_id=session_id,
                           error=None,
                           resumen=resumen,
                           coincidencias=comparador.resultados['coincidencias'],
                           discrepancias=comparador.resultados['discrepancias_cantidad'],
                           faltantes_ingresos=comparador.resultados['faltantes_en_ingresos'],
                           faltantes_recepcion=comparador.resultados['faltantes_en_recepcion'],
                           sugerencias=comparador.resultados.get('sugerencias', []),
                           threshold=threshold,
                           nombre_rec=os.path.basename(ruta_rec),
                           nombre_ing=os.path.basename(ruta_ing))


@app.route('/recomparar', methods=['POST'])
def recomparar():
    session_id = request.form.get('session_id')
    threshold = int(request.form.get('threshold', 70))
    tmp = tempfile.gettempdir()
    ruta_rec = os.path.join(tmp, f'rec_{session_id}.xlsx')
    ruta_ing = os.path.join(tmp, f'ing_{session_id}.xlsx')

    if not os.path.exists(ruta_rec) or not os.path.exists(ruta_ing):
        return render_template('resultados.html',
                               error="Los archivos temporales ya no están disponibles. Vuelve a cargarlos.")

    comparador = ComparadorMedicamentos(threshold=threshold)

    if os.path.exists(RUTA_DICCIONARIO_BASE):
        comparador.cargar_equivalencias(RUTA_DICCIONARIO_BASE)

    equivalencias_usuario = request.form.get('equivalencias_usuario', '[]')
    try:
        for eq in json.loads(equivalencias_usuario):
            comparador.agregar_equivalencia_manual(eq['rec'], eq['ing'])
    except Exception:
        pass

    ok_rec, err_rec = comparador.cargar_recepcion(ruta_rec)
    if not ok_rec:
        return render_template('resultados.html', error=err_rec)

    ok_ing, err_ing = comparador.cargar_ingresos(ruta_ing)
    if not ok_ing:
        return render_template('resultados.html', error=err_ing)

    resultado = comparador.comparar()
    if resultado.get('error'):
        return render_template('resultados.html', error=resultado['error'])

    resumen = comparador.obtener_resumen()

    return render_template('resultados.html',
                           session_id=session_id,
                           error=None,
                           resumen=resumen,
                           coincidencias=comparador.resultados['coincidencias'],
                           discrepancias=comparador.resultados['discrepancias_cantidad'],
                           faltantes_ingresos=comparador.resultados['faltantes_en_ingresos'],
                           faltantes_recepcion=comparador.resultados['faltantes_en_recepcion'],
                           sugerencias=comparador.resultados.get('sugerencias', []),
                           threshold=threshold,
                           nombre_rec='',
                           nombre_ing='')


@app.route('/descargar/pdf', methods=['POST'])
def descargar_pdf():
    session_id = request.form.get('session_id')
    observaciones = request.form.get('observaciones', '')
    tmp = tempfile.gettempdir()
    ruta_rec = os.path.join(tmp, f'rec_{session_id}.xlsx')
    ruta_ing = os.path.join(tmp, f'ing_{session_id}.xlsx')

    comparador = ComparadorMedicamentos()
    if os.path.exists(RUTA_DICCIONARIO_BASE):
        comparador.cargar_equivalencias(RUTA_DICCIONARIO_BASE)

    equivalencias_usuario = request.form.get('equivalencias_usuario', '[]')
    try:
        for eq in json.loads(equivalencias_usuario):
            comparador.agregar_equivalencia_manual(eq['rec'], eq['ing'])
    except Exception:
        pass

    if os.path.exists(ruta_rec):
        comparador.cargar_recepcion(ruta_rec)
    if os.path.exists(ruta_ing):
        comparador.cargar_ingresos(ruta_ing)
    comparador.comparar()

    ruta_pdf = os.path.join(tmp, f'reporte_{session_id}.pdf')
    exito, msg = generar_informe_pdf(ruta_pdf, comparador, observaciones)
    if not exito:
        return msg, 400
    return send_file(ruta_pdf, as_attachment=True, download_name=f'Reporte_Comparacion.pdf')


@app.route('/descargar/excel/<tipo>', methods=['POST'])
def descargar_excel(tipo):
    data = request.get_json(force=True, silent=True)
    if not data:
        return "No data", 400
    df = pd.DataFrame(data)
    tmp = tempfile.gettempdir()
    ruta = os.path.join(tmp, f'{tipo}_{uuid.uuid4().hex}.xlsx')
    df.to_excel(ruta, index=False)
    return send_file(ruta, as_attachment=True, download_name=f'{tipo}.xlsx')


@app.route('/descargar/diccionario', methods=['POST'])
def descargar_diccionario():
    equivalencias = json.loads(request.form.get('equivalencias', '[]'))
    base = cargar_diccionario_base()
    todas = base + [{'Medicamento_Recepcion': e['rec'], 'Nombre_Ingresos': e['ing']} for e in equivalencias]
    df = pd.DataFrame(todas)
    tmp = tempfile.gettempdir()
    ruta = os.path.join(tmp, f'diccionario_{uuid.uuid4().hex}.xlsx')
    df.to_excel(ruta, index=False)
    return send_file(ruta, as_attachment=True, download_name='diccionario_equivalencias.xlsx')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
