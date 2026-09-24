"""Analisa fotos e videos e remove somente os arquivos corrompidos."""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    Image = None
    UnidentifiedImageError = OSError


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
@dataclass(frozen=True)
class MediaFile:
    source: Path
    kind: str


@dataclass(frozen=True)
class ResultEvent:
    analyzed: int
    corrupt: int
    deleted: int
    failures: list[str]
    corrupt_sources: list[Path]


@dataclass(frozen=True)
class ProgressEvent:
    current: int
    total: int
    message: str


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = (
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft/WinGet/Packages/Gyan.FFmpeg.Shared_Msix64__8wekyb3d8bbwe/ffmpeg.exe",
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def scan_files(input_dir: Path) -> list[MediaFile]:
    files: list[MediaFile] = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.casefold()
        if suffix in PHOTO_EXTENSIONS:
            files.append(MediaFile(path, "foto"))
        elif suffix in VIDEO_EXTENSIONS:
            files.append(MediaFile(path, "video"))
    return sorted(files, key=lambda item: str(item.source).casefold())


def validate_photo(source: Path) -> None:
    if Image is None:
        raise RuntimeError("A biblioteca Pillow nao esta instalada.")
    try:
        with Image.open(source) as image:
            image.verify()
    except UnidentifiedImageError as error:
        raise RuntimeError("imagem invalida ou corrompida") from error
    except (OSError, ValueError) as error:
        raise RuntimeError(f"imagem corrompida: {error}") from error


def has_image_signature(source: Path) -> bool:
    """Confere se existe uma assinatura conhecida de imagem no arquivo."""
    try:
        header = source.read_bytes()[:32]
    except OSError as error:
        raise RuntimeError(f"nao foi possivel ler o arquivo: {error}") from error
    signatures = (
        b"\xff\xd8\xff",  # JPEG
        b"\x89PNG\r\n\x1a\n",
        b"GIF87a",
        b"GIF89a",
        b"BM",  # BMP
        b"II*\x00",  # TIFF little-endian
        b"MM\x00*",  # TIFF big-endian
        b"RIFF",  # WEBP/AVI
    )
    return any(header.startswith(signature) for signature in signatures)


def validate_video(source: Path, ffmpeg: str) -> None:
    command = [
        ffmpeg, "-v", "error", "-i", str(source), "-map", "0:v:0",
        "-map", "0:a?", "-f", "null", "-",
    ]
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "video invalido ou corrompido")


def process_all(
    input_dir: Path,
    report: Callable[[int, int, str], None],
    stop_event: threading.Event,
) -> ResultEvent:
    files = scan_files(input_dir)
    ffmpeg = find_ffmpeg()
    failures: list[str] = []
    corrupt_sources: list[Path] = []
    analyzed = corrupt = 0

    for index, media in enumerate(files, start=1):
        if stop_event.is_set():
            break
        analyzed += 1
        report(index - 1, len(files), f"🔎 Analisando: {media.source.name}")
        try:
            if media.kind == "foto":
                validate_photo(media.source)
            elif ffmpeg is None:
                raise RuntimeError("FFmpeg nao encontrado para analisar videos")
            else:
                validate_video(media.source, ffmpeg)
        except (OSError, RuntimeError, ValueError) as error:
            corrupt += 1
            corrupt_sources.append(media.source)
            report(index, len(files), f"⚠️ Corrompido: {media.source.name} ({error})")
        else:
            report(index, len(files), f"✅ Saudavel: {media.source.name}")
    return ResultEvent(analyzed, corrupt, 0, failures, corrupt_sources)


class RecoveryApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("🧹 Limpeza de Fotos e Videos Corrompidos")
        self.root.geometry("820x620")
        self.root.minsize(720, 520)
        self.events: queue.Queue[ProgressEvent | ResultEvent] = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.input_var = tk.StringVar(value=r"D:\FOTOS e VIDEOS")
        self.status_var = tk.StringVar(value="Pronto para analisar a pasta.")
        self.progress_var = tk.DoubleVar(value=0)
        self._build_ui()
        self.root.after(100, self._process_events)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame, text="🧹 Limpeza de Fotos e Videos Corrompidos",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Escolha a pasta que sera analisada. Somente arquivos corrompidos serao excluidos.",
        ).pack(anchor="w", pady=(4, 18))
        self._path_row(
            frame,
            "📂 Pasta para limpar:",
            self.input_var,
            self._choose_input,
        )
        ttk.Label(
            frame,
            text="Arquivos saudaveis nao serao alterados. Os corrompidos serao listados e excluidos apos sua confirmacao.",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Separator(frame).pack(fill="x", pady=18)
        ttk.Label(frame, textvariable=self.status_var, wraplength=760).pack(anchor="w")
        ttk.Progressbar(
            frame, variable=self.progress_var, maximum=100
        ).pack(fill="x", ipady=8, pady=(8, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=14)
        self.start_button = ttk.Button(
            buttons, text="▶️ ANALISAR E LIMPAR", command=self.start
        )
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            buttons, text="⏹️ Parar", command=self.stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=8)
        log_frame = ttk.LabelFrame(frame, text="📋 Andamento e arquivos corrompidos")
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=14, state="disabled", wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _path_row(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=24).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(row, text="Procurar...", command=command).pack(
            side="left", padx=(8, 0)
        )

    def _choose_input(self) -> None:
        selected = filedialog.askdirectory(
            title="Escolha a pasta que deseja limpar",
            initialdir=self.input_var.get(),
        )
        if selected:
            self.input_var.set(selected)

    def start(self) -> None:
        if self.running:
            return
        input_dir = Path(self.input_var.get().strip())
        if not input_dir.is_dir():
            messagebox.showerror("Pasta invalida", "Escolha uma pasta de entrada existente.")
            return
        self.running = True
        self.stop_event.clear()
        self.progress_var.set(0)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._write_log("🚀 Iniciando analise dos arquivos...")
        threading.Thread(
            target=self._worker, args=(input_dir,), daemon=True
        ).start()

    def stop(self) -> None:
        if self.running:
            self.stop_event.set()
            self.status_var.set("⏹️ Parando com seguranca...")

    def _worker(self, input_dir: Path) -> None:
        result = process_all(input_dir, self._report, self.stop_event)
        self.events.put(result)

    def _report(self, current: int, total: int, message: str) -> None:
        self.events.put(ProgressEvent(current, total, message))

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if isinstance(event, ProgressEvent):
                    percent = 0 if not event.total else event.current * 100 / event.total
                    self.progress_var.set(percent)
                    self.status_var.set(event.message)
                    self._write_log(event.message)
                else:
                    self.running = False
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.progress_var.set(100 if event.analyzed else 0)
                    self._finish(event)
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)

    def _finish(self, result: ResultEvent) -> None:
        self._write_log(
            f"📊 Processo concluido: {result.analyzed} analisados, "
            f"{result.corrupt} corrompidos."
        )
        if result.corrupt_sources and messagebox.askyesno(
            "Confirmar exclusao",
            f"{len(result.corrupt_sources)} arquivo(s) foram identificados "
            "como corrompidos.\n\nExcluir esses arquivos agora?",
        ):
            deleted = 0
            for source in result.corrupt_sources:
                try:
                    source.unlink()
                    deleted += 1
                    self._write_log(f"🗑️ Excluido: {source.name}")
                except OSError as error:
                    result.failures.append(f"{source}: {error}")
                    self._write_log(f"❌ Nao foi possivel excluir {source}: {error}")
            result = ResultEvent(
                result.analyzed, result.corrupt, deleted,
                result.failures, result.corrupt_sources,
            )
        if result.failures:
            self._write_log("⚠️ Falhas ao excluir:")
            for error in result.failures[:20]:
                self._write_log(f"   {error}")
        self.status_var.set(
            f"Concluido: {result.deleted} corrompidos excluidos; "
            f"{result.corrupt - result.deleted} mantidos."
        )
        messagebox.showinfo(
            "Processo concluido",
            f"Analisados: {result.analyzed}\n"
            f"Corrompidos: {result.corrupt}\n"
            f"Excluidos: {result.deleted}\n"
            f"Falhas ao excluir: {len(result.failures)}\n\n"
            "Arquivos saudaveis nao foram alterados.",
        )

    def _write_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    RecoveryApp().run()
