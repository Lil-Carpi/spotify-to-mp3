# **MP3 Downloader**

![MP3Downloader](screenshots/screenshot.png)

**MP3 Downloader** es una aplicación de escritorio para Windows y Linux que te permite descargar playlists como archivos MP3, con portada y metadatos, usando YouTube como fuente de audio.

### **Nota: Requiere tener claves en [developers](https://developer.spotify.com/) para descargar las canciones.**

## **Características**

* Descarga playlists completas  
* Convierte automáticamente a MP3 con metadatos y portada.  
* Vista previa de la canción actual y progreso de descarga.  
* Soporte para Windows y Linux.  
* Descarga automática de FFmpeg si no está instalado.  
* Interfaz moderna con **CustomTkinter**.  
* Logs de descargas y errores.

## **Requisitos**

* Python 3.10+  
* Librerías Python:  
  * `customtkinter`  
  * `spotipy`  
  * `yt_dlp`  
  * `Pillow`  
  * `requests`  
* Conexión a Internet para descargas y autenticación.

## **Instalación**

### **Opción 1: Ejecutar con Python**

```bash
git clone https://github.com/Lil-Carpi/MP3Downloader.git
cd MP3Downloader
pip install -r requirements.txt
python main.py
```

### **Opción 2: Ejecutable (.exe)**

1. Ve a la carpeta `/dist` después de haber compilado con PyInstaller.  
2. Ejecuta `Downloader.exe`.

## **Uso**

1. Introduce tu **Client ID** y **Client Secret**  
2. Pega el enlace de la playlist que quieras descargar.  
3. Haz clic en **INICIAR DESCARGA**.  
4. La aplicación descargará cada canción como MP3 en `~/Música` (puedes cambiarlo en el código).

## **Estructura de Archivos**

Downloader/  
├─ main.py          \# Archivo principal  
├─ dist/            \# Ejecutables compilados  
├─ LICENSE          \# Licencia GPL 2.1  
├─ README.md  
├─ requirements.txt \# Dependencias Python  
└─ screenshots/     \# Imágenes para README

## **Nota sobre FFmpeg**

Si FFmpeg no está instalado en tu sistema, la aplicación descargará automáticamente los binarios necesarios y los pondrá en el directorio actual.

## **Contribuciones**

Se aceptan contribuciones mediante pull requests. Por favor, crea una issue antes de implementar cambios importantes.

