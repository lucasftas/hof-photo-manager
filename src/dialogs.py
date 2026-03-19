"""Diálogos: ConflictDialog, editor de listas, visualizador de logs."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Any, Optional

from src.config import ConfigManager
from src.constants import APP_VERSION, ConflictAction, LOG_FILE, PATH_DISPLAY_TRUNCATE, THEME


class ConflictDialog:
    """Dialog modal para resolução de conflitos de pasta existente."""

    def __init__(self, parent: tk.Toplevel, tipo: str, nome: str, caminho: str) -> None:
        self.root = tk.Toplevel(parent)
        self.root.title("Conflito Detectado")
        self.root.geometry("400x250")
        self.root.transient(parent)
        self.root.grab_set()

        self.result: tuple[ConflictAction, Optional[str]] = (ConflictAction.MERGE, None)
        self.nome = nome

        ttk.Label(
            self.root,
            text=f"O {tipo} já existe!",
            font=("Arial", 12, "bold"),
            foreground=THEME["fg_error"],
        ).pack(pady=10)
        ttk.Label(self.root, text=f"Nome: {nome}").pack()
        ttk.Label(
            self.root,
            text=f"Caminho: ...{caminho[-PATH_DISPLAY_TRUNCATE:]}",
            foreground=THEME["fg_muted"],
        ).pack()

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="x")

        ttk.Button(frame, text="Mesclar (Usar existente)", command=self._mesclar).pack(fill="x", pady=2)
        ttk.Button(frame, text="Renomear", command=self._renomear).pack(fill="x", pady=2)
        ttk.Separator(frame).pack(fill="x", pady=10)
        ttk.Button(frame, text="Cancelar Tudo", command=self._cancelar).pack(fill="x")

    def show(self) -> tuple[ConflictAction, Optional[str]]:
        """Exibe o dialog e retorna a ação escolhida."""
        self.root.wait_window()
        return self.result

    def _mesclar(self) -> None:
        self.result = (ConflictAction.MERGE, None)
        self.root.destroy()

    def _renomear(self) -> None:
        novo = simpledialog.askstring("Renomear", f"Novo nome para {self.nome}:", parent=self.root)
        if novo:
            self.result = (ConflictAction.RENAME, novo)
            self.root.destroy()

    def _cancelar(self) -> None:
        self.result = (ConflictAction.CANCEL, None)
        self.root.destroy()


def abrir_editor_lista(
    parent: tk.Tk,
    chave: str,
    config: dict[str, Any],
) -> None:
    """Abre janela para editar uma lista de configuração (professores, etapas, etc.)."""
    win = tk.Toplevel(parent)
    win.title(f"Editar {chave.capitalize()}")
    win.geometry("400x500")

    txt = scrolledtext.ScrolledText(win, width=40, height=20)
    txt.pack(padx=10, pady=10)

    atuais = config.get(chave, [])
    txt.insert("1.0", "\n".join(atuais))

    def salvar() -> None:
        conteudo = txt.get("1.0", tk.END).strip()
        nova_lista = [x.strip() for x in conteudo.split("\n") if x.strip()]
        config[chave] = nova_lista
        ConfigManager.save(config)
        messagebox.showinfo("Sucesso", "Lista atualizada!")
        win.destroy()

    ttk.Button(win, text="Salvar", command=salvar).pack(pady=10)


def abrir_visualizador_logs(parent: tk.Tk) -> None:
    """Abre janela para visualizar o arquivo de log."""
    import os

    try:
        os.startfile(LOG_FILE)
    except OSError:
        win = tk.Toplevel(parent)
        win.title("Logs")
        win.geometry("600x400")
        txt = scrolledtext.ScrolledText(win)
        txt.pack(fill="both", expand=True)
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                txt.insert("1.0", f.read())
        except OSError as e:
            txt.insert("1.0", f"Erro ao ler logs: {e}")


def mostrar_sobre(parent: tk.Tk) -> None:
    """Exibe dialog 'Sobre' com a versão do app."""
    messagebox.showinfo("Sobre", f"Versão: {APP_VERSION}")
