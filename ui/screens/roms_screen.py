# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Tela de ROMs
Tela para visualizar e gerenciar ROMs/jogos
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional, Callable, List
import os
import queue as q
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class ROMsScreen(tk.Frame):
    """Tela para visualizar e gerenciar ROMs/jogos."""

    def __init__(self, parent: tk.Widget, config_manager=None, theme_manager=None, **kwargs):
        """
        Inicializa a tela de ROMs.

        Args:
            parent: Widget pai
            config_manager: Gerenciador de configuração
            theme_manager: Gerenciador de tema
        """
        super().__init__(parent, **kwargs)

        self.config_manager = config_manager
        self.theme_manager = theme_manager

        # Estado da tela
        self.roms_data: List[Dict[str, Any]] = []
        self.filtered_data: List[Dict[str, Any]] = []
        self.current_filter = ""
        self.sort_column = "filename"
        self.sort_reverse = False

        # Callbacks
        self._callbacks: Dict[str, Callable] = {}

        # Thread safety
        self.ui_queue = q.Queue()

        self._create_ui()
        self._setup_bindings()
        self._process_ui_queue()

    def _create_ui(self):
        """Cria a interface da tela."""
        # Frame principal
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Barra de ferramentas da tela
        self._create_toolbar(main_frame)

        # Área de conteúdo
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Painel esquerdo - filtros
        self._create_filters_panel(content_frame)

        # Painel direito - lista de ROMs
        self._create_roms_panel(content_frame)

        # Barra de progresso (inicialmente oculta)
        self._create_progress_bar(main_frame)

    def _create_toolbar(self, parent):
        """Cria a barra de ferramentas da tela."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X)

        # Botão scan ROMs
        self.scan_button = ttk.Button(
            toolbar,
            text="🔍 Scan ROMs",
            command=self._on_scan_clicked
        )
        self.scan_button.pack(side=tk.LEFT, padx=(0, 5))

        # Botão atualizar
        self.refresh_button = ttk.Button(
            toolbar,
            text="🔄 Atualizar",
            command=self._on_refresh_clicked
        )
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 10))

        # Campo de busca
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(search_frame, text="Buscar:").pack(side=tk.LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=30
        )
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind('<KeyRelease>', self._on_search_changed)

        # Botão limpar busca
        self.clear_search_button = ttk.Button(
            search_frame,
            text="✕",
            width=3,
            command=self._clear_search
        )
        self.clear_search_button.pack(side=tk.LEFT, padx=(2, 0))

        # Label de status à direita
        self.status_label = ttk.Label(
            toolbar,
            text="Pronto",
            foreground="blue"
        )
        self.status_label.pack(side=tk.RIGHT)

    def _create_filters_panel(self, parent):
        """Cria o painel de filtros."""
        # Frame do painel esquerdo
        left_frame = ttk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Filtros
        filters_labelframe = ttk.LabelFrame(left_frame, text="Filtros", padding=10)
        filters_labelframe.pack(fill=tk.Y, expand=True)

        # Filtro por plataforma
        ttk.Label(filters_labelframe, text="Plataforma:").pack(anchor=tk.W, pady=(0, 5))

        self.platform_var = tk.StringVar(value="Todas")
        self.platform_combo = ttk.Combobox(
            filters_labelframe,
            textvariable=self.platform_var,
            state="readonly",
            width=15
        )
        self.platform_combo['values'] = ["Todas", "NES", "SNES", "Genesis", "PS1", "PS2", "Arcade"]
        self.platform_combo.pack(fill=tk.X, pady=(0, 10))
        self.platform_combo.bind('<<ComboboxSelected>>', self._on_filter_changed)

        # Filtro por status
        ttk.Label(filters_labelframe, text="Status:").pack(anchor=tk.W, pady=(0, 5))

        self.status_filter_var = tk.StringVar(value="Todos")
        self.status_combo = ttk.Combobox(
            filters_labelframe,
            textvariable=self.status_filter_var,
            state="readonly",
            width=15
        )
        self.status_combo['values'] = ["Todos", "Presente", "Ausente", "Corrompido"]
        self.status_combo.pack(fill=tk.X, pady=(0, 10))
        self.status_combo.bind('<<ComboboxSelected>>', self._on_filter_changed)

        # Estatísticas
        stats_labelframe = ttk.LabelFrame(left_frame, text="Estatísticas", padding=10)
        stats_labelframe.pack(fill=tk.X, pady=(10, 0))

        self.stats_labels = {}
        stats = ["Total", "Presentes", "Ausentes", "Corrompidos"]
        for stat in stats:
            self.stats_labels[stat] = ttk.Label(stats_labelframe, text=f"{stat}: 0")
            self.stats_labels[stat].pack(anchor=tk.W, pady=2)

    def _create_roms_panel(self, parent):
        """Cria o painel da lista de ROMs."""
        # Frame do painel direito
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Treeview para ROMs
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Configurar colunas
        columns = ("filename", "platform", "status", "size", "modified")
        headings = {
            "filename": "Arquivo",
            "platform": "Plataforma",
            "status": "Status",
            "size": "Tamanho",
            "modified": "Modificado"
        }

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )

        # Configurar headings
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self._sort_by_column(c))
            if col == "filename":
                self.tree.column(col, width=300, minwidth=200)
            elif col == "platform":
                self.tree.column(col, width=100, minwidth=80)
            elif col == "status":
                self.tree.column(col, width=100, minwidth=80)
            elif col == "size":
                self.tree.column(col, width=100, minwidth=80)
            elif col == "modified":
                self.tree.column(col, width=150, minwidth=120)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Layout
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Menu de contexto
        self._create_context_menu()

    def _create_progress_bar(self, parent):
        """Cria a barra de progresso."""
        self.progress_frame = ttk.Frame(parent)
        # Inicialmente oculto
        # self.progress_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(self.progress_frame, text="Progresso:").pack(side=tk.LEFT, padx=(0, 5))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100.0,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.progress_label = ttk.Label(self.progress_frame, text="0/0")
        self.progress_label.pack(side=tk.RIGHT)

    def _create_context_menu(self):
        """Cria o menu de contexto para o Treeview."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Ver detalhes", command=self._show_rom_details)
        self.context_menu.add_command(label="Localizar arquivo", command=self._locate_file)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Verificar integridade", command=self._verify_integrity)

        self.tree.bind("<Button-3>", self._show_context_menu)

    def _setup_bindings(self):
        """Configura bindings de eventos."""
        # Double-click no treeview
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _process_ui_queue(self):
        """Processa mensagens da fila da UI."""
        try:
            while True:
                message = self.ui_queue.get_nowait()
                self._handle_ui_message(message)
        except q.Empty:
            pass

        # Agenda próxima verificação
        self.after(100, self._process_ui_queue)

    def _handle_ui_message(self, message):
        """Manipula mensagens da fila da UI."""
        msg_type = message.get('type', '')
        data = message.get('data', {})

        if msg_type == 'scan_progress':
            self._update_scan_progress(data)
        elif msg_type == 'scan_complete':
            self._on_scan_complete(data)
        elif msg_type == 'rom_found':
            self._add_rom_to_list(data)

    def _update_scan_progress(self, data):
        """Atualiza progresso do scan."""
        current = data.get('current', 0)
        total = data.get('total', 1)
        filename = data.get('filename', '')

        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))

        progress = (current / total) * 100
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{current}/{total}")
        self.status_label.config(text=f"Scaneando: {os.path.basename(filename)}")

    def _on_scan_complete(self, data):
        """Chamado quando scan é concluído."""
        self.progress_frame.pack_forget()
        self.status_label.config(text="Scan concluído")
        self._update_statistics()
        self._apply_filters()

        # Reabilitar botões
        self.scan_button.config(state=tk.NORMAL)
        self.refresh_button.config(state=tk.NORMAL)

    def _add_rom_to_list(self, rom_data):
        """Adiciona ROM à lista."""
        self.roms_data.append(rom_data)

    def _on_scan_clicked(self):
        """Chamado quando botão scan é clicado."""
        callback = self._callbacks.get('scan_roms')
        if callback:
            callback()
        else:
            self.status_label.config(text="Callback scan_roms não definido")

    def _on_refresh_clicked(self):
        """Chamado quando botão atualizar é clicado."""
        self._clear_tree()
        self._apply_filters()
        self.status_label.config(text="Lista atualizada")

    def _on_search_changed(self, event=None):
        """Chamado quando busca é alterada."""
        self.current_filter = self.search_var.get().lower()
        self._apply_filters()

    def _clear_search(self):
        """Limpa campo de busca."""
        self.search_var.set("")
        self.current_filter = ""
        self._apply_filters()

    def _on_filter_changed(self, event=None):
        """Chamado quando filtros são alterados."""
        self._apply_filters()

    def _apply_filters(self):
        """Aplica filtros à lista de ROMs."""
        filtered = []

        for rom in self.roms_data:
            # Filtro de busca
            if self.current_filter:
                if self.current_filter not in rom.get('filename', '').lower():
                    continue

            # Filtro de plataforma
            platform_filter = self.platform_var.get()
            if platform_filter != "Todas":
                if rom.get('platform', '') != platform_filter:
                    continue

            # Filtro de status
            status_filter = self.status_filter_var.get()
            if status_filter != "Todos":
                if rom.get('status', '') != status_filter:
                    continue

            filtered.append(rom)

        self.filtered_data = filtered
        self._update_treeview()

    def _update_treeview(self):
        """Atualiza o Treeview com dados filtrados."""
        self._clear_tree()

        for rom in self.filtered_data:
            values = (
                rom.get('filename', ''),
                rom.get('platform', ''),
                rom.get('status', ''),
                rom.get('size', ''),
                rom.get('modified', '')
            )
            item = self.tree.insert("", tk.END, values=values)
            # Colorir baseado no status
            if rom.get('status') == 'Ausente':
                self.tree.item(item, tags=('missing',))
            elif rom.get('status') == 'Corrompido':
                self.tree.item(item, tags=('corrupted',))

        # Configurar tags de cor
        self.tree.tag_configure('missing', foreground='red')
        self.tree.tag_configure('corrupted', foreground='orange')

        self._update_statistics()

    def _clear_tree(self):
        """Limpa o Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _sort_by_column(self, col):
        """Ordena por coluna."""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        self.filtered_data.sort(key=lambda x: x.get(col, ''), reverse=self.sort_reverse)
        self._update_treeview()

    def _update_statistics(self):
        """Atualiza estatísticas."""
        total = len(self.filtered_data)
        presentes = sum(1 for rom in self.filtered_data if rom.get('status') == 'Presente')
        ausentes = sum(1 for rom in self.filtered_data if rom.get('status') == 'Ausente')
        corrompidos = sum(1 for rom in self.filtered_data if rom.get('status') == 'Corrompido')

        self.stats_labels["Total"].config(text=f"Total: {total}")
        self.stats_labels["Presentes"].config(text=f"Presentes: {presentes}")
        self.stats_labels["Ausentes"].config(text=f"Ausentes: {ausentes}")
        self.stats_labels["Corrompidos"].config(text=f"Corrompidos: {corrompidos}")

    def _show_context_menu(self, event):
        """Mostra menu de contexto."""
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
                self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Erro ao mostrar menu de contexto: {e}")

    def _on_tree_double_click(self, event):
        """Chamado quando item é double-clicked."""
        item = self.tree.selection()
        if item:
            self._show_rom_details()

    def _show_rom_details(self):
        """Mostra detalhes da ROM selecionada."""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, 'values')

        # Encontrar ROM correspondente
        filename = values[0]
        rom_data = None
        for rom in self.filtered_data:
            if rom.get('filename') == filename:
                rom_data = rom
                break

        if rom_data:
            self._show_details_dialog(rom_data)

    def _show_details_dialog(self, rom_data):
        """Mostra diálogo com detalhes da ROM."""
        dialog = tk.Toplevel(self)
        dialog.title(f"Detalhes - {rom_data.get('filename', '')}")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        # Frame principal
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Informações
        info_frame = ttk.LabelFrame(main_frame, text="Informações", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        fields = [
            ("Arquivo:", rom_data.get('filename', '')),
            ("Plataforma:", rom_data.get('platform', '')),
            ("Status:", rom_data.get('status', '')),
            ("Tamanho:", rom_data.get('size', '')),
            ("Modificado:", rom_data.get('modified', '')),
            ("Caminho:", rom_data.get('path', ''))
        ]

        for label_text, value in fields:
            field_frame = ttk.Frame(info_frame)
            field_frame.pack(fill=tk.X, pady=2)

            ttk.Label(field_frame, text=label_text, width=12, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(field_frame, text=str(value), anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Botões
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="Fechar", command=dialog.destroy).pack(side=tk.RIGHT)

    def _locate_file(self):
        """Localiza arquivo da ROM."""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, 'values')
        filename = values[0]

        # Encontrar ROM correspondente
        for rom in self.filtered_data:
            if rom.get('filename') == filename:
                file_path = rom.get('path', '')
                if file_path and os.path.exists(file_path):
                    os.startfile(os.path.dirname(file_path))
                break

    def _verify_integrity(self):
        """Verifica integridade da ROM."""
        selection = self.tree.selection()
        if not selection:
            return

        # Placeholder - implementar verificação de integridade
        self.status_label.config(text="Verificação de integridade não implementada")

    def register_callback(self, action_id: str, callback: Callable):
        """Registra callback."""
        self._callbacks[action_id] = callback

    def update_roms_data(self, roms_data: List[Dict[str, Any]]):
        """Atualiza dados das ROMs."""
        self.roms_data = roms_data
        self._apply_filters()

    def show_progress(self, show: bool = True):
        """Mostra/oculta barra de progresso."""
        if show and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        elif not show and self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def update_progress(self, current: int, total: int, filename: str = ""):
        """Atualiza progresso."""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            self.progress_label.config(text=f"{current}/{total}")
            if filename:
                self.status_label.config(text=f"Scaneando: {os.path.basename(filename)}")

    def set_status(self, message: str):
        """Define mensagem de status."""
        self.status_label.config(text=message)