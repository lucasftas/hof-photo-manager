import os
import shutil
import string
import json
import logging
import threading
import tkinter as as_tk
from tkinter import filedialog, messagebox, ttk, simpledialog, scrolledtext
from datetime import datetime
from PIL import Image, ImageTk

# --- Constants ---
APP_VERSION = 'v18.5'
CONFIG_FILE = 'config_hofphotomanager.json'
LOG_FILE = 'debug_detalhado.txt'

# --- Initialize log file ---
with open(LOG_FILE, 'w', encoding='utf-8') as f:
    f.write(f'--- INICIO DO LOG DEBUG {APP_VERSION} ---\n')

logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%H:%M:%S'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logger = logging.getLogger('AppOrganizador')


class ConfigManager:
    DEFAULT_CONFIG = {
        'professores': ['Wagner Baseggio', 'Camila Dias', 'Patrícia Ghezzi'],
        'etapas': ['Pré', 'Pós imediato', '15 dias', '30 dias'],
        'procedimentos': [
            'Full Face', 'Preenchimento Facial', 'Rinomodelação',
            'Preenchimento de Mento', 'Preenchimento de Mandíbula',
            'Preenchimento de Malar', 'Preenchimento de Lábios',
            'Preenchimento de Olheiras', 'Bioestimuladores de Colágeno',
            'Profhilo', 'Toxina Botulínica (Botox)', 'Skinbooster',
            'Peeling', 'Microagulhamento', 'Ultraformer',
            'Fios de Sustentação', 'Fios de PDO', 'Limpeza de Pele',
            'Máscaras Faciais', 'Hidratação Facial Profunda',
            'Face Lift (Ritidoplastia)', 'Blefaroplastia'
        ],
        'last_dest_dir': '',
        'last_rotation': 0
    }

    @staticmethod
    def load():
        logger.debug('Carregando configurações...')
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = {**ConfigManager.DEFAULT_CONFIG, **json.load(f)}
                    return data
            except Exception as e:
                logger.error(f'Erro ao ler config: {e}')
                return ConfigManager.DEFAULT_CONFIG
        return ConfigManager.DEFAULT_CONFIG

    @staticmethod
    def save(data):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Erro ao salvar config: {e}')


class FotoItem:
    def __init__(self, caminho, data_captura):
        self.caminho = caminho
        self.data_captura = data_captura
        self.nome_arquivo = os.path.basename(caminho)
        self.extensao = os.path.splitext(caminho)[1].lower()
        self.nome_base = os.path.splitext(self.nome_arquivo)[0]
        self.tamanho = 0
        try:
            self.tamanho = os.path.getsize(self.caminho)
        except:
            pass


class GrupoPaciente:
    def __init__(self, id_grupo, primeira_foto, rotacao=0):
        self.id = id_grupo
        self.fotos = [primeira_foto]
        self.inicio = primeira_foto.data_captura
        self.fim = primeira_foto.data_captura
        self.selecionado = False
        self.minimized = False
        self.dados_form = {'prof': '', 'paciente': '', 'proc': '', 'etapa': ''}
        self.preview_index = 0
        self.fotos_visuais = []
        self.rotacao = rotacao
        self._atualizar_cache_visual()

    def _atualizar_cache_visual(self):
        if not self.fotos:
            return
        self.fotos.sort(key=lambda x: x.data_captura)
        self.inicio = self.fotos[0].data_captura
        self.fim = self.fotos[-1].data_captura

        mapa_fotos = {}
        ordem_bases = []
        for f in self.fotos:
            if f.nome_base not in mapa_fotos:
                mapa_fotos[f.nome_base] = []
                ordem_bases.append(f.nome_base)
            mapa_fotos[f.nome_base].append(f)

        self.fotos_visuais = []
        for base in ordem_bases:
            versoes = mapa_fotos[base]
            jpg = next((x for x in versoes if x.extensao in ('.jpg', '.jpeg')), None)
            self.fotos_visuais.append(jpg if jpg else versoes[0])

        self.preview_index = len(self.fotos_visuais) // 2

    def adicionar_foto(self, foto):
        self.fotos.append(foto)
        self._atualizar_cache_visual()

    def absorver_grupo(self, outro_grupo):
        self.fotos.extend(outro_grupo.fotos)
        self._atualizar_cache_visual()

    @property
    def total_fotos(self):
        return len(self.fotos)

    @property
    def total_clicks(self):
        return len(self.fotos_visuais)

    @property
    def periodo_dia(self):
        return 'MANHÃ' if self.inicio.hour < 12 else 'TARDE'

    @property
    def data_formatada(self):
        return self.inicio.strftime('%d/%m/%Y')

    @property
    def data_obj_dia(self):
        return datetime(self.inicio.year, self.inicio.month, self.inicio.day)

    @property
    def tamanho_bytes(self):
        return sum(f.tamanho for f in self.fotos)

    @property
    def tamanho_str(self):
        b = self.tamanho_bytes
        if b >= 1073741824:
            return f'{b / 1073741824:.2f} GB'
        return f'{b / 1048576:.1f} MB'

    def get_foto_capa(self):
        if not self.fotos_visuais:
            return None
        idx = max(0, min(self.preview_index, len(self.fotos_visuais) - 1))
        return self.fotos_visuais[idx]


class AppOrganizador:
    def __init__(self, root):
        logger.info('Inicializando Aplicação...')
        self.root = root
        self.root.title(f'HOF Photo Manager {APP_VERSION}')
        self.root.geometry('1400x650')
        self.root.minsize(1024, 650)

        self.config = ConfigManager.load()

        self.grupos_pacientes = []
        self.fontes_origem = []
        self.dest_dir = self.config.get('last_dest_dir', '')
        self.image_cache = {}
        self.check_vars = {}
        self.entradas_widgets = {}
        self.stop_event = threading.Event()

        self._setup_menu()
        self._setup_toolbar()
        self._setup_main_layout()

        if self.dest_dir:
            self.lbl_dest.config(text=f'...{self.dest_dir[-40:]}')
            self._check_ready()

    def _setup_menu(self):
        menubar = as_tk.Menu(self.root)
        file_menu = as_tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Abrir Pasta Manual', command=self.adicionar_pasta_manual)
        file_menu.add_command(label='Selecionar Destino', command=self.selecionar_destino)
        file_menu.add_separator()
        file_menu.add_command(label='Resetar Tudo', command=self.resetar_app)
        file_menu.add_command(label='Sair', command=self.root.quit)
        menubar.add_cascade(label='Arquivo', menu=file_menu)

        conf_menu = as_tk.Menu(menubar, tearoff=0)
        conf_menu.add_command(label='Editar Lista Professores', command=lambda: self._editar_lista('professores'))
        conf_menu.add_command(label='Editar Lista Procedimentos', command=lambda: self._editar_lista('procedimentos'))
        conf_menu.add_command(label='Editar Lista Etapas', command=lambda: self._editar_lista('etapas'))
        menubar.add_cascade(label='Configurações', menu=conf_menu)

        help_menu = as_tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='Ver Logs', command=self._mostrar_logs)
        help_menu.add_command(label='Sobre', command=lambda: messagebox.showinfo('Sobre', f'Versão: {APP_VERSION}'))
        menubar.add_cascade(label='Ajuda', menu=help_menu)
        self.root.config(menu=menubar)

    def _setup_toolbar(self):
        toolbar = ttk.Frame(self.root, relief='raised', padding=2)
        toolbar.pack(side='top', fill='x')
        ttk.Button(toolbar, text='📷 Detectar Cartão', command=self.detectar_cartoes_auto).pack(side='left', padx=2)
        ttk.Button(toolbar, text='📂 Pasta Manual', command=self.adicionar_pasta_manual).pack(side='left', padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=5, fill='y')
        self.btn_stats = ttk.Button(toolbar, text='📊 Estatísticas', command=self._mostrar_estatisticas)
        self.btn_stats.pack(side='left', padx=2)
        self.statusbar = ttk.Label(self.root, text='Pronto', relief='sunken', anchor='w')
        self.statusbar.pack(side='bottom', fill='x')

    def _setup_main_layout(self):
        paned = ttk.PanedWindow(self.root, orient='horizontal')
        paned.pack(fill='both', expand=True)
        panel_left = ttk.Frame(paned, width=350, padding=10)
        paned.add(panel_left, weight=1)

        # --- Section 1: Origem & Destino ---
        lf_io = ttk.LabelFrame(panel_left, text='1. Origem & Destino', padding=10)
        lf_io.pack(fill='x', pady=5)
        self.lbl_src_status = ttk.Label(lf_io, text='0 fontes selecionadas', foreground='red')
        self.lbl_src_status.pack(anchor='w')
        ttk.Button(lf_io, text='Alterar Destino', command=self.selecionar_destino).pack(fill='x', pady=5)
        self.lbl_dest = ttk.Label(lf_io, text='Nenhum destino definido', foreground='gray', font=('Arial', 8), wraplength=300)
        self.lbl_dest.pack(anchor='w')
        self.btn_analisar = ttk.Button(lf_io, text='ANALISAR FOTOS 🔍', command=self.iniciar_analise, state='disabled')
        self.btn_analisar.pack(fill='x', pady=10)

        # --- Section 2: Filtros & Visualização ---
        lf_filt = ttk.LabelFrame(panel_left, text='2. Filtros & Visualização', padding=10)
        lf_filt.pack(fill='x', pady=5)
        f_dates = ttk.Frame(lf_filt)
        f_dates.pack(fill='x')
        self.combo_data_ini = ttk.Combobox(f_dates, width=10, state='readonly')
        self.combo_data_ini.pack(side='left')
        ttk.Label(f_dates, text=' até ').pack(side='left')
        self.combo_data_fim = ttk.Combobox(f_dates, width=10, state='readonly')
        self.combo_data_fim.pack(side='left')
        ttk.Button(lf_filt, text='Aplicar Filtro', command=self._aplicar_filtro_datas).pack(fill='x', pady=5)
        ttk.Button(lf_filt, text='Limpar Filtro', command=self._limpar_filtro_datas).pack(fill='x')

        f_view = ttk.Frame(lf_filt)
        f_view.pack(fill='x', pady=5)
        ttk.Button(f_view, text='Expandir Tudo', command=self.expandir_todos).pack(side='left', expand=True, fill='x')
        ttk.Button(f_view, text='Minimizar Tudo', command=self.minimizar_todos).pack(side='left', expand=True, fill='x')

        # --- Section 3: Processamento ---
        lf_act = ttk.LabelFrame(panel_left, text='3. Processamento', padding=10)
        lf_act.pack(fill='x', pady=5)
        self.btn_mesclar = ttk.Button(lf_act, text='Mesclar Grupos', command=self.mesclar_selecionados, state='disabled')
        self.btn_mesclar.pack(fill='x', pady=5)
        self.btn_processar = ttk.Button(lf_act, text='INICIAR CÓPIA', command=self.iniciar_processamento, state='disabled')
        self.btn_processar.pack(fill='x', pady=15)
        self.lbl_resumo_gb = ttk.Label(panel_left, text='0 itens (0 GB)', font=('Arial', 10, 'bold'), foreground='#007bff')
        self.lbl_resumo_gb.pack(pady=10)

        # --- Right panel: scrollable groups ---
        panel_right = ttk.Frame(paned)
        paned.add(panel_right, weight=4)
        self.canvas = as_tk.Canvas(panel_right, bg='#f5f5f5')
        self.scrollbar = ttk.Scrollbar(panel_right, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')

        self.scrollable_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window_id, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel)

    def _editar_lista(self, chave):
        win = as_tk.Toplevel(self.root)
        win.title(f'Editar {chave.capitalize()}')
        win.geometry('400x500')
        txt = scrolledtext.ScrolledText(win, width=40, height=20)
        txt.pack(padx=10, pady=10)
        atuais = self.config.get(chave, [])
        txt.insert('1.0', '\n'.join(atuais))

        def salvar():
            conteudo = txt.get('1.0', as_tk.END).strip()
            nova_lista = [x.strip() for x in conteudo.split('\n') if x.strip()]
            self.config[chave] = nova_lista
            ConfigManager.save(self.config)
            messagebox.showinfo('Sucesso', 'Lista atualizada!')
            win.destroy()

        ttk.Button(win, text='Salvar', command=salvar).pack(pady=10)

    def _mostrar_logs(self):
        try:
            os.startfile(LOG_FILE)
        except:
            win = as_tk.Toplevel(self.root)
            win.title('Logs')
            win.geometry('600x400')
            txt = scrolledtext.ScrolledText(win)
            txt.pack(fill='both', expand=True)
            try:
                with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                    txt.insert('1.0', f.read())
            except Exception as e:
                txt.insert('1.0', f'Erro: {e}')

    def _mostrar_estatisticas(self):
        if not self.grupos_pacientes:
            messagebox.showinfo('Stats', 'Analise fotos primeiro.')
            return
        total_grupos = len(self.grupos_pacientes)
        total_fotos = sum(g.total_fotos for g in self.grupos_pacientes)
        total_bytes = sum(g.tamanho_bytes for g in self.grupos_pacientes)
        gb = total_bytes / 1073741824
        msg = f'Grupos: {total_grupos}\nFotos: {total_fotos}\nTamanho: {gb:.2f} GB'
        messagebox.showinfo('Estatísticas', msg)

    def iniciar_analise(self):
        logger.info('Iniciando análise...')
        self.stop_event.clear()
        self.btn_analisar.config(state='disabled')
        self.statusbar.config(text='Analisando arquivos... aguarde.')
        self.root.update()
        threading.Thread(target=self._thread_analise, daemon=True).start()

    def _thread_analise(self):
        try:
            arquivos = []
            exts = ('.jpg', '.jpeg', '.arw')
            for fonte in self.fontes_origem:
                logger.debug(f'Analisando fonte: {fonte}')
                if self.stop_event.is_set():
                    break
                for root, _, files in os.walk(fonte):
                    for f in files:
                        if self.stop_event.is_set():
                            break
                        if not f.lower().endswith(exts):
                            continue
                        full = os.path.join(root, f)
                        try:
                            dt = datetime.fromtimestamp(os.path.getmtime(full))
                            if f.lower().endswith(('.jpg', '.jpeg')):
                                try:
                                    img = Image.open(full)
                                    exif = img._getexif()
                                    if exif:
                                        s = exif.get(36867) or exif.get(306)
                                        if s:
                                            dt = datetime.strptime(s, '%Y:%m:%d %H:%M:%S')
                                except:
                                    pass
                            arquivos.append(FotoItem(full, dt))
                        except Exception as e:
                            logger.error(f'Erro lendo {f}: {e}')

            logger.info(f'Arquivos: {len(arquivos)}')
            if not arquivos:
                self.root.after(0, lambda: messagebox.showwarning('Ops', 'Sem fotos.'))
                self.root.after(0, self._fim_analise_ui)
                return

            arquivos.sort(key=lambda x: x.data_captura)
            rot_padrao = self.config.get('last_rotation', 0)
            temp_grupos = []
            if arquivos:
                curr = GrupoPaciente(1, arquivos[0], rotacao=rot_padrao)
                temp_grupos.append(curr)
                THRESHOLD = 1200
                for i in range(1, len(arquivos)):
                    if self.stop_event.is_set():
                        break
                    foto = arquivos[i]
                    prev = arquivos[i - 1]
                    if (foto.data_captura - prev.data_captura).total_seconds() > THRESHOLD:
                        curr._atualizar_cache_visual()
                        curr = GrupoPaciente(len(temp_grupos) + 1, foto, rotacao=rot_padrao)
                        temp_grupos.append(curr)
                    else:
                        curr.adicionar_foto(foto)
                curr._atualizar_cache_visual()

            temp_grupos.sort(key=lambda g: g.inicio, reverse=True)
            self.grupos_pacientes = temp_grupos
            logger.info(f'Grupos criados: {len(self.grupos_pacientes)}')
            self.root.after(0, self._pos_analise_sucesso)
        except Exception as e:
            logger.critical(f'Erro análise: {e}')
        finally:
            self.root.after(0, self._fim_analise_ui)

    def _pos_analise_sucesso(self):
        datas = sorted(list(set([g.data_obj_dia for g in self.grupos_pacientes])), reverse=True)
        self.datas_disponiveis = datas
        vals = [d.strftime('%d/%m/%Y') for d in datas]
        self.combo_data_ini['values'] = vals
        self.combo_data_fim['values'] = vals
        self._limpar_filtro_datas()
        self.btn_processar.config(state='normal')
        self.btn_mesclar.config(state='normal')
        self.statusbar.config(text=f'Análise concluída: {len(self.grupos_pacientes)} grupos.')

    def _fim_analise_ui(self):
        self.btn_analisar.config(state='normal')

    def _gerar_lista_visual(self):
        self._salvar_dados_ui_para_modelo()
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()
        self.entradas_widgets.clear()
        self.image_cache.clear()

        d_ini = self.filtro_data_inicio
        d_fim = self.filtro_data_fim
        ultimo_marcador = None
        for grupo in self.grupos_pacientes:
            if d_ini and d_fim:
                if not (d_ini <= grupo.inicio <= d_fim):
                    continue
            marcador = f'{grupo.data_formatada} - {grupo.periodo_dia}'
            if marcador != ultimo_marcador:
                ttk.Label(self.scrollable_frame, text=f'📅 {marcador}', font=('Arial', 10, 'bold'), background='#e0e0e0', anchor='center').pack(fill='x', pady=(15, 2))
                ultimo_marcador = marcador
            self._criar_widget_grupo(grupo)
        self._atualizar_resumo_selecao()

    def _criar_widget_grupo(self, grupo):
        frame = ttk.Frame(self.scrollable_frame, relief='groove', borderwidth=1)
        frame.pack(fill='x', padx=5, pady=2)
        header = ttk.Frame(frame)
        header.pack(fill='x', padx=5, pady=2)

        var = as_tk.IntVar(value=1 if grupo.selecionado else 0)
        self.check_vars[grupo.id] = var
        cb = ttk.Checkbutton(header, variable=var, command=lambda g=grupo, v=var: self._check_callback(g, v))
        cb.pack(side='left')

        info_txt = f' Grupo #{grupo.id} | {grupo.inicio.strftime("%H:%M")} | {grupo.total_clicks} fotos | {grupo.tamanho_str}'
        ttk.Label(header, text=info_txt, font=('Arial', 9, 'bold')).pack(side='left', padx=5)

        btn_min = ttk.Button(header, text='+' if grupo.minimized else '-', width=3, command=lambda g=grupo: self.toggle_minimize(g))
        btn_min.pack(side='right')

        if grupo.minimized:
            return

        body = ttk.Frame(frame)
        body.pack(fill='x', padx=5, pady=5)
        f_img = ttk.Frame(body)
        f_img.pack(side='left')

        nav = ttk.Frame(f_img)
        nav.pack(fill='x')
        ttk.Button(nav, text='<', width=2, command=lambda g=grupo: self.mudar_foto(g, -1)).pack(side='left')
        label_inicial = f'{grupo.preview_index + 1}/{len(grupo.fotos_visuais)}'
        lbl_idx = ttk.Label(nav, text=label_inicial, font=('Arial', 7))
        lbl_idx.pack(side='left', expand=True)
        ttk.Button(nav, text='>', width=2, command=lambda g=grupo: self.mudar_foto(g, 1)).pack(side='right')

        lbl_img = ttk.Label(f_img, text='Carregando...', background='#ddd', width=20, anchor='center')
        lbl_img.pack(pady=2)

        f_rot = ttk.Frame(f_img)
        f_rot.pack(fill='x', pady=2)
        ttk.Button(f_rot, text='↺', width=2, command=lambda g=grupo: self.rotacionar_foto(g, 90)).pack(side='left', padx=2, expand=True)
        ttk.Button(f_rot, text='↻', width=2, command=lambda g=grupo: self.rotacionar_foto(g, -90)).pack(side='left', padx=2, expand=True)

        capa = grupo.get_foto_capa()
        if capa:
            thumb = self._criar_thumbnail(capa.caminho, grupo.rotacao)
            if thumb:
                lbl_img.config(text='', image=thumb)
                self.image_cache[grupo.id] = {'lbl': lbl_img, 'idx_lbl': lbl_idx, 'ref': thumb}

        f_form = ttk.Frame(body)
        f_form.pack(side='left', fill='both', expand=True, padx=10)
        self.entradas_widgets[grupo.id] = {}

        # Professor
        f1 = ttk.Frame(f_form)
        f1.pack(fill='x', pady=1)
        ttk.Label(f1, text='Professor:', width=10).pack(side='left')
        c_prof = ttk.Combobox(f1, values=self.config['professores'])
        c_prof.set(grupo.dados_form['prof'])
        c_prof.pack(side='left', fill='x', expand=True)
        self._bind_sync(c_prof, grupo.id, 'prof')
        self.entradas_widgets[grupo.id]['prof'] = c_prof

        # Paciente
        f2 = ttk.Frame(f_form)
        f2.pack(fill='x', pady=1)
        ttk.Label(f2, text='Paciente:', width=10).pack(side='left')
        e_pac = ttk.Entry(f2)
        e_pac.insert(0, grupo.dados_form['paciente'])
        e_pac.pack(side='left', fill='x', expand=True)
        self._bind_sync(e_pac, grupo.id, 'paciente')
        self.entradas_widgets[grupo.id]['paciente'] = e_pac

        # Procedimento + Etapa
        f3 = ttk.Frame(f_form)
        f3.pack(fill='x', pady=1)
        ttk.Label(f3, text='Proc:', width=10).pack(side='left')
        c_proc = ttk.Combobox(f3, values=self.config['procedimentos'])
        c_proc.set(grupo.dados_form['proc'])
        c_proc.pack(side='left', fill='x', expand=True)
        self._bind_sync(c_proc, grupo.id, 'proc')
        self.entradas_widgets[grupo.id]['proc'] = c_proc

        ttk.Label(f3, text=' Etapa:').pack(side='left')
        c_etapa = ttk.Combobox(f3, values=self.config['etapas'], width=10)
        c_etapa.set(grupo.dados_form['etapa'])
        c_etapa.pack(side='left')
        self._bind_sync(c_etapa, grupo.id, 'etapa')
        self.entradas_widgets[grupo.id]['etapa'] = c_etapa

    def _criar_thumbnail(self, path, angulo=0):
        try:
            img = Image.open(path)
            if angulo != 0:
                img = img.rotate(angulo, expand=True)
            img.thumbnail((150, 150))
            return ImageTk.PhotoImage(img)
        except:
            return None

    def _bind_sync(self, widget, gid, key):
        widget.bind('<KeyRelease>', lambda e: self._on_field_change(gid, key, widget.get()))
        if isinstance(widget, ttk.Combobox):
            widget.bind('<<ComboboxSelected>>', lambda e: self._on_field_change(gid, key, widget.get()))

    def _on_field_change(self, origin_id, key, value):
        origin_grp = next((g for g in self.grupos_pacientes if g.id == origin_id), None)
        if not origin_grp:
            return
        origin_grp.dados_form[key] = value
        if key == 'etapa':
            return
        if not origin_grp.selecionado:
            return
        for other_id, widgets in self.entradas_widgets.items():
            if other_id == origin_id:
                continue
            other_grp = next((g for g in self.grupos_pacientes if g.id == other_id), None)
            if not other_grp or not other_grp.selecionado:
                continue
            w = widgets[key]
            if w.get() != value:
                if isinstance(w, ttk.Entry):
                    w.delete(0, as_tk.END)
                    w.insert(0, value)
                else:
                    w.set(value)
                other_grp.dados_form[key] = value

    def iniciar_processamento(self):
        self._salvar_dados_ui_para_modelo()
        logger.info('Iniciando processo de cópia...')

        to_process = [g for g in self.grupos_pacientes if g.dados_form['paciente'].strip()]
        total_files = sum(len(g.fotos) for g in to_process)

        logger.debug(f'Grupos para processar: {len(to_process)}. Total fotos: {total_files}')

        if total_files == 0:
            messagebox.showwarning('Aviso', 'Nenhum paciente com nome definido.')
            return

        self.win_prog = as_tk.Toplevel(self.root)
        self.win_prog.title('Processando...')
        self.win_prog.geometry('600x450')
        self.win_prog.transient(self.root)
        self.win_prog.grab_set()
        self.stop_event.clear()

        ttk.Label(self.win_prog, text='Processando arquivos...', font=('Arial', 11, 'bold')).pack(pady=5)
        self.prog_bar = ttk.Progressbar(self.win_prog, maximum=total_files, mode='determinate')
        self.prog_bar.pack(fill='x', padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(self.win_prog, height=15, font=('Consolas', 9))
        self.log_text.pack(fill='both', expand=True, padx=10)
        self.log_text.tag_config('err', foreground='red')
        self.log_text.tag_config('ok', foreground='green')
        self.log_text.tag_config('warn', foreground='#b8860b')
        self.log_text.tag_config('folder', foreground='blue')

        btn_cancel = ttk.Button(self.win_prog, text='Cancelar', command=self._cancelar_processo)
        btn_cancel.pack(pady=10)

        threading.Thread(target=self._thread_processamento, args=(to_process,), daemon=True).start()

    def _cancelar_processo(self):
        logger.warning('Usuário solicitou cancelamento.')
        self.stop_event.set()
        self._log_gui('Solicitando cancelamento...', 'warn')

    def _log_gui(self, msg, tag='info'):
        self.log_text.insert(as_tk.END, f'{msg}\n', tag)
        self.log_text.see(as_tk.END)

    def _thread_processamento(self, grupos):
        sucesso = 0
        erros = 0

        pastas_aprovadas = set()

        def safe_name(s):
            if not s:
                return ''
            forbidden = '<>:"/\\|?*'
            cleaned = ''.join(c for c in s if c not in forbidden)
            final = cleaned.strip().strip('.')
            return final

        for g in grupos:
            if self.stop_event.is_set():
                break

            logger.info(f'--- Processando Grupo ID {g.id} ---')

            prof = safe_name(g.dados_form['prof']) or 'Sem_Professor'
            pac = safe_name(g.dados_form['paciente'])
            proc = safe_name(g.dados_form['proc']) or 'Geral'
            etapa = safe_name(g.dados_form['etapa']) or 'Unica'

            # --- Professor folder ---
            base_prof = os.path.join(self.dest_dir, prof)
            if not os.path.exists(base_prof):
                try:
                    os.makedirs(base_prof)
                    logger.debug(f'Pasta Professor criada: {base_prof}')
                except Exception as e:
                    logger.error(f'Erro criar pasta professor: {e}')

            # --- Paciente folder ---
            base_pac = os.path.join(base_prof, pac)

            if base_pac not in pastas_aprovadas and os.path.exists(base_pac):
                logger.info(f"Conflito Paciente '{pac}' detectado. Perguntando...")
                acao, novo = self._ask_conflict_main_thread('Paciente', pac, base_pac)
                logger.info(f'Decisão Paciente: {acao}')

                if acao == 'cancel':
                    self.stop_event.set()
                    break
                elif acao == 'renomear':
                    pac = safe_name(novo)
                    base_pac = os.path.join(base_prof, pac)

            if not os.path.exists(base_pac):
                try:
                    os.makedirs(base_pac)
                    logger.debug(f'Pasta Paciente criada: {base_pac}')
                except Exception as e:
                    self._log_gui(f'Erro criar pasta paciente: {e}', 'err')
                    continue

            pastas_aprovadas.add(base_pac)

            # --- Procedimento folder ---
            base_proc = os.path.join(base_pac, proc)

            if base_proc not in pastas_aprovadas and os.path.exists(base_proc):
                logger.info(f"Conflito Procedimento '{proc}'. Perguntando...")
                acao, novo = self._ask_conflict_main_thread('Procedimento', proc, base_proc)
                logger.info(f'Decisão Procedimento: {acao}')

                if acao == 'cancel':
                    self.stop_event.set()
                    break
                elif acao == 'renomear':
                    proc = safe_name(novo)
                    base_proc = os.path.join(base_pac, proc)

            if not os.path.exists(base_proc):
                os.makedirs(base_proc)

            pastas_aprovadas.add(base_proc)

            # --- Etapa folder ---
            base_etapa = os.path.join(base_proc, etapa)

            if base_etapa not in pastas_aprovadas and os.path.exists(base_etapa):
                logger.info(f"Conflito Etapa '{etapa}'. Perguntando...")
                acao, novo = self._ask_conflict_main_thread('Etapa', etapa, base_etapa)
                logger.info(f'Decisão Etapa: {acao}')

                if acao == 'cancel':
                    self.stop_event.set()
                    break
                elif acao == 'renomear':
                    etapa = safe_name(novo)
                    base_etapa = os.path.join(base_proc, etapa)

            try:
                os.makedirs(os.path.join(base_etapa, 'JPG'), exist_ok=True)
                os.makedirs(os.path.join(base_etapa, 'RAW'), exist_ok=True)
            except Exception as e:
                self.root.after(0, lambda m=f'Erro criar subpastas: {e}': self._log_gui(m, 'err'))
                erros += 1
                continue

            pastas_aprovadas.add(base_etapa)

            # --- Copy files ---
            for f in g.fotos:
                if self.stop_event.is_set():
                    break
                dest_folder = 'JPG' if f.extensao in ('.jpg', '.jpeg') else 'RAW'
                final_path = os.path.join(base_etapa, dest_folder)
                new_name = f'{pac} - {proc} - {etapa} - {f.nome_arquivo}'
                target = os.path.join(final_path, new_name)

                if os.path.exists(target):
                    ts = int(datetime.now().timestamp())
                    new_name = f'{pac} - {proc} - {etapa} - {ts}_{f.nome_arquivo}'
                    target = os.path.join(final_path, new_name)

                try:
                    shutil.copy2(f.caminho, target)
                    sucesso += 1
                    self.root.after(0, lambda: self.prog_bar.step(1))
                    self.root.after(0, lambda m=f'OK: {f.nome_arquivo}': self._log_gui(m, 'ok'))
                except Exception as e:
                    erros += 1
                    logger.error(f'Erro copy {f.caminho}: {e}')
                    self.root.after(0, lambda m=f'Erro: {f.nome_arquivo}': self._log_gui(m, 'err'))

        logger.info(f'Fim. Sucesso: {sucesso}, Erros: {erros}')

        def finalizar():
            messagebox.showinfo('Fim', f'Processo finalizado.\nSucesso: {sucesso}\nErros: {erros}')
            self.win_prog.destroy()

        self.root.after(0, finalizar)

    def _ask_conflict_main_thread(self, tipo, nome, caminho):
        result_container = {}
        event = threading.Event()

        def show():
            res = ConflictDialog(self.win_prog, tipo, nome, caminho).show()
            result_container['res'] = res
            event.set()

        self.root.after(0, show)
        event.wait()
        return result_container.get('res')

    def selecionar_destino(self):
        p = filedialog.askdirectory()
        if p:
            self.dest_dir = p
            self.lbl_dest.config(text=p)
            self.config['last_dest_dir'] = p
            ConfigManager.save(self.config)
            self._check_ready()

    def adicionar_pasta_manual(self):
        p = filedialog.askdirectory()
        if p and p not in self.fontes_origem:
            self.fontes_origem.append(p)
            self.lbl_src_status.config(text=f'{len(self.fontes_origem)} fontes selecionadas', foreground='blue')
            self._check_ready()

    def detectar_cartoes_auto(self):
        logger.info('Detectando cartões...')
        drives = []
        if os.name == 'nt':
            drives = [f'{d}:\\DCIM' for d in string.ascii_uppercase if os.path.exists(f'{d}:\\DCIM')]
        elif os.path.exists('/Volumes'):
            for d in os.listdir('/Volumes'):
                p = os.path.join('/Volumes', d, 'DCIM')
                if os.path.exists(p):
                    drives.append(p)
        if drives:
            self.fontes_origem = drives
            self.lbl_src_status.config(text=f'{len(drives)} cartões', foreground='green')
            self._check_ready()
        else:
            messagebox.showinfo('Info', 'Nenhuma pasta DCIM encontrada.')

    def _check_ready(self):
        if self.fontes_origem and self.dest_dir:
            self.btn_analisar.config(state='normal')

    def _salvar_dados_ui_para_modelo(self):
        for gid, widgets in self.entradas_widgets.items():
            grp = next((g for g in self.grupos_pacientes if g.id == gid), None)
            if not grp:
                continue
            for k, w in widgets.items():
                grp.dados_form[k] = w.get()

    def _atualizar_resumo_selecao(self):
        sels = [g for g in self.grupos_pacientes if g.selecionado]
        tb = sum(g.tamanho_bytes for g in sels)
        gb = tb / 1073741824
        self.lbl_resumo_gb.config(text=f'{len(sels)} selecionados ({gb:.2f} GB)')

    def _check_callback(self, grp, var):
        grp.selecionado = bool(var.get())
        self._atualizar_resumo_selecao()

    def resetar_app(self):
        if messagebox.askyesno('Reset', 'Limpar tudo?'):
            self.grupos_pacientes = []
            self.fontes_origem = []
            self.image_cache = {}
            self._gerar_lista_visual()
            self.lbl_src_status.config(text='0 fontes')
            self.btn_analisar.config(state='disabled')

    def toggle_minimize(self, g):
        g.minimized = not g.minimized
        self._gerar_lista_visual()

    def minimizar_todos(self):
        for g in self.grupos_pacientes:
            g.minimized = True
        self._gerar_lista_visual()

    def expandir_todos(self):
        for g in self.grupos_pacientes:
            g.minimized = False
        self._gerar_lista_visual()

    def rotacionar_foto(self, g, delta):
        g.rotacao = (g.rotacao + delta) % 360
        if self.config.get('last_rotation') != g.rotacao:
            self.config['last_rotation'] = g.rotacao
            ConfigManager.save(self.config)
        self._atualizar_imagem_grupo(g)

    def mudar_foto(self, g, delta):
        if not g.fotos_visuais:
            return
        g.preview_index = (g.preview_index + delta) % len(g.fotos_visuais)
        self._atualizar_imagem_grupo(g)

    def _atualizar_imagem_grupo(self, g):
        if g.id in self.image_cache:
            ref = self.image_cache[g.id]
            capa = g.get_foto_capa()
            th = self._criar_thumbnail(capa.caminho, g.rotacao)
            if th:
                ref['lbl'].config(image=th)
                ref['ref'] = th
                ref['idx_lbl'].config(text=f'{g.preview_index + 1}/{len(g.fotos_visuais)}')

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _aplicar_filtro_datas(self):
        try:
            d1 = datetime.strptime(self.combo_data_ini.get(), '%d/%m/%Y')
            d2 = datetime.strptime(self.combo_data_fim.get(), '%d/%m/%Y')
            self.filtro_data_inicio = min(d1, d2)
            self.filtro_data_fim = max(d1, d2).replace(hour=23, minute=59)
            self._gerar_lista_visual()
        except:
            messagebox.showerror('Erro', 'Datas inválidas')

    def _limpar_filtro_datas(self):
        self.filtro_data_inicio = None
        self.filtro_data_fim = None
        if self.datas_disponiveis:
            self.combo_data_ini.current(0)
            self.combo_data_fim.current(len(self.datas_disponiveis) - 1)
        self._gerar_lista_visual()

    def mesclar_selecionados(self):
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
        pai.selecionado = False
        self._gerar_lista_visual()
        messagebox.showinfo('OK', 'Mesclado!')


class ConflictDialog:
    def __init__(self, parent, tipo, nome, caminho):
        self.root = as_tk.Toplevel(parent)
        self.root.title('Conflito Detectado')
        self.root.geometry('400x250')
        self.root.transient(parent)
        self.root.grab_set()

        self.result = ('mesclar', None)
        self.nome = nome

        ttk.Label(self.root, text=f'O {tipo} já existe!', font=('Arial', 12, 'bold'), foreground='#d9534f').pack(pady=10)
        ttk.Label(self.root, text=f'Nome: {nome}').pack()
        ttk.Label(self.root, text=f'Caminho: ...{caminho[-40:]}', foreground='gray').pack()

        f = ttk.Frame(self.root, padding=20)
        f.pack(fill='x')

        ttk.Button(f, text='Mesclar (Usar existente)', command=self.mesclar).pack(fill='x', pady=2)
        ttk.Button(f, text='Renomear', command=self.renomear).pack(fill='x', pady=2)
        ttk.Separator(f).pack(fill='x', pady=10)
        ttk.Button(f, text='Cancelar Tudo', command=self.cancelar).pack(fill='x')

    def show(self):
        self.root.wait_window()
        return self.result

    def mesclar(self):
        self.result = ('mesclar', None)
        self.root.destroy()

    def renomear(self):
        novo = simpledialog.askstring('Renomear', f'Novo nome para {self.nome}:', parent=self.root)
        if novo:
            self.result = ('renomear', novo)
            self.root.destroy()

    def cancelar(self):
        self.result = ('cancel', None)
        self.root.destroy()


if __name__ == '__main__':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    root = as_tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')

    app = AppOrganizador(root)
    root.mainloop()
