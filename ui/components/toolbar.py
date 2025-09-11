# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Toolbar
Barra de ferramentas da aplicação principal
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
from engine.config_manager_enhanced import EnhancedConfigManager

logger = logging.getLogger(__name__)

class ToolbarItemType(Enum):
    """Tipos de itens da toolbar."""
    BUTTON = "button"
    SEPARATOR = "separator"
    DROPDOWN = "dropdown"
    TOGGLE = "toggle"
    SEARCH = "search"
    LABEL = "label"

class ToolbarStyle(Enum):
    """Estilos da toolbar."""
    ICONS_ONLY = "icons_only"
    TEXT_ONLY = "text_only"
    ICONS_AND_TEXT = "icons_and_text"
    COMPACT = "compact"

@dataclass
class ToolbarItem:
    """Item da toolbar."""
    id: str
    title: str
    item_type: ToolbarItemType
    icon: Optional[str] = None
    callback: Optional[Callable] = None
    tooltip: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    group: Optional[str] = None
    order: int = 0
    shortcut: Optional[str] = None
    toggle_state: bool = False
    dropdown_items: Optional[List[Dict[str, Any]]] = None
    width: Optional[int] = None

class Toolbar(ttk.Frame):
    """Barra de ferramentas da aplicação."""
    
    def __init__(self, parent, config_manager: EnhancedConfigManager = None, theme_manager=None, 
                 style: ToolbarStyle = ToolbarStyle.ICONS_AND_TEXT, **kwargs):
        """
        Inicializa a toolbar.
        
        Args:
            parent: Widget pai
            config_manager: Gerenciador de configurações
            theme_manager: Gerenciador de temas
            style: Estilo da toolbar
        """
        super().__init__(parent, **kwargs)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.parent = parent
        self.style = style
        
        # Estado da toolbar
        self._items: Dict[str, ToolbarItem] = {}
        self._widgets: Dict[str, tk.Widget] = {}
        self._groups: Dict[str, List[str]] = {}
        self._callbacks: Dict[str, Callable] = {}
        
        # Variáveis de controle
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_changed)
        
        # Configurações
        self.icon_size = 24
        self.button_padding = 2
        self.group_spacing = 10
        
        self._setup_ui()
        self._setup_default_items()
        self._apply_theme()
    
    def _setup_ui(self):
        """Configura a interface da toolbar."""
        # Frame principal
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Frame para itens
        self.items_frame = ttk.Frame(self.main_frame)
        self.items_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Frame para busca (lado direito)
        self.search_frame = ttk.Frame(self.main_frame)
        self.search_frame.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_default_items(self):
        """Configura itens padrão da toolbar."""
        default_items = [
            # Grupo Arquivo
            ToolbarItem(
                id="new_database",
                title="Novo",
                item_type=ToolbarItemType.BUTTON,
                icon="📄",
                callback=lambda: self._execute_action("new_database"),
                tooltip="Criar novo banco de dados (Ctrl+N)",
                group="file",
                order=1,
                shortcut="Ctrl+N"
            ),
            ToolbarItem(
                id="open_database",
                title="Abrir",
                item_type=ToolbarItemType.BUTTON,
                icon="📂",
                callback=lambda: self._execute_action("open_database"),
                tooltip="Abrir banco de dados (Ctrl+O)",
                group="file",
                order=2,
                shortcut="Ctrl+O"
            ),
            ToolbarItem(
                id="save_database",
                title="Salvar",
                item_type=ToolbarItemType.BUTTON,
                icon="💾",
                callback=lambda: self._execute_action("save_database"),
                tooltip="Salvar banco de dados (Ctrl+S)",
                group="file",
                order=3,
                shortcut="Ctrl+S"
            ),
            
            # Separador
            ToolbarItem(
                id="sep1",
                title="",
                item_type=ToolbarItemType.SEPARATOR,
                order=4
            ),
            
            # Grupo Importação
            ToolbarItem(
                id="import_xml",
                title="Importar XML",
                item_type=ToolbarItemType.BUTTON,
                icon="📥",
                callback=lambda: self._execute_action("import_xml"),
                tooltip="Importar dados de arquivo XML",
                group="import",
                order=5
            ),
            ToolbarItem(
                id="import_roms",
                title="Importar ROMs",
                item_type=ToolbarItemType.BUTTON,
                icon="💿",
                callback=lambda: self._execute_action("import_roms"),
                tooltip="Importar arquivos ROM",
                group="import",
                order=6
            ),
            ToolbarItem(
                id="export_data",
                title="Exportar",
                item_type=ToolbarItemType.DROPDOWN,
                icon="📤",
                tooltip="Exportar dados",
                group="import",
                order=7,
                dropdown_items=[
                    {"id": "export_xml", "title": "Exportar XML", "icon": "📄"},
                    {"id": "export_csv", "title": "Exportar CSV", "icon": "📊"},
                    {"id": "export_json", "title": "Exportar JSON", "icon": "📋"}
                ]
            ),
            
            # Separador
            ToolbarItem(
                id="sep2",
                title="",
                item_type=ToolbarItemType.SEPARATOR,
                order=8
            ),
            
            # Grupo Visualização
            ToolbarItem(
                id="view_list",
                title="Lista",
                item_type=ToolbarItemType.TOGGLE,
                icon="📋",
                callback=lambda: self._execute_action("view_list"),
                tooltip="Visualização em lista",
                group="view",
                order=9,
                toggle_state=True
            ),
            ToolbarItem(
                id="view_grid",
                title="Grade",
                item_type=ToolbarItemType.TOGGLE,
                icon="⊞",
                callback=lambda: self._execute_action("view_grid"),
                tooltip="Visualização em grade",
                group="view",
                order=10
            ),
            ToolbarItem(
                id="view_details",
                title="Detalhes",
                item_type=ToolbarItemType.TOGGLE,
                icon="📄",
                callback=lambda: self._execute_action("view_details"),
                tooltip="Visualização detalhada",
                group="view",
                order=11
            ),
            
            # Separador
            ToolbarItem(
                id="sep3",
                title="",
                item_type=ToolbarItemType.SEPARATOR,
                order=12
            ),
            
            # Grupo Ferramentas
            ToolbarItem(
                id="search_roms",
                title="Pesquisar",
                item_type=ToolbarItemType.BUTTON,
                icon="🔍",
                callback=lambda: self._execute_action("search_roms"),
                tooltip="Pesquisar ROMs (Ctrl+F)",
                group="tools",
                order=13,
                shortcut="Ctrl+F"
            ),
            ToolbarItem(
                id="filter_roms",
                title="Filtrar",
                item_type=ToolbarItemType.BUTTON,
                icon="🔽",
                callback=lambda: self._execute_action("filter_roms"),
                tooltip="Filtrar ROMs",
                group="tools",
                order=14
            ),
            ToolbarItem(
                id="refresh",
                title="Atualizar",
                item_type=ToolbarItemType.BUTTON,
                icon="🔄",
                callback=lambda: self._execute_action("refresh"),
                tooltip="Atualizar dados (F5)",
                group="tools",
                order=15,
                shortcut="F5"
            ),
            
            # Separador
            ToolbarItem(
                id="sep4",
                title="",
                item_type=ToolbarItemType.SEPARATOR,
                order=16
            ),
            
            # Grupo Configurações
            ToolbarItem(
                id="settings",
                title="Configurações",
                item_type=ToolbarItemType.BUTTON,
                icon="⚙️",
                callback=lambda: self._execute_action("settings"),
                tooltip="Configurações da aplicação",
                group="settings",
                order=17
            ),
            ToolbarItem(
                id="help",
                title="Ajuda",
                item_type=ToolbarItemType.BUTTON,
                icon="❓",
                callback=lambda: self._execute_action("help"),
                tooltip="Ajuda e documentação (F1)",
                group="settings",
                order=18,
                shortcut="F1"
            ),
        ]
        
        # Adiciona itens
        for item in default_items:
            self.add_item(item)
        
        # Adiciona campo de busca
        self._add_search_field()
        
        # Constrói a toolbar
        self._build_toolbar()
    
    def add_item(self, item: ToolbarItem):
        """Adiciona item à toolbar."""
        self._items[item.id] = item
        
        # Adiciona ao grupo
        if item.group:
            if item.group not in self._groups:
                self._groups[item.group] = []
            self._groups[item.group].append(item.id)
        
        logger.debug(f"Item da toolbar adicionado: {item.id}")
    
    def remove_item(self, item_id: str):
        """Remove item da toolbar."""
        if item_id in self._items:
            item = self._items[item_id]
            
            # Remove do grupo
            if item.group and item.group in self._groups:
                if item_id in self._groups[item.group]:
                    self._groups[item.group].remove(item_id)
            
            # Remove widget
            if item_id in self._widgets:
                self._widgets[item_id].destroy()
                del self._widgets[item_id]
            
            # Remove do dicionário
            del self._items[item_id]
            logger.debug(f"Item da toolbar removido: {item_id}")
    
    def update_item(self, item_id: str, **kwargs):
        """Atualiza item da toolbar."""
        if item_id in self._items:
            item = self._items[item_id]
            
            # Atualiza propriedades
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            # Atualiza widget
            if item_id in self._widgets:
                self._update_widget(item_id)
            
            logger.debug(f"Item da toolbar atualizado: {item_id}")
    
    def set_item_enabled(self, item_id: str, enabled: bool):
        """Define se um item está habilitado."""
        self.update_item(item_id, enabled=enabled)
    
    def set_item_visible(self, item_id: str, visible: bool):
        """Define se um item está visível."""
        self.update_item(item_id, visible=visible)
        
        # Reconstrói a toolbar para aplicar visibilidade
        self._build_toolbar()
    
    def set_toggle_state(self, item_id: str, state: bool):
        """Define estado de toggle de um item."""
        if item_id in self._items and self._items[item_id].item_type == ToolbarItemType.TOGGLE:
            self.update_item(item_id, toggle_state=state)
    
    def register_callback(self, action_id: str, callback: Callable):
        """Registra callback para ação."""
        self._callbacks[action_id] = callback
        logger.debug(f"Callback registrado para: {action_id}")
    
    def _add_search_field(self):
        """Adiciona campo de busca."""
        search_item = ToolbarItem(
            id="search_field",
            title="Buscar",
            item_type=ToolbarItemType.SEARCH,
            tooltip="Busca rápida",
            width=200,
            order=999  # Sempre no final
        )
        self.add_item(search_item)
    
    def _build_toolbar(self):
        """Constrói a toolbar."""
        # Limpa widgets existentes
        for widget in self._widgets.values():
            widget.destroy()
        self._widgets.clear()
        
        # Ordena itens
        sorted_items = sorted(
            [item for item in self._items.values() if item.visible],
            key=lambda x: x.order
        )
        
        # Agrupa itens
        current_group = None
        
        for item in sorted_items:
            # Adiciona espaçamento entre grupos
            if item.group != current_group and current_group is not None:
                if item.item_type != ToolbarItemType.SEPARATOR:
                    spacer = ttk.Frame(self.items_frame, width=self.group_spacing)
                    spacer.pack(side=tk.LEFT)
            
            # Cria widget do item
            if item.id == "search_field":
                self._create_search_widget(item)
            else:
                self._create_item_widget(item)
            
            current_group = item.group
    
    def _create_item_widget(self, item: ToolbarItem):
        """Cria widget para item."""
        if item.item_type == ToolbarItemType.SEPARATOR:
            widget = ttk.Separator(self.items_frame, orient=tk.VERTICAL)
            widget.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        elif item.item_type == ToolbarItemType.BUTTON:
            widget = self._create_button(item)
        
        elif item.item_type == ToolbarItemType.TOGGLE:
            widget = self._create_toggle_button(item)
        
        elif item.item_type == ToolbarItemType.DROPDOWN:
            widget = self._create_dropdown_button(item)
        
        elif item.item_type == ToolbarItemType.LABEL:
            widget = self._create_label(item)
        
        else:
            return
        
        self._widgets[item.id] = widget
    
    def _create_button(self, item: ToolbarItem) -> ttk.Button:
        """Cria botão normal."""
        text = self._get_button_text(item)
        
        button = ttk.Button(
            self.items_frame,
            text=text,
            command=lambda: self._execute_item_action(item),
            state=tk.NORMAL if item.enabled else tk.DISABLED
        )
        
        button.pack(side=tk.LEFT, padx=self.button_padding)
        
        # Adiciona tooltip
        if item.tooltip:
            self._add_tooltip(button, item.tooltip)
        
        return button
    
    def _create_toggle_button(self, item: ToolbarItem) -> ttk.Button:
        """Cria botão de toggle."""
        text = self._get_button_text(item)
        
        button = ttk.Button(
            self.items_frame,
            text=text,
            command=lambda: self._toggle_item(item),
            state=tk.NORMAL if item.enabled else tk.DISABLED
        )
        
        button.pack(side=tk.LEFT, padx=self.button_padding)
        
        # Aplica estilo de toggle
        self._apply_toggle_style(button, item.toggle_state)
        
        # Adiciona tooltip
        if item.tooltip:
            self._add_tooltip(button, item.tooltip)
        
        return button
    
    def _create_dropdown_button(self, item: ToolbarItem) -> ttk.Menubutton:
        """Cria botão dropdown."""
        text = self._get_button_text(item)
        
        menubutton = ttk.Menubutton(
            self.items_frame,
            text=text,
            state=tk.NORMAL if item.enabled else tk.DISABLED
        )
        
        # Cria menu
        menu = tk.Menu(menubutton, tearoff=0)
        menubutton.config(menu=menu)
        
        # Adiciona itens do dropdown
        if item.dropdown_items:
            for dropdown_item in item.dropdown_items:
                menu.add_command(
                    label=f"{dropdown_item.get('icon', '')} {dropdown_item['title']}".strip(),
                    command=lambda id=dropdown_item['id']: self._execute_action(id)
                )
        
        menubutton.pack(side=tk.LEFT, padx=self.button_padding)
        
        # Adiciona tooltip
        if item.tooltip:
            self._add_tooltip(menubutton, item.tooltip)
        
        return menubutton
    
    def _create_label(self, item: ToolbarItem) -> ttk.Label:
        """Cria label."""
        text = self._get_button_text(item)
        
        label = ttk.Label(
            self.items_frame,
            text=text,
            font=('TkDefaultFont', 9)
        )
        
        label.pack(side=tk.LEFT, padx=self.button_padding)
        
        return label
    
    def _create_search_widget(self, item: ToolbarItem):
        """Cria widget de busca."""
        # Frame para busca
        search_container = ttk.Frame(self.search_frame)
        search_container.pack(side=tk.RIGHT, padx=5)
        
        # Ícone de busca
        search_icon = ttk.Label(
            search_container,
            text="🔍",
            font=('TkDefaultFont', 10)
        )
        search_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        # Campo de entrada
        search_entry = ttk.Entry(
            search_container,
            textvariable=self.search_var,
            width=item.width // 8 if item.width else 25,
            font=('TkDefaultFont', 9)
        )
        search_entry.pack(side=tk.LEFT)
        
        # Placeholder
        self._add_placeholder(search_entry, "Buscar...")
        
        # Botão limpar
        clear_button = ttk.Button(
            search_container,
            text="✕",
            width=3,
            command=self._clear_search
        )
        clear_button.pack(side=tk.LEFT, padx=(2, 0))
        
        self._widgets[item.id] = search_container
        self._widgets[f"{item.id}_entry"] = search_entry
        self._widgets[f"{item.id}_clear"] = clear_button
    
    def _get_button_text(self, item: ToolbarItem) -> str:
        """Obtém texto do botão baseado no estilo."""
        if self.style == ToolbarStyle.ICONS_ONLY:
            return item.icon or ""
        elif self.style == ToolbarStyle.TEXT_ONLY:
            return item.title
        elif self.style == ToolbarStyle.ICONS_AND_TEXT:
            icon = item.icon or ""
            return f"{icon} {item.title}".strip()
        elif self.style == ToolbarStyle.COMPACT:
            return item.icon or item.title[:3]
        else:
            return item.title
    
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
    
    def _add_tooltip(self, widget, text: str):
        """Adiciona tooltip ao widget."""
        def on_enter(event):
            self._show_tooltip(event.widget, text)
        
        def on_leave(event):
            self._hide_tooltip()
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def _show_tooltip(self, widget, text: str):
        """Mostra tooltip."""
        try:
            self.tooltip_window = tk.Toplevel()
            self.tooltip_window.wm_overrideredirect(True)
            
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(
                self.tooltip_window,
                text=text,
                background='lightyellow',
                relief='solid',
                borderwidth=1,
                font=('TkDefaultFont', 8)
            )
            label.pack()
        except Exception as e:
            logger.error(f"Erro ao mostrar tooltip: {e}")
    
    def _hide_tooltip(self):
        """Oculta tooltip."""
        try:
            if hasattr(self, 'tooltip_window'):
                self.tooltip_window.destroy()
                del self.tooltip_window
        except Exception as e:
            logger.error(f"Erro ao ocultar tooltip: {e}")
    
    def _execute_item_action(self, item: ToolbarItem):
        """Executa ação do item."""
        if item.callback and item.enabled:
            try:
                item.callback()
            except Exception as e:
                logger.error(f"Erro ao executar ação do item {item.id}: {e}")
    
    def _toggle_item(self, item: ToolbarItem):
        """Alterna estado de toggle do item."""
        if not item.enabled:
            return
        
        # Atualiza estado
        item.toggle_state = not item.toggle_state
        
        # Atualiza visual
        if item.id in self._widgets:
            self._apply_toggle_style(self._widgets[item.id], item.toggle_state)
        
        # Executa callback
        if item.callback:
            try:
                item.callback()
            except Exception as e:
                logger.error(f"Erro ao executar toggle do item {item.id}: {e}")
    
    def _apply_toggle_style(self, button: ttk.Button, pressed: bool):
        """Aplica estilo de toggle ao botão."""
        # Implementação básica - pode ser melhorada com temas
        if pressed:
            button.state(['pressed'])
        else:
            button.state(['!pressed'])
    
    def _execute_action(self, action_id: str):
        """Executa ação registrada."""
        if action_id in self._callbacks:
            try:
                self._callbacks[action_id]()
            except Exception as e:
                logger.error(f"Erro ao executar ação {action_id}: {e}")
        else:
            logger.warning(f"Ação não registrada: {action_id}")
    
    def _on_search_changed(self, *args):
        """Manipula mudança na busca."""
        search_text = self.search_var.get()
        
        if search_text and search_text != "Buscar...":
            # Executa busca
            self._execute_action("search_changed")
    
    def _clear_search(self):
        """Limpa campo de busca."""
        self.search_var.set("")
        
        # Foca no campo de busca
        if "search_field_entry" in self._widgets:
            self._widgets["search_field_entry"].focus()
    
    def _update_widget(self, item_id: str):
        """Atualiza widget específico."""
        if item_id not in self._widgets or item_id not in self._items:
            return
        
        item = self._items[item_id]
        widget = self._widgets[item_id]
        
        # Atualiza propriedades comuns
        if hasattr(widget, 'config'):
            # Estado
            state = tk.NORMAL if item.enabled else tk.DISABLED
            if hasattr(widget, 'state'):
                widget.config(state=state)
            
            # Texto (se aplicável)
            if hasattr(widget, 'text') and item.item_type in [ToolbarItemType.BUTTON, ToolbarItemType.TOGGLE]:
                text = self._get_button_text(item)
                widget.config(text=text)
        
        # Atualiza toggle state
        if item.item_type == ToolbarItemType.TOGGLE:
            self._apply_toggle_style(widget, item.toggle_state)
    
    def set_style(self, style: ToolbarStyle):
        """Define estilo da toolbar."""
        self.style = style
        self._build_toolbar()
        logger.debug(f"Estilo da toolbar alterado para: {style.value}")
    
    def get_search_text(self) -> str:
        """Retorna texto da busca."""
        text = self.search_var.get()
        return text if text != "Buscar..." else ""
    
    def set_search_text(self, text: str):
        """Define texto da busca."""
        self.search_var.set(text)
    
    def _apply_theme(self):
        """Aplica tema à toolbar."""
        if self.theme_manager:
            try:
                # Aplicar configurações de tema
                theme = self.theme_manager.get_current_theme()
                
                # Configurar estilos baseados no tema
                # Implementar quando theme_manager estiver disponível
                
            except Exception as e:
                logger.error(f"Erro ao aplicar tema: {e}")
    
    def refresh(self):
        """Atualiza a toolbar."""
        self._build_toolbar()
        self._apply_theme()
        logger.debug("Toolbar atualizada")