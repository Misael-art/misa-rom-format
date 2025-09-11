#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Aplicativo Principal
Inicia a aplicação e configura monitoramento
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import traceback
from datetime import datetime
import glob
import sqlite3
import json
import csv
import xml.etree.ElementTree as ET
import re
import time
import logging.handlers

# Adiciona o diretório raiz ao PYTHONPATH se necessário
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importações dos módulos da aplicação
from engine.db import UnifiedDatabaseManager as DatabaseManager
from engine.services.config_manager import ConfigManager
from engine.services.event_manager import EventManager, EventType
from engine.services.task_manager import TaskManager
from engine.services.import_service import ImportService
from engine.services.rom_verification_service import RomVerificationService
from engine.utils.file_validator import FileValidator
from engine.utils.directory_scanner import DirectoryScanner
from engine.utils.export_utils import ExportUtils
from engine.utils.archive_utils import ArchiveUtils
from ui.themes import apply_theme_to_ttk, apply_theme_to_widgets, LIGHT_THEME, DARK_THEME
from ui.components.scrollable_frame import ScrollableFrame
from ui.dialogs.progress_dialog import ProgressDialog
from ui.screens.welcome_screen import WelcomeScreen
from constants import *

# Configuração de logging
def setup_logging():
    """Configura o sistema de logging da aplicação."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'megaemu_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # Configuração principal
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Logger específico da aplicação
    logger = logging.getLogger('MegaEmuDB')
    logger.setLevel(logging.DEBUG)
    
    return logger

# Classe principal da aplicação
class MegaEmuDBApp(tk.Tk):
    """Classe principal do aplicativo MegaEmu DataBase ROMs."""
    
    def __init__(self):
        """Inicializa a aplicação."""
        super().__init__()
        
        # Inicializa serviços e gerenciadores
        self.logger = logging.getLogger('MegaEmuDB.App')
        self.logger.info("Iniciando aplicação MegaEmu DataBase ROMs")
        
        self.config_manager = ConfigManager()
        self.event_manager = EventManager()
        
        # Inicializa o DatabaseManager e tenta conectar ao último banco usado
        self.db_manager = DatabaseManager()
        last_db = self.config_manager.get("last_db_path")
        
        # Se não houver banco anterior, cria um novo
        if not last_db or not os.path.exists(last_db):
            default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'default.db')
            os.makedirs(os.path.dirname(default_db), exist_ok=True)
            
            if self.db_manager.create_new_database(default_db, {
                'name': 'MegaEmu DataBase ROMs',
                'version': '1.0.0',
                'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }):
                self.logger.info(f"Banco de dados padrão criado: {default_db}")
                self.config_manager.set("last_db_path", default_db)
                last_db = default_db
            else:
                self.logger.error("Erro ao criar banco de dados padrão")
        
        # Tenta conectar ao banco
        if last_db and os.path.exists(last_db):
            try:
                if self.db_manager.connect(last_db):
                    self.logger.info(f"Conectado ao banco de dados: {last_db}")
                else:
                    self.logger.warning(f"Não foi possível conectar ao banco: {last_db}")
            except Exception as e:
                self.logger.error(f"Erro ao conectar ao banco: {str(e)}")
        
        # Configura interface
        self._setup_ui()
        
        # Inicializa gerenciador de tarefas com a janela principal para callbacks
        self.task_manager = TaskManager(max_workers=MAX_WORKERS_DEFAULT, gui_thread=self)
        
        # Inicializa outros serviços
        self.services = {
            'import': ImportService(self.db_manager),
            'verification': RomVerificationService(self.db_manager)
        }
        
        # Utilidades
        self.utils = {
            'file_validator': FileValidator(),
            'directory_scanner': DirectoryScanner(),
            'export': ExportUtils(),
            'archive': ArchiveUtils()
        }
        
        # Configurações de monitoramento
        self._setup_monitoring()
        
        # Subscreve para eventos
        self._subscribe_to_events()
        
        # Carrega banco de dados anterior se existir
        self._load_last_database()
        
        self.logger.info("Aplicação inicializada com sucesso")
        
        # Publica evento de inicialização
        self.event_manager.publish(EventType.APP_INITIALIZED)
        
        # Agenda a exibição da tela de boas-vindas após inicialização
        self.after(WELCOME_SCREEN_DELAY, self._show_welcome_if_needed)
    
    def _setup_ui(self):
        """Configura a interface da aplicação."""
        # Configuração da janela principal
        window_size = self.config_manager.get("window_size", DEFAULT_WINDOW_SIZE)
        self.title(APP_TITLE)
        self.geometry(window_size)
        
        # Definir a visibilidade do painel de navegação antes de criar o menu
        self.nav_visible = self.config_manager.get("show_navigation", True)
        
        # Aplicar tema
        self.theme = self.config_manager.get("theme", "light")
        self._apply_theme()
        
        # Menu principal
        self._create_menu()
        
        # Frame principal com 3 painéis: navegação, conteúdo e status
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Painel de navegação (pode ser ocultado)
        self.nav_frame = ttk.Frame(self.main_frame, width=200)
        if self.nav_visible:
            self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Conteúdo principal
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Barra de status
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar(value="Pronto")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, 
                                      anchor=tk.W, padding=(5, 2))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Indicador de BD
        self.db_status_var = tk.StringVar(value="Nenhum banco de dados aberto")
        self.db_status_label = ttk.Label(self.status_frame, textvariable=self.db_status_var,
                                        anchor=tk.E, padding=(5, 2))
        self.db_status_label.pack(side=tk.RIGHT)
        
        # Componentes de navegação
        self._setup_navigation_panel()
        
        # Componentes de conteúdo
        self._setup_content_panel()
    
    def _create_menu(self):
        """Cria o menu principal da aplicação."""
        self.menu_bar = tk.Menu(self)
        
        # Menu Arquivo
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Novo Banco de Dados", command=self._create_new_database)
        file_menu.add_command(label="Abrir Banco de Dados", command=self._open_database)
        
        # Submenu para bancos recentes
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Bancos Recentes", menu=self.recent_menu)
        self._update_recent_menu()
        
        file_menu.add_separator()
        file_menu.add_command(label="Fechar Banco de Dados", command=self._close_database)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.on_closing)
        
        # Menu Importar
        import_menu = tk.Menu(self.menu_bar, tearoff=0)
        import_menu.add_command(label="Importar Arquivo DAT", command=self._import_dat_file)
        import_menu.add_command(label="Importar Diretório de DATs", command=self._batch_import_dats)
        import_menu.add_separator()
        import_menu.add_command(label="Importar INI", command=self._import_ini_file)
        
        # Menu Ferramentas
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        tools_menu.add_command(label="Verificar ROMs", command=self._verify_roms)
        tools_menu.add_command(label="Exportar Dados", command=self._export_data)
        tools_menu.add_separator()
        tools_menu.add_command(label="Executar Consulta SQL", command=self._open_query_editor)
        tools_menu.add_command(label="Estatísticas do Banco", command=self._show_database_stats)
        
        # Menu Visualização
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        
        # Submenu de tema
        theme_menu = tk.Menu(view_menu, tearoff=0)
        theme_menu.add_command(label="Claro", command=lambda: self._change_theme("light"))
        theme_menu.add_command(label="Escuro", command=lambda: self._change_theme("dark"))
        view_menu.add_cascade(label="Tema", menu=theme_menu)
        
        view_menu.add_separator()
        self.nav_var = tk.BooleanVar(value=self.nav_visible)
        view_menu.add_checkbutton(label="Painel de Navegação", 
                                 variable=self.nav_var,
                                 command=self._toggle_navigation)
        
        # Menu Ajuda
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="Documentação", command=self._show_documentation)
        help_menu.add_command(label="Sobre", command=self._show_about)
        
        # Adiciona os menus à barra
        self.menu_bar.add_cascade(label="Arquivo", menu=file_menu)
        self.menu_bar.add_cascade(label="Importar", menu=import_menu)
        self.menu_bar.add_cascade(label="Ferramentas", menu=tools_menu)
        self.menu_bar.add_cascade(label="Visualização", menu=view_menu)
        self.menu_bar.add_cascade(label="Ajuda", menu=help_menu)
        
        # Configura a barra de menu
        self.config(menu=self.menu_bar)
    
    def _setup_navigation_panel(self):
        """Configura o painel de navegação."""
        # Lista de tabelas
        self.tables_frame = ttk.LabelFrame(self.nav_frame, text="Tabelas")
        self.tables_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Lista com scrollbar
        self.tables_list = tk.Listbox(self.tables_frame, height=MAX_RECORDS_PER_PAGE)
        self.tables_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tables_scroll = ttk.Scrollbar(self.tables_frame, command=self.tables_list.yview)
        tables_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tables_list.config(yscrollcommand=tables_scroll.set)
        
        # Vincular evento de seleção
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)
    
    def _setup_content_panel(self):
        """Configura o painel de conteúdo principal."""
        # Usar notebook para abas
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Aba de tabela de dados
        self.data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="Dados")
        
        # Frame rolável para a tabela
        self.data_scroll = ScrollableFrame(self.data_frame)
        self.data_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview para os dados
        self.data_tree = ttk.Treeview(self.data_scroll.get_frame())
        self.data_tree["columns"] = ()  # Colunas serão definidas dinamicamente
        
        # Scrollbars para o treeview
        vsb = ttk.Scrollbar(self.data_scroll.get_frame(), orient="vertical", command=self.data_tree.yview)
        hsb = ttk.Scrollbar(self.data_scroll.get_frame(), orient="horizontal", command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Posiciona os componentes
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.data_tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind para eventos
        self.data_tree.bind("<Double-1>", self._on_row_double_click)
        self.data_tree.bind("<Button-3>", self._on_row_right_click)
    
    def _setup_monitoring(self):
        """Configura o monitoramento da aplicação."""
        # Monitor de exceções não tratadas
        sys.excepthook = self._handle_exception
        
        # Monitor de tarefas ativas
        self._start_task_monitor()
        
        # Monitor de memória (opcional)
        # self._start_memory_monitor()
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Manipula exceções não tratadas."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Não captura interrupções de teclado
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        self.logger.critical("Exceção não tratada:", 
                           exc_info=(exc_type, exc_value, exc_traceback))
        
        # Exibe diálogo de erro
        error_message = f"Ocorreu um erro:\n{exc_type.__name__}: {exc_value}"
        self._show_error(error_message)
    
    def _start_task_monitor(self):
        """Inicia o monitor de tarefas em segundo plano."""
        def monitor_tasks():
            while True:
                try:
                    active_tasks = self.task_manager.get_active_tasks()
                    if active_tasks:
                        task_stats = [f"{task.id}: {task.progress:.1f}%" for task in active_tasks]
                        self.logger.debug(f"Tarefas ativas: {len(active_tasks)} - {', '.join(task_stats)}")
                    
                    # Limpa tarefas completadas antigas (mantém apenas as mais recentes)
                    self.task_manager.clean_completed_tasks(max_tasks=MAX_STATUS_MESSAGES)
                    
                    # Aguarda antes da próxima verificação
                    self.after(TASK_MONITOR_INTERVAL, monitor_tasks)
                    return  # Retorna para evitar recursão infinita
                except Exception as e:
                    self.logger.error(f"Erro no monitor de tarefas: {e}")
                    break
        
        # Inicia o monitor
        self.after(TASK_MONITOR_INTERVAL, monitor_tasks)
    
    def _subscribe_to_events(self):
        """Subscreve para eventos do sistema."""
        events = EventType()
        
        # Eventos de banco de dados
        self.event_manager.subscribe(events.DATABASE_OPENED, self._on_database_opened)
        self.event_manager.subscribe(events.DATABASE_CLOSED, self._on_database_closed)
        
        # Eventos de importação
        self.event_manager.subscribe(events.IMPORT_COMPLETED, self._on_import_completed)
        
        # Eventos de tema
        self.event_manager.subscribe(events.THEME_CHANGED, self._on_theme_changed)
    
    def _on_database_opened(self, db_path):
        """Manipula evento de banco de dados aberto."""
        self.db_status_var.set(f"BD: {os.path.basename(db_path)}")
        self._update_tables_list()
        self.set_status(f"Banco de dados aberto: {db_path}")
        self.config_manager.add_to_recent_databases(db_path)
        self._update_recent_menu()
    
    def _on_database_closed(self):
        """Manipula evento de banco de dados fechado."""
        self.db_status_var.set("Nenhum banco de dados aberto")
        self._clear_tables_list()
        self._clear_data_view()
        self.set_status("Banco de dados fechado")
    
    def _on_import_completed(self, source_file=None, stats=None):
        """Manipula evento de importação concluída."""
        self._update_tables_list()
        
        if source_file and stats:
            message = f"Importação concluída de {os.path.basename(source_file)}\n"
            message += f"Registros processados: {stats.get('processed_roms', 0)}\n"
            message += f"Registros inseridos: {stats.get('inserted_records', 0)}"
            self._show_info("Importação Concluída", message)
    
    def _on_theme_changed(self, theme_name):
        """Manipula evento de tema alterado."""
        self._apply_theme(theme_name)
    
    def _apply_theme(self, theme_name=None):
        """Aplica o tema à interface."""
        if theme_name is None:
            theme_name = self.theme
        else:
            self.theme = theme_name
            
        # Aplica o tema ao ttk
        apply_theme_to_ttk(theme_name)
        
        # Aplica o tema aos widgets nativos
        apply_theme_to_widgets(self, theme_name)
        
        # Cores do tema
        colors = LIGHT_THEME if theme_name == "light" else DARK_THEME
        
        # Configura cores de fundo
        self.configure(bg=colors["bg"])
        
        # Salva a configuração
        self.config_manager.set("theme", theme_name)
    
    def _load_last_database(self):
        """Carrega o último banco de dados utilizado."""
        last_db = self.config_manager.get("last_db_path")
        
        # Se não houver banco configurado ou o arquivo não existir, tenta usar o banco padrão
        if not last_db or not os.path.exists(last_db):
            # Primeiro tenta o banco game_data.db
            default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'game_data.db')
            
            # Se não existir, tenta o default.db
            if not os.path.exists(default_db):
                default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'default.db')
            
            if os.path.exists(default_db):
                self.logger.info(f"Usando banco de dados padrão: {default_db}")
                last_db = default_db
                # Atualiza a configuração
                self.config_manager.set("last_db_path", default_db)
            else:
                self.logger.warning("Nenhum banco de dados encontrado. Criando um novo banco padrão.")
                
                # Cria diretório de dados se não existir
                data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
                os.makedirs(data_dir, exist_ok=True)
                
                # Cria um novo banco padrão
                default_db = os.path.join(data_dir, 'default.db')
                if self.db_manager.create_new_database(default_db, {
                    'name': 'MegaEmu DataBase ROMs',
                    'version': '1.0.0',
                    'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }):
                    self.logger.info(f"Banco de dados padrão criado: {default_db}")
                    self.config_manager.set("last_db_path", default_db)
                    last_db = default_db
                else:
                    self.logger.error("Erro ao criar banco de dados padrão")
                    self.db_status_var.set("Erro ao criar banco de dados")
                    messagebox.showerror(
                        "Erro ao Criar Banco",
                        "Não foi possível criar um banco de dados padrão.\n"
                        "Tente criar um novo banco pelo menu Arquivo."
                    )
                    return
        
        # Tenta conectar ao banco
        try:
            # Verifica se já está conectado
            if self.db_manager.get_connection() and self.db_manager.current_db == last_db:
                self.logger.info(f"Já conectado ao banco: {last_db}")
                self._update_tables_list()
                self.db_status_var.set(f"Banco: {os.path.basename(last_db)}")
                return
            
            self.logger.info(f"Tentando conectar ao banco: {last_db}")
            
            # Tenta conectar até vezes
            for attempt in range(DB_CONNECTION_RETRY_ATTEMPTS):
                if self.db_manager.connect(last_db):
                    self.logger.info(f"Conectado ao banco de dados: {last_db}")
                    self._update_tables_list()
                    self.db_status_var.set(f"Banco: {os.path.basename(last_db)}")
                    
                    # Publica evento de banco aberto
                    self.event_manager.publish(EventType.DATABASE_OPENED, last_db)
                    return
                else:
                    self.logger.warning(f"Tentativa {attempt+1} falhou ao conectar ao banco: {last_db}")
                    # Pequena pausa entre tentativas
                    time.sleep(DB_CONNECTION_RETRY_DELAY)
            
            # Se chegou aqui, todas as tentativas falharam
            self.logger.warning(f"Não foi possível conectar ao banco após várias tentativas: {last_db}")
            self.db_status_var.set("Falha ao conectar ao banco de dados")
            
            # Exibe mensagem ao usuário
            messagebox.showwarning(
                "Problema ao Conectar",
                f"Não foi possível conectar ao banco de dados: {last_db}\n\n"
                "Você pode tentar criar um novo banco de dados pelo menu Arquivo."
            )
        except Exception as e:
            self.logger.error(f"Erro ao carregar último banco: {str(e)}")
            self.db_status_var.set("Erro ao carregar banco de dados")
            
            # Exibe mensagem de erro ao usuário
            messagebox.showerror(
                "Erro ao Carregar Banco",
                f"Ocorreu um erro ao carregar o banco de dados:\n{str(e)}"
            )
    
    def _update_tables_list(self):
        """Atualiza a lista de tabelas."""
        if not self.db_manager.get_connection():
            self.tables_list.delete(0, tk.END)
            return
            
        try:
            tables = self.db_manager.get_tables()
            self.tables_list.delete(0, tk.END)
            for table in tables:
                self.tables_list.insert(tk.END, table)
        except Exception as e:
            self.logger.error(f"Erro ao atualizar lista de tabelas: {str(e)}")
    
    def _clear_tables_list(self):
        """Limpa a lista de tabelas."""
        self.tables_list.delete(0, tk.END)
    
    def _clear_data_view(self):
        """Limpa a visualização de dados."""
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        # Redefine as colunas
        self.data_tree["columns"] = ()
    
    def _on_table_selected(self, event):
        """Manipula evento de seleção de tabela."""
        selection = self.tables_list.curselection()
        if not selection:
            return
        
        table_name = self.tables_list.get(selection[0])
        self._show_table_data(table_name)
    
    def _show_table_data(self, table_name):
        """Exibe os dados de uma tabela."""
        self._clear_data_view()
        
        try:
            # Obtém informações da tabela
            table_info = self.db_manager.get_table_info(table_name)
            if not table_info:
                self.set_status(f"Não foi possível obter informações da tabela {table_name}")
                return
            
            # Define as colunas
            columns = [col[1] for col in table_info]
            self.data_tree["columns"] = columns
            
            # Configura as colunas
            self.data_tree.column("#0", width=50, stretch=False)
            for col in columns:
                self.data_tree.column(col, width=150, stretch=True)
                self.data_tree.heading(col, text=col)
            
            # Obtém os dados (limitados a registros)
            query = f"SELECT * FROM {table_name} LIMIT {MAX_RECORDS_DISPLAY}"
            rows = self.db_manager.execute_query(query)
            
            if not rows:
                self.set_status(f"Tabela {table_name} está vazia")
                return
            
            # Adiciona os dados à árvore
            for i, row in enumerate(rows):
                values = [row[col] for col in columns]
                self.data_tree.insert("", tk.END, text=str(i+1), values=values)
            
            total_rows = self.db_manager.get_row_count(table_name)
            showing = min(len(rows), MAX_RECORDS_DISPLAY)
            
            self.set_status(f"Exibindo {showing} de {total_rows} registros da tabela {table_name}")
            
        except Exception as e:
            self.logger.error(f"Erro ao exibir dados da tabela {table_name}: {e}")
            self.set_status(f"Erro ao exibir tabela: {str(e)}")
    
    def _on_row_double_click(self, event):
        """Manipula evento de duplo clique em uma linha."""
        item = self.data_tree.identify('item', event.x, event.y)
        if not item:
            return
        
        # Obtém os dados da linha
        values = self.data_tree.item(item, 'values')
        
        # Exibe os detalhes em uma janela de diálogo
        self._show_row_details(item, values)
    
    def _on_row_right_click(self, event):
        """Manipula evento de clique direito em uma linha."""
        item = self.data_tree.identify('item', event.x, event.y)
        if not item:
            return
        
        # Seleciona o item
        self.data_tree.selection_set(item)
        
        # Cria menu de contexto
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Ver Detalhes", 
                                command=lambda: self._show_row_details(item, self.data_tree.item(item, 'values')))
        context_menu.add_command(label="Editar", 
                                command=lambda: self._edit_row(item))
        context_menu.add_separator()
        context_menu.add_command(label="Excluir", 
                                command=lambda: self._delete_row(item))
        
        # Exibe o menu
        context_menu.tk_popup(event.x_root, event.y_root)
    
    def _show_row_details(self, item_id, values):
        """Exibe os detalhes de uma linha."""
        if not values:
            return
        
        # Obtém os nomes das colunas
        columns = self.data_tree["columns"]
        
        # Cria uma janela de diálogo
        details_dialog = tk.Toplevel(self)
        details_dialog.title("Detalhes do Registro")
        details_dialog.geometry(DETAILS_DIALOG_SIZE)
        details_dialog.transient(self)
        details_dialog.grab_set()
        
        # Aplica o tema
        if self.theme == "dark":
            details_dialog.configure(bg=DARK_THEME["bg"])
        else:
            details_dialog.configure(bg=LIGHT_THEME["bg"])
        
        # Frame com scrollbar
        details_frame = ScrollableFrame(details_dialog)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Adiciona os detalhes
        frame = details_frame.get_frame()
        for i, (col, val) in enumerate(zip(columns, values)):
            # Label para o nome da coluna
            lbl_col = ttk.Label(frame, text=f"{col}:", font=("Segoe UI", 10, "bold"))
            lbl_col.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            # Label para o valor
            val_str = str(val) if val is not None else ""
            lbl_val = ttk.Label(frame, text=val_str, wraplength=350)
            lbl_val.grid(row=i, column=1, sticky="w", padx=5, pady=2)
        
        # Botão de fechar
        btn_close = ttk.Button(details_dialog, text="Fechar", command=details_dialog.destroy)
        btn_close.pack(pady=10)
    
    def _edit_row(self, item_id):
        """Abre um diálogo para edição de linha."""
        # Implementação será adicionada
        self.set_status("Funcionalidade de edição não implementada")
    
    def _delete_row(self, item_id):
        """Exclui uma linha da tabela."""
        # Implementação será adicionada
        self.set_status("Funcionalidade de exclusão não implementada")
    
    def _create_new_database(self):
        """Cria um novo banco de dados."""
        # Solicita o local para salvar o novo banco de dados
        file_path = filedialog.asksaveasfilename(
            title="Criar Banco de Dados Padrão",
            defaultextension=".db",
            filetypes=[
                ("Banco de dados SQLite", "*.db"),
                ("Todos os arquivos", "*.*")
            ]
        )
        
        if not file_path:
            return  # Operação cancelada pelo usuário
        
        # Verifica se deve fechar o banco atual antes de criar o novo
        if self.db_manager.get_connection():
            confirmed = messagebox.askyesno(
                "Confirmar", 
                "Já existe um banco de dados aberto. Deseja fechá-lo e abrir o novo banco de dados?")
            if confirmed:
                self.close_database()
            else:
                return
        
        # Obtém o tema atual para o diálogo de progresso
        theme = self.config_manager.get("theme", "light")
        
        # Cria uma janela de progresso
        progress_dialog = ProgressDialog(
            self, 
            title="Criando Banco de Dados", 
            message="Preparando para criar o banco de dados...",
            determinate=True,
            theme=theme
        )
        
        # Define a função que será executada em uma thread separada
        def create_db_task():
            try:
                # Cria o banco de dados
                progress_dialog.update_progress(10, "Criando arquivo de banco de dados...")
                
                # Verifica se o arquivo já existe e o remove
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        error_msg = f"Erro ao remover banco de dados existente: {str(e)}"
                        progress_dialog.complete(error_msg)
                        return
                
                # Cria conexão com o novo banco
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                
                # Cria a tabela principal
                progress_dialog.update_progress(30, "Criando tabela padrão para ROMs...")
                
                # Definição da tabela ROMS atualizada
                create_table_sql = '''
                CREATE TABLE IF NOT EXISTS roms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,                    -- Nome limpo do jogo
                    description TEXT,              -- Descrição completa do DAT
                    name_nointro TEXT,             -- Nome original do DAT
                    name_goodtools TEXT,           -- Nome formato GoodTools
                    name_TOSEC TEXT,               -- Nome formato TOSEC
                    name_redump TEXT,              -- Nome formato Redump
                    name_ROM_Header TEXT,          -- Nome do cabeçalho da ROM
                    name_progetto_EMU TEXT,        -- Nome Progetto EMU
                    name_custom TEXT,              -- Nome customizado
                    name_unofficial_dumps TEXT,    -- Nome de dumps não oficiais
                    flag TEXT,                     -- Flags (bad, verified, etc)
                    language TEXT,                 -- Idiomas
                    distribution TEXT,             -- Tipo de distribuição
                    versions TEXT,                 -- Versão da ROM
                    region TEXT,                   -- Região
                    platform TEXT,                 -- Plataforma/Sistema
                    name TEXT,                     -- Nome do arquivo ROM
                    path_file TEXT,                -- Caminho do arquivo
                    path_image TEXT,               -- Caminho da imagem
                    size_file TEXT,                -- Tamanho do arquivo
                    crc TEXT,                      -- CRC32
                    md5 TEXT,                      -- MD5
                    sha1 TEXT UNIQUE,              -- SHA1 (único)
                    sha256 TEXT,                   -- SHA256
                    serial TEXT,                   -- Número serial
                    BIOS BOOLEAN DEFAULT 0,        -- Se é BIOS
                    source_file TEXT,              -- Arquivo DAT fonte
                    date_added TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Índices para melhorar performance
                CREATE INDEX IF NOT EXISTS idx_title ON roms (title);
                CREATE INDEX IF NOT EXISTS idx_platform ON roms (platform);
                CREATE INDEX IF NOT EXISTS idx_region ON roms (region);
                CREATE INDEX IF NOT EXISTS idx_serial ON roms (serial);
                CREATE INDEX IF NOT EXISTS idx_sha1 ON roms (sha1);
                '''
                
                cursor.executescript(create_table_sql)
                
                # Cria uma tabela de metadados do banco
                progress_dialog.update_progress(80, "Criando metadados...")
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                ''')
                
                # Insere informações de metadados
                metadata = [
                    ('database_version', '1.0'),
                    ('created_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    ('created_by', APP_NAME),
                    ('app_version', APP_VERSION),
                    ('description', 'Banco de dados padrão para ROMs')
                ]
                
                cursor.executemany('INSERT OR REPLACE INTO database_info (key, value) VALUES (?, ?)', metadata)
                
                # Confirma as alterações
                conn.commit()
                conn.close()
                
                # Finaliza com sucesso
                progress_dialog.complete("Banco de dados criado com sucesso!")
                
                # Atualiza a interface após um tempo
                def open_new_db():
                    self.open_database(file_path)
                
                # Agenda a abertura do banco na thread principal após delay
                self.after(WELCOME_SCREEN_DELAY, open_new_db)
                
            except Exception as e:
                error_msg = f"Erro durante a criação: {str(e)}"
                progress_dialog.complete(error_msg)
                messagebox.showerror("Erro", error_msg)
        
        # Executa a tarefa em uma thread separada
        thread = threading.Thread(target=create_db_task)
        thread.start()
    
    def _open_database(self):
        """Abre um diálogo para selecionar um banco de dados."""
        from tkinter import filedialog
        
        file_path = filedialog.askopenfilename(
            title="Abrir Banco de Dados",
            filetypes=[("Banco de Dados SQLite", "*.db *.sqlite *.sqlite3"), 
                      ("Todos os Arquivos", "*.*")]
        )
        
        if file_path:
            self._open_database_file(file_path)
    
    def _open_database_file(self, file_path):
        """Abre um arquivo de banco de dados."""
        # Fecha o banco atual se estiver aberto
        self.db_manager.close()
        
        # Tenta abrir o novo banco
        if self.db_manager.connect(file_path):
            self.event_manager.publish(EventType.DATABASE_OPENED, db_path=file_path)
        else:
            self._show_error("Erro ao abrir banco", 
                           f"Não foi possível abrir o banco de dados:\n{file_path}")
    
    def _close_database(self):
        """Fecha o banco de dados atual."""
        self.db_manager.close()
        self.event_manager.publish(EventType.DATABASE_CLOSED)
    
    def _update_recent_menu(self):
        """Atualiza o menu de bancos de dados recentes."""
        # Limpa o menu
        self.recent_menu.delete(0, tk.END)
        
        # Obtém a lista de bancos recentes
        recent_dbs = self.config_manager.get("recent_databases", [])
        
        if not recent_dbs:
            self.recent_menu.add_command(label="Nenhum banco recente", state=tk.DISABLED)
            return
        
        # Adiciona os bancos recentes ao menu
        for db_path in recent_dbs:
            # Limita o tamanho do caminho exibido
            display_path = db_path
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]
                
            self.recent_menu.add_command(
                label=display_path,
                command=lambda p=db_path: self._open_database_file(p)
            )
        
        # Adiciona opção para limpar a lista
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Limpar Lista", command=self._clear_recent_databases)
    
    def _clear_recent_databases(self):
        """Limpa a lista de bancos de dados recentes."""
        self.config_manager.clear_recent_databases()
        self._update_recent_menu()
    
    def _toggle_navigation(self):
        """Alterna a visibilidade do painel de navegação."""
        self.nav_visible = self.nav_var.get()
        
        if self.nav_visible:
            self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        else:
            self.nav_frame.pack_forget()
        
        # Salva a configuração
        self.config_manager.set("show_navigation", self.nav_visible)
    
    def _change_theme(self, theme_name):
        """Altera o tema da aplicação."""
        self.event_manager.publish(EventType.THEME_CHANGED, theme_name=theme_name)
    
    def _import_dat_file(self):
        """Importa um arquivo DAT."""
        
        if not self.db_manager.get_connection():
            self._show_error("Banco não aberto", 
                           "Você precisa abrir um banco de dados antes de importar")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar Arquivo DAT",
            filetypes=[("Arquivos DAT", "*.dat *.xml"), 
                      ("Todos os Arquivos", "*.*")]
        )
        
        if not file_path:
            return
            
        # Cria diálogo de progresso
        progress_dialog = ProgressDialog(
            self, 
            "Importando DAT", 
            f"Importando {os.path.basename(file_path)}...",
            theme=self.theme
        )
        
        # Função de callback de progresso
        def progress_callback(percent, message, status):
            return progress_dialog.update_progress(percent, message, status)
        
        # Executa a importação em uma tarefa
        def import_task():
            try:
                import_service = self.services['import']
                result = import_service.import_nointro_dats(
                    [file_path], 
                    progress_callback
                )
                
                if progress_dialog.is_cancelled():
                    return
                    
                # Publica evento de importação concluída
                self.event_manager.publish(
                    EventType.IMPORT_COMPLETED, 
                    source_file=file_path, 
                    stats=result
                )
                
                # Atualiza o diálogo de progresso
                progress_dialog.complete("Importação concluída com sucesso!")
                
            except Exception as e:
                self.logger.error(f"Erro na importação: {e}\n{traceback.format_exc()}")
                progress_dialog.error(f"Erro na importação: {str(e)}")
        
        # Agenda a tarefa
        self.task_manager.schedule(
            import_task,
            on_error=lambda task, error, tb: self.logger.error(f"Erro na tarefa de importação: {error}\n{tb}")
        )
    
    def _batch_import_dats(self):
        """Importa um diretório de arquivos DAT."""
        if not self.db_manager.get_connection():
            # Pergunta se deseja criar um novo banco de dados
            should_create = messagebox.askyesno(
                "Banco de Dados Necessário",
                "Nenhum banco de dados está aberto. Deseja criar um novo banco de dados?"
            )
            if should_create:
                # Cria um novo banco de dados
                file_path = filedialog.asksaveasfilename(
                    title="Criar Novo Banco de Dados",
                    defaultextension=".db",
                    filetypes=[("Banco de dados SQLite", "*.db"), ("Todos os arquivos", "*.*")]
                )
                
                if not file_path:
                    return
                
                try:
                    # Remove o arquivo se já existir
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    # Cria nova conexão
                    conn = sqlite3.connect(file_path)
                    cursor = conn.cursor()
                    
                    # Cria a tabela roms
                    cursor.executescript('''
                    CREATE TABLE IF NOT EXISTS roms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,                    -- Nome limpo do jogo
                        description TEXT,              -- Descrição completa do DAT
                        name_nointro TEXT,             -- Nome original do DAT
                        name_goodtools TEXT,           -- Nome formato GoodTools
                        name_TOSEC TEXT,               -- Nome formato TOSEC
                        name_redump TEXT,              -- Nome formato Redump
                        name_ROM_Header TEXT,          -- Nome do cabeçalho da ROM
                        name_progetto_EMU TEXT,        -- Nome Progetto EMU
                        name_custom TEXT,              -- Nome customizado
                        name_unofficial_dumps TEXT,    -- Nome de dumps não oficiais
                        flag TEXT,                     -- Flags (bad, verified, etc)
                        language TEXT,                 -- Idiomas
                        distribution TEXT,             -- Tipo de distribuição
                        versions TEXT,                 -- Versão da ROM
                        region TEXT,                   -- Região
                        platform TEXT,                 -- Plataforma/Sistema
                        name TEXT,                     -- Nome do arquivo ROM
                        path_file TEXT,                -- Caminho do arquivo
                        path_image TEXT,               -- Caminho da imagem
                        size_file TEXT,                -- Tamanho do arquivo
                        crc TEXT,                      -- CRC32
                        md5 TEXT,                      -- MD5
                        sha1 TEXT UNIQUE,              -- SHA1 (único)
                        sha256 TEXT,                   -- SHA256
                        serial TEXT,                   -- Número serial
                        BIOS BOOLEAN DEFAULT 0,        -- Se é BIOS
                        source_file TEXT,              -- Arquivo DAT fonte
                        date_added TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Índices para melhorar performance
                    CREATE INDEX IF NOT EXISTS idx_title ON roms (title);
                    CREATE INDEX IF NOT EXISTS idx_platform ON roms (platform);
                    CREATE INDEX IF NOT EXISTS idx_region ON roms (region);
                    CREATE INDEX IF NOT EXISTS idx_serial ON roms (serial);
                    CREATE INDEX IF NOT EXISTS idx_sha1 ON roms (sha1);
                    
                    -- Tabela de metadados
                    CREATE TABLE IF NOT EXISTS database_info (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                    ''')
                    
                    # Insere metadados
                    metadata = [
                        ('database_version', '1.0'),
                        ('created_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        ('created_by', APP_NAME),
                        ('app_version', APP_VERSION),
                        ('description', 'Banco de dados padrão para ROMs')
                    ]
                    
                    cursor.executemany(
                        'INSERT OR REPLACE INTO database_info (key, value) VALUES (?, ?)',
                        metadata
                    )
                    
                    conn.commit()
                    conn.close()
                    
                    # Verifica a integridade do schema após criação
                    try:
                        from engine.database.schema_validator import validate_database_schema, ValidationLevel
                        result = validate_database_schema(file_path, ValidationLevel.STANDARD)
                        
                        if not result.is_valid:
                            print(f"Aviso: Schema do banco de dados possui problemas:")
                            for issue in result.issues:
                                print(f"  - {issue}")
                            
                            # Tenta correção automática se disponível
                            try:
                                from engine.database.migration_script import DatabaseMigrator
                                migrator = DatabaseMigrator()
                                if migrator.migrate_database(file_path, backup=True):
                                    print("Schema corrigido automaticamente.")
                                else:
                                    print("Falha na correção automática do schema.")
                            except ImportError:
                                print("Script de migração não disponível para correção automática.")
                        else:
                            print("Schema do banco de dados validado com sucesso.")
                            
                    except ImportError:
                        print("Validador de schema não disponível - continuando sem validação.")
                    except Exception as e:
                        print(f"Erro durante validação do schema: {e}")
                    
                    # Abre o novo banco de dados
                    self.db_manager.connect(file_path)
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao criar banco de dados: {str(e)}")
                    return
            else:
                return
        
        # Verifica se a tabela roms existe com a estrutura correta
        cursor = self.db_manager.cursor
        cursor.execute("PRAGMA table_info(roms)")
        columns = {col[1] for col in cursor.fetchall()}
        
        required_columns = {
            'title', 'description', 'name_nointro', 'platform', 
            'name', 'size_file', 'crc', 'md5', 'sha1', 
            'sha256', 'serial', 'BIOS', 'source_file'
        }
        
        missing_columns = required_columns - columns
        if missing_columns:
            # Se faltam colunas, recria a tabela
            should_recreate = messagebox.askyesno(
                "Estrutura Incompatível",
                f"A tabela 'roms' não tem todas as colunas necessárias. Faltam: {', '.join(missing_columns)}.\n\n"
                "Deseja recriar o banco de dados com a estrutura correta?"
            )
            if should_recreate:
                # Fecha a conexão atual
                self.db_manager.close()
                
                # Cria novo banco de dados
                file_path = filedialog.asksaveasfilename(
                    title="Criar Novo Banco de Dados",
                    defaultextension=".db",
                    filetypes=[("Banco de dados SQLite", "*.db"), ("Todos os arquivos", "*.*")]
                )
                
                if not file_path:
                    return
                
                try:
                    # Remove o arquivo se já existir
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    # Cria nova conexão
                    conn = sqlite3.connect(file_path)
                    cursor = conn.cursor()
                    
                    # Cria a tabela roms
                    cursor.executescript('''
                    CREATE TABLE IF NOT EXISTS roms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,                    -- Nome limpo do jogo
                        description TEXT,              -- Descrição completa do DAT
                        name_nointro TEXT,             -- Nome original do DAT
                        name_goodtools TEXT,           -- Nome formato GoodTools
                        name_TOSEC TEXT,               -- Nome formato TOSEC
                        name_redump TEXT,              -- Nome formato Redump
                        name_ROM_Header TEXT,          -- Nome do cabeçalho da ROM
                        name_progetto_EMU TEXT,        -- Nome Progetto EMU
                        name_custom TEXT,              -- Nome customizado
                        name_unofficial_dumps TEXT,    -- Nome de dumps não oficiais
                        flag TEXT,                     -- Flags (bad, verified, etc)
                        language TEXT,                 -- Idiomas
                        distribution TEXT,             -- Tipo de distribuição
                        versions TEXT,                 -- Versão da ROM
                        region TEXT,                   -- Região
                        platform TEXT,                 -- Plataforma/Sistema
                        name TEXT,                     -- Nome do arquivo ROM
                        path_file TEXT,                -- Caminho do arquivo
                        path_image TEXT,               -- Caminho da imagem
                        size_file TEXT,                -- Tamanho do arquivo
                        crc TEXT,                      -- CRC32
                        md5 TEXT,                      -- MD5
                        sha1 TEXT UNIQUE,              -- SHA1 (único)
                        sha256 TEXT,                   -- SHA256
                        serial TEXT,                   -- Número serial
                        BIOS BOOLEAN DEFAULT 0,        -- Se é BIOS
                        source_file TEXT,              -- Arquivo DAT fonte
                        date_added TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Índices para melhorar performance
                    CREATE INDEX IF NOT EXISTS idx_title ON roms (title);
                    CREATE INDEX IF NOT EXISTS idx_platform ON roms (platform);
                    CREATE INDEX IF NOT EXISTS idx_region ON roms (region);
                    CREATE INDEX IF NOT EXISTS idx_serial ON roms (serial);
                    CREATE INDEX IF NOT EXISTS idx_sha1 ON roms (sha1);
                    
                    -- Tabela de metadados
                    CREATE TABLE IF NOT EXISTS database_info (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                    ''')
                    
                    # Insere metadados
                    metadata = [
                        ('database_version', '1.0'),
                        ('created_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        ('created_by', APP_NAME),
                        ('app_version', APP_VERSION),
                        ('description', 'Banco de dados padrão para ROMs')
                    ]
                    
                    cursor.executemany(
                        'INSERT OR REPLACE INTO database_info (key, value) VALUES (?, ?)',
                        metadata
                    )
                    
                    conn.commit()
                    conn.close()
                    
                    # Abre o novo banco de dados
                    self.db_manager.connect(file_path)
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao recriar banco de dados: {str(e)}")
                    return
            else:
                return
        
        # Seleciona o diretório
        dir_path = filedialog.askdirectory(
            title="Selecionar Diretório com Arquivos DAT/XML",
            initialdir=self.config_manager.get("last_import_dir", "")
        )
        
        if not dir_path:
            return
            
        # Salva o diretório para uso futuro
        self.config_manager.set("last_import_dir", dir_path)
        
        # Configura logging específico para esta importação
        log_filename = f"logs/batch_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        os.makedirs(os.path.dirname(log_filename), exist_ok=True)
        
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger = logging.getLogger('batch_import')
        logger.addHandler(file_handler)
        
        try:
            # Busca arquivos DAT e XML recursivamente
            all_files = []
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(('.dat', '.xml')):
                        all_files.append(os.path.join(root, file))
            
            if not all_files:
                messagebox.showwarning(
                    "Aviso", 
                    f"Nenhum arquivo DAT/XML encontrado em:\n{dir_path}"
                )
                return
            
            # Cria diálogo de progresso
            progress_dialog = ProgressDialog(
                self,
                "Importando DATs/XMLs",
                f"Encontrados {len(all_files)} arquivos para processamento...",
                determinate=True,
                theme=self.config_manager.get("theme", "light")
            )
            
            # Estatísticas globais
            total_stats = {
                'processed_files': 0,
                'processed_games': 0,
                'inserted_roms': 0,
                'skipped_roms': 0,
                'errors': 0
            }
            
            # Processa cada arquivo
            for file_idx, file_path in enumerate(all_files, 1):
                if progress_dialog.is_cancelled():
                    logger.info("Importação cancelada pelo usuário")
                    break
                
                file_name = os.path.basename(file_path)
                progress = (file_idx / len(all_files)) * 100
                
                progress_dialog.update_progress(
                    progress,
                    f"Processando arquivo {file_idx} de {len(all_files)}",
                    file_name
                )
                
                logger.info(f"Processando arquivo: {file_path}")
                
                try:
                    # Usa o parser XML atualizado
                    parser = XMLParser()
                    roms_data, file_stats = parser.parse_nointro_xml(
                        file_path,
                        lambda p, m, s: progress_dialog.update_progress(
                            progress + (p / len(all_files)),
                            m, s
                        )
                    )
                    
                    # Atualiza estatísticas
                    total_stats['processed_files'] += 1
                    total_stats['processed_games'] += file_stats['processed_games']
                    total_stats['skipped_roms'] += file_stats['skipped_roms']
                    total_stats['errors'] += file_stats['errors']
                    
                    # Insere os dados no banco
                    for rom_data in roms_data:
                        try:
                            # Verifica se a ROM já existe (pelo SHA1)
                            sha1 = rom_data.get('sha1')
                            if not sha1:
                                logger.warning(f"ROM sem SHA1 em {file_name}, pulando...")
                                total_stats['skipped_roms'] += 1
                                continue
                            
                            # Verifica existência
                            cursor = self.db_manager.cursor
                            cursor.execute("SELECT id FROM roms WHERE sha1 = ?", (sha1,))
                            if cursor.fetchone():
                                logger.debug(f"ROM {rom_data.get('name')} já existe, pulando...")
                                total_stats['skipped_roms'] += 1
                                continue
                            
                            # Prepara a inserção
                            columns = list(rom_data.keys())
                            placeholders = ','.join(['?' for _ in columns])
                            values = [rom_data[col] for col in columns]
                            
                            # Insere no banco
                            query = f"INSERT INTO roms ({','.join(columns)}) VALUES ({placeholders})"
                            cursor.execute(query, values)
                            conn = self.db_manager.get_connection()
                            if conn:
                                conn.commit()
                            
                            total_stats['inserted_roms'] += 1
                            
                        except Exception as e:
                            logger.error(f"Erro ao inserir ROM {rom_data.get('name')}: {e}")
                            total_stats['errors'] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar arquivo {file_path}: {e}\n{traceback.format_exc()}")
                    total_stats['errors'] += 1
            
            # Atualiza a interface
            self.update_tables_list()
            if self.current_table == 'roms':
                self.show_table_data('roms')
            
            # Mostra resumo
            summary = (
                f"Importação concluída!\n\n"
                f"Arquivos processados: {total_stats['processed_files']}\n"
                f"Jogos processados: {total_stats['processed_games']}\n"
                f"ROMs inseridas: {total_stats['inserted_roms']}\n"
                f"ROMs puladas: {total_stats['skipped_roms']}\n"
                f"Erros: {total_stats['errors']}"
            )
            
            progress_dialog.complete(summary)
            logger.info(summary)
            
        except Exception as e:
            error_msg = f"Erro durante a importação: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            progress_dialog.complete(error_msg)
            messagebox.showerror("Erro", error_msg)
        
        finally:
            # Remove o handler de log
            logger.removeHandler(file_handler)
            file_handler.close()
    
    def _import_ini_file(self):
        """Importa um arquivo INI."""
        
        if not self.db_manager.get_connection():
            self._show_error("Banco não aberto", 
                           "Você precisa abrir um banco de dados antes de importar")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar Arquivo INI/TXT",
            filetypes=[("Arquivos INI/TXT", "*.ini *.txt"), 
                      ("Todos os Arquivos", "*.*")]
        )
        
        if not file_path:
            return
            
        # Cria diálogo de progresso
        progress_dialog = ProgressDialog(
            self, 
            "Importando INI", 
            f"Importando {os.path.basename(file_path)}...",
            theme=self.theme
        )
        
        # Função de callback de progresso
        def progress_callback(percent, message, status):
            return progress_dialog.update_progress(percent, message, status)
        
        # Executa a importação em uma tarefa
        def import_task():
            try:
                import_service = self.services['import']
                result = import_service.import_ini_file(
                    file_path, 
                    progress_callback
                )
                
                if progress_dialog.is_cancelled():
                    return
                    
                # Publica evento de importação concluída
                self.event_manager.publish(
                    EventType.IMPORT_COMPLETED, 
                    source_file=file_path, 
                    stats=result
                )
                
                # Atualiza o diálogo de progresso
                progress_dialog.complete("Importação concluída com sucesso!")
                
            except AttributeError:
                # Caso o método import_ini_file não exista no serviço
                error_msg = "Método de importação INI não implementado no serviço"
                self.logger.error(error_msg)
                progress_dialog.error(error_msg)
            except Exception as e:
                self.logger.error(f"Erro na importação INI: {e}\n{traceback.format_exc()}")
                progress_dialog.error(f"Erro na importação: {str(e)}")
        
        # Agenda a tarefa
        self.task_manager.schedule(
            import_task,
            on_error=lambda task, error, tb: self.logger.error(f"Erro na tarefa de importação INI: {error}\n{tb}")
        )
    
    def _verify_roms(self):
        """Verifica ROMs em um diretório."""
        
        if not self.db_manager.get_connection():
            self._show_error("Banco não aberto", 
                           "Você precisa abrir um banco de dados antes de verificar ROMs")
            return
        
        # Verifica se a tabela roms existe
        if not self.db_manager.table_exists('roms'):
            self._show_error("Tabela não encontrada", 
                           "A tabela 'roms' não existe no banco de dados. Importe DATs primeiro.")
            return
        
        # Diálogo para selecionar o diretório de ROMs
        dir_path = filedialog.askdirectory(
            title="Selecionar Diretório de ROMs para Verificação",
            initialdir=self.config_manager.get("last_roms_dir", "")
        )
        
        if not dir_path:
            return
            
        # Salva o diretório para uso futuro
        self.config_manager.set("last_roms_dir", dir_path)
        
        # Cria diálogo de progresso
        progress_dialog = ProgressDialog(
            self, 
            "Verificando ROMs", 
            f"Escaneando diretório: {dir_path}...",
            theme=self.theme
        )
        
        # Função de callback de progresso
        def progress_callback(percent, message, status):
            return progress_dialog.update_progress(percent, message, status)
        
        # Executa a verificação em uma tarefa
        def verify_task():
            try:
                verification_service = self.services['verification']
                result = verification_service.verify_directory(
                    dir_path, 
                    progress_callback
                )
                
                if progress_dialog.is_cancelled():
                    return
                
                # Exibe resultados da verificação
                matched = result.get('matched', 0)
                missing = result.get('missing', 0)
                unknown = result.get('unknown', 0)
                total = matched + missing + unknown
                
                summary = f"Verificação concluída!\n\n"
                summary += f"Total de arquivos: {total}\n"
                summary += f"Encontrados no banco: {matched}\n"
                summary += f"Ausentes no banco: {missing}\n"
                summary += f"Desconhecidos: {unknown}"
                
                progress_dialog.complete(summary)
                
            except AttributeError:
                # Caso o método verify_directory não exista no serviço
                error_msg = "Método de verificação não implementado no serviço"
                self.logger.error(error_msg)
                progress_dialog.error(error_msg)
            except Exception as e:
                self.logger.error(f"Erro na verificação: {e}\n{traceback.format_exc()}")
                progress_dialog.error(f"Erro durante verificação: {str(e)}")
        
        # Agenda a tarefa
        self.task_manager.schedule(
            verify_task,
            on_error=lambda task, error, tb: self.logger.error(f"Erro na tarefa de verificação: {error}\n{tb}")
        )
    
    def _export_data(self):
        """Exporta dados da tabela atual."""
        # Implementação será adicionada
        self.set_status("Funcionalidade de exportação não implementada")
    
    def _open_query_editor(self):
        """Abre o editor de consultas SQL."""
        # Implementação será adicionada
        self.set_status("Funcionalidade de consulta SQL não implementada")
    
    def _show_database_stats(self):
        """Exibe estatísticas do banco de dados."""
        # Implementação será adicionada
        self.set_status("Funcionalidade de estatísticas não implementada")
    
    def _show_documentation(self):
        """Exibe a documentação do aplicativo."""
        self._show_info("Documentação", 
                       "A documentação completa está disponível em:\nhttps://github.com/seu-usuario/megaemu-database")
    
    def _show_about(self):
        """Exibe informações sobre o aplicativo."""
        about_text = """
        MegaEmu DataBase ROMs
        
        Versão: 1.0.0
        
        Um aplicativo para gerenciamento de coleções de ROMs
        com funcionalidades de importação, verificação e organização.
        
        Desenvolvido com Python e Tkinter.
        """
        
        self._show_info("Sobre", about_text)
    
    def _show_info(self, title, message):
        """Exibe uma mensagem de informação."""
        from tkinter import messagebox
        messagebox.showinfo(title, message, parent=self)
    
    def _show_error(self, title, message):
        """Exibe uma mensagem de erro."""
        messagebox.showerror(title, message, parent=self)
    
    def _show_warning(self, title, message):
        """Exibe uma mensagem de aviso."""
        messagebox.showwarning(title, message, parent=self)
    
    def set_status(self, message):
        """Define a mensagem na barra de status."""
        self.status_var.set(message)
        self.logger.info(message)
    
    def on_closing(self):
        """Manipula o evento de fechamento da aplicação."""
        # Salva o tamanho da janela
        window_size = f"{self.winfo_width()}x{self.winfo_height()}"
        self.config_manager.set("window_size", window_size)
        
        # Publica evento de fechamento
        self.event_manager.publish(EventType.APP_CLOSING)
        
        # Fecha o banco de dados
        self.db_manager.close()
        
        # Desliga o gerenciador de tarefas
        self.task_manager.shutdown()
        
        # Fecha a aplicação
        self.logger.info("Aplicação encerrada pelo usuário")
        self.destroy()

    def _show_welcome_if_needed(self):
        """Exibe a tela de boas-vindas se configurado para tal."""
        show_welcome = self.config_manager.get("show_welcome", True)
        
        if show_welcome:
            self.logger.info("Exibindo tela de boas-vindas")
            
            # Callbacks para as ações da tela de boas-vindas
            callbacks = {
                "create_database": self._create_new_database,
                "open_database": self._open_database,
                "open_database_file": self._open_database_file,
                "import_dat": self._import_dat_file,
                "import_ini": self._import_ini_file,
                "verify_roms": self._verify_roms,
                "explore_directory": self._explore_directory  # Você pode implementar este método
            }
            
            welcome_screen = WelcomeScreen(
                self,
                self.config_manager,
                self.theme,
                callbacks
            )

    def _explore_directory(self):
        """Explora um diretório de ROMs para análise."""
        
        dir_path = filedialog.askdirectory(
            title="Selecionar Diretório de ROMs",
            initialdir=self.config_manager.get("last_roms_dir", "")
        )
        
        if not dir_path:
            return
        
        # Salva o diretório para uso futuro
        self.config_manager.set("last_roms_dir", dir_path)
        
        # Cria diálogo de progresso
        progress_dialog = ProgressDialog(
            self, 
            "Analisando Diretório", 
            f"Escaneando {dir_path}...",
            theme=self.theme
        )
        
        # Executa análise em uma tarefa separada
        def scan_task():
            try:
                scanner = self.utils['directory_scanner']
                result = scanner.scan_directory(
                    dir_path,
                    lambda percent, message, status: progress_dialog.update_progress(percent, message, status)
                )
                
                if progress_dialog.is_cancelled():
                    return
                
                progress_dialog.complete(f"Análise concluída. Encontrados {len(result['files'])} arquivos.")
                
                # Exibe os resultados
                self._show_directory_scan_results(result)
                
            except Exception as e:
                self.logger.error(f"Erro ao analisar diretório: {e}\n{traceback.format_exc()}")
                progress_dialog.error(f"Erro na análise: {str(e)}")
        
        # Agenda a tarefa
        self.task_manager.schedule(
            scan_task,
            on_error=lambda task, error, tb: self.logger.error(f"Erro na tarefa de análise: {error}\n{tb}")
        )

    def _show_directory_scan_results(self, scan_results):
        """Exibe os resultados da análise de diretório."""
        # Implementação simples para mostrar estatísticas
        stats = {
            "total_files": len(scan_results["files"]),
            "total_size": sum(f["size"] for f in scan_results["files"]),
            "extensions": {}
        }
        
        # Conta arquivos por extensão
        for file in scan_results["files"]:
            ext = os.path.splitext(file["name"])[1].lower()
            if ext in stats["extensions"]:
                stats["extensions"][ext] += 1
            else:
                stats["extensions"][ext] = 1
        
        # Formata o tamanho
        total_size_formatted = self._format_size(stats["total_size"])
        
        # Monta a mensagem
        message = f"Total de arquivos: {stats['total_files']}\n"
        message += f"Tamanho total: {total_size_formatted}\n\n"
        message += "Arquivos por extensão:\n"
        
        for ext, count in sorted(stats["extensions"].items(), key=lambda x: x[1], reverse=True):
            message += f"  {ext}: {count}\n"
        
        # Exibe a mensagem
        self._show_info("Análise de Diretório", message)
        
        # TODO: Implementar uma visualização mais detalhada dos resultados
        # em uma janela separada com opções para verificar ou importar os arquivos

    def _format_size(self, size_bytes):
        """Formata o tamanho em bytes para uma string legível."""
        try:
            size = float(size_bytes)
            # Bytes
            if size < 1024:
                return f"{size:.0f} B"
            # Kilobytes
            if size < 1024 * 1024:
                return f"{size/1024:.2f} KB"
            # Megabytes
            if size < 1024 * 1024 * 1024:
                return f"{size/(1024*1024):.2f} MB"
            # Gigabytes
            return f"{size/(1024*1024*1024):.2f} GB"
        except (ValueError, TypeError):
            return "Desconhecido"

    def create_standard_database(self):
        """Cria um novo banco de dados com estrutura padrão para ROMs."""
        # ... código existente ...

        # Definição da tabela ROMS atualizada
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS roms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,                    -- Nome limpo do jogo
            description TEXT,              -- Descrição completa do DAT
            name_nointro TEXT,             -- Nome original do DAT
            name_goodtools TEXT,           -- Nome formato GoodTools
            name_TOSEC TEXT,               -- Nome formato TOSEC
            name_redump TEXT,              -- Nome formato Redump
            name_ROM_Header TEXT,          -- Nome do cabeçalho da ROM
            name_progetto_EMU TEXT,        -- Nome Progetto EMU
            name_custom TEXT,              -- Nome customizado
            name_unofficial_dumps TEXT,    -- Nome de dumps não oficiais
            flag TEXT,                     -- Flags (bad, verified, etc)
            language TEXT,                 -- Idiomas
            distribution TEXT,             -- Tipo de distribuição
            versions TEXT,                 -- Versão da ROM
            region TEXT,                   -- Região
            platform TEXT,                 -- Plataforma/Sistema
            name TEXT,                     -- Nome do arquivo ROM
            path_file TEXT,                -- Caminho do arquivo
            path_image TEXT,               -- Caminho da imagem
            size_file TEXT,                -- Tamanho do arquivo
            crc TEXT,                      -- CRC32
            md5 TEXT,                      -- MD5
            sha1 TEXT UNIQUE,              -- SHA1 (único)
            sha256 TEXT,                   -- SHA256
            serial TEXT,                   -- Número serial
            BIOS BOOLEAN DEFAULT 0,        -- Se é BIOS
            source_file TEXT,              -- Arquivo DAT fonte
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sha1)                   -- Garante SHA1 único
        );
        
        -- Índices para melhorar performance
        CREATE INDEX IF NOT EXISTS idx_title ON roms (title);
        CREATE INDEX IF NOT EXISTS idx_platform ON roms (platform);
        CREATE INDEX IF NOT EXISTS idx_region ON roms (region);
        CREATE INDEX IF NOT EXISTS idx_serial ON roms (serial);
        '''

# Ponto de entrada principal
if __name__ == "__main__":
    # Configura logging
    logger = setup_logging()
    
    try:
        # Inicia a aplicação
        app = MegaEmuDBApp()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Erro fatal na aplicação: {e}", exc_info=True)
        
        # Tenta exibir uma mensagem de erro mesmo em caso de falha
        try:
            import tkinter.messagebox as msgbox
            msgbox.showerror("Erro Fatal", 
                           f"Um erro crítico ocorreu e o aplicativo precisa ser encerrado:\n\n{str(e)}")
        except:
            pass