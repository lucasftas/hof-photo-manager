"""AppOrganizador — controlador principal da interface Tkinter."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from datetime import datetime
from queue import Empty, Queue
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Optional

from src.config import ConfigManager
from src.constants import (
    APP_VERSION,
    BYTES_PER_GB,
    ConflictAction,
    LOGGER_NAME,
    PATH_DISPLAY_TRUNCATE,
    THEME,
    WINDOW_GEOMETRY,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_TITLE,
)
from src.dialogs import (
    ConflictDialog,
    abrir_editor_lista,
    abrir_visualizador_logs,
    mostrar_sobre,
)
from src.models import GrupoPaciente
from src.processing import detectar_cartoes_sd, thread_analise, thread_processamento
from src.utils import criar_thumbnail

logger = logging.getLogger(LOGGER_NAME)

UI_POLL_INTERVAL_MS: int = 100


class AppOrganizador:
    """Controlador principal: monta a UI e coordena análise/processamento."""

    def __init__(self, root: tk.Tk) -> None:
        logger.info("Inicializando Aplicação...")
        self.root = root
        self.root.title(f"{WINDOW_TITLE} {APP_VERSION}")
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.config: dict[str, Any] = ConfigManager.load()

        self.grupos_pacientes: list[GrupoPaciente] = []
        self._grupos_por_id: dict[int, GrupoPaciente] = {}
        self.fontes_origem: list[str] = []
        self.dest_dir: str = self.config.get("last_dest_dir", "")
        self.image_cache: dict[int, dict[str, Any]] = {}
        self.check_vars: dict[int, tk.IntVar] = {}
        self.entradas_widgets: dict[int, dict[str, ttk.Combobox | ttk.Entry]] = {}
        self.stop_event = threading.Event()
        self.datas_disponiveis: list[datetime] = []
        self.filtro_data_inicio: Optional[datetime] = None
        self.filtro_data_fim: Optional[datetime] = None

        self._setup_menu()
        self._setup_toolbar()
        self._setup_main_layout()

        if self.dest_dir:
            self.lbl_dest.config(text=f"...{self.dest_dir[-PATH_DISPLAY_TRUNCATE:]}")
            self._check_ready()

    # ------------------------------------------------------------------ Menu
    def _setup_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Abrir Pasta Manual", command=self.adicionar_pasta_manual)
        file_menu.add_command(label="Selecionar Destino", command=self.selecionar_destino)
        file_menu.add_separator()
        file_menu.add_command(label="Resetar Tudo", command=self.resetar_app)
        file_menu.add_command(label="Sair", command=self.root.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        conf_menu = tk.Menu(menubar, tearoff=0)
        conf_menu.add_command(
            label="Editar Lista Professores",
            command=lambda: abrir_editor_lista(self.root, "professores", self.config),
        )
        conf_menu.add_command(
            label="Editar Lista Procedimentos",
            command=lambda: abrir_editor_lista(self.root, "procedimentos", self.config),
        )
        conf_menu.add_command(
            label="Editar Lista Etapas",
            command=lambda: abrir_editor_lista(self.root, "etapas", self.config),
        )
        menubar.add_cascade(label="Configurações", menu=conf_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Ver Logs", command=lambda: abrir_visualizador_logs(self.root))
        help_menu.add_command(label="Sobre", command=lambda: mostrar_sobre(self.root))
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        self.root.config(menu=menubar)

    # --------------------------------------------------------------- Toolbar
    def _setup_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, relief="raised", padding=2)
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="📷 Detectar Cartão", command=self.detectar_cartoes_auto).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📂 Pasta Manual", command=self.adicionar_pasta_manual).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=5, fill="y")
        self.btn_stats = ttk.Button(toolbar, text="📊 Estatísticas", command=self._mostrar_estatisticas)
        self.btn_stats.pack(side="left", padx=2)
        self.statusbar = ttk.Label(self.root, text="Pronto", relief="sunken", anchor="w")
        self.statusbar.pack(side="bottom", fill="x")

    # ----------------------------------------------------------- Main Layout
    def _setup_main_layout(self) -> None:
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)
        panel_left = ttk.Frame(paned, width=350, padding=10)
        paned.add(panel_left, weight=1)

        # Section 1: Origem & Destino
        lf_io = ttk.LabelFrame(panel_left, text="1. Origem & Destino", padding=10)
        lf_io.pack(fill="x", pady=5)
        self.lbl_src_status = ttk.Label(lf_io, text="0 fontes selecionadas", foreground=THEME["fg_missing"])
        self.lbl_src_status.pack(anchor="w")
        ttk.Button(lf_io, text="Alterar Destino", command=self.selecionar_destino).pack(fill="x", pady=5)
        self.lbl_dest = ttk.Label(
            lf_io, text="Nenhum destino definido",
            foreground=THEME["fg_muted"], font=("Arial", 8), wraplength=300,
        )
        self.lbl_dest.pack(anchor="w")
        self.btn_analisar = ttk.Button(lf_io, text="ANALISAR FOTOS 🔍", command=self.iniciar_analise, state="disabled")
        self.btn_analisar.pack(fill="x", pady=10)

        # Section 2: Filtros & Visualização
        lf_filt = ttk.LabelFrame(panel_left, text="2. Filtros & Visualização", padding=10)
        lf_filt.pack(fill="x", pady=5)
        f_dates = ttk.Frame(lf_filt)
        f_dates.pack(fill="x")
        self.combo_data_ini = ttk.Combobox(f_dates, width=10, state="readonly")
        self.combo_data_ini.pack(side="left")
        ttk.Label(f_dates, text=" até ").pack(side="left")
        self.combo_data_fim = ttk.Combobox(f_dates, width=10, state="readonly")
        self.combo_data_fim.pack(side="left")
        ttk.Button(lf_filt, text="Aplicar Filtro", command=self._aplicar_filtro_datas).pack(fill="x", pady=5)
        ttk.Button(lf_filt, text="Limpar Filtro", command=self._limpar_filtro_datas).pack(fill="x")

        f_view = ttk.Frame(lf_filt)
        f_view.pack(fill="x", pady=5)
        ttk.Button(f_view, text="Expandir Tudo", command=self.expandir_todos).pack(side="left", expand=True, fill="x")
        ttk.Button(f_view, text="Minimizar Tudo", command=self.minimizar_todos).pack(side="left", expand=True, fill="x")

        # Section 3: Processamento
        lf_act = ttk.LabelFrame(panel_left, text="3. Processamento", padding=10)
        lf_act.pack(fill="x", pady=5)
        self.btn_mesclar = ttk.Button(lf_act, text="Mesclar Grupos", command=self.mesclar_selecionados, state="disabled")
        self.btn_mesclar.pack(fill="x", pady=5)
        self.btn_processar = ttk.Button(lf_act, text="INICIAR CÓPIA", command=self.iniciar_processamento, state="disabled")
        self.btn_processar.pack(fill="x", pady=15)
        self.lbl_resumo_gb = ttk.Label(
            panel_left, text="0 itens (0 GB)",
            font=("Arial", 10, "bold"), foreground=THEME["fg_primary"],
        )
        self.lbl_resumo_gb.pack(pady=10)

        # Right panel: scrollable groups
        panel_right = ttk.Frame(paned)
        paned.add(panel_right, weight=4)
        self.canvas = tk.Canvas(panel_right, bg=THEME["bg_canvas"])
        self.scrollbar = ttk.Scrollbar(panel_right, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window_id, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ---------------------------------------------------------- Estatísticas
    def _mostrar_estatisticas(self) -> None:
        if not self.grupos_pacientes:
            messagebox.showinfo("Stats", "Analise fotos primeiro.")
            return
        total_grupos = len(self.grupos_pacientes)
        total_fotos = sum(g.total_fotos for g in self.grupos_pacientes)
        total_bytes = sum(g.tamanho_bytes for g in self.grupos_pacientes)
        gb = total_bytes / BYTES_PER_GB
        messagebox.showinfo("Estatísticas", f"Grupos: {total_grupos}\nFotos: {total_fotos}\nTamanho: {gb:.2f} GB")

    # ------------------------------------------------------------- Análise
    def iniciar_analise(self) -> None:
        logger.info("Iniciando análise...")
        self.stop_event.clear()
        self.btn_analisar.config(state="disabled")
        self.statusbar.config(text="Analisando arquivos... aguarde.")
        self.root.update()

        def on_success(grupos: list[GrupoPaciente]) -> None:
            self.root.after(0, lambda: self._pos_analise_sucesso(grupos))

        def on_empty() -> None:
            self.root.after(0, lambda: messagebox.showwarning("Ops", "Sem fotos."))

        def on_error(msg: str) -> None:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro na análise: {msg}"))

        def on_finish() -> None:
            self.root.after(0, self._fim_analise_ui)

        threading.Thread(
            target=thread_analise,
            args=(self.fontes_origem, self.stop_event, self.config, on_success, on_empty, on_error, on_finish),
            daemon=True,
        ).start()

    def _pos_analise_sucesso(self, grupos: list[GrupoPaciente]) -> None:
        self.grupos_pacientes = grupos
        self._grupos_por_id = {g.id: g for g in grupos}

        datas = sorted(list(set(g.data_obj_dia for g in self.grupos_pacientes)), reverse=True)
        self.datas_disponiveis = datas
        vals = [d.strftime("%d/%m/%Y") for d in datas]
        self.combo_data_ini["values"] = vals
        self.combo_data_fim["values"] = vals
        self._limpar_filtro_datas()
        self.btn_processar.config(state="normal")
        self.btn_mesclar.config(state="normal")
        self.statusbar.config(text=f"Análise concluída: {len(self.grupos_pacientes)} grupos.")

    def _fim_analise_ui(self) -> None:
        self.btn_analisar.config(state="normal")

    # ---------------------------------------------------- Lista Visual
    def _gerar_lista_visual(self) -> None:
        self._salvar_dados_ui_para_modelo()
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()
        self.entradas_widgets.clear()
        self.image_cache.clear()

        d_ini = self.filtro_data_inicio
        d_fim = self.filtro_data_fim
        ultimo_marcador: Optional[str] = None

        for grupo in self.grupos_pacientes:
            if d_ini and d_fim:
                if not (d_ini <= grupo.inicio <= d_fim):
                    continue
            marcador = f"{grupo.data_formatada} - {grupo.periodo_dia}"
            if marcador != ultimo_marcador:
                ttk.Label(
                    self.scrollable_frame, text=f"📅 {marcador}",
                    font=("Arial", 10, "bold"), background=THEME["bg_header"], anchor="center",
                ).pack(fill="x", pady=(15, 2))
                ultimo_marcador = marcador
            self._criar_widget_grupo(grupo)
        self._atualizar_resumo_selecao()

    def _criar_widget_grupo(self, grupo: GrupoPaciente) -> None:
        frame = ttk.Frame(self.scrollable_frame, relief="groove", borderwidth=1)
        frame.pack(fill="x", padx=5, pady=2)
        header = ttk.Frame(frame)
        header.pack(fill="x", padx=5, pady=2)

        var = tk.IntVar(value=1 if grupo.selecionado else 0)
        self.check_vars[grupo.id] = var
        cb = ttk.Checkbutton(header, variable=var, command=lambda g=grupo, v=var: self._check_callback(g, v))
        cb.pack(side="left")

        info_txt = f' Grupo #{grupo.id} | {grupo.inicio.strftime("%H:%M")} | {grupo.total_clicks} fotos | {grupo.tamanho_str}'
        ttk.Label(header, text=info_txt, font=("Arial", 9, "bold")).pack(side="left", padx=5)

        btn_min = ttk.Button(header, text="+" if grupo.minimized else "-", width=3, command=lambda g=grupo: self.toggle_minimize(g))
        btn_min.pack(side="right")

        if grupo.minimized:
            return

        body = ttk.Frame(frame)
        body.pack(fill="x", padx=5, pady=5)
        f_img = ttk.Frame(body)
        f_img.pack(side="left")

        # Navegação de fotos
        nav = ttk.Frame(f_img)
        nav.pack(fill="x")
        ttk.Button(nav, text="<", width=2, command=lambda g=grupo: self.mudar_foto(g, -1)).pack(side="left")
        lbl_idx = ttk.Label(nav, text=f"{grupo.preview_index + 1}/{len(grupo.fotos_visuais)}", font=("Arial", 7))
        lbl_idx.pack(side="left", expand=True)
        ttk.Button(nav, text=">", width=2, command=lambda g=grupo: self.mudar_foto(g, 1)).pack(side="right")

        lbl_img = ttk.Label(f_img, text="Carregando...", background=THEME["bg_thumbnail"], width=20, anchor="center")
        lbl_img.pack(pady=2)

        # Rotação
        f_rot = ttk.Frame(f_img)
        f_rot.pack(fill="x", pady=2)
        ttk.Button(f_rot, text="↺", width=2, command=lambda g=grupo: self.rotacionar_foto(g, 90)).pack(side="left", padx=2, expand=True)
        ttk.Button(f_rot, text="↻", width=2, command=lambda g=grupo: self.rotacionar_foto(g, -90)).pack(side="left", padx=2, expand=True)

        capa = grupo.get_foto_capa()
        if capa:
            thumb = criar_thumbnail(capa.caminho, grupo.rotacao)
            if thumb:
                lbl_img.config(text="", image=thumb)
                self.image_cache[grupo.id] = {"lbl": lbl_img, "idx_lbl": lbl_idx, "ref": thumb}

        # Formulário
        f_form = ttk.Frame(body)
        f_form.pack(side="left", fill="both", expand=True, padx=10)
        self.entradas_widgets[grupo.id] = {}

        # Professor
        f1 = ttk.Frame(f_form)
        f1.pack(fill="x", pady=1)
        ttk.Label(f1, text="Professor:", width=10).pack(side="left")
        c_prof = ttk.Combobox(f1, values=self.config["professores"])
        c_prof.set(grupo.dados_form["prof"])
        c_prof.pack(side="left", fill="x", expand=True)
        self._bind_sync(c_prof, grupo.id, "prof")
        self.entradas_widgets[grupo.id]["prof"] = c_prof

        # Paciente
        f2 = ttk.Frame(f_form)
        f2.pack(fill="x", pady=1)
        ttk.Label(f2, text="Paciente:", width=10).pack(side="left")
        e_pac = ttk.Entry(f2)
        e_pac.insert(0, grupo.dados_form["paciente"])
        e_pac.pack(side="left", fill="x", expand=True)
        self._bind_sync(e_pac, grupo.id, "paciente")
        self.entradas_widgets[grupo.id]["paciente"] = e_pac

        # Procedimento + Etapa
        f3 = ttk.Frame(f_form)
        f3.pack(fill="x", pady=1)
        ttk.Label(f3, text="Proc:", width=10).pack(side="left")
        c_proc = ttk.Combobox(f3, values=self.config["procedimentos"])
        c_proc.set(grupo.dados_form["proc"])
        c_proc.pack(side="left", fill="x", expand=True)
        self._bind_sync(c_proc, grupo.id, "proc")
        self.entradas_widgets[grupo.id]["proc"] = c_proc

        ttk.Label(f3, text=" Etapa:").pack(side="left")
        c_etapa = ttk.Combobox(f3, values=self.config["etapas"], width=10)
        c_etapa.set(grupo.dados_form["etapa"])
        c_etapa.pack(side="left")
        self._bind_sync(c_etapa, grupo.id, "etapa")
        self.entradas_widgets[grupo.id]["etapa"] = c_etapa

    # -------------------------------------------------------- Sync de campos
    def _bind_sync(self, widget: ttk.Combobox | ttk.Entry, gid: int, key: str) -> None:
        widget.bind("<KeyRelease>", lambda e: self._on_field_change(gid, key, widget.get()))
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda e: self._on_field_change(gid, key, widget.get()))

    def _on_field_change(self, origin_id: int, key: str, value: str) -> None:
        origin_grp = self._grupos_por_id.get(origin_id)
        if not origin_grp:
            return
        origin_grp.dados_form[key] = value
        if key == "etapa" or not origin_grp.selecionado:
            return
        for other_id, widgets in self.entradas_widgets.items():
            if other_id == origin_id:
                continue
            other_grp = self._grupos_por_id.get(other_id)
            if not other_grp or not other_grp.selecionado:
                continue
            w = widgets[key]
            if w.get() != value:
                if isinstance(w, ttk.Entry):
                    w.delete(0, tk.END)
                    w.insert(0, value)
                else:
                    w.set(value)
                other_grp.dados_form[key] = value

    # ------------------------------------------------------- Processamento
    def iniciar_processamento(self) -> None:
        self._salvar_dados_ui_para_modelo()
        logger.info("Iniciando processo de cópia...")

        to_process = [g for g in self.grupos_pacientes if g.dados_form["paciente"].strip()]
        total_files = sum(len(g.fotos) for g in to_process)

        logger.debug(f"Grupos para processar: {len(to_process)}. Total fotos: {total_files}")

        if total_files == 0:
            messagebox.showwarning("Aviso", "Nenhum paciente com nome definido.")
            return

        self.win_prog = tk.Toplevel(self.root)
        self.win_prog.title("Processando...")
        self.win_prog.geometry("600x450")
        self.win_prog.transient(self.root)
        self.win_prog.grab_set()
        self.stop_event.clear()

        ttk.Label(self.win_prog, text="Processando arquivos...", font=("Arial", 11, "bold")).pack(pady=5)
        self.prog_bar = ttk.Progressbar(self.win_prog, maximum=total_files, mode="determinate")
        self.prog_bar.pack(fill="x", padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(self.win_prog, height=15, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10)
        self.log_text.tag_config("err", foreground=THEME["fg_error"])
        self.log_text.tag_config("ok", foreground=THEME["fg_success"])
        self.log_text.tag_config("warn", foreground=THEME["fg_warning"])
        self.log_text.tag_config("folder", foreground=THEME["fg_folder"])

        ttk.Button(self.win_prog, text="Cancelar", command=self._cancelar_processo).pack(pady=10)

        self._ui_queue: Queue[dict[str, Any]] = Queue()
        self._poll_ui_queue()

        threading.Thread(
            target=thread_processamento,
            args=(to_process, self.dest_dir, self.stop_event, self._ask_conflict_main_thread, self._ui_queue),
            daemon=True,
        ).start()

    def _poll_ui_queue(self) -> None:
        """Processa mensagens da thread de processamento em batch."""
        try:
            for _ in range(50):  # Processa até 50 msgs por ciclo
                msg = self._ui_queue.get_nowait()
                if msg["type"] == "log":
                    self.log_text.insert(tk.END, f'{msg["msg"]}\n', msg.get("tag", "info"))
                    self.log_text.see(tk.END)
                elif msg["type"] == "progress":
                    self.prog_bar.step(msg["step"])
                elif msg["type"] == "done":
                    s, e = msg["sucesso"], msg["erros"]
                    messagebox.showinfo("Fim", f"Processo finalizado.\nSucesso: {s}\nErros: {e}")
                    self.win_prog.destroy()
                    return
        except Empty:
            pass
        self.root.after(UI_POLL_INTERVAL_MS, self._poll_ui_queue)

    def _cancelar_processo(self) -> None:
        logger.warning("Usuário solicitou cancelamento.")
        self.stop_event.set()
        self.log_text.insert(tk.END, "Solicitando cancelamento...\n", "warn")
        self.log_text.see(tk.END)

    def _ask_conflict_main_thread(self, tipo: str, nome: str, caminho: str) -> tuple[ConflictAction, Optional[str]]:
        """Mostra ConflictDialog na thread principal, bloqueando a worker thread."""
        result_container: dict[str, tuple[ConflictAction, Optional[str]]] = {}
        event = threading.Event()

        def show() -> None:
            res = ConflictDialog(self.win_prog, tipo, nome, caminho).show()
            result_container["res"] = res
            event.set()

        self.root.after(0, show)
        event.wait(timeout=300)
        return result_container.get("res", (ConflictAction.CANCEL, None))

    # ------------------------------------------------------ Ações da toolbar
    def selecionar_destino(self) -> None:
        p = filedialog.askdirectory()
        if p:
            self.dest_dir = p
            self.lbl_dest.config(text=p)
            self.config["last_dest_dir"] = p
            ConfigManager.save(self.config)
            self._check_ready()

    def adicionar_pasta_manual(self) -> None:
        p = filedialog.askdirectory()
        if p and p not in self.fontes_origem:
            self.fontes_origem.append(p)
            self.lbl_src_status.config(
                text=f"{len(self.fontes_origem)} fontes selecionadas",
                foreground=THEME["fg_folder"],
            )
            self._check_ready()

    def detectar_cartoes_auto(self) -> None:
        logger.info("Detectando cartões...")
        drives = detectar_cartoes_sd()
        if drives:
            self.fontes_origem = drives
            self.lbl_src_status.config(text=f"{len(drives)} cartões", foreground=THEME["fg_success"])
            self._check_ready()
        else:
            messagebox.showinfo("Info", "Nenhuma pasta DCIM encontrada.")

    # ------------------------------------------------------ Utilitários
    def _check_ready(self) -> None:
        if self.fontes_origem and self.dest_dir:
            self.btn_analisar.config(state="normal")

    def _salvar_dados_ui_para_modelo(self) -> None:
        for gid, widgets in self.entradas_widgets.items():
            grp = self._grupos_por_id.get(gid)
            if not grp:
                continue
            for k, w in widgets.items():
                grp.dados_form[k] = w.get()

    def _atualizar_resumo_selecao(self) -> None:
        sels = [g for g in self.grupos_pacientes if g.selecionado]
        tb = sum(g.tamanho_bytes for g in sels)
        gb = tb / BYTES_PER_GB
        self.lbl_resumo_gb.config(text=f"{len(sels)} selecionados ({gb:.2f} GB)")

    def _check_callback(self, grp: GrupoPaciente, var: tk.IntVar) -> None:
        grp.selecionado = bool(var.get())
        self._atualizar_resumo_selecao()

    def resetar_app(self) -> None:
        if messagebox.askyesno("Reset", "Limpar tudo?"):
            self.grupos_pacientes = []
            self._grupos_por_id = {}
            self.fontes_origem = []
            self.image_cache = {}
            self._gerar_lista_visual()
            self.lbl_src_status.config(text="0 fontes")
            self.btn_analisar.config(state="disabled")

    # --------------------------------------------------- Manipulação de grupo
    def toggle_minimize(self, g: GrupoPaciente) -> None:
        g.minimized = not g.minimized
        self._gerar_lista_visual()

    def minimizar_todos(self) -> None:
        for g in self.grupos_pacientes:
            g.minimized = True
        self._gerar_lista_visual()

    def expandir_todos(self) -> None:
        for g in self.grupos_pacientes:
            g.minimized = False
        self._gerar_lista_visual()

    def rotacionar_foto(self, g: GrupoPaciente, delta: int) -> None:
        g.rotacao = (g.rotacao + delta) % 360
        if self.config.get("last_rotation") != g.rotacao:
            self.config["last_rotation"] = g.rotacao
            ConfigManager.save(self.config)
        self._atualizar_imagem_grupo(g)

    def mudar_foto(self, g: GrupoPaciente, delta: int) -> None:
        if not g.fotos_visuais:
            return
        g.preview_index = (g.preview_index + delta) % len(g.fotos_visuais)
        self._atualizar_imagem_grupo(g)

    def _atualizar_imagem_grupo(self, g: GrupoPaciente) -> None:
        if g.id not in self.image_cache:
            return
        ref = self.image_cache[g.id]
        capa = g.get_foto_capa()
        if not capa:
            return
        th = criar_thumbnail(capa.caminho, g.rotacao)
        if th:
            ref["lbl"].config(image=th)
            ref["ref"] = th
            ref["idx_lbl"].config(text=f"{g.preview_index + 1}/{len(g.fotos_visuais)}")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # --------------------------------------------------- Filtro de datas
    def _aplicar_filtro_datas(self) -> None:
        try:
            d1 = datetime.strptime(self.combo_data_ini.get(), "%d/%m/%Y")
            d2 = datetime.strptime(self.combo_data_fim.get(), "%d/%m/%Y")
            self.filtro_data_inicio = min(d1, d2)
            self.filtro_data_fim = max(d1, d2).replace(hour=23, minute=59)
            self._gerar_lista_visual()
        except ValueError:
            messagebox.showerror("Erro", "Datas inválidas")

    def _limpar_filtro_datas(self) -> None:
        self.filtro_data_inicio = None
        self.filtro_data_fim = None
        if self.datas_disponiveis:
            self.combo_data_ini.current(0)
            self.combo_data_fim.current(len(self.datas_disponiveis) - 1)
        self._gerar_lista_visual()

    # --------------------------------------------------- Merge
    def mesclar_selecionados(self) -> None:
        self._salvar_dados_ui_para_modelo()
        sels = sorted([g for g in self.grupos_pacientes if g.selecionado], key=lambda x: x.inicio)
        if len(sels) < 2:
            return
        pai = sels[0]
        if not any(pai.dados_form.values()):
            for s in sels[1:]:
                if any(s.dados_form.values()):
                    pai.dados_form = s.dados_form
                    break
        for s in sels[1:]:
            pai.absorver_grupo(s)
            self.grupos_pacientes.remove(s)
            self._grupos_por_id.pop(s.id, None)
        pai.selecionado = False
        self._gerar_lista_visual()
        messagebox.showinfo("OK", "Mesclado!")
