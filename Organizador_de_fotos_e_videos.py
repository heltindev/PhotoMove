import os
import re
import json
import shutil
import time
import hashlib
import ctypes
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# ============================================================
# CONFIGURAÇÃO
# ============================================================

ORIGEM = Path(
    r"D:\Takeout"
)

DESTINO = Path(
    r"D:\FOTOS e VIDEOS"
)

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


# ============================================================
# EXTENSÕES
# ============================================================

EXTENSOES_FOTOS = {
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png", ".webp", ".avif", ".gif", ".bmp",
    ".tif", ".tiff",
    ".heic", ".heif", ".heics", ".heifs",
    ".jp2", ".j2k", ".jpf", ".jpx", ".jpm", ".mj2",

    # RAW
    ".raw", ".dng",
    ".cr2", ".cr3",
    ".nef", ".nrw",
    ".arw", ".srf", ".sr2",
    ".orf",
    ".rw2",
    ".raf",
    ".pef",
    ".rwl",
    ".3fr",
    ".iiq",
    ".kdc",
    ".dcr",
    ".erf",
    ".x3f",
}

EXTENSOES_VIDEOS = {
    ".mp4", ".m4v",
    ".mov", ".qt",
    ".avi",
    ".mkv", ".mk3d",
    ".webm",
    ".wmv", ".asf",
    ".flv", ".f4v",
    ".mpeg", ".mpg", ".mpe", ".mpv",
    ".3gp", ".3g2",
    ".ts", ".mts", ".m2ts", ".m2t",
    ".vob",
    ".ogv", ".ogg",
    ".rm", ".rmvb",
    ".divx",
}

EXTENSOES_MIDIA = (
    EXTENSOES_FOTOS |
    EXTENSOES_VIDEOS
)


# ============================================================
# UTILIDADES
# ============================================================

def tamanho_formatado(valor):

    unidades = [
        "B", "KB", "MB",
        "GB", "TB", "PB"
    ]

    valor = float(valor)

    for unidade in unidades:

        if valor < 1024:

            return f"{valor:.2f} {unidade}"

        valor /= 1024

    return f"{valor:.2f} PB"


def tempo_formatado(segundos):

    if segundos == float("inf"):

        return "--:--:--"

    segundos = max(
        0,
        int(segundos)
    )

    horas = segundos // 3600

    minutos = (
        segundos % 3600
    ) // 60

    segundos = segundos % 60

    return (
        f"{horas:02d}:"
        f"{minutos:02d}:"
        f"{segundos:02d}"
    )


def normalizar_nome(nome):

    return Path(
        str(nome)
    ).name.strip().lower()


# ============================================================
# PROGRESSO
# ============================================================

class Progresso:

    def __init__(
        self,
        total,
        total_bytes
    ):

        self.total = total
        self.total_bytes = total_bytes

        self.atual = 0
        self.bytes_atual = 0

        self.inicio = time.time()

    def atualizar(
        self,
        tamanho=0
    ):

        self.atual += 1
        self.bytes_atual += tamanho

        self.mostrar()

    def concluir(self):
        """Exibe explicitamente 100% mesmo quando a etapa não tem bytes."""

        self.atual = self.total
        self.bytes_atual = self.total_bytes
        self.mostrar()

    def mostrar(self):

        if self.total == 0 and self.total_bytes == 0:
            percentual = 100

        elif self.total_bytes > 0:

            percentual = (
                self.bytes_atual /
                self.total_bytes
            ) * 100

        else:

            percentual = (
                self.atual /
                max(self.total, 1)
            ) * 100

        percentual = min(
            percentual,
            100
        )

        largura = 45

        preenchido = int(
            largura *
            percentual /
            100
        )

        barra = (
            "█" * preenchido +
            "░" * (
                largura -
                preenchido
            )
        )

        decorrido = (
            time.time() -
            self.inicio
        )

        if self.bytes_atual > 0:

            velocidade = (
                self.bytes_atual /
                max(decorrido, 0.001)
            )

            restantes = (
                self.total_bytes -
                self.bytes_atual
            )

            tempo_restante = (
                restantes /
                velocidade
            )

        else:

            velocidade = 0
            tempo_restante = float("inf")

        print(
            "\r"
            f"[{barra}] "
            f"{percentual:6.2f}% "
            f"| {self.atual:,}/{self.total:,} "
            f"| ⏳ {tempo_formatado(tempo_restante)} "
            f"| 🚀 {tamanho_formatado(velocidade)}/s",
            end="",
            flush=True
        )


# ============================================================
# LER TODOS OS JSON
# ============================================================

def ler_todos_json():

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                 1/4 — LENDO JSON                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    arquivos_json = []

    for raiz, _, nomes in os.walk(ORIGEM):

        for nome in nomes:

            if not nome.lower().endswith(".json"):
                continue

            arquivos_json.append(
                Path(raiz) / nome
            )

    print(
        f"📄 JSON encontrados: "
        f"{len(arquivos_json):,}"
    )

    indice = {}

    lidos = 0
    validos = 0
    com_data = 0
    progresso = Progresso(
        len(arquivos_json),
        0
    )

    for json_path in arquivos_json:

        try:

            with open(
                json_path,
                "r",
                encoding="utf-8"
            ) as arquivo:

                dados = json.load(
                    arquivo
                )

            lidos += 1

        except Exception:
            progresso.atualizar()
            continue

        if not isinstance(
            dados,
            dict
        ):

            progresso.atualizar()
            continue

        validos += 1

        timestamp = None

        # ----------------------------------------------------
        # PHOTO TAKEN TIME
        # ----------------------------------------------------

        bloco = dados.get(
            "photoTakenTime"
        )

        if isinstance(
            bloco,
            dict
        ):

            timestamp = bloco.get(
                "timestamp"
            )

        # ----------------------------------------------------
        # CREATION TIME
        # ----------------------------------------------------

        if not timestamp:

            bloco = dados.get(
                "creationTime"
            )

            if isinstance(
                bloco,
                dict
            ):

                timestamp = bloco.get(
                    "timestamp"
                )

        if not timestamp:

            progresso.atualizar()
            continue

        try:

            data = datetime.fromtimestamp(
                int(timestamp)
            )

        except Exception:

            progresso.atualizar()
            continue

        com_data += 1

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = dados.get(
            "title"
        )

        if title:

            nome = normalizar_nome(
                title
            )

            indice[nome] = (
                data,
                json_path
            )

        progresso.atualizar()

    progresso.concluir()

    print(
        f"   JSON lidos      : {lidos:,}"
    )

    print(
        f"   JSON válidos    : {validos:,}"
    )

    print(
        f"   JSON com data   : {com_data:,}"
    )

    print(
        f"   Títulos indexados: {len(indice):,}"
    )

    return indice


# ============================================================
# DATA PELO NOME
# ============================================================

def data_pelo_nome(nome):

    nome = Path(nome).stem

    # --------------------------------------------------------
    # Exemplo:
    # 20190730_112831
    # --------------------------------------------------------

    resultado = re.search(
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        r"(0[1-9]|1[0-2])"
        r"(0[1-9]|[12]\d|3[01])"
        r"[_-]"
        r"([01]\d|2[0-3])"
        r"([0-5]\d)"
        r"([0-5]\d)"
        r"(?!\d)",
        nome
    )

    if resultado:

        try:

            return datetime(
                int(resultado.group(1)),
                int(resultado.group(2)),
                int(resultado.group(3)),
                int(resultado.group(4)),
                int(resultado.group(5)),
                int(resultado.group(6))
            )

        except ValueError:
            pass

    # --------------------------------------------------------
    # Apenas YYYYMMDD
    # --------------------------------------------------------

    resultado = re.search(
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        r"(0[1-9]|1[0-2])"
        r"(0[1-9]|[12]\d|3[01])"
        r"(?!\d)",
        nome
    )

    if resultado:

        try:

            return datetime(
                int(resultado.group(1)),
                int(resultado.group(2)),
                int(resultado.group(3))
            )

        except ValueError:
            pass

    return None


# ============================================================
# DATA PELO NOME DA PASTA
# ============================================================

def data_pela_pasta(caminho):

    for parte in reversed(
        caminho.parts
    ):

        # YYYY_MM_DD

        resultado = re.search(
            r"(?<!\d)"
            r"(19\d{2}|20\d{2})"
            r"[_\-.]"
            r"(0[1-9]|1[0-2])"
            r"[_\-.]"
            r"(0[1-9]|[12]\d|3[01])"
            r"(?!\d)",
            parte
        )

        if resultado:

            try:

                return datetime(
                    int(resultado.group(1)),
                    int(resultado.group(2)),
                    int(resultado.group(3))
                )

            except ValueError:
                pass

        # YYYY_MM

        resultado = re.search(
            r"(?<!\d)"
            r"(19\d{2}|20\d{2})"
            r"[_\-.]"
            r"(0[1-9]|1[0-2])"
            r"(?!\d)",
            parte
        )

        if resultado:

            try:

                return datetime(
                    int(resultado.group(1)),
                    int(resultado.group(2)),
                    1
                )

            except ValueError:
                pass

        # YYYY

        resultado = re.search(
            r"(?<!\d)"
            r"(19\d{2}|20\d{2})"
            r"(?!\d)",
            parte
        )

        if resultado:

            try:

                return datetime(
                    int(resultado.group(1)),
                    1,
                    1
                )

            except ValueError:
                pass

    return None


# ============================================================
# DESCOBRIR DATA
# ============================================================

def descobrir_data(
    arquivo,
    indice
):

    nome = normalizar_nome(
        arquivo.name
    )

    # ========================================================
    # 1 — JSON CORRESPONDENTE
    # ========================================================

    if nome in indice:

        data, json_path = indice[
            nome
        ]

        return (
            data,
            "JSON",
            json_path
        )

    # ========================================================
    # 2 — DATA NO NOME
    #
    # Ex:
    #
    # 20190730_112831.jpg
    #
    # ========================================================

    data = data_pelo_nome(
        arquivo.name
    )

    if data:

        return (
            data,
            "NOME",
            None
        )

    # ========================================================
    # 3 — EXIF
    # ========================================================

    if (
        arquivo.suffix.lower()
        in EXTENSOES_FOTOS
    ):

        try:

            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(
                arquivo
            ) as imagem:

                exif = imagem.getexif()

                if exif:

                    for tag_id, valor in exif.items():

                        tag = TAGS.get(
                            tag_id,
                            ""
                        )

                        if tag not in {
                            "DateTimeOriginal",
                            "DateTimeDigitized",
                            "DateTime"
                        }:

                            continue

                        if not isinstance(
                            valor,
                            str
                        ):

                            continue

                        try:

                            data = datetime.strptime(
                                valor,
                                "%Y:%m:%d %H:%M:%S"
                            )

                            return (
                                data,
                                "EXIF",
                                None
                            )

                        except ValueError:
                            pass

        except Exception:
            pass

    # ========================================================
    # 4 — DATA DA PASTA
    # ========================================================

    data = data_pela_pasta(
        arquivo.parent
    )

    if data:

        return (
            data,
            "PASTA",
            None
        )

    # ========================================================
    # 5 — WINDOWS
    # ========================================================

    try:

        data = datetime.fromtimestamp(
            arquivo.stat().st_mtime
        )

    except (OSError, OverflowError, ValueError):

        data = datetime.now()

    return (
        data,
        "WINDOWS",
        None
    )


# ============================================================
# ALTERAR DATA DO WINDOWS
# ============================================================

def alterar_data(
    arquivo,
    data
):

    """
    Altera as datas de acesso/modificação e, no Windows, a data de criação.

    IMPORTANTE:
    Datas muito antigas (ex.: 1903) podem fazer os.utime() levantar
    OSError [Errno 22] no Windows. Esse erro é tratado aqui para que
    um arquivo antigo não interrompa a organização.
    """

    # --------------------------------------------------------
    # MODIFICAÇÃO + ACESSO
    # --------------------------------------------------------

    try:
        timestamp = data.timestamp()

        # No Windows, timestamps muito antigos podem não ser aceitos
        # pelo os.utime(). Se falhar, seguimos para a data de criação.
        os.utime(
            str(arquivo),
            (timestamp, timestamp)
        )

    except (OSError, OverflowError, ValueError):
        pass

    # --------------------------------------------------------
    # CRIAÇÃO — WINDOWS
    # --------------------------------------------------------

    if os.name != "nt":
        return

    try:
        # FILETIME usa 100 ns desde 1601-01-01 UTC.
        # Fazemos o cálculo diretamente para também suportar datas
        # anteriores a 1970.
        from datetime import timezone

        data_utc = data.replace(tzinfo=None).replace(
            tzinfo=timezone.utc
        )

        segundos_desde_1601 = (
            data_utc - datetime(1601, 1, 1, tzinfo=timezone.utc)
        ).total_seconds()

        if segundos_desde_1601 < 0:
            return

        valor = int(segundos_desde_1601 * 10_000_000)

        low = valor & 0xFFFFFFFF
        high = (valor >> 32) & 0xFFFFFFFF

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", ctypes.c_uint32),
                ("dwHighDateTime", ctypes.c_uint32),
            ]

        filetime = FILETIME(low, high)

        kernel32 = ctypes.WinDLL(
            "kernel32",
            use_last_error=True
        )

        FILE_WRITE_ATTRIBUTES = 0x0100
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        # Define os tipos para o Windows receber o caminho corretamente.
        kernel32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        kernel32.CreateFileW.restype = ctypes.c_void_p

        kernel32.SetFileTime.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.SetFileTime.restype = ctypes.c_int

        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int

        handle = kernel32.CreateFileW(
            str(arquivo),
            FILE_WRITE_ATTRIBUTES,
            0x00000007,  # leitura/escrita/exclusão compartilhadas
            None,
            OPEN_EXISTING,
            0,
            None
        )

        if not handle or handle == INVALID_HANDLE_VALUE:
            return

        try:
            # Mantém a mesma data para criação, acesso e modificação.
            kernel32.SetFileTime(
                handle,
                ctypes.byref(filetime),
                ctypes.byref(filetime),
                ctypes.byref(filetime)
            )
        finally:
            kernel32.CloseHandle(handle)

    except (OSError, OverflowError, ValueError, AttributeError):
        # Falha ao alterar metadados não deve interromper a cópia.
        pass


# ============================================================
# COPIAR ARQUIVO SEM COPIAR METADADOS DO WINDOWS
# ============================================================

def copiar_arquivo_seguro(origem, destino):
    """
    Copia somente o conteúdo do arquivo.

    Não usa shutil.copy2(), porque o copy2() tenta copiar os
    timestamps/metadados do arquivo de origem. No Windows isso pode
    causar [Errno 22] Invalid argument quando a mídia possui uma
    data antiga, como 1903.

    Depois da cópia, alterar_data() aplica a data desejada.
    """

    with open(origem, "rb") as entrada, open(destino, "wb") as saida:
        shutil.copyfileobj(
            entrada,
            saida,
            length=8 * 1024 * 1024
        )

    # Mantém permissões básicas quando possível, sem copiar timestamps.
    try:
        shutil.copymode(origem, destino)
    except (OSError, PermissionError):
        pass


# ============================================================
# ENCONTRAR MÍDIAS
# ============================================================

def encontrar_midias(
    raiz
):

    arquivos = []

    total_bytes = 0

    for pasta, _, nomes in os.walk(
        raiz
    ):

        for nome in nomes:

            caminho = (
                Path(pasta) /
                nome
            )

            if (
                caminho.suffix.lower()
                not in EXTENSOES_MIDIA
            ):

                continue

            try:

                tamanho = (
                    caminho.stat().st_size
                )

            except OSError:

                continue

            arquivos.append(
                (
                    caminho,
                    tamanho
                )
            )

            total_bytes += tamanho

    return (
        arquivos,
        total_bytes
    )


# ============================================================
# ESTRUTURA CORRETA
# ============================================================

def destino_correto(data):

    return (
        DESTINO /
        str(data.year) /
        MESES[data.month]
    )

# ============================================================
# VERIFICAR SE ESTÁ NO LUGAR CERTO
# ============================================================

def esta_no_lugar_certo(
    arquivo,
    data
):

    pasta_certa = destino_correto(
        data
    )

    try:

        return (
            arquivo.parent.resolve()
            ==
            pasta_certa.resolve()
        )

    except Exception:

        return False


# ============================================================
# NOME CORRETO DO ARQUIVO
# ============================================================

def nome_correto(data, arquivo):
    """
    Garante que o arquivo tenha a data no início do nome:
    DD_MM_AAAA.ext

    Exemplo:
        24_05_2026.jpg
        24_05_2026.mp4
    """
    return f"{data.day:02d}_{data.month:02d}_{data.year:04d}{arquivo.suffix.lower()}"


def nome_tem_data_correta(arquivo, data):
    """
    Verifica se o nome já está exatamente no padrão DD_MM_AAAA.ext
    correspondente à data descoberta para o arquivo.
    """
    esperado = nome_correto(data, arquivo)
    return arquivo.name.lower() == esperado.lower()


# ============================================================
# RESOLVER DUPLICADO
# ============================================================

def destino_sem_conflito(
    origem,
    destino
):

    if not destino.exists():

        return destino

    # Mesmo tamanho não significa necessariamente
    # arquivo igual.
    #
    # O hash será usado depois para confirmar.

    contador = 1

    while True:

        novo = (
            destino.parent /
            (
                f"{destino.stem}_"
                f"{contador}"
                f"{destino.suffix}"
            )
        )

        if not novo.exists():

            return novo

        contador += 1


# ============================================================
# HASH DO ARQUIVO
# ============================================================

def calcular_hash(
    arquivo,
    tamanho_bloco=8 * 1024 * 1024
):

    sha256 = hashlib.sha256()

    with open(
        arquivo,
        "rb"
    ) as f:

        while True:

            bloco = f.read(
                tamanho_bloco
            )

            if not bloco:
                break

            sha256.update(
                bloco
            )

    return sha256.hexdigest()


# ============================================================
# DEFINIR DATA DE UM ARQUIVO NO DESTINO
# ============================================================

def data_destino_existente(
    arquivo,
    indice
):

    data, origem, json_path = (
        descobrir_data(
            arquivo,
            indice
        )
    )

    return (
        data,
        origem
    )


# ============================================================
# ORGANIZAR DESTINO EXISTENTE
# ============================================================

def analisar_e_corrigir_destino(
    indice
):

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          🔎 AUDITORIA DA ESTRUTURA FINAL              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    arquivos, total_bytes = (
        encontrar_midias(
            DESTINO
        )
    )

    print(
        f"📦 Mídias encontradas: "
        f"{len(arquivos):,}"
    )

    print(
        f"💾 Tamanho: "
        f"{tamanho_formatado(total_bytes)}"
    )

    print()

    if not arquivos:

        Progresso(0, 0).concluir()
        print(
            "✓ Nenhum arquivo antigo para corrigir."
        )

        return

    copiados = 0
    corretos = 0
    erros = 0

    inicio = time.time()

    progresso = Progresso(
        len(arquivos),
        total_bytes
    )

    print(
        "🔧 Verificando localização e datas..."
    )

    print()

    for arquivo, tamanho in arquivos:

        try:

            data, origem_data, json_path = (
                descobrir_data(
                    arquivo,
                    indice
                )
            )

            pasta_certa = destino_correto(
                data
            )

            pasta_certa.mkdir(
                parents=True,
                exist_ok=True
            )

            # ----------------------------------------------------
            # NOME: DD_MM_AAAA.ext
            # Se estiver errado, o arquivo será renomeado/copiado
            # com o nome correto.
            # ----------------------------------------------------
            nome_certo = nome_correto(data, arquivo)

            if esta_no_lugar_certo(
                arquivo,
                data
            ) and nome_tem_data_correta(
                arquivo,
                data
            ):

                # Está no lugar e com o nome correto.
                alterar_data(
                    arquivo,
                    data
                )

                corretos += 1

            else:

                destino = pasta_certa / nome_certo

                # Se o destino já existir e não for o próprio arquivo,
                # resolve o conflito sem sobrescrever.
                if destino.resolve() == arquivo.resolve():
                    destino_final = destino
                else:
                    destino_final = destino_sem_conflito(
                        arquivo,
                        destino
                    )

                # COPIA o arquivo e mantém o original intacto.
                # Depois o original errado poderá ser removido somente
                # quando ele estiver dentro do DESTINO.
                copiar_arquivo_seguro(
                    arquivo,
                    destino_final
                )

                alterar_data(
                    destino_final,
                    data
                )

                # Se o arquivo original estava dentro do DESTINO,
                # removemos o nome antigo depois da cópia.
                if arquivo.resolve() != destino_final.resolve():
                    try:
                        arquivo.unlink()
                    except OSError:
                        pass

                copiados += 1

        except Exception as erro:

            erros += 1
            print()
            print(f"❌ ERRO: {arquivo}")
            print(f"   Motivo: {erro}")

        progresso.atualizar(
            tamanho
        )

    print()
    print()

    print(
        "✓ Auditoria concluída."
    )

    print(
        f"   Já corretos : {corretos:,}"
    )

    print(
        f"   Reorganizados: {copiados:,}"
    )

    print(
        f"   Erros        : {erros:,}"
    )


# ============================================================
# VERIFICAÇÃO FINAL DA ESTRUTURA
# ============================================================

def verificar_estrutura_final(indice):

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          🔍 VERIFICAÇÃO FINAL DA ESTRUTURA             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    arquivos, total_bytes = encontrar_midias(DESTINO)

    if not arquivos:
        Progresso(0, 0).concluir()
        print("📂 Nenhuma mídia encontrada no destino.")
        return True

    fora_do_lugar = []
    corretos = 0

    inicio = time.time()
    total = len(arquivos)

    for i, (arquivo, tamanho) in enumerate(arquivos, 1):

        try:
            data, _, _ = descobrir_data(arquivo, indice)
            pasta_certa = destino_correto(data)

            if (
                arquivo.parent.resolve() == pasta_certa.resolve()
                and nome_tem_data_correta(arquivo, data)
            ):
                corretos += 1
            else:
                fora_do_lugar.append(
                    (
                        arquivo,
                        f"{pasta_certa}\\{nome_correto(data, arquivo)}"
                    )
                )

        except Exception as erro:
            fora_do_lugar.append((arquivo, f"ERRO: {erro}"))

        percentual = (i / total) * 100
        decorrido = time.time() - inicio
        restante = ((decorrido / i) * (total - i)) if i else 0

        largura = 40
        preenchido = int(largura * percentual / 100)
        barra = "█" * preenchido + "░" * (largura - preenchido)

        print(
            "\r"
            f"🔍 [{barra}] {percentual:6.2f}% "
            f"| {i:,}/{total:,} "
            f"| ⏳ {tempo_formatado(restante)}",
            end="",
            flush=True
        )

    if total:
        print(
            "\r"
            f"🔍 [{'█' * 40}] 100.00% "
            f"| {total:,}/{total:,} "
            "| ⏳ 00:00:00",
            end="",
            flush=True
        )

    print()
    print()

    if not fora_do_lugar:
        print("✅ TUDO CERTO!")
        print(f"📁 {corretos:,} arquivos estão em ANO\\MÊS e com nome DD_MM_AAAA.")
        return True

    print("⚠️ Ainda existem arquivos fora da estrutura correta:")
    print(f"   ✅ Corretos: {corretos:,}")
    print(f"   ❌ Fora do lugar: {len(fora_do_lugar):,}")
    print()

    for arquivo, esperado in fora_do_lugar[:50]:
        print(f"❌ {arquivo}")
        print(f"   ➜ Esperado: {esperado}")

    if len(fora_do_lugar) > 50:
        print(f"... e mais {len(fora_do_lugar) - 50:,} arquivos.")

    return False


# ============================================================
# REMOVER PASTAS VAZIAS
# ============================================================

def remover_pastas_vazias():

    removidas = 0

    # Caminha de baixo para cima para conseguir remover também
    # pastas-pai que ficaram vazias depois da limpeza.
    todas = sorted(
        [
            p
            for p in DESTINO.rglob("*")
            if p.is_dir()
        ],
        key=lambda p: len(p.parts),
        reverse=True
    )

    progresso = Progresso(
        len(todas),
        0
    )

    for pasta in todas:

        try:

            if not any(pasta.iterdir()):

                pasta.rmdir()
                removidas += 1

        except Exception:
            pass

        progresso.atualizar()

    progresso.concluir()
    return removidas

# ============================================================
# DETECTAR DUPLICADOS
# ============================================================

def remover_duplicados():

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║               DUPLICADOS                                ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    arquivos, total_bytes = (
        encontrar_midias(
            DESTINO
        )
    )

    print(
        f"🔎 Analisando {len(arquivos):,} arquivos..."
    )

    print(
        "🧬 Calculando hashes SHA-256..."
    )

    print()

    inicio = time.time()

    # Primeiro agrupa por tamanho.
    # Arquivos de tamanhos diferentes
    # nunca podem ser idênticos.

    por_tamanho = defaultdict(list)

    for arquivo, tamanho in arquivos:

        por_tamanho[
            tamanho
        ].append(
            arquivo
        )

    candidatos = []

    for tamanho, lista in (
        por_tamanho.items()
    ):

        if len(lista) > 1:

            candidatos.extend(
                lista
            )

    print(
        f"📌 Candidatos por tamanho: "
        f"{len(candidatos):,}"
    )

    if not candidatos:

        Progresso(0, 0).concluir()
        print(
            "✓ Nenhum duplicado encontrado."
        )

        return

    hashes = {}

    duplicados = []

    for i, arquivo in enumerate(
        candidatos,
        1
    ):

        try:

            hash_arquivo = calcular_hash(
                arquivo
            )

            if hash_arquivo in hashes:

                duplicados.append(
                    (
                        arquivo,
                        hashes[hash_arquivo]
                    )
                )

            else:

                hashes[
                    hash_arquivo
                ] = arquivo

        except Exception:
            pass

        percentual = (
            i /
            len(candidatos)
        ) * 100

        decorrido = (
            time.time() -
            inicio
        )

        if i > 0:

            restante = (
                decorrido /
                i
            ) * (
                len(candidatos) -
                i
            )

        else:

            restante = 0

        print(
            "\r"
            f"🧬 Hash: "
            f"{percentual:6.2f}% "
            f"| {i:,}/{len(candidatos):,} "
            f"| ⏳ {tempo_formatado(restante)}",
            end="",
            flush=True
        )

    print(
        "\r"
        f"🧬 Hash: {'█' * 40} 100.00% "
        f"| {len(candidatos):,}/{len(candidatos):,} "
        "| ⏳ 00:00:00",
        end="",
        flush=True
    )

    print()
    print()

    print(
        f"♻️ Duplicados encontrados: "
        f"{len(duplicados):,}"
    )

    recopiados = 0
    progresso_remocao = Progresso(
        len(duplicados),
        0
    )

    for duplicado, original in duplicados:

        try:

            duplicado.unlink()

            recopiados += 1

        except Exception:
            pass
        progresso_remocao.atualizar()

    progresso_remocao.concluir()

    print(
        f"🗑️ Duplicados removidos: "
        f"{recopiados:,}"
    )


# ============================================================
# SALVAR LOG
# ============================================================

def salvar_log(
    erros
):

    if not erros:
        return

    log = (
        DESTINO /
        "ARQUIVOS_COM_ERRO.txt"
    )

    with open(
        log,
        "w",
        encoding="utf-8"
    ) as f:

        for arquivo, erro in erros:

            f.write(
                "ARQUIVO:\n"
            )

            f.write(
                f"{arquivo}\n"
            )

            f.write(
                "\nERRO:\n"
            )

            f.write(
                f"{erro}\n"
            )

            f.write(
                "\n"
                + "-" * 80 +
                "\n"
            )

    print()
    print(
        f"📄 Log de erros: {log}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "╔══════════════════════════════════════════════════════════╗"
    )
    print(
        "║                                                          ║"
    )
    print(
        "║              📸 PHOTO COPY PYTHON 🎥                    ║"
    )
    print(
        "║                                                          ║"
    )
    print(
        "║        GOOGLE TAKEOUT → ORGANIZAÇÃO POR DATA            ║"
    )
    print(
        "║                                                          ║"
    )
    print(
        "╚══════════════════════════════════════════════════════════╝"
    )

    print()

    print(
        "📥 ORIGEM:"
    )

    print(
        ORIGEM
    )

    print()

    print(
        "📤 DESTINO:"
    )

    print(
        DESTINO
    )

    print()

    if not ORIGEM.exists():

        print(
            "❌ A origem não existe."
        )

        input(
            "\nENTER para sair..."
        )

        return

    DESTINO.mkdir(
        parents=True,
        exist_ok=True
    )

    # ========================================================
    # 1 — LER TODOS OS JSON
    # ========================================================

    indice = ler_todos_json()

    # ========================================================
    # 2 — ORGANIZAR O QUE JÁ EXISTE
    # ========================================================

    analisar_e_corrigir_destino(
        indice
    )

    # ========================================================
    # 3 — LER MÍDIAS DA ORIGEM
    # ========================================================

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              2/4 — MÍDIAS DA ORIGEM                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    arquivos, total_bytes = (
        encontrar_midias(
            ORIGEM
        )
    )

    print(
        f"📦 Arquivos encontrados: "
        f"{len(arquivos):,}"
    )

    print(
        f"💾 Tamanho total: "
        f"{tamanho_formatado(total_bytes)}"
    )

    print()

    if not arquivos:

        Progresso(0, 0).concluir()
        print(
            "✓ Nenhuma mídia restante na origem."
        )

    else:

        # ====================================================
        # 4 — CONFIRMAÇÃO
        # ====================================================

        print(
            "⚠️ O programa irá:"
        )

        print(
            "   📋 COPIAR os arquivos (sem apagar a origem)"
        )

        print(
            "   📅 Usar os JSON quando houver correspondência"
        )

        print(
            "   🕐 Corrigir as datas dos arquivos"
        )

        print(
        "   📂 Organizar como ANO\\MM - MÊS "
        "(01 - JANEIRO, 02 - FEVEREIRO, ...)"
        )

        print(
        "   🏷️ Renomear como DD_MM_AAAA.ext"
        )

        print(
            "   🧹 Corrigir arquivos já existentes no destino (local, nome e data)"
        )

        print(
            "   ♻️ Remover duplicados idênticos APENAS DO DESTINO"
        )

        print()

        print(
            "Exemplo:"
        )

        print(
            r"D:\FOTOS e VIDEOS\2018\11 - NOVEMBRO"
        )

        print()

        confirmacao = input(
            "Digite COPIAR para continuar: "
        ).strip().upper()

        if confirmacao != "COPIAR":

            print(
                "\n❌ Cancelado."
            )

            input(
                "\nENTER para sair..."
            )

            return

        # ====================================================
        # TRANSFERÊNCIA
        # ====================================================

        print()
        print(
            "╔══════════════════════════════════════════════════════════╗"
        )
        print(
            "║              3/4 — COPIANDO                            ║"
        )
        print(
            "╚══════════════════════════════════════════════════════════╝"
        )
        print()

        progresso = Progresso(
            len(arquivos),
            total_bytes
        )

        copiados = 0
        erros = []

        via_json = 0
        via_nome = 0
        via_exif = 0
        via_pasta = 0
        via_windows = 0

        inicio = time.time()

        for arquivo, tamanho in arquivos:

            try:

                # --------------------------------------------
                # DATA
                # --------------------------------------------

                (
                    data,
                    origem_data,
                    json_path
                ) = descobrir_data(
                    arquivo,
                    indice
                )

                if origem_data == "JSON":

                    via_json += 1

                elif origem_data == "NOME":

                    via_nome += 1

                elif origem_data == "EXIF":

                    via_exif += 1

                elif origem_data == "PASTA":

                    via_pasta += 1

                else:

                    via_windows += 1

                # --------------------------------------------
                # DESTINO
                # --------------------------------------------

                pasta = destino_correto(
                    data
                )

                pasta.mkdir(
                    parents=True,
                    exist_ok=True
                )

                # Nome final obrigatório: DD_MM_AAAA.ext
                destino = (
                    pasta /
                    nome_correto(data, arquivo)
                )

                destino = destino_sem_conflito(
                    arquivo,
                    destino
                )

                # --------------------------------------------
                # COPIAR
                # --------------------------------------------

                # COPIA o arquivo e mantém o original intacto (NÃO MOVE).
                copiar_arquivo_seguro(
                    arquivo,
                    destino
                )

                # --------------------------------------------
                # CORRIGIR DATA
                # --------------------------------------------

                alterar_data(
                    destino,
                    data
                )

                copiados += 1

            except Exception as erro:

                erros.append(
                    (
                        str(arquivo),
                        str(erro)
                    )
                )

                print()
                print(f"❌ ERRO AO COPIAR: {arquivo}")
                print(f"   Motivo: {erro}")

            progresso.atualizar(
                tamanho
            )

        print()
        print()

        print(
            "📋 Copiados:"
            f" {copiados:,}"
        )

        print(
            f"❌ Erros: {len(erros):,}"
        )

        print()

        print(
            "📅 FONTES DAS DATAS"
        )

        print(
            f"   JSON     : {via_json:,}"
        )

        print(
            f"   Nome     : {via_nome:,}"
        )

        print(
            f"   EXIF     : {via_exif:,}"
        )

        print(
            f"   Pasta    : {via_pasta:,}"
        )

        print(
            f"   Windows  : {via_windows:,}"
        )

        salvar_log(
            erros
        )

    # ========================================================
    # 4 — DUPLICADOS + LIMPEZA
    # ========================================================

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              4/4 — LIMPEZA FINAL                       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    remover_duplicados()

    # --------------------------------------------------------
    # PASTAS VAZIAS
    # --------------------------------------------------------

    print()
    print(
        "🧹 Removendo pastas vazias/erradas após a cópia..."
    )

    removidas = remover_pastas_vazias()

    print(
        f"✓ Pastas vazias removidas: "
        f"{removidas:,}"
    )

    # ========================================================
    # VERIFICAÇÃO FINAL
    # ========================================================

    verificar_estrutura_final(indice)

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print(
        "╔══════════════════════════════════════════════════════════╗"
    )
    print(
        "║                    🎉 FINALIZADO                       ║"
    )
    print(
        "╚══════════════════════════════════════════════════════════╝"
    )

    print()

    print(
        "📁 Estrutura final:"
    )

    print(
        r"D:\FOTOS e VIDEOS\AAAA\MM - MÊS"
    )

    print()

    print(
        "Exemplo:"
    )

    print(
        r"D:\FOTOS e VIDEOS\2018\11 - NOVEMBRO"
    )

    print()

    print(
        "✓ JSON analisados antes da transferência"
    )

    print(
        "✓ Arquivos copiados"
    )

    print(
        "✓ Datas corrigidas"
    )

    print(
        "✓ Estrutura final ANO\\MM - MÊS verificada"
    )

    print(
        "✓ Pastas vazias removidas"
    )

    print(
        "✓ Duplicados idênticos removidos"
    )

    print()

    input(
        "Pressione ENTER para fechar..."
    )


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()
