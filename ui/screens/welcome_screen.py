#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Tela de Boas-vindas
Tela inicial para novos usuários com opções para iniciar o uso do aplicativo
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog
import logging
from typing import Callable, Dict

# Logger
logger = logging.getLogger(__name__)

class WelcomeScreen(tk.Toplevel):
    """
    Tela de boas-vindas do MegaEmu DataBase ROMs.
    
    Exibe opções iniciais para o usuário, como criar ou abrir um banco de dados.
    """
    
    def __init__(self, parent, config_manager, theme="light", callbacks: Dict[str, Callable] = None):
        """
        Inicializa a tela de boas-vindas.
        
        Args:
            parent: Widget pai (janela principal)
            config_manager: Gerenciador de configurações
            theme: Tema a ser aplicado (light/dark)
            callbacks: Dicionário de funções de callback para ações
        """
        super().__init__(parent)
        
        self.parent = parent
        self.config_manager = config_manager
        self.theme = theme
        self.callbacks = callbacks or {}
        # Dicionário para armazenar caminhos completos dos bancos de dados recentes
        self.recent_db_paths = {}
        
        # Configuração da janela
        self.title("Bem-vindo ao MegaEmu DataBase ROMs")
        self.geometry("800x600")
        self.minsize(700, 500)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Centraliza a janela
        self.center_window()
        
        # Configura a interface
        self._setup_ui()
        
        logger.info("Tela de boas-vindas inicializada")
    
    def center_window(self):
        """Centraliza a janela na tela."""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        width = 800
        height = 600
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def _setup_ui(self):
        """Configura a interface da tela de boas-vindas."""
        # Frame principal
        self.main_frame = ttk.Frame(self, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_frame = ttk.Frame(self.main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        logo_label = ttk.Label(title_frame, text="🎮", font=("Segoe UI", 48))
        logo_label.pack(pady=(0, 10))
        
        title_label = ttk.Label(
            title_frame, 
            text="MegaEmu DataBase ROMs",
            font=("Segoe UI", 24, "bold")
        )
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(
            title_frame,
            text="Gerenciador completo para coleções de ROMs",
            font=("Segoe UI", 12)
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Container para o conteúdo principal (2 colunas)
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        
        # Coluna Esquerda - Bancos de Dados
        db_frame = ttk.LabelFrame(content_frame, text="Banco de Dados", padding=15)
        db_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        
        # Botões de banco de dados
        ttk.Button(
            db_frame,
            text="Criar Novo Banco de Dados",
            command=self._create_database,
            style="AccentButton.TButton"
        ).pack(fill=tk.X, pady=5)
        
        ttk.Button(
            db_frame,
            text="Abrir Banco de Dados Existente",
            command=self._open_database
        ).pack(fill=tk.X, pady=5)
        
        # Frame para bancos recentes
        recent_frame = ttk.LabelFrame(db_frame, text="Bancos Recentes", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # Lista de bancos recentes
        self.recent_list = tk.Listbox(
            recent_frame,
            selectmode=tk.SINGLE,
            height=6
        )
        self.recent_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        recent_scroll = ttk.Scrollbar(recent_frame, command=self.recent_list.yview)
        recent_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.recent_list.config(yscrollcommand=recent_scroll.set)
        
        # Vincular evento de duplo clique
        self.recent_list.bind("<Double-1>", self._open_selected_database)
        
        # Preenche a lista de bancos recentes
        self._populate_recent_databases()
        
        # Coluna Direita - Utilitários
        tools_frame = ttk.LabelFrame(content_frame, text="Utilitários", padding=15)
        tools_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=10)
        
        # Botões de utilitários
        ttk.Button(
            tools_frame,
            text="Importar Arquivo DAT/XML",
            command=self._import_dat_file
        ).pack(fill=tk.X, pady=5)
        
        ttk.Button(
            tools_frame,
            text="Importar Arquivo INI",
            command=self._import_ini_file
        ).pack(fill=tk.X, pady=5)
        
        ttk.Button(
            tools_frame,
            text="Verificar ROMs",
            command=self._verify_roms
        ).pack(fill=tk.X, pady=5)
        
        ttk.Button(
            tools_frame,
            text="Explorar Diretório",
            command=self._explore_directory
        ).pack(fill=tk.X, pady=5)
        
        # Dicas e informações
        tips_frame = ttk.LabelFrame(tools_frame, text="Dicas", padding=10)
        tips_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        tips_text = (
            "• Comece criando um novo banco de dados ou abra um existente\n"
            "• Importe arquivos DAT/XML para adicionar informações de ROMs\n"
            "• Use a verificação de ROMs para validar sua coleção\n"
            "• Os bancos recentes permitem acesso rápido aos seus dados\n"
            "• Configure o tema claro/escuro no menu Visualização"
        )
        
        ttk.Label(
            tips_frame,
            text=tips_text,
            justify=tk.LEFT,
            wraplength=300
        ).pack(fill=tk.BOTH, expand=True)
        
        # Botão para não mostrar esta tela novamente
        show_frame = ttk.Frame(self.main_frame)
        show_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.show_on_startup_var = tk.BooleanVar(value=self.config_manager.get("show_welcome", True))
        
        ttk.Checkbutton(
            show_frame,
            text="Mostrar esta tela ao iniciar",
            variable=self.show_on_startup_var,
            command=self._toggle_show_on_startup
        ).pack(side=tk.LEFT)
        
        # Botões de ação
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(
            buttons_frame,
            text="Fechar",
            command=self.on_close
        ).pack(side=tk.RIGHT)
    
    def _toggle_show_on_startup(self):
        """Atualiza a configuração para mostrar/ocultar a tela de boas-vindas na inicialização."""
        show_value = self.show_on_startup_var.get()
        self.config_manager.set("show_welcome", show_value)
        logger.info(f"Configuração 'show_welcome' atualizada para: {show_value}")
    
    def _populate_recent_databases(self):
        """Preenche a lista de bancos de dados recentes."""
        # Limpa a lista
        self.recent_list.delete(0, tk.END)
        self.recent_db_paths.clear()
        
        # Obtém a lista de bancos recentes
        recent_dbs = self.config_manager.get("recent_databases", [])
        
        if not recent_dbs:
            self.recent_list.insert(tk.END, "Nenhum banco recente")
            self.recent_list.config(state=tk.DISABLED)
            return
        
        # Adiciona os bancos recentes à lista
        for i, db_path in enumerate(recent_dbs):
            # Exibe apenas o nome do arquivo, não o caminho completo
            display_name = os.path.basename(db_path)
            self.recent_list.insert(tk.END, display_name)
            # Armazena o caminho completo no dicionário
            self.recent_db_paths[i] = db_path
    
    def _create_database(self):
        """Cria um novo banco de dados."""
        if "create_database" in self.callbacks:
            self.callbacks["create_database"]()
            self.on_close()
    
    def _open_database(self):
        """Abre um banco de dados existente."""
        if "open_database" in self.callbacks:
            self.callbacks["open_database"]()
            self.on_close()
    
    def _open_selected_database(self, event=None):
        """Abre o banco de dados selecionado na lista de recentes."""
        selection = self.recent_list.curselection()
        if not selection:
            return
        
        # Obtém o índice selecionado
        index = selection[0]
        
        # Verifica se há caminho armazenado para este índice
        if index not in self.recent_db_paths:
            return
        
        # Obtém o caminho completo
        db_path = self.recent_db_paths[index]
        
        # Chama o callback com o caminho
        if "open_database_file" in self.callbacks:
            self.callbacks["open_database_file"](db_path)
            self.on_close()
    
    def _import_dat_file(self):
        """Importa um arquivo DAT/XML."""
        if "import_dat" in self.callbacks:
            self.callbacks["import_dat"]()
            self.on_close()
    
    def _import_ini_file(self):
        """Importa um arquivo INI."""
        if "import_ini" in self.callbacks:
            self.callbacks["import_ini"]()
            self.on_close()
    
    def _verify_roms(self):
        """Verifica ROMs."""
        if "verify_roms" in self.callbacks:
            self.callbacks["verify_roms"]()
            self.on_close()
    
    def _explore_directory(self):
        """Explora um diretório de ROMs."""
        if "explore_directory" in self.callbacks:
            self.callbacks["explore_directory"]()
            self.on_close()
    
    def on_close(self):
        """Fecha a tela de boas-vindas."""
        logger.info("Tela de boas-vindas fechada")
        self.grab_release()
        self.destroy() 