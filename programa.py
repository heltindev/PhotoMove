"""PHOTOMOVE - organizador visual de fotos e videos.

O programa foi mantido em um unico arquivo para facilitar testes e a futura
geracao de um executavel. A operacao padrao e COPIAR: a origem permanece
intacta ate que o usuario escolha explicitamente MOVER.
"""

from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import os
import queue
import re
import shutil
import threading
import time
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:  # Permite abrir o programa antes da instalacao da dependencia.
    ctk = None

try:
    from PIL import ExifTags, Image
except ImportError:
    ExifTags = None
    Image = None


MESES = {
    1: "01 - JANEIRO", 2: "02 - FEVEREIRO", 3: "03 - MARÇO",
    4: "04 - ABRIL", 5: "05 - MAIO", 6: "06 - JUNHO",
    7: "07 - JULHO", 8: "08 - AGOSTO", 9: "09 - SETEMBRO",
    10: "10 - OUTUBRO", 11: "11 - NOVEMBRO", 12: "12 - DEZEMBRO",
}
FOTOS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".avif", ".gif",
    ".bmp", ".tif", ".tiff", ".heic", ".heif", ".heics", ".heifs",
    ".jp2", ".j2k", ".jpf", ".jpx", ".raw", ".dng", ".cr2", ".cr3",
    ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf", ".rw2", ".raf",
    ".pef", ".rwl", ".3fr", ".iiq", ".kdc", ".dcr", ".erf", ".x3f",
}
VIDEOS = {
    ".mp4", ".m4v", ".mov", ".qt", ".avi", ".mkv", ".mk3d", ".webm",
    ".wmv", ".asf", ".flv", ".f4v", ".mpeg", ".mpg", ".mpe", ".mpv",
    ".3gp", ".3g2", ".ts", ".mts", ".m2ts", ".m2t", ".vob", ".ogv",
    ".ogg", ".rm", ".rmvb", ".divx",
}
MIDIA = FOTOS | VIDEOS


def format_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def format_time(seconds: Optional[float]) -> str:
    if seconds is None or seconds == float("inf"):
        return "--:--:--"
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalized_name(name: str) -> str:
    return Path(name).name.strip().lower()


def iter_media(root: Path):
    """Percorre a árvore sem materializar todos os caminhos na memória."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            path = Path(entry.path)
                            if path.suffix.lower() in MIDIA:
                                yield path, entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for counter in range(1, 1_000_000):
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Não foi possível criar nome livre para {path.name}")


def read_json_index(root: Path) -> dict[str, datetime]:
    index: dict[str, datetime] = {}
    for json_path in root.rglob("*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            block = data.get("photoTakenTime") or data.get("creationTime")
            timestamp = block.get("timestamp") if isinstance(block, dict) else None
            if timestamp and data.get("title"):
                index[normalized_name(str(data["title"]))] = datetime.fromtimestamp(int(timestamp))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return index


def date_from_name(name: str) -> Optional[datetime]:
    stem = Path(name).stem
    patterns = (
        (r"(?<!\d)(\d{2})[_\-.](\d{2})[_\-.](\d{4})(?!\d)", (2, 1, 0)),
        (r"(?<!\d)(19\d{2}|20\d{2})[_\-.](\d{2})[_\-.](\d{2})(?!\d)", (0, 1, 2)),
        (r"(?<!\d)(19\d{2}|20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", (0, 1, 2)),
    )
    for pattern, order in patterns:
        match = re.search(pattern, stem)
        if match:
            try:
                values = [int(match.group(i + 1)) for i in order]
                return datetime(values[0], values[1], values[2])
            except ValueError:
                continue
    return None


def date_from_exif(path: Path) -> Optional[datetime]:
    if Image is None or path.suffix.lower() not in FOTOS:
        return None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            tags = ExifTags.TAGS if ExifTags else {}
            for tag_id, value in exif.items():
                if tags.get(tag_id) in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}:
                    if isinstance(value, str):
                        try:
                            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
    except (OSError, ValueError, SyntaxError):
        return None
    return None


def date_from_folder(path: Path) -> Optional[datetime]:
    parts = list(path.parts)
    for part in reversed(parts):
        match = re.search(r"(?<!\d)(19\d{2}|20\d{2})[_\-.](\d{2})[_\-.](\d{2})(?!\d)", part)
        if match:
            try:
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass
    for index, part in enumerate(parts[:-1]):
        year = re.fullmatch(r"(19\d{2}|20\d{2})", part)
        if year:
            month_match = re.match(r"\s*(\d{1,2})\s*-\s*", parts[index + 1])
            if month_match and 1 <= int(month_match.group(1)) <= 12:
                return datetime(int(year.group(1)), int(month_match.group(1)), 1)
    return None


def discover_date(path: Path, index: dict[str, datetime], enabled: dict[str, bool]) -> tuple[datetime, str]:
    candidates: list[tuple[str, Optional[datetime]]] = []
    if enabled["json"]:
        candidates.append(("JSON", index.get(normalized_name(path.name))))
    if enabled["name"]:
        candidates.append(("NOME", date_from_name(path.name)))
    if enabled["exif"]:
        candidates.append(("EXIF", date_from_exif(path)))
    if enabled["folder"]:
        candidates.append(("PASTA", date_from_folder(path.parent)))
    for source, value in candidates:
        if value:
            return value, source
    if enabled.get("windows", True):
        try:
            return datetime.fromtimestamp(path.stat().st_mtime), "WINDOWS"
        except (OSError, ValueError, OverflowError):
            pass
    return datetime.now(), "SISTEMA"


def recycle_file(path: Path) -> None:
    """Envia um arquivo para a Lixeira do Windows, sem apagar permanentemente."""
    if os.name != "nt":
        path.unlink()
        return
    class SHFILEOPSTRUCT(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p),
        ]
    operation = SHFILEOPSTRUCT(None, 3, f"{path}\0\0", None, 0x0040 | 0x0010, 0, None, None)
    last_error = 0
    for attempt in range(5):
        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        if not result:
            return
        last_error = result
        gc.collect()
        time.sleep(0.35 * (attempt + 1))
    raise OSError(
        last_error,
        f"O Windows manteve o arquivo em uso. Feche a visualização/Explorador "
        f"e tente novamente: {path.name}",
    )


class OperationCancelled(Exception):
    pass


class PhotoMoveApp:
    def __init__(self) -> None:
        if ctk:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()
        self.root.title("PHOTOMOVE | Organizador de fotos e vídeos")
        self.root.geometry("1180x780")
        self.root.minsize(920, 650)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: Optional[threading.Thread] = None
        self.loading_frame = None
        self.loading_label = None
        self._build_ui2()
        self.root.after(100, self._poll_events)

    def widget(self, parent, kind: str, **kwargs):
        if ctk:
            return getattr(ctk, f"CTk{kind}")(parent, **kwargs)
        fallback_names = {
            "Frame": "Frame",
            "Label": "Label",
            "Entry": "Entry",
            "Button": "Button",
            "ProgressBar": "Progressbar",
            "RadioButton": "Radiobutton",
            "CheckBox": "Checkbutton",
            "ScrollableFrame": "Frame",
        }
        kwargs.pop("fg_color", None)
        kwargs.pop("text_color", None)
        kwargs.pop("corner_radius", None)
        kwargs.pop("placeholder_text", None)
        return getattr(ttk, fallback_names[kind])(parent, **kwargs)

    def _build_ui2(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        sidebar = self.widget(self.root, "Frame", fg_color=("#e5e7eb", "#172033") if ctk else None)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.rowconfigure(4, weight=1)
        self.widget(sidebar, "Label", text="PHOTOMOVE", font=("Segoe UI", 21, "bold")).grid(row=0, column=0, padx=18, pady=(24, 2))
        self.widget(sidebar, "Label", text="PHOTO TOOLS", font=("Segoe UI", 10, "bold"), text_color="#60a5fa" if ctk else None).grid(row=1, column=0, padx=18, pady=(0, 22))
        self.nav_photo = self.widget(sidebar, "Button", text="📁  Organizar fotos", anchor="w", command=lambda: self._show_page("organizer"))
        self.nav_photo.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.nav_screens = self.widget(sidebar, "Button", text="▣  Screenshots", anchor="w", command=lambda: self._show_page("screenshots"))
        self.nav_screens.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        self.widget(sidebar, "Label", text="Desenvolvido por\n@heltonleiras", justify="left", text_color="#93c5fd" if ctk else None).grid(row=5, column=0, sticky="sw", padx=18, pady=18)
        self.content = self.widget(self.root, "Frame")
        self.content.grid(row=0, column=1, sticky="nsew", padx=22, pady=20)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.organizer_page = self.widget(self.content, "Frame")
        self.screenshots_page = self.widget(self.content, "Frame")
        self.organizer_page.grid(row=0, column=0, sticky="nsew")
        self.screenshots_page.grid(row=0, column=0, sticky="nsew")
        self._build_organizer_page()
        self._build_screenshots_page()
        self._build_loading_overlay()
        self._show_page("organizer")

    def _build_loading_overlay(self) -> None:
        if ctk:
            self.loading_frame = ctk.CTkFrame(self.root, corner_radius=18, fg_color="#111827")
            self.loading_label = ctk.CTkLabel(
                self.loading_frame,
                text="Preparando...\n0%",
                font=("Segoe UI", 22, "bold"),
                text_color="#dbeafe",
            )
        else:
            self.loading_frame = ttk.Frame(self.root)
            self.loading_label = ttk.Label(self.loading_frame, text="Preparando...\n0%")
        self.loading_label.pack(padx=48, pady=34)

    def _set_loading(self, visible: bool, text: str = "Processando...", percent: int = 0) -> None:
        if visible:
            try:
                self.root.attributes("-alpha", 0.78)
            except tk.TclError:
                pass
            self.loading_label.configure(text=f"{text}\n{percent}%")
            self.loading_frame.place(relx=0.62, rely=0.48, anchor="center")
            self.loading_frame.lift()
        else:
            self.loading_frame.place_forget()
            try:
                self.root.attributes("-alpha", 1.0)
            except tk.TclError:
                pass

    def _update_loading(self, percent: int, text: str = "Processando...") -> None:
        self.loading_label.configure(text=f"{text}\n{percent}%")

    def _build_organizer_page(self) -> None:
        body = self.organizer_page
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)
        self.widget(body, "Label", text="Organizar fotos e vídeos", font=("Segoe UI", 25, "bold")).grid(row=0, column=0, sticky="w")
        self.widget(body, "Label", text="Backup seguro do Google Takeout por data, sem apagar a origem no modo padrão.", text_color="#9ca3af" if ctk else None).grid(row=1, column=0, sticky="w", pady=(2, 18))
        paths = self.widget(body, "Frame", fg_color="#202938" if ctk else None, corner_radius=12)
        paths.grid(row=2, column=0, sticky="ew")
        paths.columnconfigure(0, weight=1)
        self._path_row(paths, 0, "INPUT / ORIGEM", "input_path")
        self._path_row(paths, 1, "OUTPUT / DESTINO", "output_path")
        options = self.widget(body, "Frame", fg_color="#202938" if ctk else None, corner_radius=12)
        options.grid(row=3, column=0, sticky="ew", pady=14)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=2)
        mode_box = self.widget(options, "Frame")
        mode_box.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        self.widget(mode_box, "Label", text="Transferência", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.mode = tk.StringVar(value="copy")
        for text, value in (("COPIAR (recomendado)", "copy"), ("MOVER (remove da origem)", "move")):
            self.widget(mode_box, "RadioButton", text=text, variable=self.mode, value=value).pack(anchor="w", pady=2)
        checks = self.widget(options, "Frame")
        checks.grid(row=0, column=1, sticky="nw")
        self.widget(checks, "Label", text="Funções opcionais", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        defaults = {"json": True, "exif": True, "name": True, "folder": True, "windows": True, "rename": True, "date": True, "duplicates": False, "empty": True}
        self.options = {key: tk.BooleanVar(value=value) for key, value in defaults.items()}
        labels = [("json", "Usar JSON do Google Takeout"), ("exif", "Usar EXIF"), ("name", "Data no nome"), ("folder", "Data da pasta"), ("windows", "Data do Windows"), ("rename", "Renomear DD_MM_AAAA"), ("date", "Ajustar datas do Windows"), ("duplicates", "Detectar duplicados"), ("empty", "Remover pastas vazias")]
        for index, (key, text) in enumerate(labels):
            self.widget(checks, "CheckBox", text=text, variable=self.options[key]).grid(row=1 + index // 2, column=index % 2, sticky="w", padx=(0, 16), pady=1)
        activity = self.widget(body, "Frame", fg_color="#111827" if ctk else None, corner_radius=12)
        activity.grid(row=4, column=0, sticky="nsew")
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(1, weight=1)
        self.progress = self.widget(activity, "ProgressBar")
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.progress.set(0) if ctk else None
        self.status = self.widget(activity, "Label", text="Pronto para organizar.", anchor="w")
        self.status.grid(row=0, column=1, padx=12)
        self.log = tk.Text(activity, height=12, bg="#0b1220", fg="#dbeafe", insertbackground="white", relief="flat", borderwidth=0, padx=12, pady=10)
        self.log.grid(row=1, column=0, columnspan=2, sticky="nsew")
        footer = self.widget(body, "Frame")
        footer.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        self.start_button = self.widget(footer, "Button", text="▶  ORGANIZAR", command=self.start)
        self.start_button.pack(side="left")
        self.cancel_button = self.widget(footer, "Button", text="■  CANCELAR", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)

    def _build_screenshots_page(self) -> None:
        page = self.screenshots_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)
        self.widget(page, "Label", text="Ferramenta Screenshots", font=("Segoe UI", 25, "bold")).grid(row=0, column=0, sticky="w")
        self.widget(page, "Label", text="Encontre capturas de tela do celular e envie somente as selecionadas para a Lixeira.", text_color="#9ca3af" if ctk else None).grid(row=1, column=0, sticky="w", pady=(2, 18))
        chooser = self.widget(page, "Frame", fg_color="#202938" if ctk else None, corner_radius=12)
        chooser.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        chooser.columnconfigure(0, weight=1)
        self.screenshot_path = tk.StringVar()
        entry_kwargs = {"textvariable": self.screenshot_path}
        if ctk:
            entry_kwargs["placeholder_text"] = "Selecione a pasta onde procurar screenshots..."
        self.widget(chooser, "Entry", **entry_kwargs).grid(row=0, column=0, sticky="ew")
        self.widget(chooser, "Button", text="📂 Selecionar pasta", command=self._choose_screenshot_folder).grid(row=0, column=1, padx=(8, 0))
        self.widget(chooser, "Button", text="🔎 Procurar", command=self._scan_screenshots).grid(row=0, column=2, padx=(8, 0))
        actions = self.widget(page, "Frame")
        actions.grid(row=3, column=0, sticky="ew")
        self.screenshot_count = self.widget(actions, "Label", text="Nenhuma busca realizada.", anchor="w")
        self.screenshot_count.pack(side="left")
        self.widget(actions, "Button", text="Marcar todos", command=lambda: self._set_screenshot_selection(True)).pack(side="right")
        self.widget(actions, "Button", text="Desmarcar todos", command=lambda: self._set_screenshot_selection(False)).pack(side="right", padx=8)
        self.screenshot_items = self.widget(page, "ScrollableFrame", fg_color="#111827" if ctk else None, corner_radius=12)
        self.screenshot_items.grid(row=4, column=0, sticky="nsew", pady=(8, 10))
        self.screenshot_selection: list[tuple[Path, tk.BooleanVar]] = []
        self.widget(page, "Button", text="🗑  Enviar selecionados para a Lixeira", command=lambda: self._delete_screenshots(self.screenshot_selection, None)).grid(row=5, column=0, sticky="w")

    def _show_page(self, page: str) -> None:
        (self.organizer_page if page == "organizer" else self.screenshots_page).tkraise()
        if ctk:
            self.nav_photo.configure(fg_color="#2563eb" if page == "organizer" else "transparent")
            self.nav_screens.configure(fg_color="#2563eb" if page == "screenshots" else "transparent")

    def _choose_screenshot_folder(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta para procurar screenshots")
        if selected:
            self.screenshot_path.set(selected)
            self._scan_screenshots()

    def _scan_screenshots(self) -> None:
        for child in self.screenshot_items.winfo_children():
            child.destroy()
        self.screenshot_selection.clear()
        root = Path(self.screenshot_path.get().strip())
        if not root.is_dir():
            messagebox.showerror("Pasta inválida", "Selecione uma pasta existente para procurar screenshots.")
            return
        self.screenshot_count.configure(text="Procurando screenshots...")
        threading.Thread(target=self._scan_screenshots_worker, args=(root,), daemon=True).start()

    def _scan_screenshots_worker(self, root: Path) -> None:
        found: list[Path] = []
        for path, _ in iter_media(root):
            if path.suffix.lower() in FOTOS and self._is_screenshot(path):
                found.append(path)
        self.events.put(("screenshots", found))

    def _render_screenshots(self, paths: list[Path]) -> None:
        for path in paths:
            variable = tk.BooleanVar(value=True)
            self.screenshot_selection.append((path, variable))
            self.widget(self.screenshot_items, "CheckBox", text=str(path), variable=variable).pack(anchor="w", padx=8, pady=3)
        self.screenshot_count.configure(text=f"{len(paths):,} screenshot(s) encontrados.")

    def _scan_screenshots_old(self) -> None:
        """Compatibilidade interna; a busca atual usa uma thread."""
        root = Path(self.screenshot_path.get().strip())
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in FOTOS and self._is_screenshot(path):
                variable = tk.BooleanVar(value=True)
                self.screenshot_selection.append((path, variable))
                self.widget(self.screenshot_items, "CheckBox", text=str(path), variable=variable).pack(anchor="w", padx=8, pady=3)
        self.screenshot_count.configure(text=f"{len(self.screenshot_selection):,} screenshot(s) encontrados.")

    def _set_screenshot_selection(self, value: bool) -> None:
        for _, variable in self.screenshot_selection:
            variable.set(value)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = self.widget(self.root, "Frame", fg_color=("white", "#111827") if ctk else None)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        title = self.widget(header, "Label", text="PHOTOMOVE", font=("Segoe UI", 26, "bold"))
        title.pack(anchor="w", padx=16, pady=(10, 0))
        subtitle = self.widget(header, "Label", text="Organizador seguro para Google Takeout", text_color="#93c5fd" if ctk else None)
        subtitle.pack(anchor="w", padx=16, pady=(0, 10))

        body = self.widget(self.root, "Frame")
        body.grid(row=1, column=0, sticky="nsew", padx=18)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        self._path_row(body, 0, "📥  INPUT / ORIGEM", "input_path")
        self._path_row(body, 1, "📤  OUTPUT / DESTINO", "output_path")

        options = self.widget(body, "Frame")
        options.grid(row=2, column=0, sticky="ew", pady=12)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        mode_box = self.widget(options, "Frame")
        mode_box.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        self.widget(mode_box, "Label", text="Modo de transferência", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.mode = tk.StringVar(value="copy")
        for text, value in (("COPIAR (recomendado)", "copy"), ("MOVER (remove da origem)", "move")):
            self.widget(mode_box, "RadioButton", text=text, variable=self.mode, value=value).pack(anchor="w", pady=2)
        checks = self.widget(options, "Frame")
        checks.grid(row=0, column=1, sticky="nw")
        self.widget(checks, "Label", text="Funções", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        defaults = {"json": True, "exif": True, "name": True, "folder": True, "windows": True,
                    "rename": True, "date": True, "duplicates": False, "empty": True}
        self.options = {key: tk.BooleanVar(value=value) for key, value in defaults.items()}
        labels = [("json", "Usar JSON do Google Takeout"), ("exif", "Usar EXIF"), ("name", "Data no nome"),
                  ("folder", "Data da pasta"), ("windows", "Data do Windows"), ("rename", "Renomear DD_MM_AAAA"),
                  ("date", "Ajustar datas do Windows"), ("duplicates", "Detectar duplicados"), ("empty", "Remover pastas vazias")]
        for index, (key, text) in enumerate(labels):
            self.widget(checks, "CheckBox", text=text, variable=self.options[key]).grid(row=1 + index // 2, column=index % 2, sticky="w", padx=(0, 16), pady=1)

        activity = self.widget(body, "Frame")
        activity.grid(row=3, column=0, sticky="nsew")
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(1, weight=1)
        self.progress = self.widget(activity, "ProgressBar")
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.progress.set(0) if ctk else None
        self.status = self.widget(activity, "Label", text="Pronto para organizar.")
        self.status.grid(row=0, column=1, padx=12)
        self.log = tk.Text(activity, height=12, bg="#0b1220", fg="#dbeafe", insertbackground="white", relief="flat")
        self.log.grid(row=1, column=0, columnspan=2, sticky="nsew")
        footer = self.widget(self.root, "Frame")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=12)
        self.start_button = self.widget(footer, "Button", text="▶  ORGANIZAR", command=self.start)
        self.start_button.pack(side="left")
        self.cancel_button = self.widget(footer, "Button", text="■  CANCELAR", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.widget(footer, "Button", text="🖼  FERRAMENTA SCREENSHOTS", command=self.open_screenshots).pack(side="left", padx=8)
        self.widget(footer, "Label", text="Desenvolvido por @heltonleiras", text_color="#93c5fd" if ctk else None).pack(side="right")

    def _path_row(self, parent, row: int, label: str, attribute: str) -> None:
        frame = self.widget(parent, "Frame")
        frame.grid(row=row, column=0, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)
        self.widget(frame, "Label", text=label, width=190, anchor="w").grid(row=0, column=0, padx=(0, 8))
        variable = tk.StringVar()
        setattr(self, attribute, variable)
        self.widget(frame, "Entry", textvariable=variable).grid(row=0, column=1, sticky="ew")
        self.widget(frame, "Button", text="Selecionar...", width=110, command=lambda: self._choose_folder(variable)).grid(row=0, column=2, padx=(8, 0))

    def _choose_folder(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory()
        if selected:
            variable.set(selected)

    def write_log(self, message: str) -> None:
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        source, target = Path(self.input_path.get().strip()), Path(self.output_path.get().strip())
        if not source.is_dir():
            messagebox.showerror("Origem inválida", "Selecione uma pasta de INPUT existente.")
            return
        if source.resolve() == target.resolve():
            messagebox.showerror("Pastas iguais", "INPUT e OUTPUT precisam ser diferentes.")
            return
        target.mkdir(parents=True, exist_ok=True)
        self.cancel_event.clear()
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.log.delete("1.0", "end")
        self._set_loading(True, "Organizando fotos e vídeos", 0)
        settings = {
            "mode": self.mode.get(),
            "json": self.options["json"].get(),
            "name": self.options["name"].get(),
            "exif": self.options["exif"].get(),
            "folder": self.options["folder"].get(),
            "windows": self.options["windows"].get(),
            "rename": self.options["rename"].get(),
            "date": self.options["date"].get(),
            "duplicates": self.options["duplicates"].get(),
            "empty": self.options["empty"].get(),
        }
        self.worker = threading.Thread(target=self._run, args=(source, target, settings), daemon=True)
        self.worker.start()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.write_log("Cancelamento solicitado; finalizando o arquivo atual...")

    def _run(self, source: Path, target: Path, settings: dict[str, object]) -> None:
        try:
            media = list(iter_media(source))
            total = sum(size for _, size in media)
            self.events.put(("log", f"{len(media):,} mídias encontradas ({format_bytes(total)})."))
            index = read_json_index(source) if settings["json"] else {}
            enabled = {key: bool(settings[key]) for key in ("json", "name", "exif", "folder", "windows")}
            done_bytes = 0
            started = time.time()
            last_progress = 0.0
            for number, (path, size) in enumerate(media, 1):
                if self.cancel_event.is_set():
                    raise OperationCancelled
                date, origin = discover_date(path, index, enabled)
                folder = target / str(date.year) / MESES[date.month]
                folder.mkdir(parents=True, exist_ok=True)
                name = f"{date.day:02d}_{date.month:02d}_{date.year:04d}{path.suffix.lower()}" if settings["rename"] else path.name
                destination = unique_destination(folder / name)
                if settings["mode"] == "move":
                    shutil.move(str(path), str(destination))
                else:
                    with path.open("rb") as source_file, destination.open("wb") as target_file:
                        while chunk := source_file.read(8 * 1024 * 1024):
                            if self.cancel_event.is_set():
                                raise OperationCancelled
                            target_file.write(chunk)
                if settings["date"]:
                    timestamp = date.timestamp()
                    try:
                        os.utime(destination, (timestamp, timestamp))
                    except (OSError, OverflowError, ValueError):
                        pass
                done_bytes += size
                elapsed = max(time.time() - started, 0.001)
                speed = done_bytes / elapsed
                remaining = (total - done_bytes) / speed if speed else None
                now = time.monotonic()
                if now - last_progress >= 0.15 or number == len(media):
                    self.events.put(("progress", (done_bytes / total if total else 1, f"{number}/{len(media)} | {origin} | {format_bytes(speed)}/s | restante {format_time(remaining)}")))
                    last_progress = now
            if settings["duplicates"]:
                self._remove_duplicates(target)
            if settings["empty"]:
                self._remove_empty(target)
            self.events.put(("done", f"Concluído: {len(media):,} arquivos processados."))
        except OperationCancelled:
            self.events.put(("cancelled", "Operação cancelada pelo usuário."))
        except Exception as error:
            self.events.put(("error", f"ERRO: {error}"))

    def _remove_duplicates(self, root: Path) -> None:
        groups: dict[int, list[Path]] = defaultdict(list)
        for path, _ in iter_media(root):
            if path.suffix.lower() in MIDIA:
                try:
                    groups[path.stat().st_size].append(path)
                except OSError:
                    continue
        known: dict[str, Path] = {}
        removed = 0
        for candidates in groups.values():
            for path in candidates:
                digest = self._file_hash(path)
                if not digest:
                    continue
                if digest in known:
                    recycle_file(path)
                    removed += 1
                else:
                    known[digest] = path
        self.events.put(("log", f"Duplicados enviados para a Lixeira: {removed:,}."))

    @staticmethod
    def _file_hash(path: Path) -> Optional[str]:
        digest = hashlib.sha256()
        try:
            with path.open("rb", buffering=1024 * 1024) as file:
                while chunk := file.read(8 * 1024 * 1024):
                    digest.update(chunk)
        except OSError:
            return None
        return digest.hexdigest()

    def _remove_empty(self, root: Path) -> None:
        removed = 0
        for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                if not any(directory.iterdir()):
                    directory.rmdir()
                    removed += 1
            except OSError:
                continue
        self.events.put(("log", f"Pastas vazias removidas: {removed:,}."))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "log":
                    self.write_log(str(payload))
                elif event == "screenshots":
                    self._render_screenshots(payload)
                elif event == "screenshot_delete_progress":
                    value, errors = payload
                    self._update_loading(int(value * 100), "Enviando screenshots para a Lixeira")
                elif event == "screenshot_delete_done":
                    total, errors = payload
                    self._set_loading(False)
                    if errors:
                        messagebox.showwarning(
                            "Resultado",
                            f"{total - errors} enviado(s) para a Lixeira. "
                            f"{errors} arquivo(s) estavam em uso ou falharam.",
                            parent=self.root,
                        )
                    else:
                        messagebox.showinfo("Resultado", "Screenshots enviados para a Lixeira.", parent=self.root)
                    self._scan_screenshots()
                elif event == "progress":
                    value, text = payload
                    self.progress.set(value) if ctk else self.progress.configure(value=value)
                    self.status.configure(text=text)
                    self._update_loading(int(value * 100), "Organizando fotos e vídeos")
                elif event == "done":
                    self.write_log(str(payload))
                    self.status.configure(text="Finalizado")
                    self._set_loading(False)
                    self._set_idle()
                elif event == "cancelled":
                    self.write_log(str(payload))
                    self.status.configure(text="Cancelado")
                    self._set_loading(False)
                    self._set_idle()
                elif event == "error":
                    self.write_log(str(payload))
                    self.status.configure(text="Erro")
                    self._set_loading(False)
                    self._set_idle()
                    messagebox.showerror("PHOTOMOVE", str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _set_idle(self) -> None:
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def open_screenshots(self) -> None:
        window = ctk.CTkToplevel(self.root) if ctk else tk.Toplevel(self.root)
        window.title("PHOTOMOVE | Screenshots do celular")
        window.geometry("850x560")
        path_var = tk.StringVar(value=self.output_path.get())
        top = self.widget(window, "Frame")
        top.pack(fill="x", padx=12, pady=12)
        self.widget(top, "Entry", textvariable=path_var).pack(side="left", fill="x", expand=True)
        items_frame = self.widget(window, "ScrollableFrame") if ctk else tk.Frame(window)
        items_frame.pack(fill="both", expand=True, padx=12)
        selected: list[tuple[Path, tk.BooleanVar]] = []

        def scan() -> None:
            for child in items_frame.winfo_children():
                child.destroy()
            selected.clear()
            root = Path(path_var.get().strip())
            if not root.is_dir():
                messagebox.showerror("Pasta inválida", "Selecione uma pasta válida.", parent=window)
                return
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in FOTOS and self._is_screenshot(path):
                    variable = tk.BooleanVar(value=True)
                    selected.append((path, variable))
                    self.widget(items_frame, "CheckBox", text=str(path), variable=variable).pack(anchor="w", padx=8, pady=2)
            self.widget(items_frame, "Label", text=f"{len(selected):,} screenshot(s) encontrados.").pack(anchor="w", pady=8)

        def select_all(value: bool) -> None:
            for _, variable in selected:
                variable.set(value)

        self.widget(top, "Button", text="🔎 Procurar", command=scan).pack(side="left", padx=6)
        self.widget(top, "Button", text="Marcar todos", command=lambda: select_all(True)).pack(side="left")
        self.widget(top, "Button", text="Desmarcar todos", command=lambda: select_all(False)).pack(side="left", padx=6)
        self.widget(window, "Button", text="Enviar selecionados para a Lixeira", command=lambda: self._delete_screenshots(selected, window)).pack(pady=12)

    @staticmethod
    def _is_screenshot(path: Path) -> bool:
        name = path.name.lower()
        keywords = ("screenshot", "screen_shot", "captura de tela", "captura_de_tela", "スクリーンショット")
        if any(keyword in name for keyword in keywords):
            return True
        if Image is None:
            return False
        try:
            with Image.open(path) as image:
                tags = ExifTags.TAGS if ExifTags else {}
                values = [str(value).lower() for key, value in image.getexif().items() if tags.get(key) in {"Software", "ImageDescription", "Make", "Model"}]
                return any("screenshot" in value or "screen capture" in value for value in values)
        except (OSError, ValueError, SyntaxError):
            return False

    def _delete_screenshots(self, selected: list[tuple[Path, tk.BooleanVar]], window) -> None:
        chosen = [path for path, variable in selected if variable.get()]
        if not chosen or not messagebox.askyesno("Confirmar", f"Enviar {len(chosen)} arquivo(s) para a Lixeira?", parent=window or self.root):
            return
        self._set_loading(True, "Enviando screenshots para a Lixeira", 0)
        threading.Thread(target=self._delete_screenshots_worker, args=(chosen,), daemon=True).start()

    def _delete_screenshots_worker(self, chosen: list[Path]) -> None:
        errors = 0
        for index, path in enumerate(chosen, 1):
            try:
                recycle_file(path)
            except OSError:
                errors += 1
            self.events.put(("screenshot_delete_progress", (index / len(chosen), errors)))
        self.events.put(("screenshot_delete_done", (len(chosen), errors)))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    PhotoMoveApp().run()
