import os
import threading
import platform
import shutil
import zipfile
import tarfile
import requests
import re
import subprocess
from io import BytesIO
from PIL import Image
import customtkinter as ctk
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- CONFIGURACIÓN ---
DOWNLOAD_DIR = os.path.expanduser("~/Música")
LOG_FILE = os.path.join(DOWNLOAD_DIR, "spotify_downloader.log")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- VARIABLES DE ESTADO ---
        self.ffmpeg_dir = None # Guardamos el DIRECTORIO, no el binario
        self.stop_event = threading.Event()
        self.current_image = None # Referencia para evitar Garbage Collection
        self.cover_cache = {}     # Caché de imágenes {url: ctk_image}
        self.is_downloading = False
        
        # --- CONFIGURACIÓN DE VENTANA ---
        self.title("Spotify → MP3 Downloader")
        self.geometry("1150x700") 
        self.attributes('-alpha', 0.98)
        
        # Grid: Col 0 (Config), Col 1 (Main), Col 2 (Info Actual)
        self.grid_columnconfigure(0, weight=0) # Fija
        self.grid_columnconfigure(1, weight=1) # Elástica
        self.grid_columnconfigure(2, weight=0) # Fija
        self.grid_rowconfigure(0, weight=1)

        # --- 1. SIDEBAR IZQUIERDA (CONFIG & TOOLS) ---
        self.sidebar_left = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_left.grid(row=0, column=0, sticky="nsew")
        self.sidebar_left.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self.sidebar_left, text="Configuración", font=("Roboto Medium", 20)).grid(row=0, column=0, padx=20, pady=(20, 10))

        ctk.CTkLabel(self.sidebar_left, text="Client ID:", anchor="w").grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.entry_client_id = ctk.CTkEntry(self.sidebar_left, placeholder_text="Pegar ID")
        self.entry_client_id.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")

        ctk.CTkLabel(self.sidebar_left, text="Client Secret:", anchor="w").grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.entry_client_secret = ctk.CTkEntry(self.sidebar_left, placeholder_text="Pegar Secret", show="*")
        self.entry_client_secret.grid(row=4, column=0, padx=20, pady=(5, 20), sticky="ew")

        # Botones de utilidad
        self.btn_open_folder = ctk.CTkButton(self.sidebar_left, text="📂 Abrir Carpeta", command=self.open_download_folder, fg_color="#555555", hover_color="#666666")
        self.btn_open_folder.grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        self.btn_open_log = ctk.CTkButton(self.sidebar_left, text="📄 Ver Logs", command=self.open_log_file, fg_color="#555555", hover_color="#666666")
        self.btn_open_log.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="nEW")

        # --- 2. CONTENIDO CENTRAL ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # 2.1 Panel Superior
        self.top_frame = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=("gray90", "#2b2b2b"))
        self.top_frame.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="ew")
        self.top_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.top_frame, text="Descargador de Playlists", font=("Roboto Medium", 20)).grid(row=0, column=0, padx=10, pady=(15, 5), sticky="w")
        
        self.entry_url = ctk.CTkEntry(self.top_frame, placeholder_text="Pega el enlace de la Playlist aquí...", height=40)
        self.entry_url.grid(row=1, column=0, padx=15, pady=10, sticky="ew")

        self.btn_action = ctk.CTkButton(
            self.top_frame, 
            text="INICIAR DESCARGA", 
            command=self.toggle_download,
            height=40,
            fg_color="#1DB954", 
            hover_color="#1ed760",
            font=("Roboto Medium", 14)
        )
        self.btn_action.grid(row=2, column=0, padx=15, pady=(0, 20), sticky="ew")

        # 2.2 Panel de Progreso (Global)
        self.progress_frame = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=("gray90", "#1f1f1f"))
        self.progress_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(self.progress_frame, text="Listo para empezar", text_color="gray")
        self.lbl_status.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")
        
        self.lbl_percentage = ctk.CTkLabel(self.progress_frame, text="Global: 0%", font=("Roboto Medium", 14))
        self.lbl_percentage.grid(row=0, column=1, padx=15, pady=(10, 0), sticky="e")

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, orientation="horizontal", height=15)
        self.progressbar.set(0)
        self.progressbar.grid(row=1, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")

        # 2.3 Consola
        self.console_frame = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color="transparent")
        self.console_frame.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="nsew")
        self.console_frame.grid_rowconfigure(0, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        self.console = ctk.CTkTextbox(self.console_frame, font=("Consolas", 11), activate_scrollbars=True, fg_color="#111111", text_color="#f8f8f2")
        self.console.grid(row=0, column=0, sticky="nsew")
        
        self.console._textbox.tag_config("info", foreground="#f8f8f2")
        self.console._textbox.tag_config("success", foreground="#50fa7b")
        self.console._textbox.tag_config("error", foreground="#ff5555")
        self.console._textbox.tag_config("warn", foreground="#f1fa8c")

        # --- 3. SIDEBAR DERECHA (INFO CANCIÓN) ---
        self.sidebar_right = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_right.grid(row=0, column=2, sticky="nsew")
        self.sidebar_right.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.sidebar_right, text="Reproduciendo", font=("Roboto Medium", 18)).grid(row=0, column=0, pady=(20, 10))
        
        self.lbl_art = ctk.CTkLabel(self.sidebar_right, text="", width=220, height=220, fg_color="gray20", corner_radius=10)
        self.lbl_art.grid(row=1, column=0, padx=20, pady=10)

        self.lbl_track_title = ctk.CTkLabel(self.sidebar_right, text="-", font=("Roboto Medium", 16), wraplength=250)
        self.lbl_track_title.grid(row=2, column=0, padx=10, pady=(10, 5))

        self.lbl_track_artist = ctk.CTkLabel(self.sidebar_right, text="-", font=("Roboto", 14), text_color="gray")
        self.lbl_track_artist.grid(row=3, column=0, padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar_right, text="Progreso Canción", font=("Roboto", 12), text_color="gray").grid(row=4, column=0, sticky="w", padx=20)
        self.progressbar_song = ctk.CTkProgressBar(self.sidebar_right, orientation="horizontal", height=10, progress_color="#1DB954")
        self.progressbar_song.set(0)
        self.progressbar_song.grid(row=5, column=0, padx=20, pady=(5, 20), sticky="ew")

        # --- INICIO ---
        self.log(f"Directorio: {DOWNLOAD_DIR}", "info")
        self.check_ffmpeg_startup()

    # --- UTILIDADES THREAD-SAFE ---
    def _safe_config(self, widget, **kwargs):
        """Actualiza widgets desde hilos secundarios de forma segura"""
        self.after(0, lambda: widget.configure(**kwargs))

    def _safe_set_progress(self, widget, value):
        self.after(0, lambda: widget.set(value))

    def log(self, text, level="info"):
        def _log_ui():
            self.console.configure(state="normal")
            prefix = ">> "
            if level == "success": prefix = "✔ "
            elif level == "error": prefix = "✘ "
            elif level == "warn": prefix = "⚠ "
            
            self.console.insert("end", f"{prefix}{text}\n", level)
            self.console.see("end")
            self.console.configure(state="disabled")

        self.after(0, _log_ui)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{level.upper()}] {text}\n")
        except Exception:
            pass

    def update_global_progress(self, percentage, status_text):
        self._safe_set_progress(self.progressbar, percentage / 100)
        self._safe_config(self.lbl_percentage, text=f"Global: {percentage:.1f}%")
        self._safe_config(self.lbl_status, text=status_text)

    def update_song_progress(self, percentage):
        self._safe_set_progress(self.progressbar_song, percentage)

    # --- MANEJO DE IMÁGENES ASÍNCRONO ---
    def update_cover_art(self, url):
        # 1. Reset si no hay URL
        if not url:
            self._safe_config(self.lbl_art, image=None)
            return

        # 2. Check Caché
        if url in self.cover_cache:
            self.after(0, lambda: self._apply_cover(self.cover_cache[url]))
            return

        # 3. Descarga en hilo separado
        threading.Thread(target=self._fetch_image_thread, args=(url,), daemon=True).start()

    def _fetch_image_thread(self, url):
        try:
            response = requests.get(url, timeout=5)
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            
            # Programar creación de CTkImage en el hilo principal
            self.after(0, lambda: self._create_and_cache_image(url, img))
        except Exception as e:
            self.log(f"Error cargando imagen: {e}", "warn")

    def _create_and_cache_image(self, url, pil_img):
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(220, 220))
        self.cover_cache[url] = ctk_img
        self._apply_cover(ctk_img)

    def _apply_cover(self, ctk_img):
        self.lbl_art.configure(image=ctk_img)
        self.current_image = ctk_img # Evitar GC

    # --- OTROS ---
    def sanitize_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', "", name)

    def set_inputs_state(self, state):
        self._safe_config(self.entry_url, state=state)
        self._safe_config(self.entry_client_id, state=state)
        self._safe_config(self.entry_client_secret, state=state)

    def open_download_folder(self):
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        
        path = DOWNLOAD_DIR
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Linux":
                subprocess.call(["xdg-open", path])
        except Exception:
            self.log("No se pudo abrir la carpeta", "error")

    def open_log_file(self):
        if not os.path.exists(LOG_FILE):
            self.log("Log no existe aún", "warn")
            return
        
        path = LOG_FILE
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Linux":
                subprocess.call(["xdg-open", path])
        except Exception:
            self.log("No se pudo abrir log", "error")

    # --- FFMPEG ---
    def check_ffmpeg_startup(self):
        # 1. Verificar SISTEMA: Deben existir AMBOS ffmpeg y ffprobe
        sys_ffmpeg = shutil.which("ffmpeg")
        sys_ffprobe = shutil.which("ffprobe")
        
        if sys_ffmpeg and sys_ffprobe:
            self.ffmpeg_dir = None # Usar PATH del sistema
            self.log("FFmpeg y FFprobe detectados en sistema.", "success")
            return

        # 2. Verificar LOCAL: Buscamos carpeta local
        local_ffmpeg = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        local_ffprobe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
        
        cwd = os.getcwd()
        has_local_ffmpeg = os.path.exists(os.path.join(cwd, local_ffmpeg))
        has_local_ffprobe = os.path.exists(os.path.join(cwd, local_ffprobe))
        
        if has_local_ffmpeg and has_local_ffprobe:
            self.ffmpeg_dir = cwd # Pasar directorio actual
            self.log(f"FFmpeg/FFprobe locales detectados.", "success")
            return

        # 3. Faltan dependencias
        self._safe_config(self.btn_action, state="disabled", text="Falta Dependencia")
        if sys_ffmpeg and not sys_ffprobe:
            self.log("Existe ffmpeg pero falta ffprobe. Descargando pack completo...", "warn")
        else:
            self.log("Faltan FFmpeg/FFprobe. Iniciando descarga automática...", "warn")
            
        threading.Thread(target=self.download_ffmpeg, daemon=True).start()

    def download_ffmpeg(self):
        try:
            self.log("Iniciando descarga de herramientas...", "info")
            system = platform.system()
            url = ""
            if system == "Windows":
                url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            elif system == "Linux":
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            else:
                self.log("SO no soportado para auto-descarga.", "error")
                return

            # Descarga
            resp = requests.get(url, stream=True)
            total_size = int(resp.headers.get('content-length', 0))
            data_io = BytesIO()
            dl = 0
            
            for chunk in resp.iter_content(chunk_size=4096):
                dl += len(chunk)
                data_io.write(chunk)
                if total_size:
                    pct = int(dl / total_size * 100)
                    if pct % 10 == 0: self.log(f"Descargando binarios: {pct}%...", "info")
            
            self.log("Descarga completada. Extrayendo...", "info")
            data_io.seek(0)
            
            cwd = os.getcwd()
            
            # Extracción inteligente
            if system == "Windows":
                with zipfile.ZipFile(data_io) as z:
                    for name in z.namelist():
                        # Extraer tanto ffmpeg.exe como ffprobe.exe
                        if name.endswith("bin/ffmpeg.exe") or name.endswith("bin/ffprobe.exe"):
                            filename = os.path.basename(name)
                            target = os.path.join(cwd, filename)
                            with z.open(name) as source, open(target, "wb") as dest:
                                shutil.copyfileobj(source, dest)
                                
            elif system == "Linux":
                with tarfile.open(fileobj=data_io, mode="r:xz") as t:
                    for member in t.getmembers():
                        # Extraer ffmpeg y ffprobe
                        if member.name.endswith("/ffmpeg") or member.name.endswith("/ffprobe"):
                            filename = os.path.basename(member.name)
                            target = os.path.join(cwd, filename)
                            f_obj = t.extractfile(member)
                            if f_obj:
                                with open(target, "wb") as dest:
                                    shutil.copyfileobj(f_obj, dest)
                                os.chmod(target, 0o755) # Permisos ejecución

            self.ffmpeg_dir = cwd
            self.log("Dependencias instaladas correctamente.", "success")
            self._safe_config(self.btn_action, state="normal", text="INICIAR DESCARGA")

        except Exception as e:
            self.log(f"Error crítico en descarga: {e}", "error")

    # --- CONTROL ---
    def toggle_download(self):
        if self.is_downloading:
            self.stop_event.set()
            self.btn_action.configure(state="disabled", text="Deteniendo...")
        else:
            self.start_download_thread()

    def start_download_thread(self):
        self.stop_event.clear()
        self.is_downloading = True
        self.set_inputs_state("disabled")
        self.btn_action.configure(text="CANCELAR", fg_color="#e74c3c", hover_color="#c0392b")
        self.progressbar.set(0)
        self.progressbar_song.set(0)
        self.lbl_percentage.configure(text="Global: 0%")
        threading.Thread(target=self.download_playlist, daemon=True).start()

    def reset_sidebar_error(self):
        """Muestra estado de error en la sidebar"""
        self._safe_config(self.lbl_track_title, text="Error / Cancelado", text_color="#ff5555")
        self._safe_config(self.lbl_track_artist, text="-")
        self.update_cover_art(None)
        self.update_song_progress(0)

    def download_playlist(self):
        try:
            url = self.entry_url.get().strip()
            c_id = self.entry_client_id.get().strip()
            c_secret = self.entry_client_secret.get().strip()

            if not c_id or not c_secret:
                self.log("Faltan credenciales.", "error")
                self.after(0, self.reset_ui_state)
                return

            self.log("Autenticando...", "info")
            auth_manager = SpotifyClientCredentials(client_id=c_id, client_secret=c_secret)
            sp = spotipy.Spotify(auth_manager=auth_manager)
            
            self.log("Cargando playlist...", "info")
            results = sp.playlist_tracks(url)
            tracks_data = []
            
            while results:
                for item in results['items']:
                    if item['track']:
                        track = item['track']
                        imgs = track['album']['images']
                        img_url = imgs[0]['url'] if imgs else None
                        
                        tracks_data.append({
                            "name": track['name'],
                            "artist": track['artists'][0]['name'],
                            "full_name": f"{track['artists'][0]['name']} - {track['name']}",
                            "image": img_url
                        })
                if results['next']: results = sp.next(results)
                else: results = None

            n_tracks = len(tracks_data)
            self.log(f"Playlist: {n_tracks} canciones.", "success")
            
            finished_tracks = 0
            
            for i, data in enumerate(tracks_data):
                if self.stop_event.is_set():
                    self.log("Cancelado por usuario.", "warn")
                    self.after(0, self.reset_sidebar_error)
                    break

                # UI Update Sidebar (Thread Safe)
                self._safe_config(self.lbl_track_title, text=data['name'], text_color="white")
                self._safe_config(self.lbl_track_artist, text=data['artist'])
                self.update_cover_art(data['image'])
                self.update_song_progress(0)
                
                safe_name = self.sanitize_filename(data['full_name'])
                expected_file = os.path.join(DOWNLOAD_DIR, f"{safe_name}.mp3")
                
                if os.path.exists(expected_file):
                    self.log(f"[{i+1}/{n_tracks}] Saltando (Existe): {data['full_name']}", "warn")
                    finished_tracks += 1
                    self.update_global_progress((finished_tracks / n_tracks) * 100, f"Saltado: {data['name']}")
                    continue

                self.log(f"[{i+1}/{n_tracks}] Descargando: {data['full_name']}", "info")

                def progreso_hook(d):
                    if self.stop_event.is_set(): raise Exception("CanceladoUser")
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate')
                        if total:
                            p_song = d.get('downloaded_bytes', 0) / total
                            self.update_song_progress(p_song)

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f'{DOWNLOAD_DIR}/{safe_name}.%(ext)s',
                    'quiet': True,
                    'noplaylist': True,
                    'nocheckcertificate': True,
                    # PASAR EL DIRECTORIO, NO EL BINARIO. O None si es system path
                    'ffmpeg_location': self.ffmpeg_dir,
                    'progress_hooks': [progreso_hook],
                    'writethumbnail': True, 
                    'postprocessors': [
                        {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'},
                        {'key': 'FFmpegMetadata'},
                        {'key': 'EmbedThumbnail'},
                    ],
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"ytsearch1:{data['full_name']}"])
                    
                    self.log(f"Completado: {data['name']}", "success")
                    finished_tracks += 1
                    self.update_global_progress((finished_tracks / n_tracks) * 100, f"Listo: {data['name']}")
                
                except Exception as e:
                    if "CanceladoUser" in str(e): break
                    self.log(f"Error {data['name']}: {e}", "error")
                    # Visualizar error en sidebar momentáneamente
                    self._safe_config(self.lbl_track_title, text="Error en descarga", text_color="#ff5555")
                    finished_tracks += 1 

            self.log("--- FINALIZADO ---", "success")
            self.after(0, self.reset_ui_state)

        except Exception as e:
            self.log(f"Error General: {e}", "error")
            self.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        self.is_downloading = False
        self.stop_event.clear()
        self.set_inputs_state("normal")
        self.btn_action.configure(state="normal", text="INICIAR DESCARGA", fg_color="#1DB954", hover_color="#1ed760")
        self.lbl_status.configure(text="Listo")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        
    app = App()
    app.mainloop()