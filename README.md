# 📸 PhotoMove

Organizador automático de fotos e vídeos por **data (Ano/Mês)**, feito em Python para lidar com bagunças de backups, exports do Google Fotos (Takeout) e pastas desorganizadas no Windows.

O PhotoMove lê metadados (JSON do Google Takeout, EXIF, nome do arquivo, nome da pasta ou data do sistema), copia os arquivos para uma estrutura limpa `ANO\MÊS`, renomeia tudo no padrão `DD_MM_AAAA.ext`, corrige as datas do Windows e remove duplicados idênticos.

---

## 📌 About

Sem descrição, site ou tópicos definidos ainda.

**Desenvolvido por:** [@heltonleiras](https://github.com/heltonleiras)

> 🚧 Este projeto está em desenvolvimento — atualmente sendo produzida uma versão **.exe** para facilitar o uso por quem não tem Python instalado.

---

## 🧩 Scripts do projeto

### 1️⃣ [`Organizador_de_fotos_e_videos.py`](https://github.com/heltindev/photomove/blob/main/Organizador_de_fotos_e_videos.py)

Este é o script **principal**, responsável por toda a organização e cópia dos arquivos. Ele:

- Lê **todos os arquivos `.json`** de uma pasta de origem (formato do **Google Takeout**), indexando as datas (`photoTakenTime` ou `creationTime`) por título de arquivo.
- Varre a pasta de origem em busca de fotos e vídeos (praticamente todos os formatos comuns e RAW de câmeras: JPG, PNG, HEIC, CR2, NEF, ARW, DNG, MP4, MOV, MKV, etc.).
- Descobre a data de cada arquivo seguindo uma ordem de prioridade:
  1. **JSON** correspondente (Google Takeout)
  2. **Nome do arquivo** (ex: `20190730_112831.jpg`)
  3. **EXIF** da imagem
  4. **Nome da pasta** onde o arquivo está (ex: `2020_05`)
  5. **Data do sistema** (Windows) como último recurso
- **Copia** (nunca move nem apaga a origem) os arquivos para `D:\FOTOS e VIDEOS\ANO\MÊS`.
- Renomeia cada arquivo para o padrão `DD_MM_AAAA.ext`.
- Corrige as datas de criação/modificação/acesso do arquivo no Windows (usando a API do `kernel32` via `ctypes`), inclusive para datas muito antigas.
- Também **audita e corrige** arquivos que já estão na pasta de destino, movendo/renomeando o que estiver fora do padrão.
- Ao final, calcula **hash SHA-256** dos arquivos para detectar e remover **duplicados idênticos** (apenas dentro do destino).
- Remove pastas vazias e gera um log de erros (`ARQUIVOS_COM_ERRO.txt`), caso algum arquivo falhe.
- Mostra uma barra de progresso no terminal com velocidade e tempo estimado.

⚠️ Antes de copiar, o script pede confirmação digitando `COPIAR`.

### 2️⃣ [`verificar_se_as_pastas_estao_corretas.py`](https://github.com/heltindev/photomove/blob/main/verificar_se_as_pastas_estao_corretas.py)

Este script é um **auditor/corretor independente**, usado para conferir se a pasta de destino (`D:\FOTOS e VIDEOS`) já está 100% organizada, sem precisar rodar o processo completo de cópia. Ele:

- Varre a pasta de destino em busca de mídias.
- Para cada arquivo, descobre a data pela mesma lógica (nome do arquivo → EXIF → nome da pasta → data do sistema).
- Verifica se o arquivo está na pasta certa (`ANO\MÊS`) e com o nome certo (`DD_MM_AAAA.ext`).
- Lista todos os arquivos que estão fora do padrão, mostrando onde deveriam estar.
- Se houver problemas, pede confirmação digitando `CORRIGIR` para então **mover e renomear** os arquivos automaticamente.
- Remove pastas vazias ao final.

Use este script quando quiser apenas **validar** a organização já feita, sem reler todos os JSON do Google Takeout novamente.

---

## ⚙️ Requisitos

- Python 3.9 ou superior
- Windows (o ajuste de data de criação usa a API nativa do Windows via `ctypes`; em outros sistemas essa parte é ignorada)
- Biblioteca [Pillow](https://pypi.org/project/Pillow/) (para leitura de EXIF)

## 🐍 Como rodar (usando ambiente virtual `.venv`)

> É necessário criar e ativar um ambiente virtual (`.venv`) antes de rodar os scripts.

```bash
# 1. Clone o repositório
git clone https://github.com/heltindev/photomove.git
cd photomove

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat

# 4. Instale as dependências
pip install Pillow

# 5. Configure os caminhos de ORIGEM e DESTINO diretamente no início do script
#    Organizador_de_fotos_e_videos.py

# 6. Rode o organizador principal
python Organizador_de_fotos_e_videos.py

# 7. (Opcional) Rode a verificação/correção da estrutura final
python verificar_se_as_pastas_estao_corretas.py
```

---

## 🛣️ Roadmap

- [ ] Publicar versão `.exe` (em produção) para uso sem precisar instalar Python.
- [ ] Interface gráfica opcional.

---

## 👤 Autor

Projeto desenvolvido por **[@heltonleiras](https://github.com/heltonleiras)**.
