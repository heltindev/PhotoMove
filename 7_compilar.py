"""Compila o PHOTOMOVE para uma pasta distribuivel no Windows.

Uso:
    .venv\Scripts\python.exe compilar.py

Saida:
    build\PHOTOMOVE\PHOTOMOVE.exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENTRYPOINT = ROOT / "programa.py"
BUILD_DIR = ROOT / "build"
DIST_DIR = BUILD_DIR / "PHOTOMOVE"
WORK_DIR = ROOT / "build_temp"
SPEC_DIR = BUILD_DIR


def remove_directory(path: Path) -> bool:
    if path.exists():
        try:
            shutil.rmtree(path)
        except PermissionError:
            print(f"ERRO: não foi possível limpar {path}.")
            print("Feche o PHOTOMOVE.exe e qualquer janela que esteja usando a build.")
            return False
    return True


def main() -> int:
    if not ENTRYPOINT.is_file():
        print(f"ERRO: arquivo principal não encontrado: {ENTRYPOINT}")
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("ERRO: PyInstaller não está instalado neste ambiente.")
        print(f"Instale com: {sys.executable} -m pip install pyinstaller")
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if not remove_directory(DIST_DIR) or not remove_directory(WORK_DIR):
        return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "PHOTOMOVE",
        "--distpath",
        str(BUILD_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--collect-all",
        "customtkinter",
        str(ENTRYPOINT),
    ]

    icon = ROOT / "icon.ico"
    if icon.is_file():
        command.extend(["--icon", str(icon)])

    print("Compilando PHOTOMOVE...")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        print("ERRO: a compilação falhou.")
        return result.returncode

    executable = DIST_DIR / "PHOTOMOVE.exe"
    if not executable.is_file():
        print(f"ERRO: executável não encontrado em {executable}")
        return 1

    print()
    print("Compilação concluída com sucesso.")
    print(f"Pasta distribuível: {DIST_DIR}")
    print(f"Executável: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
