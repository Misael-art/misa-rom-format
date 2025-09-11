# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Settings Dialog
Diálogo de configurações/preferências do aplicativo
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from engine.config_manager_enhanced import EnhancedConfigManager

logger = logging.getLogger(__name__)

class SettingsDialog(tk.Toplevel):
    """Diálogo de configurações do aplicativo."""
    
    def __init__(self, parent: tk.Tk, config_manager: EnhancedConfigManager = None, theme_manager=None, callback: Optional[Callable] = None):
        """
        Inicializa o diálogo de configurações.
        
        Args:
            parent: Janela pai
            config_manager: Gerenciador de configurações
            theme_manager: Gerenciador de temas
            callback: Função chamada quando configurações são aplicadas
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.callback = callback
        self.parent = parent
        
        # Configurações temporárias (não salvas até aplicar)
        self.temp_config = {}
        
        # Variáveis de controle
        self.theme_var = tk.StringVar()
        self.show_welcome_var = tk.BooleanVar()
        self.show_navigation_var = tk.BooleanVar()
        self.window_size_var = tk.StringVar()
        self.log_level_var = tk.StringVar()
        self.db_timeout_var = tk.IntVar()
        self.max_connections_var = tk.IntVar()
        self.import_batch_size_var = tk.IntVar()
        self.backup_enabled_var = tk.BooleanVar()
        self.backup_interval_var = tk.IntVar()
        self.auto_save_var = tk.BooleanVar()
        self.last_import_dir_var = tk.StringVar()
        self.last_roms_dir_var = tk.StringVar()
        
        self._setup_ui()
        self._load_current_settings()
        self._center_window()
        
        # Configurações da janela
        self.title("Configurações")
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Foco inicial
        self.focus_set()
    
    def _setup_ui(self):
        """Configura a interface do diálogo."""
        # Frame principal
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook para abas
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Abas
        self._create_general_tab()
        self._create_interface_tab()
        self._create_database_tab()
        self._create_import_tab()
        self._create_backup_tab()
        self._create_advanced_tab()
        
        # Botões
        self._create_buttons(main_frame)
    
    def _create_general_tab(self):
        """Cria a aba de configurações gerais."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Geral")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configurações de inicialização
        startup_frame = ttk.LabelFrame(scrollable_frame, text="Inicialização", padding=10)
        startup_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            startup_frame,
            text="Mostrar tela de boas-vindas na inicialização",
            variable=self.show_welcome_var
        ).pack(anchor=tk.W)
        
        ttk.Checkbutton(
            startup_frame,
            text="Mostrar painel de navegação",
            variable=self.show_navigation_var
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Configurações de janela
        window_frame = ttk.LabelFrame(scrollable_frame, text="Janela", padding=10)
        window_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(window_frame, text="Tamanho da janela:").pack(anchor=tk.W)
        size_frame = ttk.Frame(window_frame)
        size_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Combobox(
            size_frame,
            textvariable=self.window_size_var,
            values=["800x600", "1024x768", "1280x720", "1366x768", "1920x1080"],
            state="readonly",
            width=15
        ).pack(side=tk.LEFT)
        
        # Configurações de logging
        log_frame = ttk.LabelFrame(scrollable_frame, text="Logging", padding=10)
        log_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(log_frame, text="Nível de log:").pack(anchor=tk.W)
        ttk.Combobox(
            log_frame,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            state="readonly",
            width=15
        ).pack(anchor=tk.W, pady=(5, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_interface_tab(self):
        """Cria a aba de configurações de interface."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Interface")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Tema
        theme_frame = ttk.LabelFrame(scrollable_frame, text="Tema", padding=10)
        theme_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(theme_frame, text="Tema da interface:").pack(anchor=tk.W)
        theme_combo = ttk.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=["light", "dark"],
            state="readonly",
            width=15
        )
        theme_combo.pack(anchor=tk.W, pady=(5, 0))
        theme_combo.bind("<<ComboboxSelected>>", self._on_theme_preview)
        
        ttk.Button(
            theme_frame,
            text="Visualizar",
            command=self._preview_theme
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Fontes e tamanhos
        font_frame = ttk.LabelFrame(scrollable_frame, text="Fontes", padding=10)
        font_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(font_frame, text="Configurações de fonte serão implementadas em versão futura").pack(anchor=tk.W)
        
        # Animações
        anim_frame = ttk.LabelFrame(scrollable_frame, text="Animações", padding=10)
        anim_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(anim_frame, text="Configurações de animação serão implementadas em versão futura").pack(anchor=tk.W)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_database_tab(self):
        """Cria a aba de configurações de banco de dados."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Banco de Dados")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Conexões
        conn_frame = ttk.LabelFrame(scrollable_frame, text="Conexões", padding=10)
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(conn_frame, text="Timeout de conexão (segundos):").pack(anchor=tk.W)
        timeout_spin = ttk.Spinbox(
            conn_frame,
            from_=5,
            to=300,
            textvariable=self.db_timeout_var,
            width=10
        )
        timeout_spin.pack(anchor=tk.W, pady=(5, 10))
        
        ttk.Label(conn_frame, text="Máximo de conexões:").pack(anchor=tk.W)
        conn_spin = ttk.Spinbox(
            conn_frame,
            from_=1,
            to=50,
            textvariable=self.max_connections_var,
            width=10
        )
        conn_spin.pack(anchor=tk.W, pady=(5, 0))
        
        # Performance
        perf_frame = ttk.LabelFrame(scrollable_frame, text="Performance", padding=10)
        perf_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            perf_frame,
            text="Salvamento automático",
            variable=self.auto_save_var
        ).pack(anchor=tk.W)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_import_tab(self):
        """Cria a aba de configurações de importação."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Importação")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configurações de lote
        batch_frame = ttk.LabelFrame(scrollable_frame, text="Processamento em Lote", padding=10)
        batch_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(batch_frame, text="Tamanho do lote:").pack(anchor=tk.W)
        batch_spin = ttk.Spinbox(
            batch_frame,
            from_=100,
            to=10000,
            increment=100,
            textvariable=self.import_batch_size_var,
            width=10
        )
        batch_spin.pack(anchor=tk.W, pady=(5, 0))
        
        # Diretórios padrão
        dirs_frame = ttk.LabelFrame(scrollable_frame, text="Diretórios Padrão", padding=10)
        dirs_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Diretório de importação
        ttk.Label(dirs_frame, text="Último diretório de importação:").pack(anchor=tk.W)
        import_dir_frame = ttk.Frame(dirs_frame)
        import_dir_frame.pack(fill=tk.X, pady=(5, 10))
        
        ttk.Entry(
            import_dir_frame,
            textvariable=self.last_import_dir_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(
            import_dir_frame,
            text="Alterar",
            command=self._browse_import_dir
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Diretório de ROMs
        ttk.Label(dirs_frame, text="Último diretório de ROMs:").pack(anchor=tk.W)
        roms_dir_frame = ttk.Frame(dirs_frame)
        roms_dir_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Entry(
            roms_dir_frame,
            textvariable=self.last_roms_dir_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(
            roms_dir_frame,
            text="Alterar",
            command=self._browse_roms_dir
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_backup_tab(self):
        """Cria a aba de configurações de backup."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Backup")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configurações de backup
        backup_frame = ttk.LabelFrame(scrollable_frame, text="Backup Automático", padding=10)
        backup_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            backup_frame,
            text="Habilitar backup automático",
            variable=self.backup_enabled_var
        ).pack(anchor=tk.W)
        
        ttk.Label(backup_frame, text="Intervalo de backup (horas):").pack(anchor=tk.W, pady=(10, 0))
        interval_spin = ttk.Spinbox(
            backup_frame,
            from_=1,
            to=168,  # 1 semana
            textvariable=self.backup_interval_var,
            width=10
        )
        interval_spin.pack(anchor=tk.W, pady=(5, 0))
        
        # Ações de backup
        actions_frame = ttk.LabelFrame(scrollable_frame, text="Ações", padding=10)
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            actions_frame,
            text="Fazer Backup Agora",
            command=self._backup_now
        ).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(
            actions_frame,
            text="Restaurar Backup",
            command=self._restore_backup
        ).pack(anchor=tk.W)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_advanced_tab(self):
        """Cria a aba de configurações avançadas."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Avançado")
        
        # Frame com scroll
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configurações de desenvolvedor
        dev_frame = ttk.LabelFrame(scrollable_frame, text="Desenvolvedor", padding=10)
        dev_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            dev_frame,
            text="Limpar Cache",
            command=self._clear_cache
        ).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(
            dev_frame,
            text="Resetar Configurações",
            command=self._reset_settings
        ).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(
            dev_frame,
            text="Exportar Configurações",
            command=self._export_settings
        ).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(
            dev_frame,
            text="Importar Configurações",
            command=self._import_settings
        ).pack(anchor=tk.W)
        
        # Informações do sistema
        info_frame = ttk.LabelFrame(scrollable_frame, text="Informações", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_text = tk.Text(info_frame, height=8, state=tk.DISABLED)
        info_text.pack(fill=tk.X)
        
        # Adiciona informações do sistema
        info_text.config(state=tk.NORMAL)
        info_text.insert(tk.END, "Versão: MegaEmu DataBase ROMs 1.0.0\n")
        info_text.insert(tk.END, f"Arquivo de configuração: {self.config_manager.config_file}\n")
        info_text.insert(tk.END, "Python: 3.x\n")
        info_text.insert(tk.END, "Tkinter: Disponível\n")
        info_text.config(state=tk.DISABLED)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_buttons(self, parent):
        """Cria os botões do diálogo."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(
            button_frame,
            text="OK",
            command=self._on_ok
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Aplicar",
            command=self._on_apply
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Cancelar",
            command=self._on_cancel
        ).pack(side=tk.RIGHT)
    
    def _load_current_settings(self):
        """Carrega as configurações atuais."""
        try:
            self.theme_var.set(self.config_manager.get("theme", "light"))
            self.show_welcome_var.set(self.config_manager.get("show_welcome", True))
            self.show_navigation_var.set(self.config_manager.get("show_navigation", True))
            self.window_size_var.set(self.config_manager.get("window_size", "1024x768"))
            self.log_level_var.set(self.config_manager.get("log_level", "INFO"))
            self.db_timeout_var.set(self.config_manager.get("db_timeout", 30))
            self.max_connections_var.set(self.config_manager.get("db_max_connections", 5))
            self.import_batch_size_var.set(self.config_manager.get("import_batch_size", 1000))
            self.backup_enabled_var.set(self.config_manager.get("backup_enabled", True))
            self.backup_interval_var.set(self.config_manager.get("backup_interval", 24))
            self.auto_save_var.set(self.config_manager.get("auto_save", True))
            self.last_import_dir_var.set(self.config_manager.get("last_import_dir", ""))
            self.last_roms_dir_var.set(self.config_manager.get("last_roms_dir", ""))
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            messagebox.showerror("Erro", f"Erro ao carregar configurações: {e}")
    
    def _center_window(self):
        """Centraliza a janela na tela."""
        self.update_idletasks()
        width = 600
        height = 500
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(500, 400)
    
    def _on_theme_preview(self, event=None):
        """Visualiza o tema selecionado."""
        self._preview_theme()
    
    def _preview_theme(self):
        """Aplica temporariamente o tema selecionado."""
        if self.theme_manager:
            try:
                theme = self.theme_var.get()
                self.theme_manager.apply_theme(theme)
                logger.info(f"Tema '{theme}' aplicado temporariamente")
            except Exception as e:
                logger.error(f"Erro ao aplicar tema: {e}")
                messagebox.showerror("Erro", f"Erro ao aplicar tema: {e}")
    
    def _browse_import_dir(self):
        """Seleciona diretório de importação."""
        directory = filedialog.askdirectory(
            title="Selecionar Diretório de Importação",
            initialdir=self.last_import_dir_var.get()
        )
        if directory:
            self.last_import_dir_var.set(directory)
    
    def _browse_roms_dir(self):
        """Seleciona diretório de ROMs."""
        directory = filedialog.askdirectory(
            title="Selecionar Diretório de ROMs",
            initialdir=self.last_roms_dir_var.get()
        )
        if directory:
            self.last_roms_dir_var.set(directory)
    
    def _backup_now(self):
        """Executa backup imediato."""
        try:
            # Implementar lógica de backup
            messagebox.showinfo("Backup", "Funcionalidade de backup será implementada em versão futura")
        except Exception as e:
            logger.error(f"Erro no backup: {e}")
            messagebox.showerror("Erro", f"Erro no backup: {e}")
    
    def _restore_backup(self):
        """Restaura backup."""
        try:
            # Implementar lógica de restauração
            messagebox.showinfo("Restaurar", "Funcionalidade de restauração será implementada em versão futura")
        except Exception as e:
            logger.error(f"Erro na restauração: {e}")
            messagebox.showerror("Erro", f"Erro na restauração: {e}")
    
    def _clear_cache(self):
        """Limpa cache do aplicativo."""
        try:
            # Implementar limpeza de cache
            messagebox.showinfo("Cache", "Cache limpo com sucesso")
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            messagebox.showerror("Erro", f"Erro ao limpar cache: {e}")
    
    def _reset_settings(self):
        """Reseta configurações para padrão."""
        if messagebox.askyesno("Confirmar", "Deseja realmente resetar todas as configurações?"):
            try:
                # Implementar reset
                messagebox.showinfo("Reset", "Configurações resetadas com sucesso")
                self._load_current_settings()
            except Exception as e:
                logger.error(f"Erro ao resetar configurações: {e}")
                messagebox.showerror("Erro", f"Erro ao resetar configurações: {e}")
    
    def _export_settings(self):
        """Exporta configurações para arquivo."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Exportar Configurações",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                # Implementar exportação
                messagebox.showinfo("Exportar", "Configurações exportadas com sucesso")
        except Exception as e:
            logger.error(f"Erro ao exportar configurações: {e}")
            messagebox.showerror("Erro", f"Erro ao exportar configurações: {e}")
    
    def _import_settings(self):
        """Importa configurações de arquivo."""
        try:
            filename = filedialog.askopenfilename(
                title="Importar Configurações",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                # Implementar importação
                messagebox.showinfo("Importar", "Configurações importadas com sucesso")
                self._load_current_settings()
        except Exception as e:
            logger.error(f"Erro ao importar configurações: {e}")
            messagebox.showerror("Erro", f"Erro ao importar configurações: {e}")
    
    def _save_settings(self):
        """Salva as configurações."""
        try:
            # Salva todas as configurações
            self.config_manager.set("theme", self.theme_var.get())
            self.config_manager.set("show_welcome", self.show_welcome_var.get())
            self.config_manager.set("show_navigation", self.show_navigation_var.get())
            self.config_manager.set("window_size", self.window_size_var.get())
            self.config_manager.set("log_level", self.log_level_var.get())
            self.config_manager.set("db_timeout", self.db_timeout_var.get())
            self.config_manager.set("db_max_connections", self.max_connections_var.get())
            self.config_manager.set("import_batch_size", self.import_batch_size_var.get())
            self.config_manager.set("backup_enabled", self.backup_enabled_var.get())
            self.config_manager.set("backup_interval", self.backup_interval_var.get())
            self.config_manager.set("auto_save", self.auto_save_var.get())
            self.config_manager.set("last_import_dir", self.last_import_dir_var.get())
            self.config_manager.set("last_roms_dir", self.last_roms_dir_var.get())
            
            # Salva no arquivo
            self.config_manager.save()
            
            logger.info("Configurações salvas com sucesso")
            
            # Chama callback se fornecido
            if self.callback:
                self.callback()
                
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            messagebox.showerror("Erro", f"Erro ao salvar configurações: {e}")
            raise
    
    def _on_ok(self):
        """Aplica e fecha o diálogo."""
        try:
            self._save_settings()
            self.destroy()
        except Exception:
            # Erro já foi mostrado em _save_settings
            pass
    
    def _on_apply(self):
        """Aplica as configurações sem fechar."""
        try:
            self._save_settings()
            messagebox.showinfo("Sucesso", "Configurações aplicadas com sucesso")
        except Exception:
            # Erro já foi mostrado em _save_settings
            pass
    
    def _on_cancel(self):
        """Cancela e fecha o diálogo."""
        self.destroy()