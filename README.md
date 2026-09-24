# 📸 PhotoMove

Organizador automático de fotos e vídeos por **data (Ano/Mês)**, feito em Python para lidar com bagunças de backups, exports do Google Fotos (Takeout) e pastas desorganizadas no Windows.

O PhotoMove lê metadados (JSON do Google Takeout, EXIF, nome do arquivo, nome da pasta ou data do sistema), copia os arquivos para uma estrutura limpa `ANO\MÊS`, renomeia tudo no padrão `DD_MM_AAAA.ext`, corrige as datas do Windows, remove duplicados idênticos, identifica screenshots e ainda converte mídias para PNG/MP4.

---

> ## 🚧 PROJETO EM CONSTRUÇÃO
> Os scripts numerados (`1_` a `7_`) ainda estão sendo unificados. Hoje cada um funciona de forma **independente**, mas a ideia final é que o **`6_programa.py`** reúna todas as funções em um único programa com interface gráfica (e, futuramente, um `.exe` gerado pelo `7_compilar.py`). Até lá, algumas telas/funções do `6_programa.py` podem estar incompletas ou em teste.

---

## 📌 About

**Desenvolvido por:** [@heltonleiras](https://github.com/heltonleiras)

---

## 🧩 Scripts do projeto

### 1️⃣ [`1_Organizador_de_fotos_e_videos.py`](https://github.com/heltindev/photomove/blob/main/1_Organizador_de_fotos_e_videos.py)

Script **principal** de linha de comando, responsável por toda a organização e cópia dos arquivos. Ele:

- Lê **todos os arquivos `.json`** de uma pasta de origem (formato do **Google Takeout**), indexando as datas (`photoTakenTime` ou `creationTime`) pelo título do arquivo.
- Varre a pasta de origem em busca de fotos e vídeos (formatos comuns e RAW de câmeras: JPG, PNG, HEIC, CR2, NEF, ARW, DNG, MP4, MOV, MKV, etc.).
- Descobre a data de cada arquivo seguindo uma ordem de prioridade:
  1. **JSON** correspondente (Google Takeout)
  2. **Nome do arquivo** (ex: `20190730_112831.jpg`)
  3. **EXIF** da imagem
  4. **Nome da pasta** onde o arquivo está (ex: `2020_05`)
  5. **Data do sistema** (Windows) como último recurso
- **Copia** (nunca move nem apaga a origem) os arquivos para `D:\FOTOS e VIDEOS\ANO\MÊS`.
- Renomeia cada arquivo para o padrão `DD_MM_AAAA.ext`.
- Corrige as datas de criação/modificação/acesso do arquivo no Windows (via API do `kernel32` usando `ctypes`), inclusive para datas muito antigas.
- **Audita e corrige** arquivos que já estão na pasta de destino, movendo/renomeando o que estiver fora do padrão.
- Calcula **hash SHA-256** para detectar e remover **duplicados idênticos** (apenas dentro do destino).
- Remove pastas vazias e gera um log de erros (`ARQUIVOS_COM_ERRO.txt`), caso algum arquivo falhe.
- Mostra barra de progresso no terminal com velocidade e tempo estimado.

⚠️ Antes de copiar, o script pede confirmação digitando `COPIAR`.

### 2️⃣ [`2_Verificar_se_as_pastas_estao_corretas`](https://github.com/heltindev/photomove/blob/main/2_Verificar_se_as_pastas_estao_corretas)

**Auditor/corretor independente**, usado para conferir se a pasta de destino (`D:\FOTOS e VIDEOS`) já está 100% organizada, sem precisar rodar o processo completo de cópia. Ele:

- Varre a pasta de destino em busca de mídias.
- Descobre a data de cada arquivo (nome do arquivo → EXIF → nome da pasta → data do Windows).
- Verifica se o arquivo está na pasta certa (`ANO\MÊS`) e com o nome certo (`DD_MM_AAAA.ext`, aceitando sufixos `_1`, `_2`, etc. para evitar conflitos).
- Lista todos os arquivos fora do padrão, mostrando onde deveriam estar.
- Se houver problemas, pede confirmação digitando `CORRIGIR` para então **mover e renomear** os arquivos automaticamente.
- Remove pastas vazias ao final.

Use este script quando quiser apenas **validar** a organização já feita, sem reler todos os JSON do Google Takeout novamente.

### 3️⃣ [`3_Remover_itens_duplicados.py`](https://github.com/heltindev/photomove/blob/main/3_Remover_itens_duplicados.py)

Aplicativo com **interface gráfica (Tkinter)** para localizar e remover duplicatas exatas de fotos e vídeos, com revisão visual antes de qualquer exclusão. Ele:

- Agrupa arquivos por tamanho e depois por **hash SHA-256** para achar duplicatas com conteúdo idêntico.
- Mostra miniaturas de cada grupo de duplicados, permitindo escolher qual arquivo é o "principal" (mantido).
- Envia os demais arquivos do grupo para a **Lixeira do Windows** (nunca apaga permanentemente), somente após confirmação.
- Tem um modo **"Limpar tudo automaticamente"**, que mantém o primeiro arquivo de cada grupo e envia os demais para a Lixeira, com barra de progresso.
- Nunca remove nada sem confirmação do usuário.

### 4️⃣ [`4_remover_screenshots.py`](https://github.com/heltindev/photomove/blob/main/4_remover_screenshots.py)

Script de linha de comando que localiza e remove **capturas de tela (screenshots)** com base em **metadados internos da imagem** (EXIF/propriedades), não no nome do arquivo. Ele:

- Varre uma pasta (recursivamente por padrão) procurando imagens.
- Analisa metadados/EXIF em busca de termos como `screenshot`, `screen capture`, `captura de tela`, etc.
- Lista todos os candidatos encontrados antes de apagar qualquer coisa.
- Pede confirmação explícita (`SIM`/`NAO`) antes de apagar os arquivos identificados.

### 5️⃣ [`5_converter_arquivos.py`](https://github.com/heltindev/photomove/blob/main/5_converter_arquivos.py)

Aplicativo com **interface gráfica (Tkinter)** para converter fotos em **PNG** e vídeos em **MP4**. Ele:

- Nunca altera os arquivos originais — gera as conversões em uma pasta de saída separada, mantendo a estrutura de subpastas.
- Converte fotos usando Pillow (corrigindo orientação EXIF) e vídeos usando **FFmpeg** (precisa estar instalado/no PATH).
- Preserva metadados e as datas de acesso/modificação dos arquivos convertidos.
- Permite dividir a saída em subpastas com uma quantidade configurável de arquivos por pasta, em ordem cronológica.
- Tem opção de pular arquivos já convertidos e mostra um log detalhado do progresso.

### 6️⃣ [`6_programa.py`](https://github.com/heltindev/photomove/blob/main/6_programa.py) — 🚧 EM CONSTRUÇÃO

Este é o programa que vai **acoplar todos os códigos em 1** só: uma aplicação única com interface gráfica (usando `customtkinter`, com fallback para Tkinter puro) reunindo o organizador de fotos/vídeos e a ferramenta de screenshots em um só lugar, com navegação por abas/menu lateral.

- Já inclui a lógica de organização por data (JSON, nome, EXIF, pasta, Windows), cópia/movimentação, renomeação, ajuste de datas, remoção de duplicados (com envio para a Lixeira) e remoção de pastas vazias — tudo configurável por checkboxes na interface.
- Já inclui uma tela de busca e remoção de screenshots, com seleção manual dos arquivos antes de enviar para a Lixeira.
- **Ainda em desenvolvimento**: é o script mais recente do projeto e pode ter partes incompletas, funções dos scripts `3_`, `4_` e `5_` que ainda não foram totalmente incorporadas, e ajustes de interface pendentes.

Este é o script pensado para virar o executável final do projeto.

### 7️⃣ [`7_compilar.py`](https://github.com/heltindev/photomove/blob/main/7_compilar.py)

Script auxiliar para **gerar o executável do PHOTOMOVE** (`6_programa.py`) usando **PyInstaller**. Ele:

- Limpa builds anteriores (`build/PHOTOMOVE` e pastas temporárias).
- Empacota o programa em modo `--onedir` e `--windowed` (sem console), incluindo as dependências do `customtkinter`.
- Gera o executável final em `build\PHOTOMOVE\PHOTOMOVE.exe`.

---

## ⚙️ Requisitos

- **Python 3.9 ou superior**
- **Windows** (o ajuste de data de criação e o envio para a Lixeira usam APIs nativas do Windows via `ctypes`; em outros sistemas essas partes são ignoradas ou não funcionam)
- **FFmpeg** instalado e no PATH (apenas necessário para o `5_converter_arquivos.py` converter vídeos)
- Dependências Python listadas em [`requirements.txt`](https://github.com/heltindev/photomove/blob/main/requirements.txt):
  - `customtkinter>=5.2`
  - `Pillow>=10.0`
  - `pyinstaller>=6.0`

## 🐍 Como rodar (é necessário baixar/criar o `.venv`)

> ⚠️ **É obrigatório criar e ativar um ambiente virtual (`.venv`) antes de rodar qualquer script deste projeto.**

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
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 5. Configure os caminhos de ORIGEM e DESTINO diretamente no início do script
#    1_Organizador_de_fotos_e_videos.py (variáveis ORIGEM e DESTINO)

# 6. Rode o organizador principal
.venv\Scripts\python.exe 1_Organizador_de_fotos_e_videos.py

# 7. (Opcional) Rode a verificação/correção da estrutura final
.venv\Scripts\python.exe 2_Verificar_se_as_pastas_estao_corretas

# 8. (Opcional) Rode as demais ferramentas
.venv\Scripts\python.exe 3_Remover_itens_duplicados.py
.venv\Scripts\python.exe 4_remover_screenshots.py
.venv\Scripts\python.exe 5_converter_arquivos.py

# 9. (Em construção) Programa unificado
.venv\Scripts\python.exe 6_programa.py

# 10. (Opcional) Gerar o executável a partir do programa unificado
.venv\Scripts\python.exe 7_compilar.py
```

---

## 🛣️ Roadmap

- [ ] Finalizar a unificação de todos os scripts dentro do `6_programa.py`.
- [ ] Publicar versão `.exe` gerada pelo `7_compilar.py` para uso sem precisar instalar Python.
- [ ] Revisar e polir a interface gráfica.

---

## 👤 Autor

Projeto desenvolvido por **[@heltonleiras](https://github.com/heltonleiras)**.
