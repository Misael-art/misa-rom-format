#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Janela Principal
Interface gráfica principal do aplicativo
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
import threading
from datetime import datetime
from threading import Thread

from ..config.app_config import AppConfig
from ..db.database_manager import DatabaseManager
from ..db.db_locks import db_write_lock
from ..services.import_service import ImportService
from ..services.verification_service import VerificationService
from .dialogs import ProgressDialog
from .theme_manager import ThemeManager
from ..utils.compression import compress_rom, compress_hybrid, decompress_hybrid, get_compression_ratio
from ..config.constants import COMPRESSION_LEVEL_LZ4
import hashlib

logger = logging.getLogger(__name__)

class MainWindow(tk.Tk):
    """Janela principal do aplicativo."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        app_config: AppConfig,
        theme_manager: ThemeManager
    ):
        """
        Inicializa a janela principal.
        
        Args:
            db_manager: Gerenciador do banco de dados
            app_config: Configurações do aplicativo
            theme_manager: Gerenciador de temas
        """
        super().__init__()
        
        # Salva referências
        self.db_manager = db_manager
        self.app_config = app_config
        self.theme_manager = theme_manager
        
        # Cria serviços
        self.import_service = ImportService(db_manager)
        self.verify_service = VerificationService(db_manager)
        
        # Configura janela
        self.title("MegaEmu DataBase ROMs")
        self.geometry("800x600")
        self.minsize(800, 600)
        
        # Cria widgets
        self._create_widgets()
        
        # Configura eventos
        self.bind("<Configure>", self.on_resize)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        
        # Atualiza interface
        self.update_db_status()
    
    def _create_widgets(self):
        """Cria os widgets da interface."""
        try:
            # Frame principal
            self.main_frame = ttk.Frame(self)
            self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Frame superior
            self.top_frame = ttk.Frame(self.main_frame)
            self.top_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Botões
            self.open_button = ttk.Button(
                self.top_frame,
                text="Abrir Banco",
                command=self._open_database
            )
            self.open_button.pack(side=tk.LEFT)
            
            self.close_button = ttk.Button(
                self.top_frame,
                text="Fechar Banco",
                command=self.close_database
            )
            self.close_button.pack(side=tk.LEFT, padx=5)
            
            self.import_button = ttk.Button(
                self.top_frame,
                text="Importar DAT",
                command=self._import_dat
            )
            self.import_button.pack(side=tk.LEFT)
            
            self.verify_button = ttk.Button(
                self.top_frame,
                text="Verificar ROMs",
                command=self.verify_roms
            )
            self.verify_button.pack(side=tk.LEFT, padx=5)
            
            # Frame central
            self.center_frame = ttk.Frame(self.main_frame)
            self.center_frame.pack(fill=tk.BOTH, expand=True)
            
            # Lista de tabelas
            self.tables_frame = ttk.Frame(self.center_frame)
            self.tables_frame.pack(side=tk.LEFT, fill=tk.Y)
            
            self.tables_label = ttk.Label(
                self.tables_frame,
                text="Tabelas"
            )
            self.tables_label.pack()
            
            self.tables_list = tk.Listbox(
                self.tables_frame,
                width=20,
                selectmode=tk.SINGLE
            )
            self.tables_list.pack(fill=tk.Y, expand=True)
            self.tables_list.bind("<<ListboxSelect>>", self.on_table_selected)
            
            # Dados da tabela
            self.data_frame = ttk.Frame(self.center_frame)
            self.data_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
            
            self.data_label = ttk.Label(
                self.data_frame,
                text="Dados"
            )
            self.data_label.pack()
            
            # Treeview
            self.tree = ttk.Treeview(
                self.data_frame,
                selectmode="browse",
                show="headings"
            )
            self.tree.pack(fill=tk.BOTH, expand=True)
            
            # Scrollbars
            self.vsb = ttk.Scrollbar(
                self.data_frame,
                orient="vertical",
                command=self.tree.yview
            )
            self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.hsb = ttk.Scrollbar(
                self.data_frame,
                orient="horizontal",
                command=self.tree.xview
            )
            self.hsb.pack(side=tk.BOTTOM, fill=tk.X)
            
            self.tree.configure(
                yscrollcommand=self.vsb.set,
                xscrollcommand=self.hsb.set
            )
            
            # Status
            self.status_frame = ttk.Frame(self.main_frame)
            self.status_frame.pack(fill=tk.X, pady=(10, 0))
            
            self.status_label = ttk.Label(
                self.status_frame,
                text="Banco: Nenhum"
            )
            self.status_label.pack(side=tk.LEFT)
            
        except Exception as e:
            logging.error(f"Erro ao criar widgets: {str(e)}", exc_info=True)
            raise
    
    def _apply_theme(self):
        """Aplica o tema atual."""
        try:
            # Obtém tema atual
            theme = self.app_config.get("theme", "light")
            
            # Obtém cores do tema
            colors = self.app_config.get_theme_colors(theme)
            
            # Aplica cores
            self.configure(bg=colors["background"])
            
            # Configura estilos
            style = ttk.Style()
            style.configure(".", background=colors["background"])
            style.configure("TLabel", background=colors["background"], foreground=colors["foreground"])
            style.configure("TButton", background=colors["button"], foreground=colors["foreground"])
            style.configure("TEntry", fieldbackground=colors["background"], foreground=colors["foreground"])
            style.configure("TFrame", background=colors["background"])
            
            # Atualiza widgets
            for widget in self.winfo_children():
                if isinstance(widget, (ttk.Frame, ttk.Label)):
                    widget.configure(style="TFrame" if isinstance(widget, ttk.Frame) else "TLabel")
            
            logging.info(f"Tema aplicado: {theme}")
            
        except Exception as e:
            logging.error(f"Erro ao aplicar tema: {str(e)}", exc_info=True)
    
    def load_last_database(self):
        """Carrega último banco de dados usado."""
        last_db = self.app_config.get("last_db_path")
        if last_db and os.path.exists(last_db):
            self._open_database(last_db)
    
    def update_tables_list(self):
        """Atualiza lista de tabelas."""
        try:
            # Limpa lista
            self.tables_list.delete(0, tk.END)
            
            # Verifica conexão
            if not self.db_manager.is_connected:
                return
                
            # Lista tabelas
            tables = self.db_manager.get_tables()
            for table in tables:
                self.tables_list.insert(tk.END, table)
                
        except Exception as e:
            logging.error(f"Erro ao atualizar tabelas: {str(e)}", exc_info=True)
            
    def update_recent_menu(self):
        """Atualiza menu de bancos recentes."""
        self.recent_menu.delete(0, tk.END)
        
        recent = self.app_config.get("recent_databases", [])
        if recent:
            for db_path in recent:
                if os.path.exists(db_path):
                    self.recent_menu.add_command(
                        label=os.path.basename(db_path),
                        command=lambda p=db_path: self._open_database(p)
                    )
            
            self.recent_menu.add_separator()
            self.recent_menu.add_command(
                label="Limpar lista",
                command=self.clear_recent
            )
        else:
            self.recent_menu.add_command(
                label="(Nenhum banco recente)",
                state="disabled"
            )
    
    def set_status(self, message: str):
        """Define mensagem na barra de status."""
        self.status_label.config(text=message)
    
    def update_db_status(self):
        """Atualiza status do banco."""
        try:
            if self.db_manager.is_connected:
                self.status_label["text"] = f"Banco: {self.db_manager.current_db}"
            else:
                self.status_label["text"] = "Banco: Nenhum"
                
        except Exception as e:
            logging.error(f"Erro ao atualizar status: {str(e)}", exc_info=True)
    
    def _quit(self):
        """Fecha o aplicativo."""
        try:
            # Fecha banco
            if self.db_manager.is_connected:
                self.db_manager.close()
                
            # Salva configurações
            self.app_config.save()
            
            # Fecha janela
            self.quit()
            
        except Exception as e:
            logging.error(f"Erro ao fechar aplicativo: {str(e)}", exc_info=True)
            self.quit()
    
    def on_resize(self, event):
        """Manipula redimensionamento da janela."""
        if event.widget == self:
            self.app_config.set(
                "window_size",
                f"{event.width}x{event.height}"
            )
    
    def on_table_selected(self, event):
        """Manipula seleção de tabela."""
        if not self.tables_list.curselection():
            return
        
        selection = self.tables_list.get(self.tables_list.curselection())
        table_name = selection.split(" (")[0]
        
        self.show_table_data(table_name)
    
    def show_table_data(self, table_name: str):
        """Exibe dados de uma tabela."""
        if not self.db_manager.is_connected:
            return
        
        # Limpa treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Obtém colunas
        columns = self.db_manager.get_table_info(table_name)
        if not columns:
            return
        
        # Configura colunas
        self.tree["columns"] = [col[1] for col in columns]
        self.tree["show"] = "headings"
        
        for col in columns:
            self.tree.heading(col[1], text=col[1])
            self.tree.column(col[1], width=100)
        
        # Obtém dados
        query = f"SELECT * FROM {table_name} LIMIT 1000"
        rows = self.db_manager.execute_query(query)
        
        # Insere dados
        for row in rows:
            values = [str(val) if val is not None else "" for val in row]
            self.tree.insert("", tk.END, values=values)
        
        # Atualiza status
        total = self.db_manager.get_row_count(table_name)
        self.set_status(f"Tabela {table_name}: {total} registros")
    
    def refresh_data(self):
        """Atualiza dados da tabela atual."""
        if not self.tables_list.curselection():
            return
        
        selection = self.tables_list.get(self.tables_list.curselection())
        table_name = selection.split(" (")[0]
        
        self.show_table_data(table_name)
    
    def _new_database(self):
        """Cria novo banco de dados."""
        file_path = filedialog.asksaveasfilename(
            title="Criar Banco de Dados",
            defaultextension=".db",
            filetypes=[("Banco SQLite", "*.db")]
        )
        
        if not file_path:
            return
        
        if self.db_manager.create_new_database(file_path, self.app_config.get_app_info()):
            self._open_database(file_path)
            self.set_status("Banco de dados criado com sucesso")
        else:
            messagebox.showerror(
                "Erro",
                "Não foi possível criar o banco de dados"
            )
    
    def _open_database(self, db_path: str = None):
        """
        Abre um banco de dados.
        
        Args:
            db_path: Caminho do banco ou None para escolher
        """
        try:
            # Solicita arquivo se não informado
            if not db_path:
                db_path = filedialog.askopenfilename(
                    title="Abrir banco de dados",
                    filetypes=[("SQLite", "*.db"), ("Todos", "*.*")]
                )
                
            if not db_path:
                return
                
            # Conecta ao banco
            if not self.db_manager.connect(db_path):
                messagebox.showerror(
                    "Erro",
                    "Erro ao abrir banco de dados"
                )
                return
                
            # Adiciona aos recentes
            self.app_config.add_recent_database(db_path)
            
            # Atualiza interface
            self.update_tables_list()
            self.update_recent_menu()
            self.update_db_status()
            
        except Exception as e:
            logging.error(f"Erro ao abrir banco: {str(e)}", exc_info=True)
            messagebox.showerror(
                "Erro",
                f"Erro ao abrir banco: {str(e)}"
            )
    
    def close_database(self):
        """Fecha o banco atual."""
        try:
            if self.db_manager.is_connected:
                self.db_manager.close()
                self.update_tables_list()
                self.update_db_status()
                
        except Exception as e:
            logging.error(f"Erro ao fechar banco: {str(e)}", exc_info=True)
    
    def clear_recent(self):
        """Limpa lista de bancos recentes."""
        self.app_config.clear_recent_databases()
        self.update_recent_menu()
    
    def _import_dat(self):
        """Importa arquivo DAT."""
        try:
            # Seleciona arquivo
            file_path = filedialog.askopenfilename(
                title="Selecionar arquivo DAT",
                filetypes=[("DAT files", "*.dat"), ("XML files", "*.xml"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
                
            # Cria diálogo de progresso
            progress = ProgressDialog(
                self,
                "Importando arquivo DAT",
                "Processando jogos..."
            )
            
            def update_progress(value: float):
                progress.update_progress(value)
                
            # Importa em thread
            def import_thread():
                try:
                    success = self.import_service.import_dat_file(
                        file_path,
                        progress_callback=update_progress
                    )
                    
                    if success:
                        self.after(0, lambda: messagebox.showinfo(
                            "Sucesso",
                            "Arquivo DAT importado com sucesso!"
                        ))
                    else:
                        self.after(0, lambda: messagebox.showerror(
                            "Erro",
                            "Erro ao importar arquivo DAT.\nVerifique o log para mais detalhes."
                        ))
                        
                except Exception as e:
                    logging.error(f"Erro na thread de importação: {str(e)}", exc_info=True)
                    self.after(0, lambda: messagebox.showerror(
                        "Erro",
                        "Erro ao importar arquivo DAT.\nVerifique o log para mais detalhes."
                    ))
                finally:
                    progress.cancel()
                    self.update_tables_list()
                    
            # Inicia thread
            thread = Thread(target=import_thread)
            thread.start()
            
        except Exception as e:
            logging.error(f"Erro ao importar DAT: {str(e)}", exc_info=True)
            messagebox.showerror(
                "Erro",
                "Erro ao importar arquivo DAT.\nVerifique o log para mais detalhes."
            )
    
    def batch_import(self):
        """Importa arquivos em lote."""
        if not self.db_manager.is_connected:
            messagebox.showwarning(
                "Aviso",
                "Nenhum banco de dados aberto"
            )
            return
        
        directory = filedialog.askdirectory(
            title="Selecionar Diretório"
        )
        
        if not directory:
            return
        
        progress = ProgressDialog(
            self,
            "Importação em Lote",
            "Preparando importação...",
            self.app_config.get("theme", "light")
        )
        
        def import_task():
            success, stats = self.import_service.import_directory(
                directory,
                True,
                progress.update_progress
            )
            
            if success:
                progress.complete(
                    f"Importação concluída:\n"
                    f"- {stats['imported']} ROMs importadas\n"
                    f"- {stats['skipped']} ROMs ignoradas\n"
                    f"- {stats['errors']} erros"
                )
                self.update_tables_list()
                self.refresh_data()
            else:
                progress.complete("Erro durante importação")
        
        import threading
        thread = threading.Thread(target=import_task)
        thread.daemon = True
        thread.start()
    
    def verify_roms(self):
        """Verifica ROMs."""
        try:
            # Seleciona diretório
            dir_path = filedialog.askdirectory(
                title="Selecionar diretório de ROMs"
            )
            
            if not dir_path:
                return
                
            # Cria diálogo de progresso
            progress = ProgressDialog(
                self,
                "Verificando ROMs",
                "Processando arquivos..."
            )
            
            def update_progress(value: float):
                progress.update_progress(value)
                
            # Verifica em thread
            def verify_thread():
                try:
                    success = self.verify_service.verify_roms(
                        dir_path,
                        progress_callback=update_progress
                    )
                    
                    if success:
                        self.after(0, lambda: messagebox.showinfo(
                            "Sucesso",
                            "Verificação concluída com sucesso!"
                        ))
                    else:
                        self.after(0, lambda: messagebox.showerror(
                            "Erro",
                            "Erro ao verificar ROMs.\nVerifique o log para mais detalhes."
                        ))
                        
                except Exception as e:
                    logging.error(f"Erro na thread de verificação: {str(e)}", exc_info=True)
                    self.after(0, lambda: messagebox.showerror(
                        "Erro",
                        "Erro ao verificar ROMs.\nVerifique o log para mais detalhes."
                    ))
                finally:
                    progress.cancel()
                    
            # Inicia thread
            thread = Thread(target=verify_thread)
            thread.start()
            
        except Exception as e:
            logging.error(f"Erro ao verificar ROMs: {str(e)}", exc_info=True)
            messagebox.showerror(
                "Erro",
                "Erro ao verificar ROMs.\nVerifique o log para mais detalhes."
            )
    
    def show_verification_results(self, results: List[Dict]):
        """Exibe resultados da verificação."""
        try:
            # Cria janela de resultados
            results_window = tk.Toplevel(self)
            results_window.title("Resultados da Verificação")
            results_window.geometry("800x600")

            # Frame principal
            main_frame = ttk.Frame(results_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Treeview para resultados
            tree = ttk.Treeview(main_frame, show="headings")
            tree.pack(fill=tk.BOTH, expand=True)

            # Scrollbars
            vsb = ttk.Scrollbar(main_frame, orient="vertical", command=tree.yview)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=tree.xview)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

            tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            # Configura colunas
            columns = ["Arquivo", "Status", "Hash Calculado", "Hash Esperado", "Tamanho"]
            tree["columns"] = columns

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            # Insere resultados
            for result in results:
                values = [
                    result.get("filename", ""),
                    result.get("status", ""),
                    result.get("calculated_hash", ""),
                    result.get("expected_hash", ""),
                    str(result.get("size", ""))
                ]
                tree.insert("", tk.END, values=values)

            # Botão fechar
            close_button = ttk.Button(
                results_window,
                text="Fechar",
                command=results_window.destroy
            )
            close_button.pack(pady=10)

        except Exception as e:
            logging.error(f"Erro ao exibir resultados: {str(e)}", exc_info=True)
            messagebox.showerror(
                "Erro",
                f"Erro ao exibir resultados: {str(e)}"
            )
    
    def show_statistics(self):
        """Exibe estatísticas do banco de dados."""
        if not self.db_manager.is_connected:
            messagebox.showwarning(
                "Aviso",
                "Nenhum banco de dados aberto"
            )
            return
        
        stats = self.verify_service.get_verification_summary()
        
        messagebox.showinfo(
            "Estatísticas",
            f"Total de ROMs: {stats['total']}\n"
            f"ROMs verificadas: {stats['verified']}\n"
            f"Matches exatos: {stats['matched']}\n"
            f"Matches parciais: {stats['partial']}\n"
            f"ROMs faltantes: {stats['missing']}"
        )
    
    def show_documentation(self):
        """Exibe documentação do aplicativo."""
        messagebox.showinfo(
            "Documentação",
            "A documentação completa está disponível em:\n"
            "https://github.com/seu-usuario/megaemu-database"
        )
    
    def _show_about(self):
        """Exibe informações sobre o aplicativo."""
        messagebox.showinfo(
            "Sobre",
            f"{self.app_config.APP_NAME} v{self.app_config.APP_VERSION}\n\n"
            f"{self.app_config.APP_DESCRIPTION}\n\n"
            f"Autor: {self.app_config.APP_AUTHOR}\n"
            f"Licença: {self.app_config.APP_LICENSE}"
        )
    
    def _change_theme(self, theme_name: str):
        """
        Altera o tema da interface.
        
        Args:
            theme_name: Nome do tema ('light' ou 'dark')
        """
        # Aplica novo tema
        self.theme_manager.apply_theme(theme_name)
        self._apply_theme()
        
        # Salva preferência
        self.app_config.set("theme", theme_name)
        self.app_config.save()
        
        logging.info(f"Tema alterado para: {theme_name}")
    
    def toggle_navigation(self):
        """Mostra/oculta painel de navegação."""
        show = self.show_nav_var.get()
        self.app_config.set("show_navigation", show)
        
        if show:
            self.nav_frame.pack(
                side="left",
                fill="y",
                padx=(0, 5)
            )
        else:
            self.nav_frame.pack_forget()
    
    def add_item(self):
        """Adiciona novo item."""
        # TODO: Implementar adição de item
        pass
    
    def edit_item(self):
        """Edita item selecionado."""
        # TODO: Implementar edição de item
        pass
    
    def delete_item(self):
        """Exclui item selecionado."""
        # TODO: Implementar exclusão de item
        pass
    
    def execute_query(self):
        """Executa consulta SQL."""
        if not self.db_manager.is_connected:
            messagebox.showwarning(
                "Aviso",
                "Nenhum banco de dados aberto"
            )
            return
        
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            return
        
        try:
            results = self.db_manager.execute_query(query)
            
            # Limpa resultados anteriores
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            if not results:
                self.set_status("Consulta executada com sucesso")
                return
            
            # Configura colunas
            columns = [desc[0] for desc in self.db_manager.cursor.description]
            self.results_tree["columns"] = columns
            self.results_tree["show"] = "headings"
            
            for col in columns:
                self.results_tree.heading(col, text=col)
                self.results_tree.column(col, width=100)
            
            # Insere resultados
            for row in results:
                values = [str(val) if val is not None else "" for val in row]
                self.results_tree.insert("", tk.END, values=values)
            
            self.set_status(f"Consulta executada: {len(results)} resultados")
            
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Erro ao executar consulta:\n{str(e)}"
            )