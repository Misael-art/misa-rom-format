# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Main Window
Janela principal da aplicação
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from typing import Dict, Any, Optional, Callable
import os
import sys
import queue
from pathlib import Path
import xml.etree.ElementTree as ET # Importar para tratar erros de parsing XML
import sqlite3 # Importar para tratar erros de SQLite
from concurrent.futures import ThreadPoolExecutor

# Import do módulo de compressão
from engine.utils.compression import compress_rom, decompress_rom, get_compression_ratio
# Import do módulo de compressão
from engine.utils.compression import compress_rom, decompress_rom, get_compression_ratio, compress_misa, decompress_misa
from engine.ai_picker import pick_ultimate_strategy
from engine.utils.capp import fingerprint_header
from engine.config import (
    SUPPORTED_FORMATS, DEFAULT_DB_PATH, MISA_HEADER_SIZE, MISA_META_FMT,
    COMPRESSION_LEVELS, BATCH_SIZE, MAX_WORKERS
)
from engine.errors import DependencyResolutionError

# Adiciona o diretório raiz ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from ui.components.navigation_panel import NavigationPanel
from ui.components.status_bar import StatusBar, StatusType
from ui.components.toolbar import Toolbar, ToolbarStyle
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.progress_dialog import ProgressDialog
from ui.screens.welcome_screen import WelcomeScreen
from ui.screens.roms_screen import ROMsScreen
from engine.config_manager_enhanced import EnhancedConfigManager
from engine.ui import UnifiedThemeManager as ThemeManager
from engine.di.dependency_container import DependencyContainer
from engine.errors import ConfigError, DependencyResolutionError

logger = logging.getLogger(__name__)

class MainWindow:
    """Janela principal da aplicação."""
    
    def __init__(self, dependency_container: DependencyContainer = None):
        """
        Inicializa a janela principal.
        
        Args:
            dependency_container: Container de dependências
        """
        self.dependency_container = dependency_container or DependencyContainer()
        
        # Componentes principais
        self.root = None
        self.navigation_panel = None
        self.toolbar = None
        self.status_bar = None
        self.content_area = None
        self.current_screen = None
        
        # Gerenciadores
        self.config_manager = None
        self.theme_manager = None
        
        # Estado da aplicação
        self.is_maximized = False
        self.window_geometry = "1200x800"
        self.current_database = None

        # Fila para comunicação thread-safe com UI
        self.ui_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Callbacks
        self._callbacks: Dict[str, Callable] = {}
        
        self._setup_managers()
        self._create_window()
        self._setup_ui()
        self._setup_callbacks()
        self._setup_shortcuts()
        self._apply_theme()
        
        # Mostra tela de boas-vindas
        self._show_welcome_screen()
        
        logger.info("Janela principal inicializada")
    
    def _setup_managers(self):
        """Configura os gerenciadores."""
        try:
            # Config Manager
            self.config_manager = self.dependency_container.resolve(EnhancedConfigManager)
            if not self.config_manager:
                self.config_manager = EnhancedConfigManager()
                self.dependency_container.register_singleton(EnhancedConfigManager, self.config_manager)
                
            # Theme Manager
            self.theme_manager = self.dependency_container.resolve(ThemeManager)
            if not self.theme_manager:
                self.theme_manager = ThemeManager(self.config_manager)
                self.dependency_container.register_singleton(ThemeManager, self.theme_manager)
                
        except (ConfigError, DependencyResolutionError) as e:
            logger.error(f"Erro ao configurar gerenciadores (ConfigError/DependencyResolutionError): {e}")
            # Fallback para gerenciadores padrão
            self.config_manager = EnhancedConfigManager()
            self.theme_manager = ThemeManager(self.config_manager)
        except Exception as e:
            logger.error(f"Erro inesperado ao configurar gerenciadores: {e}", exc_info=True)
            # Fallback para gerenciadores padrão
            self.config_manager = EnhancedConfigManager()
            self.theme_manager = ThemeManager(self.config_manager)
    
    def _create_window(self):
        """Cria a janela principal."""
        self.root = tk.Tk()
        self.root.title("MegaEmu DataBase ROMs")
        
        # Configurações da janela
        self.root.geometry(self.window_geometry)
        self.root.minsize(800, 600)
        
        # Ícone da aplicação
        try:
            # Tenta carregar ícone se existir
            icon_path = Path(__file__).parent / "assets" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except FileNotFoundError:
            logger.warning(f"Arquivo de ícone não encontrado: {icon_path}")
        except tk.TclError as e:
            logger.warning(f"Erro do Tkinter ao carregar ícone: {e}")
        except Exception as e:
            logger.warning(f"Erro inesperado ao carregar ícone: {e}", exc_info=True)
        
        # Protocolo de fechamento
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Eventos da janela
        self.root.bind('<Configure>', self._on_window_configure)
        
        # Centraliza a janela
        self._center_window()
    
    def _setup_ui(self):
        """Configura a interface da janela."""
        # Frame principal
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Toolbar
        self._create_toolbar()
        
        # Frame de conteúdo
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Painel de navegação
        self._create_navigation_panel()
        
        # Separador
        separator = ttk.Separator(self.content_frame, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Área de conteúdo principal
        self._create_content_area()
        
        # Barra de status
        self._create_status_bar()
    
    def _create_toolbar(self):
        """Cria a toolbar."""
        self.toolbar = Toolbar(
            self.main_frame,
            config_manager=self.config_manager,
            theme_manager=self.theme_manager,
            style=ToolbarStyle.ICONS_AND_TEXT
        )
        self.toolbar.pack(fill=tk.X, pady=(0, 2))
    
    def _create_navigation_panel(self):
        """Cria o painel de navegação."""
        self.navigation_panel = NavigationPanel(
            self.content_frame,
            config_manager=self.config_manager,
            theme_manager=self.theme_manager
        )
        self.navigation_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        
        # Define largura inicial
        self.navigation_panel.config(width=250)
    
    def _create_content_area(self):
        """Cria a área de conteúdo principal."""
        self.content_area = ttk.Frame(self.content_frame)
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame para telas
        self.screen_frame = ttk.Frame(self.content_area)
        self.screen_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _create_status_bar(self):
        """Cria a barra de status."""
        self.status_bar = StatusBar(
            self.main_frame,
            config_manager=self.config_manager,
            theme_manager=self.theme_manager
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(2, 0))
    
    def _setup_callbacks(self):
        """Configura callbacks dos componentes."""
        # Callbacks da toolbar
        toolbar_callbacks = {
            "compress_roms": self._compress_selected_roms,
            "decompress_roms": self._decompress_selected_roms,
            "optimize_misa": self._optimize_misa_clicked,
            "new_database": self._new_database,
            "open_database": self._open_database,
            "save_database": self._save_database,
            "import_xml": self._import_xml,
            "import_roms": self._import_roms,
            "compress_roms": self._compress_selected_roms,
            "decompress_roms": self._decompress_selected_roms,
            "export_xml": self._export_xml,
            "export_csv": self._export_csv,
            "export_json": self._export_json,
            "view_list": self._view_list,
            "view_grid": self._view_grid,
            "view_details": self._view_details,
            "search_roms": self._search_roms,
            "filter_roms": self._filter_roms,
            "refresh": self._refresh,
            "settings": self._show_settings,
            "help": self._show_help,
            "search_changed": self._on_search_changed
        }
        
        for action_id, callback in toolbar_callbacks.items():
            self.toolbar.register_callback(action_id, callback)
        
        # Callbacks do painel de navegação
        navigation_callbacks = {
            "view_roms": self._view_roms,
            "search_roms": self._search_roms,
            "statistics": self._show_statistics,
            "import_xml": self._import_xml,
            "import_roms": self._import_roms,
            "import_history": self._show_import_history,
            "backup": self._backup_database,
            "maintenance": self._show_maintenance,
            "export": self._export_data,
            "preferences": self._show_settings,
            "themes": self._show_theme_settings,
            "about": self._show_about,
            "documentation": self._show_documentation
        }
        
        for action_id, callback in navigation_callbacks.items():
            self.navigation_panel.register_callback(action_id, callback)
    
    def _setup_shortcuts(self):
        """Configura atalhos de teclado."""
        shortcuts = {
            '<Control-n>': self._new_database,
            '<Control-o>': self._open_database,
            '<Control-s>': self._save_database,
            '<Control-f>': self._search_roms,
            '<F5>': self._refresh,
            '<F1>': self._show_help,
            '<Control-q>': self._on_closing,
            '<Alt-F4>': self._on_closing,
            '<Escape>': self._on_escape
        }
        
        for shortcut, callback in shortcuts.items():
            self.root.bind(shortcut, lambda event, cb=callback: cb())
    
    def _center_window(self):
        """Centraliza a janela na tela."""
        self.root.update_idletasks()
        
        # Obtém dimensões da tela
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Obtém dimensões da janela
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Calcula posição central
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"+{x}+{y}")
    
    def _show_welcome_screen(self):
        """Mostra a tela de boas-vindas."""
        try:
            self._clear_content_area()
            
            self.current_screen = WelcomeScreen(
                self.screen_frame,
                config_manager=self.config_manager,
                theme_manager=self.theme_manager
            )
            self.current_screen.pack(fill=tk.BOTH, expand=True)
            
            # Registra callbacks da tela de boas-vindas
            welcome_callbacks = {
                "new_database": self._new_database,
                "open_database": self._open_database,
                "import_xml": self._import_xml,
                "settings": self._show_settings
            }
            
            for action_id, callback in welcome_callbacks.items():
                self.current_screen.register_callback(action_id, callback)
            
            self.status_bar.show_message("Bem-vindo ao MegaEmu DataBase ROMs", StatusType.INFO)
            
        except Exception as e:
            logger.error(f"Erro inesperado ao mostrar tela de boas-vindas: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao carregar tela inicial: {e}", StatusType.ERROR)
    
    def _clear_content_area(self):
        """Limpa a área de conteúdo."""
        for widget in self.screen_frame.winfo_children():
            widget.destroy()
        self.current_screen = None
    
    # Callbacks da Toolbar
    def _new_database(self):
        """Cria novo banco de dados."""
        try:
            # Implementar criação de novo banco
            self.status_bar.show_message("Criando novo banco de dados...", StatusType.INFO)
            logger.info("Novo banco de dados solicitado")
            
            # Placeholder - implementar lógica real
            messagebox.showinfo("Novo Banco", "Funcionalidade em desenvolvimento")
            
        except (OSError, PermissionError) as e:
            logger.error(f"Erro de sistema de arquivos ao criar novo banco: {e}")
            self.status_bar.show_message(f"Erro de permissão/disco ao criar banco: {e}", StatusType.ERROR)
        except Exception as e:
            logger.error(f"Erro inesperado ao criar novo banco: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao criar banco: {e}", StatusType.ERROR)
    
    def _open_database(self):
        """Abre banco de dados existente."""
        try:
            file_path = filedialog.askopenfilename(
                title="Abrir Banco de Dados",
                filetypes=[
                    ("Banco SQLite", "*.db *.sqlite *.sqlite3"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if file_path:
                self.status_bar.show_message(f"Abrindo banco: {os.path.basename(file_path)}", StatusType.INFO)
                logger.info(f"Abrindo banco de dados: {file_path}")
                
                # Placeholder - implementar lógica real
                self.current_database = file_path
                messagebox.showinfo("Banco Aberto", f"Banco carregado: {os.path.basename(file_path)}")
                
        except FileNotFoundError:
            logger.error(f"Arquivo de banco de dados não encontrado: {file_path}")
            self.status_bar.show_message("Erro: Arquivo de banco de dados não encontrado.", StatusType.ERROR)
        except PermissionError:
            logger.error(f"Permissão negada ao abrir banco de dados: {file_path}")
            self.status_bar.show_message("Erro: Permissão negada para abrir o banco de dados.", StatusType.ERROR)
        except sqlite3.Error as e:
            logger.error(f"Erro de SQLite ao abrir banco de dados: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro de banco de dados: {e}", StatusType.ERROR)
        except Exception as e:
            logger.error(f"Erro inesperado ao abrir banco de dados: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao abrir banco: {e}", StatusType.ERROR)
    
    def _save_database(self):
        """Salva banco de dados atual."""
        try:
            if not self.current_database:
                self.status_bar.show_message("Nenhum banco aberto", StatusType.WARNING)
                return
            
            self.status_bar.show_message("Salvando banco de dados...", StatusType.INFO)
            logger.info("Salvando banco de dados")
            
            # Placeholder - implementar lógica real
            messagebox.showinfo("Salvar", "Banco salvo com sucesso")
            
        except (OSError, PermissionError) as e:
            logger.error(f"Erro de sistema de arquivos ao salvar banco de dados: {e}")
            self.status_bar.show_message(f"Erro de permissão/disco ao salvar banco: {e}", StatusType.ERROR)
        except sqlite3.Error as e:
            logger.error(f"Erro de SQLite ao salvar banco de dados: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro de banco de dados ao salvar: {e}", StatusType.ERROR)
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar banco de dados: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao salvar banco: {e}", StatusType.ERROR)
    
    def _import_xml(self):
        """Importa dados de arquivo XML."""
        try:
            file_path = filedialog.askopenfilename(
                title="Importar XML",
                filetypes=[
                    ("Arquivos XML", "*.xml"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if file_path:
                self.status_bar.show_message(f"Importando XML: {os.path.basename(file_path)}", StatusType.INFO)
                logger.info(f"Importando XML: {file_path}")
                
                # Mostra diálogo de progresso
                progress_dialog = ProgressDialog(
                    self.root,
                    title="Importando XML",
                    message="Processando arquivo XML..."
                )
                
                # Placeholder - implementar lógica real
                progress_dialog.destroy()
                messagebox.showinfo("Importação", "XML importado com sucesso")
                
        except FileNotFoundError:
            logger.error(f"Arquivo XML não encontrado: {file_path}")
            self.status_bar.show_message("Erro: Arquivo XML não encontrado.", StatusType.ERROR)
        except PermissionError:
            logger.error(f"Permissão negada ao importar XML: {file_path}")
            self.status_bar.show_message("Erro: Permissão negada para importar XML.", StatusType.ERROR)
        except ET.ParseError as e: # Para erros de parsing XML
            logger.error(f"Erro de parsing XML ao importar: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro de parsing XML: {e}", StatusType.ERROR)
        except sqlite3.Error as e: # Para erros de banco de dados durante a importação
            logger.error(f"Erro de SQLite durante a importação de XML: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro de banco de dados na importação: {e}", StatusType.ERROR)
        except Exception as e:
            logger.error(f"Erro inesperado ao importar XML: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao importar XML: {e}", StatusType.ERROR)
    
    def _import_roms(self):
        """Importa arquivos ROM."""
        try:
            folder_path = filedialog.askdirectory(
                title="Selecionar Pasta de ROMs"
            )
            
            if folder_path:
                self.status_bar.show_message(f"Importando ROMs de: {os.path.basename(folder_path)}", StatusType.INFO)
                logger.info(f"Importando ROMs de: {folder_path}")
                
                # Placeholder - implementar lógica real
                messagebox.showinfo("Importação", "ROMs importados com sucesso")
                
        except (OSError, PermissionError) as e:
            logger.error(f"Erro de sistema de arquivos ao importar ROMs: {e}")
            self.status_bar.show_message(f"Erro de permissão/disco ao importar ROMs: {e}", StatusType.ERROR)
        except Exception as e:
            logger.error(f"Erro inesperado ao importar ROMs: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao importar ROMs: {e}", StatusType.ERROR)
    
    def _export_xml(self):
        """Exporta dados para XML."""
        self._export_data("XML")
    
    def _export_csv(self):
        """Exporta dados para CSV."""
        self._export_data("CSV")
    
    def _export_json(self):
        """Exporta dados para JSON."""
        self._export_data("JSON")
    
    def _export_data(self, format_type: str = "XML"):
        """Exporta dados no formato especificado."""
        try:
            file_types = {
                "XML": [("Arquivos XML", "*.xml")],
                "CSV": [("Arquivos CSV", "*.csv")],
                "JSON": [("Arquivos JSON", "*.json")]
            }
            
            file_path = filedialog.asksaveasfilename(
                title=f"Exportar {format_type}",
                filetypes=file_types.get(format_type, [("Todos os arquivos", "*.*")])
            )
            
            if file_path:
                self.status_bar.show_message(f"Exportando para {format_type}...", StatusType.INFO)
                logger.info(f"Exportando para {format_type}: {file_path}")
                
                # Placeholder - implementar lógica real
                messagebox.showinfo("Exportação", f"Dados exportados para {format_type} com sucesso")
                
        except (OSError, PermissionError) as e:
            logger.error(f"Erro de sistema de arquivos ao exportar para {format_type}: {e}")
            self.status_bar.show_message(f"Erro de permissão/disco ao exportar: {e}", StatusType.ERROR)
        except Exception as e: # Captura outras exceções inesperadas
            logger.error(f"Erro inesperado ao exportar para {format_type}: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro inesperado ao exportar: {e}", StatusType.ERROR)
    
    def _view_list(self):
        """Alterna para visualização em lista."""
        self.toolbar.set_toggle_state("view_list", True)
        self.toolbar.set_toggle_state("view_grid", False)
        self.toolbar.set_toggle_state("view_details", False)
        self.status_bar.show_message("Visualização em lista ativada", StatusType.INFO)
    
    def _view_grid(self):
        """Alterna para visualização em grade."""
        self.toolbar.set_toggle_state("view_list", False)
        self.toolbar.set_toggle_state("view_grid", True)
        self.toolbar.set_toggle_state("view_details", False)
        self.status_bar.show_message("Visualização em grade ativada", StatusType.INFO)
    
    def _view_details(self):
        """Alterna para visualização detalhada."""
        self.toolbar.set_toggle_state("view_list", False)
        self.toolbar.set_toggle_state("view_grid", False)
        self.toolbar.set_toggle_state("view_details", True)
        self.status_bar.show_message("Visualização detalhada ativada", StatusType.INFO)
    
    def _search_roms(self):
        """Abre busca de ROMs."""
        try:
            # Foca no campo de busca da toolbar
            search_entry = self.toolbar._widgets.get("search_field_entry")
            if search_entry:
                search_entry.focus()
            
            self.status_bar.show_message("Modo de busca ativado", StatusType.INFO)
            
        except Exception as e:
            logger.error(f"Erro ao ativar busca: {e}")
            self.status_bar.show_message(f"Erro ao ativar busca: {e}", StatusType.ERROR)
    
    def _filter_roms(self):
        """Abre filtros de ROMs."""
        try:
            self.status_bar.show_message("Abrindo filtros...", StatusType.INFO)
            # Placeholder - implementar diálogo de filtros
            messagebox.showinfo("Filtros", "Funcionalidade em desenvolvimento")
            
        except Exception as e:
            logger.error(f"Erro ao abrir filtros: {e}")
            self.status_bar.show_message(f"Erro ao abrir filtros: {e}", StatusType.ERROR)
    
    def _refresh(self):
        """Atualiza dados da aplicação."""
        try:
            self.status_bar.show_message("Atualizando dados...", StatusType.INFO)
            
            # Atualiza componentes
            if self.navigation_panel:
                self.navigation_panel.refresh()
            if self.toolbar:
                self.toolbar.refresh()
            if self.status_bar:
                self.status_bar.refresh()
            
            self.status_bar.show_message("Dados atualizados", StatusType.SUCCESS)
            logger.info("Dados atualizados")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar dados: {e}")
            self.status_bar.show_message(f"Erro ao atualizar: {e}", StatusType.ERROR)
    
    def _show_settings(self):
        """Mostra diálogo de configurações."""
        try:
            settings_dialog = SettingsDialog(
                self.root,
                config_manager=self.config_manager,
                theme_manager=self.theme_manager
            )
            
            # Aguarda fechamento do diálogo
            self.root.wait_window(settings_dialog)
            
            # Aplica mudanças se necessário
            self._apply_theme()
            
        except Exception as e:
            logger.error(f"Erro ao abrir configurações: {e}")
            self.status_bar.show_message(f"Erro ao abrir configurações: {e}", StatusType.ERROR)
    
    def _show_help(self):
        """Mostra ajuda da aplicação."""
        try:
            help_text = """
        except Exception as e:
        logger.error(f"Erro em _show_help: {e}", exc_info=True)
        raise
MegaEmu DataBase ROMs - Ajuda

Atalhos de Teclado:
• Ctrl+N: Novo banco de dados
• Ctrl+O: Abrir banco de dados
• Ctrl+S: Salvar banco de dados
• Ctrl+F: Buscar ROMs
• F5: Atualizar dados
• F1: Mostrar esta ajuda
• Ctrl+Q: Sair da aplicação

Funcionalidades:
• Importação de dados XML
• Gerenciamento de ROMs
• Busca e filtros avançados
• Exportação de dados
• Temas personalizáveis

Para mais informações, consulte a documentação.
            """
            
            messagebox.showinfo("Ajuda", help_text)
            
        except Exception as e:
            logger.error(f"Erro ao mostrar ajuda: {e}")
            self.status_bar.show_message(f"Erro ao mostrar ajuda: {e}", StatusType.ERROR)
    def _optimize_misa_clicked(self):
        """Otimiza ROMs selecionadas com formato MISA."""
        try:
            if not hasattr(self, 'current_screen') or not isinstance(self.current_screen, ROMsScreen):
                self.status_bar.show_message("Selecione ROMs primeiro", StatusType.WARNING)
                return

            selected_roms = self.current_screen.get_selected_roms()
            if not selected_roms:
                self.status_bar.show_message("Nenhuma ROM selecionada", StatusType.WARNING)
                return

            # Confirma operação
            result = messagebox.askyesno(
                "Otimizar com MISA",
                f"Otimizar {len(selected_roms)} ROM(s) selecionada(s) com formato MISA?\n"
                "Isso aplicará CAPP otimizado e compressão adaptativa."
            )

            if result:
                self.status_bar.show_message("Otimizando ROMs com MISA...", StatusType.INFO)

                # Executa otimização em background
                self.executor.submit(self._perform_misa_optimization, selected_roms)

        except Exception as e:
            logger.error(f"Erro ao iniciar otimização MISA: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao otimizar: {e}", StatusType.ERROR)

    def _perform_misa_optimization(self, roms):
        """Executa otimização MISA em background."""
        try:
            total_files = len(roms)
            processed_files = 0
            success_count = 0

            # Envia progresso inicial
            self.ui_queue.put({
                'type': 'misa_progress',
                'data': {'current': 0, 'total': total_files, 'filename': 'Iniciando...'}
            })

            for rom in roms:
                try:
                    file_path = rom.get('path', '')
                    console = rom.get('console', 'unknown')

                    # Lê dados da ROM
                    with open(file_path, 'rb') as f:
                        rom_data = f.read()

                    # Seleciona estratégia ótima
                    strategy = pick_ultimate_strategy(Path(file_path), console)

                    # Comprime com MISA
                    misa_data = compress_misa(rom_data, console)

                    # Define caminho de saída (.misa)
                    misa_path = file_path.rsplit('.', 1)[0] + '.misa'
                    with open(misa_path, 'wb') as f:
                        f.write(misa_data)

                    # Calcula ganho
                    original_size = len(rom_data)
                    compressed_size = len(misa_data)
                    gain = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

                    success_count += 1
                    processed_files += 1

                    # Envia progresso
                    self.ui_queue.put({
                        'type': 'misa_progress',
                        'data': {
                            'current': processed_files,
                            'total': total_files,
                            'filename': rom.get('filename', ''),
                            'capp': strategy['capp'],
                            'gain': gain
                        }
                    })

                except Exception as e:
                    logger.error(f"Erro ao processar {rom.get('filename', '')}: {e}")
                    processed_files += 1

            # Otimização concluída
            self.ui_queue.put({
                'type': 'misa_complete',
                'data': {'successful': success_count, 'total': total_files}
            })

        except Exception as e:
            logger.error(f"Erro durante otimização MISA: {e}", exc_info=True)
            self.ui_queue.put({
                'type': 'misa_error',
                'data': {'error': str(e)}
            })

    def _compress_selected_roms(self):
    
    def _on_search_changed(self):
        """Manipula mudança na busca."""
        search_text = self.toolbar.get_search_text()
        if search_text:
            self.status_bar.show_message(f"Buscando: {search_text}", StatusType.INFO)
            # Implementar lógica de busca

    def _compress_selected_roms(self):
        """Comprime ROMs selecionadas."""
        try:
            if not hasattr(self, 'current_screen') or not isinstance(self.current_screen, ROMsScreen):
                self.status_bar.show_message("Selecione ROMs primeiro", StatusType.WARNING)
                return

            selected_roms = self.current_screen.get_selected_roms()
            if not selected_roms:
                self.status_bar.show_message("Nenhuma ROM selecionada", StatusType.WARNING)
                return

            # Confirma operação
            result = messagebox.askyesno(
                "Comprimir ROMs",
                f"Comprimir {len(selected_roms)} ROM(s) selecionada(s)?\n"
                "Isso criará arquivos .misa comprimidos."
            )

            if result:
                self.status_bar.show_message("Comprimindo ROMs...", StatusType.INFO)

                # Executa compressão em background
                self.executor.submit(self._perform_compression, selected_roms, "compress")

        except Exception as e:
            logger.error(f"Erro ao iniciar compressão: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao comprimir: {e}", StatusType.ERROR)

    def _decompress_selected_roms(self):
        """Descomprime ROMs selecionadas."""
        try:
            if not hasattr(self, 'current_screen') or not isinstance(self.current_screen, ROMsScreen):
                self.status_bar.show_message("Selecione ROMs primeiro", StatusType.WARNING)
                return

            selected_roms = self.current_screen.get_selected_roms()
            if not selected_roms:
                self.status_bar.show_message("Nenhuma ROM selecionada", StatusType.WARNING)
                return

            # Filtra apenas arquivos .misa
            misa_files = [rom for rom in selected_roms if rom.get('filename', '').endswith('.misa')]
            if not misa_files:
                self.status_bar.show_message("Nenhum arquivo .misa selecionado", StatusType.WARNING)
                return

            # Confirma operação
            result = messagebox.askyesno(
                "Descomprimir ROMs",
                f"Descomprimir {len(misa_files)} arquivo(s) .misa?\n"
                "Isso restaurará os arquivos originais."
            )

            if result:
                self.status_bar.show_message("Descomprimindo ROMs...", StatusType.INFO)

                # Executa descompressão em background
                self.executor.submit(self._perform_compression, misa_files, "decompress")

        except Exception as e:
            logger.error(f"Erro ao iniciar descompressão: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao descomprimir: {e}", StatusType.ERROR)
    
    # Callbacks do Painel de Navegação
    def _view_roms(self):
        """Mostra visualização de ROMs."""
        self.status_bar.show_message("Carregando lista de ROMs...", StatusType.INFO)
        # Implementar visualização de ROMs
    
    def _show_statistics(self):
        """Mostra estatísticas do banco."""
        self.status_bar.show_message("Carregando estatísticas...", StatusType.INFO)
        # Implementar estatísticas
    
    def _show_import_history(self):
        """Mostra histórico de importações."""
        self.status_bar.show_message("Carregando histórico...", StatusType.INFO)
        # Implementar histórico
    
    def _backup_database(self):
        """Faz backup do banco de dados."""
        try:
            if not self.current_database:
                self.status_bar.show_message("Nenhum banco aberto", StatusType.WARNING)
                return
            
            backup_path = filedialog.asksaveasfilename(
                title="Salvar Backup",
                filetypes=[("Backup SQLite", "*.bak"), ("Todos os arquivos", "*.*")]
            )
            
            if backup_path:
                self.status_bar.show_message("Criando backup...", StatusType.INFO)
                # Implementar backup
                messagebox.showinfo("Backup", "Backup criado com sucesso")
                
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            self.status_bar.show_message(f"Erro ao criar backup: {e}", StatusType.ERROR)
    
    def _show_maintenance(self):
        """Mostra ferramentas de manutenção."""
        self.status_bar.show_message("Abrindo manutenção...", StatusType.INFO)
        # Implementar manutenção
    
    def _show_theme_settings(self):
        """Mostra configurações de tema."""
        self._show_settings()  # Por enquanto, redireciona para configurações gerais
    
    def _show_about(self):
        """Mostra informações sobre a aplicação."""
        try:
            about_text = """
MegaEmu DataBase ROMs
Versão 1.0.0

Um gerenciador completo de banco de dados para ROMs de emuladores.

Desenvolvido com Python e Tkinter.

© 2024 - Todos os direitos reservados.
            """
            
            messagebox.showinfo("Sobre", about_text)
            
        except Exception as e:
            logger.error(f"Erro ao mostrar sobre: {e}")
    
    def _show_documentation(self):
        """Mostra documentação."""
        try:
            # Implementar abertura de documentação
            messagebox.showinfo("Documentação", "Documentação em desenvolvimento")
            
        except Exception as e:
            logger.error(f"Erro ao abrir documentação: {e}")
    
    # Eventos da Janela
    def _on_window_configure(self, event):
        """Manipula redimensionamento da janela."""
        if event.widget == self.root:
            # Salva geometria da janela
            self.window_geometry = self.root.geometry()
        # Agenda processamento da fila UI
        self.root.after(100, self._process_ui_queue)

        logger.info("Janela principal inicializada")
    
    def _on_closing(self):
        """Manipula fechamento da aplicação."""
        try:
            # Confirma fechamento se houver dados não salvos
            if self.current_database:
                result = messagebox.askyesnocancel(
                    "Fechar Aplicação",
                    "Deseja salvar as alterações antes de sair?"
                )
                
                if result is None:  # Cancelar
                    return
                elif result:  # Sim
                    self._save_database()
            
            # Salva configurações
            if self.config_manager:
                try:
                    self.config_manager.save_config()
                except Exception as e:
        elif msg_type == 'compress_progress':
            self._update_compress_progress(data)
        elif msg_type == 'compress_complete':
            self._on_compress_complete(data)
        elif msg_type == 'compress_error':
            self._on_compress_error(data)
        elif msg_type == 'misa_progress':
            self._update_misa_progress(data)
        elif msg_type == 'misa_complete':
            self._on_misa_complete(data)
        elif msg_type == 'misa_error':
            self._on_misa_error(data)
                    logger.error(f"Erro ao salvar configurações: {e}")
            
            logger.info("Aplicação fechada")
            self.root.destroy()
            
        except Exception as e:
            logger.error(f"Erro ao fechar aplicação: {e}")
            self.root.destroy()
    
    def _on_escape(self):
        """Manipula tecla Escape."""
        # Limpa busca ou fecha diálogos
        if self.toolbar:
            self.toolbar.set_search_text("")
    
    def _apply_theme(self):
        """Aplica tema à janela."""
        if self.theme_manager:
            try:
                # Aplicar tema aos componentes
                theme = self.theme_manager.get_current_theme()
                
                # Atualizar componentes
                if self.navigation_panel:
                    self.navigation_panel.refresh()
                if self.toolbar:
                    self.toolbar.refresh()
                if self.status_bar:
                    self.status_bar.refresh()
                
    def _update_misa_progress(self, data):
        """Atualiza progresso da otimização MISA."""
        current = data.get('current', 0)
        total = data.get('total', 1)
        filename = data.get('filename', '')
        capp = data.get('capp', 0)
        gain = data.get('gain', 0)

        # Atualiza status bar se existir
        if hasattr(self.status_bar, 'show_progress'):
            progress = (current / total) * 100 if total > 0 else 0
            message = f"Otimizando: {os.path.basename(filename) if filename else 'arquivo'}"
            if capp > 0:
                message += f" (CAPP: 0x{capp:02X}, ganho: {gain:.1f}%)"
            self.status_bar.show_progress(message, progress)

    def _on_misa_complete(self, data):
        """Chamado quando otimização MISA é concluída."""
        successful = data.get('successful', 0)
        total = data.get('total', 0)

        # Oculta progresso
        if hasattr(self.status_bar, 'hide_progress'):
            self.status_bar.hide_progress()

        # Atualiza status
        if successful == total:
            self.status_bar.show_message(
                f"Otimização MISA concluída: {successful}/{total} arquivos",
                StatusType.SUCCESS
            )
        else:
            self.status_bar.show_message(
                f"Otimização MISA concluída: {successful}/{total} arquivos (com erros)",
                StatusType.WARNING
            )

        # Atualiza tela de ROMs se estiver ativa
        if hasattr(self, 'current_screen') and isinstance(self.current_screen, ROMsScreen):
            self.current_screen.refresh()  # Recarrega dados

    def _on_misa_error(self, data):
        """Manipula erros durante otimização MISA."""
        error_msg = data.get('error', 'Erro desconhecido')
        self.status_bar.show_message(f"Erro na otimização MISA: {error_msg}", StatusType.ERROR)

    def _update_compress_progress(self, data):
            except Exception as e:
                logger.error(f"Erro ao aplicar tema: {e}")
    
    def run(self):
        """Executa a aplicação."""
        try:
            logger.info("Iniciando aplicação")
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Erro na execução da aplicação: {e}")
            raise
    
    def show_message(self, message: str, message_type: StatusType = StatusType.INFO):
        """Mostra mensagem na barra de status."""
        if self.status_bar:
            self.status_bar.show_message(message, message_type)
    
    def show_progress(self, message: str, progress: float):
        """Mostra progresso na barra de status."""
        if self.status_bar:
            self.status_bar.show_progress(message, progress)
    
    def hide_progress(self):
        """Oculta progresso da barra de status."""
        if self.status_bar:
            self.status_bar.hide_progress()
    
    def get_root(self) -> tk.Tk:
        """Retorna a janela raiz."""
        return self.root
    
    def register_callback(self, action_id: str, callback: Callable):
        """Registra callback personalizado."""
        self._callbacks[action_id] = callback

        # Registra nos componentes apropriados
        if self.toolbar:
            self.toolbar.register_callback(action_id, callback)
        if self.navigation_panel:
            self.navigation_panel.register_callback(action_id, callback)

    def _process_ui_queue(self):
        """Processa mensagens da fila da UI para thread-safety."""
        try:
            while True:
                message = self.ui_queue.get_nowait()
                self._handle_ui_message(message)
        except queue.Empty:
            pass

        # Agenda próxima verificação
        self.root.after(100, self._process_ui_queue)

    def _handle_ui_message(self, message):
        """Manipula mensagens da fila da UI."""
        msg_type = message.get('type', '')
        data = message.get('data', {})

        if msg_type == 'scan_progress':
            self._update_scan_progress(data)
        elif msg_type == 'scan_complete':
            self._on_scan_complete(data)
        elif msg_type == 'rom_found':
            self._add_rom_to_screen(data)
        elif msg_type == 'scan_error':
            self._on_scan_error(data)
        elif msg_type == 'compress_progress':
            self._update_compress_progress(data)
        elif msg_type == 'compress_complete':
            self._on_compress_complete(data)
        elif msg_type == 'compress_error':
            self._on_compress_error(data)
        elif msg_type == 'misa_progress':
            self._update_misa_progress(data)
        elif msg_type == 'misa_complete':
            self._on_misa_complete(data)
        elif msg_type == 'misa_error':
            self._on_misa_error(data)

    def _update_scan_progress(self, data):
        """Atualiza progresso do scan."""
        current = data.get('current', 0)
        total = data.get('total', 1)
        filename = data.get('filename', '')

        # Atualiza status bar se existir
        if hasattr(self.status_bar, 'show_progress'):
            progress = (current / total) * 100 if total > 0 else 0
            self.status_bar.show_progress(f"Scaneando: {os.path.basename(filename) if filename else 'ROMs'}", progress)

    def _on_scan_complete(self, data):
        """Chamado quando scan é concluído."""
        self.is_scanning = False

        # Oculta progresso
        if hasattr(self.status_bar, 'hide_progress'):
            self.status_bar.hide_progress()

        # Atualiza status
        roms_found = data.get('roms_found', 0)
        self.status_bar.show_message(f"Scan concluído: {roms_found} ROMs encontradas", StatusType.SUCCESS)

        # Atualiza tela de ROMs se estiver ativa
        if hasattr(self, 'current_screen') and isinstance(self.current_screen, ROMsScreen):
            roms_data = data.get('roms_data', [])
            self.current_screen.update_roms_data(roms_data)

    def _add_rom_to_screen(self, data):
        """Adiciona ROM à tela atual."""
        if hasattr(self, 'current_screen') and isinstance(self.current_screen, ROMsScreen):
            rom_data = data.get('rom_data', {})
            self.current_screen.roms_data.append(rom_data)
            self.current_screen._apply_filters()

    def _on_scan_error(self, data):
        """Manipula erros durante scan."""
        self.is_scanning = False
        error_msg = data.get('error', 'Erro desconhecido durante scan')
        self.status_bar.show_message(f"Erro no scan: {error_msg}", StatusType.ERROR)

    def _update_compress_progress(self, data):
        """Atualiza progresso da compressão/descompressão."""
        current = data.get('current', 0)
        total = data.get('total', 1)
        filename = data.get('filename', '')
        ratio = data.get('ratio', 0)

        # Atualiza status bar se existir
        if hasattr(self.status_bar, 'show_progress'):
            progress = (current / total) * 100 if total > 0 else 0
            message = f"Processando: {os.path.basename(filename) if filename else 'arquivo'}"
            if ratio > 0:
                message += f" (ratio: {ratio:.2f})"
            self.status_bar.show_progress(message, progress)

    def _on_compress_complete(self, data):
        """Chamado quando compressão/descompressão é concluída."""
        operation = data.get('operation', 'operação')
        processed = data.get('processed', 0)
        successful = data.get('successful', 0)

        # Oculta progresso
        if hasattr(self.status_bar, 'hide_progress'):
            self.status_bar.hide_progress()

        # Atualiza status
        if successful == processed:
            self.status_bar.show_message(
                f"{operation.capitalize()} concluída: {successful}/{processed} arquivos",
                StatusType.SUCCESS
            )
        else:
            self.status_bar.show_message(
                f"{operation.capitalize()} concluída: {successful}/{processed} arquivos (com erros)",
                StatusType.WARNING
            )

        # Atualiza tela de ROMs se estiver ativa
        if hasattr(self, 'current_screen') and isinstance(self.current_screen, ROMsScreen):
            self.current_screen.refresh()  # Recarrega dados

    def _on_compress_error(self, data):
        """Manipula erros durante compressão/descompressão."""
        error_msg = data.get('error', 'Erro desconhecido')
        operation = data.get('operation', 'operação')
        self.status_bar.show_message(f"Erro na {operation}: {error_msg}", StatusType.ERROR)

    def _scan_roms(self):
        """Inicia scan de ROMs em background."""
        if hasattr(self, 'is_scanning') and self.is_scanning:
            self.status_bar.show_message("Scan já em andamento", StatusType.WARNING)
            return

        try:
            folder_path = filedialog.askdirectory(
                title="Selecionar Pasta para Scan de ROMs"
            )

            if folder_path:
                self.is_scanning = True
                self.status_bar.show_message("Iniciando scan de ROMs...", StatusType.INFO)
                logger.info(f"Iniciando scan de ROMs em: {folder_path}")

                # Executa scan em background
                self.executor.submit(self._perform_scan, folder_path)

                # Mostra tela de ROMs se não estiver ativa
                if not hasattr(self, 'current_screen') or not isinstance(self.current_screen, ROMsScreen):
                    self._show_roms_screen()

        except Exception as e:
            logger.error(f"Erro ao iniciar scan de ROMs: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao iniciar scan: {e}", StatusType.ERROR)
            if hasattr(self, 'is_scanning'):
                self.is_scanning = False

    def _perform_scan(self, folder_path):
        """Executa scan de ROMs em background."""
        try:
            total_files = 0
            processed_files = 0
            roms_found = []

            # Conta total de arquivos primeiro
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(('.zip', '.7z', '.rar', '.nes', '.sfc', '.smc', '.gba', '.gbc', '.gb', '.nds', '.md', '.gen', '.bin', '.cue', '.iso')):
                        total_files += 1

            # Envia mensagem de progresso inicial
            self.ui_queue.put({
                'type': 'scan_progress',
                'data': {'current': 0, 'total': total_files, 'filename': 'Iniciando...'}
            })

            # Scan dos arquivos
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(('.zip', '.7z', '.rar', '.nes', '.sfc', '.smc', '.gba', '.gbc', '.gb', '.nds', '.md', '.gen', '.bin', '.cue', '.iso')):
                        processed_files += 1

                        # Simula processamento (em produção, verificar hash, tamanho, etc.)
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        file_modified = os.path.getmtime(file_path) if os.path.exists(file_path) else 0

                        # Determina plataforma baseada na extensão
                        platform = self._guess_platform(file)

                        rom_data = {
                            'filename': file,
                            'path': file_path,
                            'platform': platform,
                            'size': self._format_size(file_size),
                            'modified': self._format_date(file_modified),
                            'status': 'Presente' if os.path.exists(file_path) else 'Ausente'
                        }

                        roms_found.append(rom_data)

                        # Envia progresso
                        self.ui_queue.put({
                            'type': 'scan_progress',
                            'data': {'current': processed_files, 'total': total_files, 'filename': file}
                        })

                        # Pequena pausa para simular processamento
                        import time
                        time.sleep(0.01)

            # Scan concluído
            self.ui_queue.put({
                'type': 'scan_complete',
                'data': {'roms_found': len(roms_found), 'roms_data': roms_found}
            })

        except Exception as e:
            logger.error(f"Erro durante scan: {e}", exc_info=True)
            self.ui_queue.put({
                'type': 'scan_error',
                'data': {'error': str(e)}
            })
            if hasattr(self, 'is_scanning'):
                self.is_scanning = False

    def _guess_platform(self, filename):
        """Tenta determinar plataforma baseada no nome do arquivo."""
        filename_lower = filename.lower()

        if any(ext in filename_lower for ext in ['.nes']):
            return 'NES'
        elif any(ext in filename_lower for ext in ['.sfc', '.smc']):
            return 'SNES'
        elif any(ext in filename_lower for ext in ['.gba']):
            return 'GBA'
        elif any(ext in filename_lower for ext in ['.gbc']):
            return 'GBC'
        elif any(ext in filename_lower for ext in ['.gb']):
            return 'GB'
        elif any(ext in filename_lower for ext in ['.nds']):
            return 'NDS'
        elif any(ext in filename_lower for ext in ['.md', '.gen']):
            return 'Genesis'
        elif any(ext in filename_lower for ext in ['.bin', '.cue', '.iso']):
            return 'PS1'
        else:
            return 'Desconhecida'

    def _format_size(self, size_bytes):
        """Formata tamanho de arquivo."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_date(self, timestamp):
        """Formata timestamp para data."""
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))

    def _show_roms_screen(self):
        """Mostra tela de ROMs."""
        try:
            self._clear_content_area()

            self.current_screen = ROMsScreen(
                self.screen_frame,
                config_manager=self.config_manager,
                theme_manager=self.theme_manager
            )
            self.current_screen.pack(fill=tk.BOTH, expand=True)

            # Registra callback para scan
            self.current_screen.register_callback("scan_roms", self._scan_roms)

            self.status_bar.show_message("Tela de ROMs carregada", StatusType.INFO)

        except Exception as e:
            logger.error(f"Erro ao mostrar tela de ROMs: {e}", exc_info=True)
            self.status_bar.show_message(f"Erro ao carregar tela de ROMs: {e}", StatusType.ERROR)

    def _perform_compression(self, roms_list, operation):
        """Executa compressão/descompressão em background."""
        try:
            total_files = len(roms_list)
            processed_files = 0
            success_count = 0

            # Envia progresso inicial
            self.ui_queue.put({
                'type': 'compress_progress',
                'data': {'current': 0, 'total': total_files, 'filename': 'Iniciando...'}
            })

            # Processa arquivos em paralelo
            futures = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                for rom in roms_list:
                    future = executor.submit(self._process_single_file, rom, operation)
                    futures.append((future, rom))

                # Coleta resultados
                for future, rom in futures:
                    try:
                        result = future.result(timeout=60)  # 60s timeout por arquivo
                        if result['success']:
                            success_count += 1

                        processed_files += 1

                        # Atualiza progresso
                        filename = rom.get('filename', 'Arquivo desconhecido')
                        self.ui_queue.put({
                            'type': 'compress_progress',
                            'data': {
                                'current': processed_files,
                                'total': total_files,
                                'filename': filename,
                                'ratio': result.get('ratio', 0)
                            }
                        })

                    except Exception as e:
                        logger.error(f"Erro ao processar {rom.get('filename', '')}: {e}")
                        processed_files += 1

            # Operação concluída
            operation_name = "compressão" if operation == "compress" else "descompressão"
            self.ui_queue.put({
                'type': 'compress_complete',
                'data': {
                    'operation': operation_name,
                    'processed': processed_files,
                    'successful': success_count
                }
            })

        except Exception as e:
            logger.error(f"Erro durante {operation}: {e}", exc_info=True)
            self.ui_queue.put({
                'type': 'compress_error',
                'data': {'error': str(e), 'operation': operation}
            })

    def _process_single_file(self, rom_data, operation):
        """Processa um arquivo individual."""
        try:
            file_path = rom_data.get('path', '')

            if operation == "compress":
                # Lê arquivo original
                with open(file_path, "rb") as f:
                    data = f.read()

                # Comprime
                compressed_data = compress_rom(data)

                # Salva como .misa
                misa_path = file_path.rsplit('.', 1)[0] + '.misa'
                with open(misa_path, "wb") as f:
                    f.write(compressed_data)

                # Calcula ratio
                ratio = get_compression_ratio(data, compressed_data)

                return {
                    'success': True,
                    'ratio': ratio,
                    'output_path': misa_path
                }

            elif operation == "decompress":
                # Lê arquivo .misa
                with open(file_path, "rb") as f:
                    compressed_data = f.read()

                # Descomprime
                original_data = decompress_rom(compressed_data)

                # Restaura nome original (remove .misa)
                original_path = file_path.rsplit('.', 1)[0]
                with open(original_path, "wb") as f:
                    f.write(original_data)

                return {
                    'success': True,
                    'ratio': 1.0,  # Descompressão sempre 1.0
                    'output_path': original_path
                }

        except Exception as e:
            logger.error(f"Erro ao processar arquivo {rom_data.get('filename', '')}: {e}")
            return {'success': False, 'error': str(e)}
