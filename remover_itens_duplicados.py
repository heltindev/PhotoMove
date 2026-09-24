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
    from PIL import Image, ImageEnhance, ImageTk
except ImportError:  # A análise continua funcionando sem miniaturas.
    Image = None
    ImageEnhance = None
    ImageTk = None


EXTENSOES_SUPORTADAS = {
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
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".m4v",
    ".3gp",
    ".webm",
}
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
        self.geometry("760x500")
        self.minsize(650, 400)
        self.grupos: list[list[Path]] = []
        self.grupo_atual = 0
        self.pasta: Path | None = None
        self.indice_principal = 0
        self.imagens_preview: list[object] = []
        self._montar_tela()

    def _montar_tela(self) -> None:
        ttk.Label(
            self,
            text="Verificador de fotos e vídeos duplicados",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=16, pady=8)
        ttk.Label(
            self,
            text=(
                "A análise encontra somente arquivos com conteúdo exatamente igual. "
                "Você revisa cada grupo antes de apagar."
            ),
            wraplength=710,
        ).pack(anchor="w", padx=16, pady=8)

        controles = ttk.Frame(self)
        controles.pack(fill="x", padx=16, pady=8)
        self.botao_pasta = ttk.Button(
            controles, text="Escolher pasta", command=self.escolher_pasta
        )
        self.botao_pasta.pack(side="left")
        self.botao_analisar = ttk.Button(
            controles, text="Analisar", command=self.iniciar_analise, state="disabled"
        )
        self.botao_analisar.pack(side="left", padx=8)
        self.pasta_label = ttk.Label(controles, text="Nenhuma pasta escolhida")
        self.pasta_label.pack(side="left", fill="x", expand=True)

        self.progresso = ttk.Progressbar(self, mode="determinate")
        self.progresso.pack(fill="x", padx=16, pady=8)
        self.status = ttk.Label(self, text="Escolha uma pasta para começar.")
        self.status.pack(anchor="w", padx=16, pady=8)

        self.preview_canvas = tk.Canvas(self, height=250, highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=16, pady=8)
        self.preview_scroll = ttk.Scrollbar(
            self, orient="horizontal", command=self.preview_canvas.xview
        )
        self.preview_scroll.pack(fill="x", padx=16)
        self.preview_canvas.configure(xscrollcommand=self.preview_scroll.set)
        self.preview_frame = ttk.Frame(self.preview_canvas)
        self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor="nw")
        self.preview_frame.bind("<Configure>", self._atualizar_area_previsualizacao)

    def _atualizar_area_previsualizacao(self, evento: tk.Event) -> None:
        del evento
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", padx=16, pady=8)
        self.botao_abrir = ttk.Button(
            botoes, text="Abrir selecionados", command=self.abrir_selecionados,
            state="disabled"
        )
        self.botao_abrir.pack(side="left")
        self.botao_apagar = ttk.Button(
            botoes, text="Enviar duplicatas para a Lixeira",
            command=self.apagar_duplicatas, state="disabled"
        )
        self.botao_apagar.pack(side="left", padx=8)
        self.botao_proximo = ttk.Button(
            botoes, text="Próximo grupo", command=self.proximo_grupo,
            state="disabled"
        )
        self.botao_proximo.pack(side="right")

    def escolher_pasta(self) -> None:
        escolhida = filedialog.askdirectory(title="Escolha a pasta para analisar")
        if escolhida:
            self.pasta = Path(escolhida)
            self.pasta_label.configure(text=str(self.pasta))
            self.botao_analisar.configure(state="normal")
            self.status.configure(text="Pasta pronta para análise.")

    def iniciar_analise(self) -> None:
        if self.pasta is None:
            return
        self.botao_analisar.configure(state="disabled")
        self.botao_pasta.configure(state="disabled")
        self.status.configure(text="Iniciando análise...")
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
            self.status.configure(text="Nenhuma duplicata exata foi encontrada.")
            self._desabilitar_acoes()
            return
        self.status.configure(text=f"{len(grupos)} grupo(s) duplicado(s) encontrado(s).")
        self._mostrar_grupo()

    def _mostrar_grupo(self) -> None:
        grupo = self.grupos[self.grupo_atual]
        self.indice_principal = 0
        self._montar_previsualizacoes(grupo)
        self.status.configure(
            text=f"Grupo {self.grupo_atual + 1} de {len(self.grupos)}. "
            "Clique na miniatura que deseja manter; ela fica em destaque."
        )
        self.botao_abrir.configure(state="normal")
        self.botao_apagar.configure(state="normal" if len(grupo) > 1 else "disabled")
        self.botao_proximo.configure(
            state="normal" if self.grupo_atual < len(self.grupos) - 1 else "disabled"
        )

    def _desabilitar_acoes(self) -> None:
        for botao in (self.botao_abrir, self.botao_apagar, self.botao_proximo):
            botao.configure(state="disabled")

    def _montar_previsualizacoes(self, grupo: list[Path]) -> None:
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.imagens_preview.clear()
        for indice, caminho in enumerate(grupo):
            card = tk.Frame(self.preview_frame, padx=8, pady=8)
            card.pack(side="left", anchor="n")
            imagem = self._criar_miniatura(caminho, indice == self.indice_principal)
            self.imagens_preview.append(imagem)
            botao = tk.Button(
                card,
                image=imagem,
                text="" if imagem is not None else "VÍDEO\nsem miniatura",
                compound="center",
                width=180,
                height=150,
                relief="solid" if indice == self.indice_principal else "flat",
                bd=3 if indice == self.indice_principal else 1,
                command=lambda i=indice: self._definir_principal(i),
            )
            botao.pack()
            nome = caminho.name
            if indice == self.indice_principal:
                nome = "★ PRINCIPAL ★\n" + nome
            ttk.Label(card, text=nome, wraplength=180, justify="center").pack(pady=5)
        self.after_idle(
            lambda: self.preview_canvas.configure(
                scrollregion=self.preview_canvas.bbox("all")
            )
        )

    def _criar_miniatura(self, caminho: Path, principal: bool) -> Any:
        if Image is None or ImageTk is None or caminho.suffix.lower() in EXTENSOES_SUPORTADAS - {
            ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".3gp", ".webm"
        }:
            return None
        try:
            with Image.open(caminho) as original:
                imagem = original.convert("RGB")
                imagem.thumbnail((180, 150))
                if not principal and ImageEnhance is not None:
                    imagem = ImageEnhance.Brightness(imagem).enhance(0.42)
                return ImageTk.PhotoImage(imagem)
        except (OSError, ValueError):
            return None

    def _definir_principal(self, indice: int) -> None:
        self.indice_principal = indice
        self._montar_previsualizacoes(self.grupos[self.grupo_atual])
        self.status.configure(
            text="Arquivo principal selecionado. Os outros serão os duplicados removidos."
        )

    def abrir_selecionados(self) -> None:
        try:
            abrir_no_windows(self.grupos[self.grupo_atual][self.indice_principal])
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
                self.status.configure(text="Todos os grupos foram revisados.")
                self._desabilitar_acoes()
                return
            self.grupo_atual = min(self.grupo_atual, len(self.grupos) - 1)
        self._mostrar_grupo()

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
