import os
import re
import shutil
from pathlib import Path
from datetime import datetime

DESTINO = Path(r"D:\FOTOS e VIDEOS")

MESES = {
    1:"JANEIRO", 2:"FEVEREIRO", 3:"MARÇO", 4:"ABRIL",
    5:"MAIO", 6:"JUNHO", 7:"JULHO", 8:"AGOSTO",
    9:"SETEMBRO", 10:"OUTUBRO", 11:"NOVEMBRO", 12:"DEZEMBRO"
}

EXTENSOES = {
    ".jpg",".jpeg",".jpe",".jfif",".png",".webp",".avif",".gif",".bmp",
    ".tif",".tiff",".heic",".heif",".heics",".heifs",".jp2",".j2k",".jpf",
    ".jpx",".jpm",".mj2",".raw",".dng",".cr2",".cr3",".nef",".nrw",".arw",
    ".srf",".sr2",".orf",".rw2",".raf",".pef",".rwl",".3fr",".iiq",".kdc",
    ".dcr",".erf",".x3f",".mp4",".m4v",".mov",".qt",".avi",".mkv",".mk3d",
    ".webm",".wmv",".asf",".flv",".f4v",".mpeg",".mpg",".mpe",".mpv",
    ".3gp",".3g2",".ts",".mts",".m2ts",".m2t",".vob",".ogv",".ogg",
    ".rm",".rmvb",".divx"
}

def nome_data(data):
    return f"{data.day:02d}_{data.month:02d}_{data.year:04d}"

def pasta_correta(data):
    return DESTINO / str(data.year) / MESES[data.month]

def nome_esta_correto(arquivo, data):
    return bool(re.fullmatch(
        rf"{re.escape(nome_data(data))}(?:_\d+)?",
        arquivo.stem,
        re.IGNORECASE
    ))

def data_do_nome(nome):
    stem = Path(nome).stem
    padroes = [
        (r"(?<!\d)(\d{2})[_\-.](\d{2})[_\-.](\d{4})(?!\d)",
         lambda m: (int(m.group(3)),int(m.group(2)),int(m.group(1)))),
        (r"(?<!\d)(19\d{2}|20\d{2})[_\-.](\d{2})[_\-.](\d{2})(?!\d)",
         lambda m: (int(m.group(1)),int(m.group(2)),int(m.group(3)))),
        (r"(?<!\d)(19\d{2}|20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:[_\-.]?\d{6})?(?!\d)",
         lambda m: (int(m.group(1)),int(m.group(2)),int(m.group(3))))
    ]
    for padrao, conv in padroes:
        m = re.search(padrao, stem)
        if m:
            try:
                a, mth, d = conv(m)
                return datetime(a,mth,d)
            except ValueError:
                pass
    return None

def data_exif(arquivo):
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        with Image.open(arquivo) as img:
            exif = img.getexif()
            for tag_id, valor in exif.items():
                tag = TAGS.get(tag_id, "")
                if tag in {"DateTimeOriginal","DateTimeDigitized","DateTime"} and isinstance(valor,str):
                    try:
                        return datetime.strptime(valor,"%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
    except Exception:
        pass
    return None

def data_pasta(arquivo):
    partes = list(arquivo.parent.parts)
    for parte in reversed(partes):
        m = re.search(r"(?<!\d)(19\d{2}|20\d{2})[_\-.](0[1-9]|1[0-2])[_\-.](0[1-9]|[12]\d|3[01])(?!\d)", parte)
        if m:
            try:
                return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)))
            except ValueError:
                pass

    for i, parte in enumerate(partes):
        if re.fullmatch(r"(19\d{2}|20\d{2})", parte) and i + 1 < len(partes):
            ano = int(parte)
            mes = partes[i+1].upper()
            for n, nome in MESES.items():
                if mes == nome:
                    return datetime(ano,n,1)
    return None

def descobrir_data(arquivo):
    for fonte, funcao in [
        ("NOME", lambda: data_do_nome(arquivo.name)),
        ("EXIF", lambda: data_exif(arquivo)),
        ("PASTA", lambda: data_pasta(arquivo))
    ]:
        data = funcao()
        if data:
            return data, fonte

    return datetime.fromtimestamp(arquivo.stat().st_mtime), "WINDOWS"

def encontrar_midias():
    arquivos = []
    if not DESTINO.exists():
        return arquivos
    for raiz, _, nomes in os.walk(DESTINO):
        for nome in nomes:
            p = Path(raiz) / nome
            if p.suffix.lower() in EXTENSOES:
                try:
                    if p.is_file():
                        arquivos.append(p)
                except OSError:
                    pass
    return arquivos

def verificar():
    print("\n" + "="*72)
    print("1/3 — VERIFICAÇÃO")
    print("="*72 + "\n")

    problemas = []
    arquivos = encontrar_midias()
    corretos = 0

    for arquivo in arquivos:
        data, fonte = descobrir_data(arquivo)
        pasta = pasta_correta(data)
        nome = nome_data(data) + arquivo.suffix.lower()

        pasta_ok = arquivo.parent.resolve() == pasta.resolve()
        nome_ok = nome_esta_correto(arquivo,data)

        if pasta_ok and nome_ok:
            corretos += 1
        else:
            problemas.append((arquivo,data,fonte,pasta,nome))

    print(f"Arquivos encontrados : {len(arquivos):,}")
    print(f"Corretos             : {corretos:,}")
    print(f"Precisam correção    : {len(problemas):,}\n")

    for arquivo,data,fonte,pasta,nome in problemas[:100]:
        print(f"❌ {arquivo}")
        print(f"   Data encontrada : {data:%d/%m/%Y} ({fonte})")
        print(f"   Novo local      : {pasta / nome}\n")

    if len(problemas) > 100:
        print(f"... e mais {len(problemas)-100:,} arquivos.\n")

    return problemas

def destino_livre(destino):
    if not destino.exists():
        return destino
    i = 1
    while True:
        novo = destino.parent / f"{destino.stem}_{i}{destino.suffix}"
        if not novo.exists():
            return novo
        i += 1

def corrigir(problemas):
    print("\n" + "="*72)
    print("2/3 — MOVENDO E RENOMEANDO")
    print("="*72 + "\n")

    feitos = erros = 0

    for i,(origem,data,fonte,pasta,nome) in enumerate(problemas,1):
        try:
            pasta.mkdir(parents=True,exist_ok=True)
            destino = pasta / nome

            if destino.resolve() != origem.resolve():
                destino = destino_livre(destino)
                print(f"[{i}/{len(problemas)}] {origem.name} -> {destino.name}")
                shutil.move(str(origem),str(destino))
                feitos += 1
        except Exception as e:
            erros += 1
            print(f"❌ ERRO: {origem}\n   {e}\n")

    print(f"\nMovidos/renomeados: {feitos:,}")
    print(f"Erros: {erros:,}")

def remover_pastas_vazias():
    print("\n" + "="*72)
    print("3/3 — REMOVENDO PASTAS VAZIAS")
    print("="*72 + "\n")

    removidas = 0
    pastas = sorted(
        [p for p in DESTINO.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True
    )

    for pasta in pastas:
        try:
            if not any(pasta.iterdir()):
                pasta.rmdir()
                print(f"🗑️ {pasta}")
                removidas += 1
        except OSError:
            pass

    print(f"\nPastas vazias removidas: {removidas:,}")

def main():
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║       ORGANIZADOR — PASTAS + NOMES COM DATA                       ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    print(f"📁 Verificando: {DESTINO}\n")

    if not DESTINO.exists():
        print("❌ A pasta não existe.")
        input("\nENTER para fechar...")
        return

    problemas = verificar()

    if problemas:
        resposta = input("Digite CORRIGIR para executar as alterações: ").strip().upper()
        if resposta != "CORRIGIR":
            print("\n❌ Cancelado.")
            input("\nENTER para fechar...")
            return
        corrigir(problemas)
    else:
        print("✅ Tudo já está correto.")

    remover_pastas_vazias()

    print("\n" + "="*72)
    print("🎉 FINALIZADO")
    print("="*72)
    print(r"\nExemplo final:")
    print(r"D:\FOTOS e VIDEOS\2026\MAIO\24_05_2026.jpg")
    print(r"D:\FOTOS e VIDEOS\2026\MAIO\24_05_2026.mp4")

    input("\nPressione ENTER para fechar...")

if __name__ == "__main__":
    main()
