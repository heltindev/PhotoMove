"""Localiza e remove capturas de tela pelos metadados das imagens.

Depois de analisar, o programa mostra os candidatos e pede confirmacao antes
de apagar qualquer arquivo.

A identificacao nao usa o nome do arquivo. Somente textos gravados nas
propriedades internas da imagem sao considerados.

Dependencia opcional:
    pip install Pillow
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path


EXTENSOES_IMAGEM = {
    # Formatos comuns de imagem.
    ".jpg", ".jpeg", ".jpe", ".jfif", ".jif", ".pjpeg", ".pjp",
    ".png", ".apng", ".webp", ".gif", ".bmp", ".dib", ".tif", ".tiff",
    ".avif", ".jxl", ".qoi", ".ico", ".cur", ".dds", ".tga", ".pcx",
    ".ppm", ".pgm", ".pbm", ".pnm", ".pam", ".sgi", ".rgb", ".rgba",
    ".icns", ".xbm", ".xpm", ".svg", ".svgz",

    # HEIC/HEIF e JPEG 2000.
    ".heic", ".heif", ".heics", ".heifs",
    ".jp2", ".j2k", ".j2c", ".jpc", ".jpf", ".jpx", ".jpm", ".mj2",

    # Camera RAW.
    ".raw", ".dng", ".crw", ".cr2", ".cr3",
    ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".orf", ".rw2", ".raf", ".pef", ".rwl",
    ".3fr", ".iiq", ".kdc", ".dcr", ".erf", ".x3f",
    ".mef", ".mos", ".mrw", ".cap", ".r3d", ".fff",
    ".bay", ".bmq", ".cine", ".cs1", ".dc2", ".dcs", ".drf",
    ".eip", ".k25", ".kc2", ".mdc", ".pxn", ".qtk", ".sti",
}

PALAVRAS_METADATA = (
    "screenshot",
    "screen shot",
    "screen capture",
    "captura de tela",
    "captura_de_tela",
    "android screenshot",
    "ios screenshot",
)

PASTA_PADRAO = Path(r"D:\FOTOS e VIDEOS")


@dataclass(frozen=True)
class Candidato:
    caminho: Path
    motivos: tuple[str, ...]


def formatar_tempo(segundos: float | None) -> str:
    if segundos is None:
        return "--:--"

    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"


def mostrar_progresso(
    etapa: str,
    atual: int,
    total: int,
    inicio: float,
    largura: int = 42,
) -> None:
    """Desenha uma barra visual uniforme para todas as etapas."""

    percentual = 100 if total == 0 else min(atual / total * 100, 100)
    preenchido = round(largura * percentual / 100)
    barra = "█" * preenchido + "░" * (largura - preenchido)
    decorrido = time.monotonic() - inicio

    if atual and decorrido > 0:
        velocidade = atual / decorrido
        restante = (total - atual) / velocidade
    else:
        velocidade = 0
        restante = None

    print(
        f"\r{etapa:<12} [{barra}] {percentual:6.2f}% "
        f"| {atual:,}/{total:,} "
        f"| {velocidade:,.1f} arq/s "
        f"| decorrido {formatar_tempo(decorrido)} "
        f"| restante {formatar_tempo(restante)}",
        end="",
        flush=True,
    )


def encontrar_imagens(pasta: Path, recursivo: bool) -> list[Path]:
    """Retorna somente imagens, sem considerar arquivos de video."""

    arquivos = pasta.rglob("*") if recursivo else pasta.glob("*")
    return sorted(
        (
            caminho for caminho in arquivos
            if caminho.is_file()
            and caminho.suffix.lower() in EXTENSOES_IMAGEM
        ),
        key=lambda caminho: str(caminho).casefold(),
    )


def valores_de_metadados(caminho: Path) -> list[str]:
    """Le nomes e valores textuais das propriedades internas da imagem."""

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        return []

    valores: list[str] = []

    try:
        with Image.open(caminho) as imagem:
            exif = imagem.getexif()
            for tag_id, valor in exif.items():
                nome_tag = TAGS.get(tag_id, str(tag_id))
                valores.append(str(nome_tag))
                if isinstance(valor, bytes):
                    valor = valor.decode("utf-8", errors="ignore")
                if isinstance(valor, str):
                    valores.append(valor)

            for chave, valor in getattr(imagem, "info", {}).items():
                valores.append(str(chave))
                if isinstance(valor, bytes):
                    valor = valor.decode("utf-8", errors="ignore")
                if isinstance(valor, str):
                    valores.append(valor)
    except Exception:
        return []

    return valores


def analisar_imagem(caminho: Path) -> Candidato | None:
    """Identifica captura somente por texto explícito nos metadados."""

    metadados = valores_de_metadados(caminho)
    texto_metadados = " | ".join(metadados).casefold()
    palavras_encontradas = [
        palavra for palavra in PALAVRAS_METADATA
        if palavra in texto_metadados
    ]

    if not palavras_encontradas:
        return None

    return Candidato(
        caminho,
        ("propriedades: " + ", ".join(palavras_encontradas),),
    )


def analisar_pasta(pasta: Path, recursivo: bool) -> tuple[list[Path], list[Candidato]]:
    imagens = encontrar_imagens(pasta, recursivo)
    candidatos: list[Candidato] = []
    inicio = time.monotonic()

    mostrar_progresso("Analisando", 0, len(imagens), inicio)

    for indice, imagem in enumerate(imagens, 1):
        candidato = analisar_imagem(imagem)
        if candidato is not None:
            candidatos.append(candidato)
        mostrar_progresso("Analisando", indice, len(imagens), inicio)

    mostrar_progresso("Analisando", len(imagens), len(imagens), inicio)
    print()
    return imagens, candidatos


def apagar_candidatos(candidatos: list[Candidato]) -> tuple[int, int]:
    removidos = 0
    erros = 0
    inicio = time.monotonic()

    mostrar_progresso("Removendo", 0, len(candidatos), inicio)

    for indice, candidato in enumerate(candidatos, 1):
        try:
            candidato.caminho.unlink()
            removidos += 1
        except OSError as erro:
            erros += 1
            print(f"\nERRO ao remover {candidato.caminho}: {erro}")

        mostrar_progresso("Removendo", indice, len(candidatos), inicio)

    mostrar_progresso("Removendo", len(candidatos), len(candidatos), inicio)
    print()
    return removidos, erros


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analisa imagens e remove capturas de tela identificadas.",
    )
    parser.add_argument(
        "pasta",
        type=Path,
        nargs="?",
        default=PASTA_PADRAO,
        help=f"Pasta que sera analisada (padrao: {PASTA_PADRAO}).",
    )
    parser.add_argument(
        "--apagar",
        action="store_true",
        help="Mantido por compatibilidade; a confirmacao sempre sera solicitada.",
    )
    parser.add_argument(
        "--nao-recursivo",
        action="store_true",
        help="Analisa somente arquivos diretamente dentro da pasta.",
    )
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    pasta = args.pasta.expanduser().resolve()

    if not pasta.is_dir():
        print(f"ERRO: a pasta nao existe ou nao e uma pasta: {pasta}")
        return 1

    try:
        print("\n" + "=" * 118)
        print("🔎 ETAPA 1/2 — ANALISANDO IMAGENS")
        print("=" * 118)
        imagens, candidatos = analisar_pasta(
            pasta,
            recursivo=not args.nao_recursivo,
        )
    except KeyboardInterrupt:
        print("\nOperacao interrompida.")
        return 130

    print(f"Imagens analisadas: {len(imagens):,}")
    print(f"Capturas identificadas: {len(candidatos):,}")

    if not candidatos:
        print("Nenhuma captura de tela identificada.")
        return 0

    print("\nCandidatos:")
    for candidato in candidatos:
        motivos = "; ".join(candidato.motivos)
        print(f" - {candidato.caminho} [{motivos}]")

    print("\n⚠️ ATENÇÃO: estas fotos foram identificadas pelas propriedades internas.")
    print("🛡️ Nenhuma foto será apagada sem a sua confirmação.")

    try:
        resposta = input(
            "\n❓ Deseja apagar essas fotos? Digite SIM ou NAO: "
        ).strip().upper()
    except (EOFError, KeyboardInterrupt):
        print("\n\n🛑 Operação cancelada. Nenhuma foto foi apagada.")
        return 0

    if resposta not in {"SIM", "S", "YES", "Y"}:
        print("\n🛑 Tudo bem! Operação cancelada.")
        print("✅ Nenhuma foto foi apagada.")
        return 0

    print("\n" + "=" * 118)
    print("🗑️ ETAPA 2/2 — APAGANDO SCREENSHOTS")
    print("=" * 118)
    print("⏳ Começando agora... por favor, aguarde.")
    removidos, erros = apagar_candidatos(candidatos)

    print("\n" + "=" * 118)
    if erros == 0:
        print("🎉🎉🎉 SUCESSO! LIMPEZA CONCLUÍDA! 🎉🎉🎉")
    else:
        print("✅ Limpeza concluída com alguns avisos.")
    print("=" * 118)
    print(f"📸 Fotos encontradas: {len(candidatos):,}")
    print(f"🗑️ Fotos removidas com sucesso: {removidos:,}")
    print(f"⚠️ Fotos que não puderam ser removidas: {erros:,}")

    if erros == 0:
        print("🥳 Pronto! Todas as screenshots identificadas foram removidas!")
    else:
        print("ℹ️ Verifique as mensagens de erro exibidas durante a remoção.")

    return 0 if erros == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
