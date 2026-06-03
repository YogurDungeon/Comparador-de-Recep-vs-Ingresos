# Comparador Web

Proyecto Flask para comparar productos y generar resultados en PDF.

Estructura:
- `app.py` — aplicación principal
- `comparador.py` — lógica de comparación
- `generador_pdf.py` — generación de PDFs
- `templates/` — plantillas HTML
- `static/` — CSS y recursos estáticos

Instalación:

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
```

Uso :

```bash
python app.py
```

Despliegue en Render:

1. Sube el proyecto a GitHub.
2. En https://render.com, crea un nuevo servicio web.
3. Conecta tu cuenta de GitHub y selecciona el repositorio `comparador-web`.
4. Usa estos ajustes:
   - Branch: `master` (o el branch que estés usando)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Si deseas, añade una variable de entorno `SECRET_KEY` en Render para producción.

Licencia: Agrega tu licencia preferida.
