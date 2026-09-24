"""Conversor simples de fotos e videos para PNG e MP4.

Os arquivos originais nunca sao alterados. A estrutura de subpastas e mantida
na pasta de saida para evitar conflitos entre arquivos com o mesmo nome.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".avif", ".gif",
    ".bmp", ".tif", ".tiff", ".heic", ".heif", ".heics", ".heifs",
    ".jp2", ".j2k", ".jpf", ".jpx", ".raw", ".dng", ".cr2", ".cr3",
    ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf", ".rw2", ".raf",
    ".pef", ".rwl", ".3fr", ".iiq", ".kdc", ".dcr", ".erf", ".x3f",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".qt", ".avi", ".mkv", ".mk3d", ".webm",
    ".wmv", ".asf", ".flv", ".f4v", ".mpeg", ".mpg", ".mpe", ".mpv",
    ".3gp", ".3g2", ".ts", ".mts", ".m2ts", ".m2t", ".vob", ".ogv",
    ".ogg", ".rm", ".rmvb", ".divx",
}

DEFAULT_INPUT = r"D:\FOTOS E VIDEOS\2003\01 - JANEIRO"
DEFAULT_OUTPUT = r"D:\CONVERTIDA"
MONTH_NAMES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass(frozen=True)
class ProgressEvent:
    current: int
    total: int
    message: str


@dataclass(frozen=True)
class FinishedEvent:
    converted: int
    skipped: int
    errors: list[str]


def find_ffmpeg() -> Optional[str]:
    """Encontra o FFmpeg no PATH ou em instalacoes comuns do Windows."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        / "Packages" / "Gyan.FFmpeg.Shared_Msix64__8wekyb3d8bbwe"
        / "ffmpeg.exe",
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def scan_files(input_dir: Path) -> list[tuple[Path, str]]:
    """Lista apenas fotos e videos, sem carregar todos os arquivos em memoria."""
    files: list[tuple[Path, str]] = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in PHOTO_EXTENSIONS:
            files.append((path, "foto"))
        elif suffix in VIDEO_EXTENSIONS:
            files.append((path, "video"))
    return files


def media_date(path: Path, kind: str) -> datetime:
    """Obtém a melhor data disponível para ordenar do mais antigo ao mais novo."""
    if kind == "foto" and Image is not None:
        try:
            with Image.open(path) as image:
                exif = image.getexif()
                for tag in (36867, 36868, 306):
                    value = exif.get(tag)
                    if isinstance(value, str):
                        try:
                            return datetime.strptime(value.strip(), "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
        except (OSError, ValueError, SyntaxError):
            pass

    stem = path.stem
    patterns = (
        (r"(?<!\d)(19\d{2}|20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)", (1, 2, 3)),
        (r"(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](19\d{2}|20\d{2})(?!\d)", (3, 2, 1)),
        (r"(?<!\d)(19\d{2})(\d{2})(\d{2})(?!\d)", (1, 2, 3)),
    )
    for pattern, groups in patterns:
        match = re.search(pattern, stem)
        if match:
            try:
                return datetime(
                    int(match.group(groups[0])),
                    int(match.group(groups[1])),
                    int(match.group(groups[2])),
                )
            except ValueError:
                pass

    parts = path.parts
    for index, part in enumerate(parts):
        year_match = re.search(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", part)
        if not year_match or index + 1 >= len(parts):
            continue
        month_part = parts[index + 1].casefold()
        month_match = re.match(r"\s*(\d{1,2})\s*[-_.]\s*([a-zç]+)", month_part)
        month = int(month_match.group(1)) if month_match else MONTH_NAMES.get(month_part.strip())
        if month and 1 <= month <= 12:
            return datetime(int(year_match.group(1)), month, 1)

    # Quando não há EXIF/nome com data, a data de modificação é o fallback.
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except (OSError, ValueError, OverflowError):
        return datetime.max


def output_path(
    source: Path,
    input_dir: Path,
    output_dir: Path,
    kind: str,
    files_per_folder: Optional[int] = None,
    file_index: int = 0,
) -> Path:
    relative = source.relative_to(input_dir)
    extension = ".png" if kind == "foto" else ".mp4"
    destination_root = output_dir
    if files_per_folder:
        folder_number = file_index // files_per_folder + 1
        destination_root /= f"Pasta {folder_number:03d}"
    return (destination_root / relative).with_suffix(extension)


def preserve_file_times(source: Path, destination: Path) -> None:
    """Mantem as datas de acesso e modificacao mostradas nas propriedades."""
    source_stat = source.stat()
    os.utime(
        destination,
        ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
    )


def convert_photo(source: Path, destination: Path) -> None:
    if Image is None or ImageOps is None:
        raise RuntimeError("A biblioteca Pillow nao esta instalada.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        exif = image.getexif()
        image_metadata = {
            key: image.info[key]
            for key in ("icc_profile", "dpi", "xmp")
            if key in image.info
        }
        image = ImageOps.exif_transpose(image)
        if exif:
            # A imagem ja foi girada fisicamente; evita que o visualizador gire
            # novamente ao ler a orientacao EXIF.
            exif[274] = 1
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        if exif:
            image_metadata["exif"] = exif.tobytes()
        image.save(destination, "PNG", **image_metadata)
    preserve_file_times(source, destination)


def convert_video(source: Path, destination: Path, ffmpeg: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-y", "-i", str(source), "-map_metadata", "0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(destination),
    ]
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip().splitlines()[-1] if result.stderr else "FFmpeg falhou.")
    preserve_file_times(source, destination)


def convert_all(
    input_dir: Path,
    output_dir: Path,
    report: Callable[[int, int, str], None],
    stop_event: threading.Event,
    files_per_folder: Optional[int] = None,
) -> tuple[int, int, list[str]]:
    files = scan_files(input_dir)
    files.sort(key=lambda item: (media_date(item[0], item[1]), str(item[0]).casefold()))
    total = len(files)
    converted = 0
    skipped = 0
    errors: list[str] = []
    ffmpeg = find_ffmpeg()
    for index, (source, kind) in enumerate(files, start=1):
        if stop_event.is_set():
            break
        destination = output_path(
            source, input_dir, output_dir, kind, files_per_folder, index - 1
        )
        report(index - 1, total, f"🔎 Analisando: {source.name}")
        try:
            if destination.exists():
                skipped += 1
                report(index, total, f"⏭️ Ja existe: {destination.name}")
                continue
            if kind == "foto":
                convert_photo(source, destination)
            elif ffmpeg is None:
                raise RuntimeError("FFmpeg nao encontrado. Instale o FFmpeg e tente novamente.")
            else:
                convert_video(source, destination, ffmpeg)
            converted += 1
            report(index, total, f"✅ Convertido: {destination.name}")
        except (OSError, RuntimeError, ValueError) as error:
            if destination.exists():
                destination.unlink(missing_ok=True)
            errors.append(f"{source}: {error}")
            report(index, total, f"❌ Erro: {source.name}")
    return converted, skipped, errors


class ConverterApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("🖼️🎬 Conversor de Fotos e Videos")
        self.root.geometry("760x560")
        self.root.minsize(680, 480)
        self.events: queue.Queue[ProgressEvent | FinishedEvent] = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.input_var = tk.StringVar(value=DEFAULT_INPUT)
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT)
        self.split_var = tk.BooleanVar(value=False)
        self.files_per_folder_var = tk.StringVar(value="100")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="👋 Pronto para analisar sua pasta.")
        self._build_ui()
        self.root.after(100, self._process_events)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="🖼️🎬 Conversor de Fotos e Videos", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Fotos viram PNG e videos viram MP4. Metadados e datas sao preservados! 🔒",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 18))
        self._path_row(frame, "📂 Pasta de entrada:", self.input_var, self._choose_input)
        self._path_row(frame, "📁 Pasta de saida:", self.output_var, self._choose_output)
        split_row = ttk.Frame(frame)
        split_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            split_row,
            text="🗂️ Dividir arquivos em pastas",
            variable=self.split_var,
        ).pack(side="left")
        ttk.Label(split_row, text="Quantidade por pasta:").pack(side="left", padx=(20, 5))
        ttk.Entry(split_row, textvariable=self.files_per_folder_var, width=10).pack(side="left")
        ttk.Label(
            frame,
            text="Exemplo: 1000 arquivos com 100 por pasta = 10 pastas. A ordem será cronológica (janeiro → dezembro).",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Separator(frame).pack(fill="x", pady=18)
        ttk.Label(frame, textvariable=self.status_var, wraplength=700).pack(anchor="w", pady=(0, 8))
        self.progress = ttk.Progressbar(frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", ipady=8)
        self.percent_label = ttk.Label(frame, text="0%")
        self.percent_label.pack(anchor="e")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=16)
        self.start_button = ttk.Button(buttons, text="▶️ COMEÇAR CONVERSAO", command=self.start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="⏹️ Parar", command=self.stop, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Label(frame, text="💡 Dica: o FFmpeg e necessario para converter videos para MP4.").pack(anchor="w")
        log_frame = ttk.LabelFrame(frame, text="📋 Andamento")
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.log = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _path_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command: Callable[[], None]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=22).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Procurar...", command=command).pack(side="left", padx=(8, 0))

    def _choose_input(self) -> None:
        selected = filedialog.askdirectory(title="Escolha a pasta com fotos e videos")
        if selected:
            self.input_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Escolha a pasta para os arquivos convertidos")
        if selected:
            self.output_var.set(selected)

    def start(self) -> None:
        if self.running:
            return
        input_dir = Path(self.input_var.get().strip())
        output_dir = Path(self.output_var.get().strip())
        files_per_folder: Optional[int] = None
        if self.split_var.get():
            try:
                files_per_folder = int(self.files_per_folder_var.get().strip())
            except ValueError:
                messagebox.showerror(
                    "❌ Quantidade invalida",
                    "Informe um numero inteiro de arquivos por pasta.",
                )
                return
            if files_per_folder < 1:
                messagebox.showerror(
                    "❌ Quantidade invalida",
                    "A quantidade por pasta precisa ser maior que zero.",
                )
                return
        if not input_dir.is_dir():
            messagebox.showerror("❌ Pasta invalida", "Escolha uma pasta de entrada existente.")
            return
        if input_dir.resolve() == output_dir.resolve():
            messagebox.showerror("❌ Pasta invalida", "A pasta de saida precisa ser diferente da entrada.")
            return
        self.running = True
        self.stop_event.clear()
        self.progress_var.set(0)
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._write_log("🚀 Iniciando analise dos arquivos...")
        threading.Thread(
            target=self._worker,
            args=(input_dir, output_dir, files_per_folder),
            daemon=True,
        ).start()

    def stop(self) -> None:
        if self.running:
            self.stop_event.set()
            self.status_var.set("⏹️ Parando com seguranca...")

    def _worker(
        self,
        input_dir: Path,
        output_dir: Path,
        files_per_folder: Optional[int],
    ) -> None:
        converted, skipped, errors = convert_all(
            input_dir, output_dir, self._report, self.stop_event, files_per_folder
        )
        self.events.put(FinishedEvent(converted, skipped, errors))

    def _report(self, current: int, total: int, message: str) -> None:
        self.events.put(ProgressEvent(current, total, message))

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if isinstance(event, ProgressEvent):
                    percent = 0 if not event.total else event.current * 100 / event.total
                    self.progress_var.set(percent)
                    self.percent_label.configure(text=f"{percent:.0f}%")
                    self.status_var.set(event.message)
                    self._write_log(event.message)
                else:
                    converted, skipped, errors = event.converted, event.skipped, event.errors
                    self.running = False
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    if errors:
                        self.status_var.set(f"⚠️ Finalizado com {len(errors)} erro(s).")
                        self._write_log("⚠️ Alguns arquivos nao puderam ser convertidos:")
                        for error in errors[:20]:
                            self._write_log(f"   {error}")
                        if len(errors) > 20:
                            self._write_log(f"   ... e mais {len(errors) - 20} erro(s).")
                        messagebox.showwarning(
                            "⚠️ Conversao concluida",
                            f"Convertidos: {converted}\nIgnorados: {skipped}\nErros: {len(errors)}\n\nVeja os detalhes na lista de andamento.",
                        )
                    else:
                        self.progress_var.set(100 if converted or skipped else 0)
                        self.percent_label.configure(text=f"{self.progress_var.get():.0f}%")
                        self.status_var.set("🎉 Tudo pronto! Os arquivos estao na pasta de saida.")
                        messagebox.showinfo(
                            "✅ Conversao concluida",
                            f"Convertidos: {converted}\nJa existentes: {skipped}\n\nOs arquivos originais nao foram apagados.",
                        )
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)

    def _write_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    ConverterApp().run()
