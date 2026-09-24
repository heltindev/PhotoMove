"""Localiza e remove duplicatas exatas de fotos e vídeos com confirmação.

Uso:
    python remover_itens_duplicados.py

O programa nunca remove um arquivo automaticamente. Para cada grupo encontrado,
ele abre os arquivos no aplicativo padrão do Windows e pede confirmação antes
de enviar os duplicados escolhidos para a Lixeira.
"""

from __future__ import annotations

import hashlib
import os
import ctypes
import ctypes.wintypes
import threading
import tkinter as tk
from collections import defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Iterable

try:
    from PIL import Image, ImageEnhance, ImageOps, ImageTk
except ImportError:  # A análise continua funcionando sem miniaturas.
    Image = None
    ImageEnhance = None
    ImageOps = None
    ImageTk = None


EXTENSOES_IMAGEM = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".avif",
}
EXTENSOES_VIDEO = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".m4v",
    ".3gp",
    ".webm",
}
EXTENSOES_SUPORTADAS = EXTENSOES_IMAGEM | EXTENSOES_VIDEO
TAMANHO_BLOCO = 1024 * 1024


def listar_arquivos(pasta: Path) -> Iterable[Path]:
    """Retorna arquivos de mídia da pasta e de suas subpastas."""
    for caminho in pasta.rglob("*"):
        if caminho.is_file() and caminho.suffix.lower() in EXTENSOES_SUPORTADAS:
            yield caminho


def calcular_hash(caminho: Path) -> str:
    """Calcula o SHA-256 sem carregar o arquivo inteiro na memória."""
    sha256 = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while bloco := arquivo.read(TAMANHO_BLOCO):
            sha256.update(bloco)
    return sha256.hexdigest()


def encontrar_duplicatas(
    pasta: Path,
    informar_progresso: Callable[[str], None],
) -> list[list[Path]]:
    """Agrupa arquivos com conteúdo binário idêntico."""
    por_tamanho: dict[int, list[Path]] = defaultdict(list)
    arquivos = list(listar_arquivos(pasta))

    for indice, caminho in enumerate(arquivos, start=1):
        try:
            por_tamanho[caminho.stat().st_size].append(caminho)
        except OSError:
            continue
        informar_progresso(f"Preparando arquivos: {indice}/{len(arquivos)}")

    grupos: list[list[Path]] = []
    candidatos = [grupo for grupo in por_tamanho.values() if len(grupo) > 1]
    total_candidatos = sum(len(grupo) for grupo in candidatos)
    processados = 0

    for grupo in candidatos:
        por_hash: dict[str, list[Path]] = defaultdict(list)
        for caminho in grupo:
            try:
                por_hash[calcular_hash(caminho)].append(caminho)
            except OSError:
                pass
            processados += 1
            informar_progresso(
                f"Comparando conteúdos: {processados}/{total_candidatos}"
            )
        grupos.extend(grupo_duplicado for grupo_duplicado in por_hash.values() if len(grupo_duplicado) > 1)

    return grupos


def abrir_no_windows(caminho: Path) -> None:
    """Abre um arquivo no aplicativo padrão, sem bloquear a janela."""
    os.startfile(caminho)  # type: ignore[attr-defined]


class Aplicacao(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Verificador de fotos e vídeos duplicados")
        self.geometry("900x700")
        self.minsize(650, 520)
        self.grupos: list[list[Path]] = []
        self.grupo_atual = 0
        self.pasta: Path | None = None
        self.indice_principal = 0
        self.imagens_preview: list[Any] = []
        self.cartoes_preview: list[tk.Frame] = []
        self.grupo_visual: list[Path] = []
        self.operacao_em_andamento = False
        self.quadro_carregamento = 0
        self.fonte_titulo = ("Segoe UI", 16, "bold")
        self.fonte_texto = ("Segoe UI", 9, "bold")
        self.fonte_pequena = ("Segoe UI", 8, "bold")
        self._montar_tela()

    def _montar_tela(self) -> None:
        estilo = ttk.Style(self)
        estilo.configure("TButton", font=self.fonte_texto)
        estilo.configure("TLabel", font=self.fonte_texto)
        estilo.configure(
            "Pasta.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10),
            foreground="#123b67", background="#dbeafe",
        )
        estilo.configure(
            "Analisar.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10),
            foreground="#145a32", background="#dcfce7",
        )
        estilo.configure(
            "Lixeira.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 12),
            foreground="#8b1e1e", background="#fee2e2",
        )
        estilo.configure(
            "Automatico.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 12),
            foreground="#7f1d1d", background="#fecaca",
        )
        estilo.configure(
            "Proximo.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 12),
            foreground="#604214", background="#fef3c7",
        )
        ttk.Label(
            self,
            text="VERIFICADOR DE FOTOS E VÍDEOS DUPLICADOS",
            font=self.fonte_titulo,
        ).pack(anchor="w", padx=16, pady=8)
        ttk.Label(
            self,
            text=(
                "A ANÁLISE ENCONTRA SOMENTE ARQUIVOS COM CONTEÚDO EXATAMENTE IGUAL. "
                "VOCÊ REVISA CADA GRUPO ANTES DE APAGAR."
            ),
            font=self.fonte_texto,
            wraplength=710,
        ).pack(anchor="w", padx=16, pady=8)

        controles = ttk.Frame(self)
        controles.pack(fill="x", padx=16, pady=8)
        self.botao_pasta = ttk.Button(
            controles, text="📁  ESCOLHER PASTA", command=self.escolher_pasta,
            style="Pasta.TButton",
        )
        self.botao_pasta.pack(side="left")
        self.botao_analisar = ttk.Button(
            controles, text="🔎  ANALISAR", command=self.iniciar_analise,
            state="disabled", style="Analisar.TButton",
        )
        self.botao_analisar.pack(side="left", padx=8)
        self.pasta_label = ttk.Label(
            controles, text="NENHUMA PASTA ESCOLHIDA", font=self.fonte_texto
        )
        self.pasta_label.pack(side="left", fill="x", expand=True)

        self.progresso = ttk.Progressbar(self, mode="determinate")
        self.progresso.pack(fill="x", padx=16, pady=8)
        self.progresso_label = ttk.Label(
            self, text="⏳ 0%", font=self.fonte_texto
        )
        self.progresso_label.pack(anchor="e", padx=16)
        self.status = ttk.Label(
            self, text="ESCOLHA UMA PASTA PARA COMEÇAR.", font=self.fonte_texto
        )
        self.status.pack(anchor="w", padx=16, pady=8)

        self.preview_area = ttk.Frame(self)
        self.preview_area.pack(fill="both", expand=True, padx=16, pady=8)
        self.preview_canvas = tk.Canvas(
            self.preview_area, height=360, highlightthickness=0,
            background="#f4f4f4",
        )
        self.preview_canvas.pack(side="left", fill="both", expand=True)
        self.preview_scroll = ttk.Scrollbar(
            self.preview_area, orient="vertical", command=self.preview_canvas.yview
        )
        self.preview_scroll.pack(side="right", fill="y")
        self.preview_canvas.configure(yscrollcommand=self.preview_scroll.set)
        self.preview_frame = ttk.Frame(self.preview_canvas)
        self.preview_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_frame, anchor="nw"
        )
        self.preview_frame.bind("<Configure>", self._atualizar_area_previsualizacao)
        self.preview_canvas.bind("<Configure>", self._redimensionar_previsualizacao)
        self.preview_canvas.bind_all("<MouseWheel>", self._rolar_previsualizacao)

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", padx=16, pady=8)
        self.botao_apagar = ttk.Button(
            botoes, text="🗑  ENVIAR DUPLICATAS PARA A LIXEIRA",
            command=self.apagar_duplicatas, state="disabled", style="Lixeira.TButton"
        )
        self.botao_apagar.pack(side="left", padx=8, ipadx=12, ipady=4)
        self.botao_automatico = ttk.Button(
            botoes, text="⚡  LIMPAR TUDO AUTOMATICAMENTE",
            command=self.limpar_tudo_automaticamente,
            state="disabled",
            style="Automatico.TButton",
        )
        self.botao_automatico.pack(side="left", padx=8, ipadx=12, ipady=4)
        self.botao_proximo = ttk.Button(
            botoes, text="➡  PRÓXIMO GRUPO", command=self.proximo_grupo,
            state="disabled", style="Proximo.TButton"
        )
        self.botao_proximo.pack(side="right", ipadx=12, ipady=4)

    def _atualizar_area_previsualizacao(self, evento: tk.Event) -> None:
        del evento
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _redimensionar_previsualizacao(self, evento: tk.Event) -> None:
        largura = max(int(evento.width) - 8, 160)
        self.preview_canvas.itemconfigure(self.preview_window, width=largura)
        self._organizar_cartoes(largura)

    def _organizar_cartoes(self, largura: int) -> None:
        if self.cartoes_preview:
            colunas = max(1, largura // 170)
            for indice, cartao in enumerate(self.cartoes_preview):
                cartao.grid_configure(row=indice // colunas, column=indice % colunas)

    def _rolar_previsualizacao(self, evento: tk.Event) -> None:
        if self.preview_canvas.winfo_exists():
            self.preview_canvas.yview_scroll(-int(evento.delta / 120), "units")

    def escolher_pasta(self) -> None:
        escolhida = filedialog.askdirectory(title="Escolha a pasta para analisar")
        if escolhida:
            self.pasta = Path(escolhida)
            self.pasta_label.configure(text=str(self.pasta))
            self.botao_analisar.configure(state="normal")
            self.status.configure(text="PASTA PRONTA PARA ANÁLISE.")

    def iniciar_analise(self) -> None:
        if self.pasta is None:
            return
        self.botao_analisar.configure(state="disabled")
        self.botao_pasta.configure(state="disabled")
        self.status.configure(text="INICIANDO ANÁLISE...")
        threading.Thread(target=self._analisar_em_segundo_plano, daemon=True).start()

    def _analisar_em_segundo_plano(self) -> None:
        assert self.pasta is not None
        try:
            grupos = encontrar_duplicatas(
                self.pasta,
                self._agendar_status,
            )
        except OSError as erro:
            self.after(0, self._mostrar_erro, f"Não foi possível analisar a pasta:\n{erro}")
            return
        self.after(0, self._analise_concluida, grupos)

    def _agendar_status(self, texto: str) -> None:
        self.after(0, self._atualizar_status, texto)

    def _atualizar_status(self, texto: str) -> None:
        self.status.configure(text=texto)

    def _analise_concluida(self, grupos: list[list[Path]]) -> None:
        self.grupos = grupos
        self.grupo_atual = 0
        self.botao_pasta.configure(state="normal")
        self.botao_analisar.configure(state="normal")
        if not grupos:
            self.status.configure(text="NENHUMA DUPLICATA EXATA FOI ENCONTRADA.")
            self._desabilitar_acoes()
            return
        self.status.configure(
            text=f"{len(grupos)} GRUPO(S) DUPLICADO(S) ENCONTRADO(S)."
        )
        self._mostrar_grupo()

    def _mostrar_grupo(self) -> None:
        grupo = self.grupos[self.grupo_atual]
        self.indice_principal = 0
        self._montar_previsualizacoes(grupo)
        self.status.configure(
            text=f"GRUPO {self.grupo_atual + 1} DE {len(self.grupos)}. "
            "CLIQUE NA MINIATURA QUE DESEJA MANTER; ELA FICA EM DESTAQUE.",
        )
        self.botao_apagar.configure(state="normal" if len(grupo) > 1 else "disabled")
        self.botao_automatico.configure(
            state="normal" if self.grupos else "disabled"
        )
        self.botao_proximo.configure(
            state="normal" if self.grupo_atual < len(self.grupos) - 1 else "disabled"
        )

    def _desabilitar_acoes(self) -> None:
        for botao in (
            self.botao_apagar,
            self.botao_automatico,
            self.botao_proximo,
        ):
            botao.configure(state="disabled")

    def _montar_previsualizacoes(self, grupo: list[Path]) -> None:
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.imagens_preview.clear()
        self.cartoes_preview.clear()
        self.grupo_visual = grupo
        largura = max(self.preview_canvas.winfo_width() - 8, 160)
        colunas = max(1, largura // 170)
        for indice, caminho in enumerate(grupo):
            card = tk.Frame(
                self.preview_frame,
                width=150,
                height=170,
                padx=5,
                pady=5,
                background="#d9f7df" if indice == self.indice_principal else "#eeeeee",
                highlightbackground="#20a046" if indice == self.indice_principal else "#aaaaaa",
                highlightthickness=2 if indice == self.indice_principal else 1,
            )
            card.grid(row=indice // colunas, column=indice % colunas, padx=4, pady=4, sticky="n")
            card.grid_propagate(False)
            self.cartoes_preview.append(card)
            imagem = self._criar_miniatura(caminho, indice == self.indice_principal)
            self.imagens_preview.append(imagem)
            miniatura = tk.Canvas(
                card,
                width=138,
                height=92,
                background="#d9f7df" if indice == self.indice_principal else "#d0d0d0",
                highlightthickness=0,
                cursor="hand2",
            )
            if imagem is not None:
                miniatura.create_image(69, 46, image=imagem)
            else:
                miniatura.create_text(
                    69, 46, text="VÍDEO\nSEM MINIATURA", justify="center",
                    fill="#555555",
                )
            miniatura.bind(
                "<Button-1>",
                lambda evento, i=indice: self._clicar_miniatura(evento, i),
            )
            miniatura.pack(padx=3, pady=3)
            nome = caminho.name.upper()
            if indice == self.indice_principal:
                nome = "★ PRINCIPAL ★\n" + nome
            tk.Label(
                card, text=nome, wraplength=150, justify="center",
                background="#d9f7df" if indice == self.indice_principal else "#eeeeee",
                font=self.fonte_pequena,
            ).pack(fill="x", padx=2, pady=(0, 4))
            ttk.Button(
                card,
                text="🖼  ABRIR FOTO",
                command=lambda arquivo=caminho: self.abrir_foto(arquivo),
            ).pack(fill="x", padx=4, pady=(0, 4))
        self.after_idle(lambda: self._organizar_cartoes(
            max(self.preview_canvas.winfo_width() - 8, 160)
        ))

    def _clicar_miniatura(self, evento: tk.Event, indice: int) -> None:
        del evento
        self._definir_principal(indice)

    def _criar_miniatura(self, caminho: Path, principal: bool) -> Any:
        if (
            Image is None
            or ImageTk is None
            or caminho.suffix.lower() not in EXTENSOES_IMAGEM
        ):
            return None
        try:
            with Image.open(caminho) as original:
                imagem = (
                    ImageOps.exif_transpose(original)
                    if ImageOps is not None
                    else original
                ).convert("RGB")
                imagem.thumbnail((138, 92))
                if not principal and ImageEnhance is not None:
                    imagem = ImageEnhance.Brightness(imagem).enhance(0.42)
                return ImageTk.PhotoImage(imagem)
        except (OSError, ValueError):
            return None

    def _definir_principal(self, indice: int) -> None:
        self.indice_principal = indice
        self._montar_previsualizacoes(self.grupos[self.grupo_atual])
        self.status.configure(
            text="ARQUIVO PRINCIPAL SELECIONADO. OS OUTROS SERÃO OS DUPLICADOS REMOVIDOS.",
        )

    def abrir_foto(self, caminho: Path) -> None:
        try:
            abrir_no_windows(caminho)
        except OSError as erro:
            messagebox.showerror("Erro ao abrir arquivo", f"{erro}")

    def apagar_duplicatas(self) -> None:
        grupo = self.grupos[self.grupo_atual]
        principal = grupo[self.indice_principal]
        selecionados = [caminho for indice, caminho in enumerate(grupo) if indice != self.indice_principal]
        resposta = messagebox.askyesno(
            "Confirmar exclusão",
            f"Manter:\n{principal.name}\n\n"
            f"Enviar os outros {len(selecionados)} arquivo(s) para a Lixeira?\n"
            "Os arquivos não serão apagados permanentemente.",
        )
        if not resposta:
            return
        erros: list[str] = []
        removidos: list[Path] = []
        for caminho in selecionados:
            try:
                enviar_para_lixeira(caminho)
                removidos.append(caminho)
            except OSError as erro:
                erros.append(f"{caminho}: {erro}")
        if erros:
            messagebox.showerror("Alguns arquivos não foram enviados", "\n".join(erros))
        self.grupos[self.grupo_atual] = [
            caminho for caminho in grupo if caminho not in removidos
        ]
        if not erros:
            del self.grupos[self.grupo_atual]
            if not self.grupos:
                self.status.configure(text="TODOS OS GRUPOS FORAM REVISADOS.")
                self._desabilitar_acoes()
                return
            self.grupo_atual = min(self.grupo_atual, len(self.grupos) - 1)
        self._mostrar_grupo()

    def limpar_tudo_automaticamente(self) -> None:
        """Mantém o primeiro arquivo de cada grupo e envia os demais à Lixeira."""
        grupos = [grupo for grupo in self.grupos if len(grupo) > 1]
        if not grupos:
            messagebox.showinfo(
                "Nenhuma duplicata",
                "NÃO HÁ DUPLICATAS PARA LIMPAR.",
            )
            return

        total_duplicatas = sum(len(grupo) - 1 for grupo in grupos)
        resposta = messagebox.askyesno(
            "Confirmar limpeza automática",
            f"FORAM ENCONTRADOS {len(grupos)} GRUPO(S) E {total_duplicatas} "
            "DUPLICATA(S).\n\n"
            "O PRIMEIRO ARQUIVO DE CADA GRUPO SERÁ MANTIDO E TODOS OS OUTROS "
            "SERÃO ENVIADOS PARA A LIXEIRA.\n\n"
            "DESEJA CONTINUAR?",
        )
        if not resposta:
            return

        self.operacao_em_andamento = True
        self.progresso.configure(value=0, maximum=100)
        self.progresso_label.configure(text="⏳ 0% - INICIANDO LIMPEZA AUTOMÁTICA")
        self.quadro_carregamento = 0
        self._animar_carregamento()
        self.botao_pasta.configure(state="disabled")
        self.botao_analisar.configure(state="disabled")
        self.botao_automatico.configure(state="disabled")
        self.botao_apagar.configure(state="disabled")
        self.botao_proximo.configure(state="disabled")
        threading.Thread(
            target=self._executar_limpeza_automatica,
            args=(grupos,),
            daemon=True,
        ).start()

    def _animar_carregamento(self) -> None:
        if not self.operacao_em_andamento:
            return
        simbolos = ("⏳", "⌛", "⏳", "⌛")
        self.progresso_label.configure(
            text=f"{simbolos[self.quadro_carregamento % len(simbolos)]} "
            f"{float(self.progresso['value']):.0f}% - PROCESSANDO"
        )
        self.quadro_carregamento += 1
        self.after(250, self._animar_carregamento)

    def _executar_limpeza_automatica(self, grupos: list[list[Path]]) -> None:
        falhas: list[list[Path]] = []
        removidos = 0
        total = sum(len(grupo) - 1 for grupo in grupos)
        processados = 0
        for indice_grupo, grupo in enumerate(grupos):
            self.after(
                0,
                self._mostrar_grupo_automatico,
                grupo,
                indice_grupo,
                len(grupos),
            )
            principal = grupo[0]
            restantes = []
            for caminho in grupo[1:]:
                try:
                    enviar_para_lixeira(caminho)
                    removidos += 1
                except OSError:
                    restantes.append(caminho)
                processados += 1
                percentual = (processados / total * 100) if total else 100
                self.after(0, self._atualizar_progresso, percentual)
            if restantes:
                falhas.append([principal, *restantes])
        self.after(0, self._finalizar_limpeza_automatica, falhas, removidos)

    def _mostrar_grupo_automatico(
        self, grupo: list[Path], indice: int, total: int
    ) -> None:
        self.indice_principal = 0
        self._montar_previsualizacoes(grupo)
        self.status.configure(
            text=f"LIMPEZA AUTOMÁTICA: GRUPO {indice + 1} DE {total}. "
            "MANTENDO O PRIMEIRO E ENVIANDO OS DUPLICADOS PARA A LIXEIRA."
        )

    def _atualizar_progresso(self, percentual: float) -> None:
        self.progresso.configure(value=percentual)
        self.progresso_label.configure(text=f"⏳ {percentual:.0f}% - PROCESSANDO")

    def _finalizar_limpeza_automatica(
        self, falhas: list[list[Path]], removidos: int
    ) -> None:
        self.operacao_em_andamento = False
        self.progresso.configure(value=100)
        self.progresso_label.configure(text="✅ 100% - CONCLUÍDO")
        self.grupos = falhas
        self.grupo_atual = 0
        self.botao_pasta.configure(state="normal")
        self.botao_analisar.configure(state="normal")
        if falhas:
            self._mostrar_grupo()
            messagebox.showwarning(
                "Limpeza incompleta",
                f"{removidos} arquivo(s) foram enviados para a Lixeira.\n"
                f"{sum(len(grupo) - 1 for grupo in falhas)} arquivo(s) não puderam ser movidos "
                "e continuam disponíveis para revisão.",
            )
        else:
            self._limpar_previsualizacao()
            self.status.configure(
                text=f"LIMPEZA AUTOMÁTICA CONCLUÍDA: {removidos} ARQUIVO(S) NA LIXEIRA."
            )
            self._desabilitar_acoes()

    def _limpar_previsualizacao(self) -> None:
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.imagens_preview.clear()
        self.cartoes_preview.clear()
        self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))

    def proximo_grupo(self) -> None:
        if self.grupo_atual < len(self.grupos) - 1:
            self.grupo_atual += 1
            self._mostrar_grupo()

    def _mostrar_erro(self, mensagem: str) -> None:
        self.botao_pasta.configure(state="normal")
        self.botao_analisar.configure(state="normal")
        messagebox.showerror("Erro", mensagem)


def enviar_para_lixeira(caminho: Path) -> None:
    """Envia para a Lixeira usando a API padrão do Windows Explorer."""
    try:
        shell32 = ctypes.windll.shell32
    except AttributeError:
        raise OSError("O envio para a Lixeira só é suportado no Windows.")
    class SHFILEOPSTRUCT(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.wintypes.HWND),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.wintypes.LPCWSTR),
            ("pTo", ctypes.wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.wintypes.LPCWSTR),
        ]

    operacao = SHFILEOPSTRUCT(
        wFunc=0x0003,  # FO_DELETE
        pFrom=str(caminho) + "\0\0",
        fFlags=0x0040 | 0x0010 | 0x0100,  # FOF_ALLOWUNDO | sem confirmação | silencioso
    )
    resultado = shell32.SHFileOperationW(ctypes.byref(operacao))
    if resultado != 0 or operacao.fAnyOperationsAborted:
        raise OSError(f"o Windows recusou a operação (código {resultado})")


if __name__ == "__main__":
    Aplicacao().mainloop()
