from flask import Flask, render_template, request, jsonify, send_file
import requests
import os
import json
import threading
import zipfile
from pathlib import Path
import tempfile
import uuid
import io
import time

app = Flask(__name__)

# Configuración - REEMPLAZA con tu URL real de Apps Script
APP_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxQdKM1feeI0Ami_nQUh-wIIZ1GeBzp0ePnP69ynbFcrkUVqFcbqlj9MXdH0tCIIjYXMA/exec"

class DownloadManager:
    def __init__(self):
        self.active_downloads = {}
    
    def start_download(self, token):
        """Iniciar proceso de descarga"""
        download_id = str(uuid.uuid4())
        self.active_downloads[download_id] = {
            'status': 'starting',
            'progress': 0,
            'total_files': 0,
            'downloaded': 0,
            'current_file': '',
            'error': None
        }
        
        # Ejecutar en hilo separado
        thread = threading.Thread(
            target=self._download_process,
            args=(token, download_id)
        )
        thread.daemon = True
        thread.start()
        
        return download_id
    
    def _download_process(self, token, download_id):
        """Proceso principal de descarga"""
        try:
            # Obtener datos de Apps Script
            response = requests.get(f"{APP_SCRIPT_URL}?token={token}")
            if response.status_code != 200:
                self.active_downloads[download_id].update({
                    'status': 'error',
                    'error': 'Error conectando con Google Apps Script'
                })
                return
            
            data = response.json()
            files = data['files']
            total_files = len(files)
            
            self.active_downloads[download_id].update({
                'status': 'downloading',
                'total_files': total_files,
                'current_file': 'Preparando...'
            })
            
            # Crear directorio PERSISTENTE para esta descarga
            download_dir = os.path.join('downloads', download_id)
            os.makedirs(download_dir, exist_ok=True)
            
            base_dir = os.path.join(download_dir, "ArchivosSeleccionados")
            os.makedirs(base_dir, exist_ok=True)
            
            downloaded_files = []
            
            # Descargar archivos
            for i, file_info in enumerate(files):
                file_path = os.path.join(base_dir, file_info['folderPath'], file_info['filename'])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                self.active_downloads[download_id].update({
                    'current_file': f"{file_info['folderPath']}/{file_info['filename']}",
                    'progress': (i / total_files) * 100
                })
                
                if self._download_single_file(file_info, file_path):
                    downloaded_files.append(file_path)
                
                self.active_downloads[download_id]['downloaded'] = i + 1
            
            # Crear ZIP
            zip_path = os.path.join(download_dir, "ArchivosSeleccionados.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file_path in downloaded_files:
                    arcname = os.path.relpath(file_path, base_dir)
                    zipf.write(file_path, arcname)
            
            self.active_downloads[download_id].update({
                'status': 'completed',
                'progress': 100,
                'zip_path': zip_path,
                'downloaded_files': len(downloaded_files),
                'download_dir': download_dir  # Guardar para limpieza posterior
            })
                
        except Exception as e:
            self.active_downloads[download_id].update({
                'status': 'error',
                'error': str(e)
            })
    
    def _download_single_file(self, file_info, file_path):
        """Descargar un archivo individual"""
        try:
            # Usar URL de descarga directa de Google Drive
            file_id = file_info['id']
            url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            session = requests.Session()
            response = session.get(url, stream=True)
            
            # Manejar confirmación para archivos grandes
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={value}"
                    response = session.get(url, stream=True)
                    break
            
            # Descargar archivo
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
            
        except Exception as e:
            print(f"Error descargando {file_info['filename']}: {e}")
            return False
    
    def get_status(self, download_id):
        """Obtener estado de descarga"""
        return self.active_downloads.get(download_id, {'status': 'not_found'})
    
    def cleanup_old_downloads(self):
        """Limpiar descargas antiguas (más de 1 hora)"""
        try:
            downloads_dir = 'downloads'
            if os.path.exists(downloads_dir):
                now = time.time()
                for item in os.listdir(downloads_dir):
                    item_path = os.path.join(downloads_dir, item)
                    # Eliminar si tiene más de 1 hora
                    if os.path.getmtime(item_path) < now - 3600:
                        import shutil
                        shutil.rmtree(item_path)
                        print(f"Limpiado: {item_path}")
        except Exception as e:
            print(f"Error en limpieza: {e}")

# Instancia global del manager
download_manager = DownloadManager()

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/start-download', methods=['POST'])
def start_download():
    """Iniciar nueva descarga"""
    token = request.json.get('token')
    if not token:
        return jsonify({'error': 'Token requerido'}), 400
    
    # Limpiar descargas antiguas antes de empezar
    download_manager.cleanup_old_downloads()
    
    download_id = download_manager.start_download(token)
    return jsonify({'download_id': download_id})

@app.route('/status/<download_id>')
def get_status(download_id):
    """Obtener estado de descarga"""
    status = download_manager.get_status(download_id)
    return jsonify(status)

@app.route('/download/<download_id>')
def download_zip(download_id):
    """Descargar archivo ZIP"""
    status = download_manager.get_status(download_id)
    if status.get('status') != 'completed':
        return "Descarga no completada", 400
    
    zip_path = status.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return "Archivo no encontrado", 404
    
    return send_file(zip_path, 
                    as_attachment=True,
                    download_name='ArchivosSeleccionados.zip',
                    mimetype='application/zip')

@app.route('/direct-download/<token>')
def direct_download(token):
    """Descarga directa sin interfaz web intermedia"""
    try:
        # Obtener datos de Apps Script
        response = requests.get(f"{APP_SCRIPT_URL}?token={token}")
        if response.status_code != 200:
            return "Error: Token inválido", 400
        
        data = response.json()
        files = data['files']
        
        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, file_info in enumerate(files):
                try:
                    # Descargar cada archivo y agregar al ZIP
                    file_id = file_info['id']
                    url = f"https://drive.google.com/uc?id={file_id}&export=download"
                    
                    session = requests.Session()
                    response = session.get(url, stream=True)
                    
                    # Manejar confirmación para archivos grandes
                    for key, value in response.cookies.items():
                        if key.startswith('download_warning'):
                            url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={value}"
                            response = session.get(url, stream=True)
                            break
                    
                    # Leer contenido del archivo
                    file_content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file_content += chunk
                    
                    # Agregar al ZIP con estructura de carpetas
                    file_path = f"{file_info['folderPath']}/{file_info['filename']}"
                    zipf.writestr(file_path, file_content)
                    
                except Exception as e:
                    print(f"Error procesando archivo {file_info['filename']}: {e}")
                    continue
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name='ArchivosSeleccionados.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    # Crear directorio de descargas si no existe
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    app.run(debug=True)
