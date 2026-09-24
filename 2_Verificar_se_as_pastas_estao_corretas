import os
import re
import shutil
import time
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DESTINO = Path(r"D:\FOTOS e VIDEOS")


MESES = {
    1: "01 - JANEIRO",
    2: "02 - FEVEREIRO",
    3: "03 - MARÇO",
    4: "04 - ABRIL",
    5: "05 - MAIO",
    6: "06 - JUNHO",
    7: "07 - JULHO",
    8: "08 - AGOSTO",
    9: "09 - SETEMBRO",
    10: "10 - OUTUBRO",
    11: "11 - NOVEMBRO",
    12: "12 - DEZEMBRO",
}


EXTENSOES = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".avif", ".gif",
    ".bmp", ".tif", ".tiff", ".heic", ".heif", ".heics", ".heifs",
    ".jp2", ".j2k", ".jpf", ".jpx", ".jpm", ".mj2",
    ".raw", ".dng", ".cr2", ".cr3", ".nef", ".nrw", ".arw",
    ".srf", ".sr2", ".orf", ".rw2", ".raf", ".pef", ".rwl",
    ".3fr", ".iiq", ".kdc", ".dcr", ".erf", ".x3f",

    ".mp4", ".m4v", ".mov", ".qt", ".avi", ".mkv", ".mk3d",
    ".webm", ".wmv", ".asf", ".flv", ".f4v", ".mpeg", ".mpg",
    ".mpe", ".mpv", ".3gp", ".3g2", ".ts", ".mts", ".m2ts",
    ".m2t", ".vob", ".ogv", ".ogg", ".rm", ".rmvb", ".divx"
}


# ============================================================
# BARRA DE PROGRESSO
# ============================================================

def formatar_tempo(segundos):
    """
    Converte segundos em um formato amigável.
    """

    if segundos is None or segundos < 0:
        return "--:--"

    segundos = int(segundos)

    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas > 0:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

    return f"{minutos:02d}:{segundos:02d}"


def barra_progresso(atual, total, inicio, largura=40):
    """
    Exibe uma barra de progresso com:
    - percentual
    - arquivos processados
    - velocidade
    - tempo restante
    """

    if total <= 0:
        return

    percentual = atual / total

    preenchido = int(largura * percentual)
    vazio = largura - preenchido

    barra = "█" * preenchido + "░" * vazio

    tempo_decorrido = time.time() - inicio

    if atual > 0 and tempo_decorrido > 0:
        velocidade = atual / tempo_decorrido
        restante = (total - atual) / velocidade
    else:
        velocidade = 0
        restante = None

    print(
        f"\r[{barra}] "
        f"{percentual * 100:6.2f}% "
        f"| {atual:,}/{total:,} "
        f"| {velocidade:,.1f} arq/s "
        f"| restante: {formatar_tempo(restante)}",
        end="",
        flush=True
    )

    if atual >= total:
        print()


# ============================================================
# DATA / NOME
# ============================================================

def nome_data(data):
    return f"{data.day:02d}_{data.month:02d}_{data.year:04d}"


def pasta_correta(data):
    return DESTINO / str(data.year) / MESES[data.month]


def nome_esta_correto(arquivo, data):
    """
    Aceita:
        24_05_2026.jpg

    Também aceita:
        24_05_2026_1.jpg
        24_05_2026_2.jpg

    Isso evita conflito quando existem vários arquivos
    com exatamente a mesma data.
    """

    padrao = rf"{re.escape(nome_data(data))}(?:_\d+)?"

    return bool(
        re.fullmatch(
            padrao,
            arquivo.stem,
            re.IGNORECASE
        )
    )


# ============================================================
# DESCOBRIR DATA PELO NOME
# ============================================================

def data_do_nome(nome):

    stem = Path(nome).stem

    padroes = [

        # DD-MM-AAAA
        (
            r"(?<!\d)(\d{2})[_\-.](\d{2})[_\-.](\d{4})(?!\d)",
            lambda m: (
                int(m.group(3)),
                int(m.group(2)),
                int(m.group(1))
            )
        ),

        # AAAA-MM-DD
        (
            r"(?<!\d)(19\d{2}|20\d{2})[_\-.](\d{2})[_\-.](\d{2})(?!\d)",
            lambda m: (
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3))
            )
        ),

        # AAAAMMDD
        (
            r"(?<!\d)(19\d{2}|20\d{2})"
            r"(0[1-9]|1[0-2])"
            r"(0[1-9]|[12]\d|3[01])"
            r"(?:[_\-.]?\d{6})?(?!\d)",

            lambda m: (
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3))
            )
        )
    ]

    for padrao, conversao in padroes:

        match = re.search(padrao, stem)

        if match:

            try:
                ano, mes, dia = conversao(match)

                return datetime(
                    ano,
                    mes,
                    dia
                )

            except ValueError:
                pass

    return None


# ============================================================
# DATA EXIF
# ============================================================

def data_exif(arquivo):

    try:

        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(arquivo) as img:

            exif = img.getexif()

            for tag_id, valor in exif.items():

                tag = TAGS.get(tag_id, "")

                if (
                    tag in {
                        "DateTimeOriginal",
                        "DateTimeDigitized",
                        "DateTime"
                    }
                    and isinstance(valor, str)
                ):

                    try:

                        return datetime.strptime(
                            valor,
                            "%Y:%m:%d %H:%M:%S"
                        )

                    except ValueError:
                        pass

    except Exception:
        pass

    return None


# ============================================================
# DATA PELA PASTA
# ============================================================

def data_pasta(arquivo):

    partes = list(arquivo.parent.parts)

    # --------------------------------------------------------
    # Procura datas como:
    #
    # 24-05-2026
    # 24_05_2026
    # 24.05.2026
    # --------------------------------------------------------

    for parte in reversed(partes):

        match = re.search(
            r"(?<!\d)"
            r"(19\d{2}|20\d{2})"
            r"[_\-.]"
            r"(0[1-9]|1[0-2])"
            r"[_\-.]"
            r"(0[1-9]|[12]\d|3[01])"
            r"(?!\d)",
            parte
        )

        if match:

            try:

                return datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3))
                )

            except ValueError:
                pass

    # --------------------------------------------------------
    # Procura estrutura:
    #
    # 2026
    # 05 - MAIO
    # --------------------------------------------------------

    for i, parte in enumerate(partes):

        if re.fullmatch(
            r"(19\d{2}|20\d{2})",
            parte
        ):

            if i + 1 < len(partes):

                ano = int(parte)

                mes_pasta = partes[i + 1].upper()

                for numero, nome in MESES.items():

                    if mes_pasta == nome:

                        return datetime(
                            ano,
                            numero,
                            1
                        )

    return None


# ============================================================
# DESCOBRIR DATA
# ============================================================

def descobrir_data(arquivo):

    fontes = [

        (
            "NOME",
            lambda: data_do_nome(
                arquivo.name
            )
        ),

        (
            "EXIF",
            lambda: data_exif(
                arquivo
            )
        ),

        (
            "PASTA",
            lambda: data_pasta(
                arquivo
            )
        )
    ]

    for fonte, funcao in fontes:

        try:

            data = funcao()

            if data:
                return data, fonte

        except Exception:
            pass

    # --------------------------------------------------------
    # Último recurso:
    # data de modificação do Windows
    # --------------------------------------------------------

    try:

        return (
            datetime.fromtimestamp(
                arquivo.stat().st_mtime
            ),
            "WINDOWS"
        )

    except Exception:

        return (
            datetime.now(),
            "SISTEMA"
        )


# ============================================================
# ENCONTRAR MÍDIAS
# ============================================================

def encontrar_midias():

    arquivos = []

    if not DESTINO.exists():
        return arquivos

    print("🔎 Procurando fotos e vídeos...")

    inicio = time.time()

    try:

        for raiz, _, nomes in os.walk(DESTINO):

            for nome in nomes:

                caminho = Path(raiz) / nome

                if caminho.suffix.lower() not in EXTENSOES:
                    continue

                try:

                    if caminho.is_file():
                        arquivos.append(caminho)

                except OSError:
                    pass

    except KeyboardInterrupt:

        print("\n\n⚠️ Operação interrompida pelo usuário.")

        return arquivos

    tempo = time.time() - inicio

    print(
        f"✅ Busca concluída: "
        f"{len(arquivos):,} arquivos "
        f"em {formatar_tempo(tempo)}.\n"
    )

    return arquivos


# ============================================================
# VERIFICAÇÃO
# ============================================================

def verificar():

    print("\n" + "=" * 72)
    print("1/3 — VERIFICAÇÃO")
    print("=" * 72 + "\n")

    problemas = []

    arquivos = encontrar_midias()

    total = len(arquivos)

    corretos = 0

    inicio = time.time()

    print("📊 Verificando arquivos...\n")

    for indice, arquivo in enumerate(arquivos, 1):

        try:

            data, fonte = descobrir_data(arquivo)

            pasta = pasta_correta(data)

            nome = (
                nome_data(data)
                + arquivo.suffix.lower()
            )

            pasta_ok = (
                arquivo.parent.resolve()
                == pasta.resolve()
            )

            nome_ok = nome_esta_correto(
                arquivo,
                data
            )

            if pasta_ok and nome_ok:

                corretos += 1

            else:

                problemas.append(
                    (
                        arquivo,
                        data,
                        fonte,
                        pasta,
                        nome
                    )
                )

        except Exception as e:

            print(
                f"\n❌ Erro ao verificar: "
                f"{arquivo}\n"
                f"   {e}\n"
            )

        barra_progresso(
            indice,
            total,
            inicio
        )

    print()

    print(f"📁 Arquivos encontrados : {total:,}")
    print(f"✅ Corretos             : {corretos:,}")
    print(f"⚠️ Precisam correção    : {len(problemas):,}\n")

    if problemas:

        print("PRIMEIROS PROBLEMAS ENCONTRADOS:\n")

        for (
            arquivo,
            data,
            fonte,
            pasta,
            nome
        ) in problemas[:100]:

            print(f"❌ {arquivo}")

            print(
                f"   Data encontrada : "
                f"{data:%d/%m/%Y} ({fonte})"
            )

            print(
                f"   Novo local      : "
                f"{pasta / nome}\n"
            )

        if len(problemas) > 100:

            print(
                f"... e mais "
                f"{len(problemas) - 100:,} arquivos.\n"
            )

    return problemas


# ============================================================
# ENCONTRAR DESTINO LIVRE
# ============================================================

def destino_livre(destino):

    if not destino.exists():
        return destino

    contador = 1

    while True:

        novo = (
            destino.parent
            / f"{destino.stem}_{contador}{destino.suffix}"
        )

        if not novo.exists():
            return novo

        contador += 1


# ============================================================
# CORRIGIR
# ============================================================

def corrigir(problemas):

    print("\n" + "=" * 72)
    print("2/3 — MOVENDO E RENOMEANDO")
    print("=" * 72 + "\n")

    total = len(problemas)

    feitos = 0
    erros = 0

    inicio = time.time()

    for indice, (
        origem,
        data,
        fonte,
        pasta,
        nome
    ) in enumerate(problemas, 1):

        try:

            pasta.mkdir(
                parents=True,
                exist_ok=True
            )

            destino = pasta / nome

            # ------------------------------------------------
            # Se o arquivo já estiver exatamente no destino
            # ------------------------------------------------

            if (
                destino.resolve()
                == origem.resolve()
            ):

                feitos += 1

            else:

                destino = destino_livre(
                    destino
                )

                shutil.move(
                    str(origem),
                    str(destino)
                )

                feitos += 1

                print(
                    f"\n📦 [{indice:,}/{total:,}] "
                    f"{origem.name} → {destino.name}"
                )

        except Exception as e:

            erros += 1

            print(
                f"\n❌ ERRO: {origem}"
                f"\n   {e}\n"
            )

        barra_progresso(
            indice,
            total,
            inicio
        )

    print()

    print(
        f"✅ Movidos/renomeados: "
        f"{feitos:,}"
    )

    print(
        f"❌ Erros: {erros:,}"
    )


# ============================================================
# REMOVER PASTAS VAZIAS
# ============================================================

def remover_pastas_vazias():

    print("\n" + "=" * 72)
    print("3/3 — REMOVENDO PASTAS VAZIAS")
    print("=" * 72 + "\n")

    try:

        pastas = sorted(
            [
                p
                for p in DESTINO.rglob("*")
                if p.is_dir()
            ],
            key=lambda p: len(p.parts),
            reverse=True
        )

    except Exception:

        pastas = []

    total = len(pastas)

    removidas = 0

    inicio = time.time()

    if total == 0:

        print("Nenhuma pasta encontrada.\n")
        return

    for indice, pasta in enumerate(
        pastas,
        1
    ):

        try:

            if not any(pasta.iterdir()):

                pasta.rmdir()

                removidas += 1

                print(
                    f"\n🗑️ Removida: {pasta}"
                )

        except OSError:
            pass

        barra_progresso(
            indice,
            total,
            inicio
        )

    print()

    print(
        f"🗑️ Pastas vazias removidas: "
        f"{removidas:,}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n╔════════════════════════════════════════════════════════════════════╗"
    )

    print(
        "║       ORGANIZADOR — FOTOS E VÍDEOS POR DATA                      ║"
    )

    print(
        "╚════════════════════════════════════════════════════════════════════╝\n"
    )

    print(
        f"📁 Pasta principal:\n"
        f"   {DESTINO}\n"
    )

    print(
        "📂 Estrutura final:"
    )

    print(
        r"   D:\FOTOS e VIDEOS\2026\05 - MAIO\24_05_2026.jpg"
    )

    print(
        r"   D:\FOTOS e VIDEOS\2026\05 - MAIO\24_05_2026.mp4"
    )

    print()

    if not DESTINO.exists():

        print(
            "❌ A pasta não existe."
        )

        input(
            "\nPressione ENTER para fechar..."
        )

        return

    # --------------------------------------------------------
    # 1 — VERIFICAÇÃO
    # --------------------------------------------------------

    problemas = verificar()

    # --------------------------------------------------------
    # 2 — CORREÇÃO
    # --------------------------------------------------------

    if problemas:

        print(
            "\n⚠️ Foram encontrados arquivos "
            "que precisam ser corrigidos."
        )

        resposta = input(
            "\nDigite CORRIGIR para executar "
            "as alterações: "
        ).strip().upper()

        if resposta != "CORRIGIR":

            print(
                "\n❌ Operação cancelada."
            )

            input(
                "\nPressione ENTER para fechar..."
            )

            return

        corrigir(problemas)

    else:

        print(
            "✅ Tudo já está correto."
        )

    # --------------------------------------------------------
    # 3 — LIMPEZA
    # --------------------------------------------------------

    remover_pastas_vazias()

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print(
        "\n" + "=" * 72
    )

    print(
        "🎉 FINALIZADO"
    )

    print(
        "=" * 72
    )

    print(
        "\nExemplo da estrutura final:"
    )

    print(
        r"D:\FOTOS e VIDEOS\2026\01 - JANEIRO\24_01_2026.jpg"
    )

    print(
        r"D:\FOTOS e VIDEOS\2026\05 - MAIO\24_05_2026.jpg"
    )

    print(
        r"D:\FOTOS e VIDEOS\2026\12 - DEZEMBRO\24_12_2026.mp4"
    )

    input(
        "\nPressione ENTER para fechar..."
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()
