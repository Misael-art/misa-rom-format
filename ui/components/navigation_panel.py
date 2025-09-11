# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Navigation Panel
Painel de navegação principal da aplicação
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class NavigationItemType(Enum):
    """Tipos de itens de navegação."""
    CATEGORY = "category"
    ACTION = "action"
    SEPARATOR = "separator"
    SUBMENU = "submenu"

@dataclass
class NavigationItem:
    """Item de navegação."""
    id: str
    title: str
    item_type: NavigationItemType
    icon: Optional[str] = None
    callback: Optional[Callable] = None
    tooltip: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    children: Optional[List['NavigationItem']] = None
    parent_id: Optional[str] = None
    order: int = 0
    badge_text: Optional[str] = None
    badge_color: str = "red"

class NavigationPanel(ttk.Frame):
    """Painel de navegação principal."""
    
    def __init__(self, parent, config_manager=None, theme_manager=None, **kwargs):
        """
        Inicializa o painel de navegação.
        
        Args:
            parent: Widget pai
            config_manager: Gerenciador de configurações
            theme_manager: Gerenciador de temas
        """
        super().__init__(parent, **kwargs)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.parent = parent
        
        # Estado do painel
        self._expanded = True
        self._items: Dict[str, NavigationItem] = {}
        self._tree_items: Dict[str, str] = {}  # id -> tree item id
        self._callbacks: Dict[str, Callable] = {}
        
        # Variáveis de controle
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_changed)
        
        self._setup_ui()
        self._setup_default_items()
        self._apply_theme()
    
    def _setup_ui(self):
        """Configura a interface do painel."""
        # Frame principal
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Cabeçalho
        self._create_header()
        
        # Barra de pesquisa
        self._create_search_bar()
        
        # Árvore de navegação
        self._create_navigation_tree()
        
        # Rodapé
        self._create_footer()
    
    def _create_header(self):
        """Cria o cabeçalho do painel."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # Título
        title_label = ttk.Label(
            header_frame,
            text="Navegação",
            font=('TkDefaultFont', 10, 'bold')
        )
        title_label.pack(side=tk.LEFT)
        
        # Botão de colapsar/expandir
        self.toggle_button = ttk.Button(
            header_frame,
            text="◀",
            width=3,
            command=self._toggle_panel
        )
        self.toggle_button.pack(side=tk.RIGHT)
    
    def _create_search_bar(self):
        """Cria a barra de pesquisa."""
        search_frame = ttk.Frame(self.main_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Campo de pesquisa
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('TkDefaultFont', 9)
        )
        self.search_entry.pack(fill=tk.X)
        
        # Placeholder
        self._add_placeholder(self.search_entry, "Pesquisar...")
    
    def _create_navigation_tree(self):
        """Cria a árvore de navegação."""
        # Frame com scrollbar
        tree_frame = ttk.Frame(self.main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            show='tree',
            selectmode='browse'
        )
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient=tk.VERTICAL,
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Layout
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Eventos
        self.tree.bind('<<TreeviewSelect>>', self._on_item_selected)
        self.tree.bind('<Double-1>', self._on_item_double_click)
        self.tree.bind('<Button-3>', self._on_right_click)
    
    def _create_footer(self):
        """Cria o rodapé do painel."""
        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Informações
        self.info_label = ttk.Label(
            footer_frame,
            text="",
            font=('TkDefaultFont', 8),
            foreground='gray'
        )
        self.info_label.pack(side=tk.LEFT)
        
        # Botão de configurações
        settings_button = ttk.Button(
            footer_frame,
            text="⚙",
            width=3,
            command=self._show_settings
        )
        settings_button.pack(side=tk.RIGHT)
    
    def _add_placeholder(self, entry: ttk.Entry, placeholder: str):
        """Adiciona placeholder a um Entry."""
        def on_focus_in(event):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(foreground='black')
        
        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(foreground='gray')
        
        entry.insert(0, placeholder)
        entry.config(foreground='gray')
        entry.bind('<FocusIn>', on_focus_in)
        entry.bind('<FocusOut>', on_focus_out)
    
    def _setup_default_items(self):
        """Configura itens padrão de navegação."""
        default_items = [
            # Categoria Principal
            NavigationItem(
                id="database",
                title="Banco de Dados",
                item_type=NavigationItemType.CATEGORY,
                icon="🗄️",
                order=1
            ),
            NavigationItem(
                id="view_roms",
                title="Visualizar ROMs",
                item_type=NavigationItemType.ACTION,
                icon="🎮",
                parent_id="database",
                callback=lambda: self._execute_action("view_roms"),
                tooltip="Visualizar lista de ROMs",
                order=1
            ),
            NavigationItem(
                id="search_roms",
                title="Pesquisar ROMs",
                item_type=NavigationItemType.ACTION,
                icon="🔍",
                parent_id="database",
                callback=lambda: self._execute_action("search_roms"),
                tooltip="Pesquisar ROMs no banco",
                order=2
            ),
            NavigationItem(
                id="statistics",
                title="Estatísticas",
                item_type=NavigationItemType.ACTION,
                icon="📊",
                parent_id="database",
                callback=lambda: self._execute_action("statistics"),
                tooltip="Ver estatísticas do banco",
                order=3
            ),
            
            # Separador
            NavigationItem(
                id="sep1",
                title="",
                item_type=NavigationItemType.SEPARATOR,
                order=2
            ),
            
            # Categoria Importação
            NavigationItem(
                id="import",
                title="Importação",
                item_type=NavigationItemType.CATEGORY,
                icon="📥",
                order=3
            ),
            NavigationItem(
                id="import_xml",
                title="Importar XML",
                item_type=NavigationItemType.ACTION,
                icon="📄",
                parent_id="import",
                callback=lambda: self._execute_action("import_xml"),
                tooltip="Importar dados de arquivo XML",
                order=1
            ),
            NavigationItem(
                id="import_roms",
                title="Importar ROMs",
                item_type=NavigationItemType.ACTION,
                icon="💿",
                parent_id="import",
                callback=lambda: self._execute_action("import_roms"),
                tooltip="Importar arquivos ROM",
                order=2
            ),
            NavigationItem(
                id="import_history",
                title="Histórico",
                item_type=NavigationItemType.ACTION,
                icon="📋",
                parent_id="import",
                callback=lambda: self._execute_action("import_history"),
                tooltip="Ver histórico de importações",
                order=3
            ),
            
            # Separador
            NavigationItem(
                id="sep2",
                title="",
                item_type=NavigationItemType.SEPARATOR,
                order=4
            ),
            
            # Categoria Ferramentas
            NavigationItem(
                id="tools",
                title="Ferramentas",
                item_type=NavigationItemType.CATEGORY,
                icon="🔧",
                order=5
            ),
            NavigationItem(
                id="backup",
                title="Backup",
                item_type=NavigationItemType.ACTION,
                icon="💾",
                parent_id="tools",
                callback=lambda: self._execute_action("backup"),
                tooltip="Fazer backup do banco",
                order=1
            ),
            NavigationItem(
                id="maintenance",
                title="Manutenção",
                item_type=NavigationItemType.ACTION,
                icon="🔨",
                parent_id="tools",
                callback=lambda: self._execute_action("maintenance"),
                tooltip="Ferramentas de manutenção",
                order=2
            ),
            NavigationItem(
                id="export",
                title="Exportar",
                item_type=NavigationItemType.ACTION,
                icon="📤",
                parent_id="tools",
                callback=lambda: self._execute_action("export"),
                tooltip="Exportar dados",
                order=3
            ),
            
            # Separador
            NavigationItem(
                id="sep3",
                title="",
                item_type=NavigationItemType.SEPARATOR,
                order=6
            ),
            
            # Categoria Configurações
            NavigationItem(
                id="settings_cat",
                title="Configurações",
                item_type=NavigationItemType.CATEGORY,
                icon="⚙️",
                order=7
            ),
            NavigationItem(
                id="preferences",
                title="Preferências",
                item_type=NavigationItemType.ACTION,
                icon="🎛️",
                parent_id="settings_cat",
                callback=lambda: self._execute_action("preferences"),
                tooltip="Configurações do aplicativo",
                order=1
            ),
            NavigationItem(
                id="themes",
                title="Temas",
                item_type=NavigationItemType.ACTION,
                icon="🎨",
                parent_id="settings_cat",
                callback=lambda: self._execute_action("themes"),
                tooltip="Configurar tema da interface",
                order=2
            ),
            
            # Separador
            NavigationItem(
                id="sep4",
                title="",
                item_type=NavigationItemType.SEPARATOR,
                order=8
            ),
            
            # Categoria Ajuda
            NavigationItem(
                id="help",
                title="Ajuda",
                item_type=NavigationItemType.CATEGORY,
                icon="❓",
                order=9
            ),
            NavigationItem(
                id="about",
                title="Sobre",
                item_type=NavigationItemType.ACTION,
                icon="ℹ️",
                parent_id="help",
                callback=lambda: self._execute_action("about"),
                tooltip="Sobre o aplicativo",
                order=1
            ),
            NavigationItem(
                id="documentation",
                title="Documentação",
                item_type=NavigationItemType.ACTION,
                icon="📖",
                parent_id="help",
                callback=lambda: self._execute_action("documentation"),
                tooltip="Documentação do usuário",
                order=2
            ),
        ]
        
        # Adiciona itens
        for item in default_items:
            self.add_item(item)
        
        # Constrói a árvore
        self._build_tree()
    
    def add_item(self, item: NavigationItem):
        """Adiciona item de navegação."""
        self._items[item.id] = item
        logger.debug(f"Item de navegação adicionado: {item.id}")
    
    def remove_item(self, item_id: str):
        """Remove item de navegação."""
        if item_id in self._items:
            # Remove filhos primeiro
            children = [item for item in self._items.values() if item.parent_id == item_id]
            for child in children:
                self.remove_item(child.id)
            
            # Remove da árvore
            if item_id in self._tree_items:
                self.tree.delete(self._tree_items[item_id])
                del self._tree_items[item_id]
            
            # Remove do dicionário
            del self._items[item_id]
            logger.debug(f"Item de navegação removido: {item_id}")
    
    def update_item(self, item_id: str, **kwargs):
        """Atualiza item de navegação."""
        if item_id in self._items:
            item = self._items[item_id]
            
            # Atualiza propriedades
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            # Atualiza na árvore
            if item_id in self._tree_items:
                tree_item_id = self._tree_items[item_id]
                text = self._format_item_text(item)
                self.tree.item(tree_item_id, text=text)
            
            logger.debug(f"Item de navegação atualizado: {item_id}")
    
    def set_item_badge(self, item_id: str, badge_text: Optional[str], badge_color: str = "red"):
        """Define badge de um item."""
        self.update_item(item_id, badge_text=badge_text, badge_color=badge_color)
    
    def set_item_enabled(self, item_id: str, enabled: bool):
        """Define se um item está habilitado."""
        self.update_item(item_id, enabled=enabled)
    
    def set_item_visible(self, item_id: str, visible: bool):
        """Define se um item está visível."""
        self.update_item(item_id, visible=visible)
        
        # Reconstrói a árvore para aplicar visibilidade
        self._build_tree()
    
    def register_callback(self, action_id: str, callback: Callable):
        """Registra callback para ação."""
        self._callbacks[action_id] = callback
        logger.debug(f"Callback registrado para: {action_id}")
    
    def _build_tree(self):
        """Constrói a árvore de navegação."""
        # Limpa árvore atual
        self.tree.delete(*self.tree.get_children())
        self._tree_items.clear()
        
        # Ordena itens
        sorted_items = sorted(self._items.values(), key=lambda x: (x.order, x.title))
        
        # Adiciona itens raiz primeiro
        for item in sorted_items:
            if item.parent_id is None and item.visible:
                self._add_tree_item(item)
        
        # Adiciona filhos
        for item in sorted_items:
            if item.parent_id is not None and item.visible:
                self._add_tree_item(item)
        
        # Expande categorias por padrão
        for item_id, tree_item_id in self._tree_items.items():
            item = self._items[item_id]
            if item.item_type == NavigationItemType.CATEGORY:
                self.tree.item(tree_item_id, open=True)
    
    def _add_tree_item(self, item: NavigationItem):
        """Adiciona item à árvore."""
        if item.item_type == NavigationItemType.SEPARATOR:
            return  # Separadores não são mostrados na árvore
        
        # Determina pai
        parent = ""
        if item.parent_id and item.parent_id in self._tree_items:
            parent = self._tree_items[item.parent_id]
        
        # Formata texto
        text = self._format_item_text(item)
        
        # Adiciona à árvore
        tree_item_id = self.tree.insert(
            parent,
            tk.END,
            text=text,
            tags=(item.item_type.value, "enabled" if item.enabled else "disabled")
        )
        
        self._tree_items[item.id] = tree_item_id
    
    def _format_item_text(self, item: NavigationItem) -> str:
        """Formata texto do item."""
        text = ""
        
        # Ícone
        if item.icon:
            text += f"{item.icon} "
        
        # Título
        text += item.title
        
        # Badge
        if item.badge_text:
            text += f" ({item.badge_text})"
        
        return text
    
    def _on_item_selected(self, event):
        """Manipula seleção de item."""
        selection = self.tree.selection()
        if not selection:
            return
        
        tree_item_id = selection[0]
        
        # Encontra item correspondente
        item_id = None
        for id_, tree_id in self._tree_items.items():
            if tree_id == tree_item_id:
                item_id = id_
                break
        
        if item_id and item_id in self._items:
            item = self._items[item_id]
            
            # Atualiza informações no rodapé
            if item.tooltip:
                self.info_label.config(text=item.tooltip)
            else:
                self.info_label.config(text=item.title)
    
    def _on_item_double_click(self, event):
        """Manipula duplo clique em item."""
        selection = self.tree.selection()
        if not selection:
            return
        
        tree_item_id = selection[0]
        
        # Encontra item correspondente
        item_id = None
        for id_, tree_id in self._tree_items.items():
            if tree_id == tree_item_id:
                item_id = id_
                break
        
        if item_id and item_id in self._items:
            item = self._items[item_id]
            
            # Executa ação se for um item de ação
            if item.item_type == NavigationItemType.ACTION and item.enabled:
                if item.callback:
                    try:
                        item.callback()
                    except Exception as e:
                        logger.error(f"Erro ao executar callback: {e}")
    
    def _on_right_click(self, event):
        """Manipula clique direito."""
        # Implementar menu de contexto se necessário
        pass
    
    def _on_search_changed(self, *args):
        """Manipula mudança na pesquisa."""
        search_text = self.search_var.get().lower()
        
        if not search_text or search_text == "pesquisar...":
            # Mostra todos os itens
            for item in self._items.values():
                self.set_item_visible(item.id, True)
        else:
            # Filtra itens
            for item in self._items.values():
                visible = search_text in item.title.lower()
                if item.tooltip:
                    visible = visible or search_text in item.tooltip.lower()
                
                self.set_item_visible(item.id, visible)
    
    def _execute_action(self, action_id: str):
        """Executa ação registrada."""
        if action_id in self._callbacks:
            try:
                self._callbacks[action_id]()
            except Exception as e:
                logger.error(f"Erro ao executar ação {action_id}: {e}")
        else:
            logger.warning(f"Ação não registrada: {action_id}")
    
    def _toggle_panel(self):
        """Alterna expansão do painel."""
        self._expanded = not self._expanded
        
        if self._expanded:
            self.toggle_button.config(text="◀")
            # Expandir painel
            # Implementar lógica de expansão
        else:
            self.toggle_button.config(text="▶")
            # Colapsar painel
            # Implementar lógica de colapso
    
    def _show_settings(self):
        """Mostra configurações do painel."""
        self._execute_action("preferences")
    
    def _apply_theme(self):
        """Aplica tema ao painel."""
        if self.theme_manager:
            try:
                # Aplicar configurações de tema
                theme = self.theme_manager.get_current_theme()
                
                # Configurar tags da árvore
                self.tree.tag_configure("category", font=('TkDefaultFont', 9, 'bold'))
                self.tree.tag_configure("action", font=('TkDefaultFont', 9))
                self.tree.tag_configure("disabled", foreground='gray')
                
            except Exception as e:
                logger.error(f"Erro ao aplicar tema: {e}")
    
    def refresh(self):
        """Atualiza o painel."""
        self._build_tree()
        self._apply_theme()
        logger.debug("Painel de navegação atualizado")
    
    def get_selected_item(self) -> Optional[NavigationItem]:
        """Retorna item selecionado."""
        selection = self.tree.selection()
        if not selection:
            return None
        
        tree_item_id = selection[0]
        
        # Encontra item correspondente
        for item_id, tree_id in self._tree_items.items():
            if tree_id == tree_item_id:
                return self._items.get(item_id)
        
        return None
    
    def select_item(self, item_id: str):
        """Seleciona item programaticamente."""
        if item_id in self._tree_items:
            tree_item_id = self._tree_items[item_id]
            self.tree.selection_set(tree_item_id)
            self.tree.focus(tree_item_id)
            self.tree.see(tree_item_id)