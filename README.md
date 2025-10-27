# Descargador Masivo - Python Backend

Backend en Python para descargar archivos masivamente desde Google Drive mediante Google Apps Script.

## 🚀 Características

- Interfaz web moderna
- Descarga sin límites de tamaño
- Progreso en tiempo real
- Estructura de carpetas preservada
- Integración con Google Apps Script

## 🛠️ Instalación

1. Clona el repositorio
2. Instala dependencias: `pip install -r requirements.txt`
3. Ejecuta: `python app.py`

## 🌐 Deployment

### En Render.com (Gratis)
1. Conecta tu repositorio de GitHub
2. Usa las siguientes configuraciones:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### En Heroku
1. Instala Heroku CLI
2. Ejecuta:
```bash
heroku create tu-app-descargador
git push heroku main
