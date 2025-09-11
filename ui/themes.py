#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Temas
Definições de cores e estilos para os temas da aplicação
"""

# Temas de cores para a aplicação

# Tema claro
LIGHT_THEME = {
    "bg": "#f5f5f5",
    "fg": "#212121",
    "accent": "#2196F3",
    "highlight": "#E3F2FD",
    "highlight_bg": "#4a6984",
    "highlight_fg": "#ffffff",
    "success": "#4CAF50",
    "warning": "#FFC107",
    "error": "#F44336",
    "border": "#BDBDBD",
    "table_row_odd": "#f9f9f9",
    "table_row_even": "#ffffff",
    "table_header": "#e9e9e9",
    "link": "#2196F3",
    "button_bg": "#e0e0e0",
    "button_fg": "#212121",
    "text_bg": "#ffffff",
    "text_fg": "#212121"
}

# Tema escuro aprimorado para melhor harmonização
DARK_THEME = {
    "bg": "#333333",
    "fg": "#f5f5f5",
    "accent": "#90CAF9",
    "highlight": "#1E1E1E",
    "highlight_bg": "#3a3a3a",
    "highlight_fg": "#ffffff",
    "success": "#81C784",
    "warning": "#FFD54F",
    "error": "#E57373",
    "border": "#616161",
    "table_row_odd": "#2a2a2a",
    "table_row_even": "#333333",
    "table_header": "#2a2a2a",
    "link": "#90CAF9",
    "button_bg": "#424242",
    "button_fg": "#f5f5f5",
    "text_bg": "#424242",
    "text_fg": "#f5f5f5"
}

def apply_theme_to_ttk(theme_name):
    """
    Aplica um tema ao ttk.
    
    Args:
        theme_name: Nome do tema ("light" ou "dark")
    """
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkFont
    
    style = ttk.Style()
    
    # Seleciona o tema de cores
    colors = LIGHT_THEME if theme_name == "light" else DARK_THEME
    
    # Configura o tema padrão
    style.theme_use("clam")  # Usa clam como base por ser mais personalizável
    
    # Configura elementos comuns
    style.configure(".",
                   background=colors["bg"],
                   foreground=colors["fg"],
                   troughcolor=colors["bg"],
                   selectbackground=colors["accent"],
                   selectforeground=colors["highlight_fg"],
                   fieldbackground=colors["text_bg"],
                   font=("Segoe UI", 10),
                   borderwidth=1)
    
    # Configura botões
    style.configure("TButton",
                   background=colors["button_bg"],
                   foreground=colors["button_fg"],
                   padding=5)
    style.map("TButton",
              background=[("active", colors["accent"]), 
                          ("pressed", colors["highlight_bg"])],
              foreground=[("active", colors["highlight_fg"])])
    
    # Configura rótulos
    style.configure("TLabel",
                   background=colors["bg"],
                   foreground=colors["fg"])
    
    # Configura entradas
    style.configure("TEntry",
                   fieldbackground=colors["text_bg"],
                   foreground=colors["text_fg"],
                   selectbackground=colors["accent"],
                   selectforeground=colors["highlight_fg"],
                   padding=5)
    
    # Configura comboboxes
    style.configure("TCombobox",
                   fieldbackground=colors["text_bg"],
                   background=colors["button_bg"],
                   foreground=colors["text_fg"],
                   selectbackground=colors["accent"],
                   selectforeground=colors["highlight_fg"],
                   arrowcolor=colors["fg"])
    
    # Configura notebooks (abas)
    style.configure("TNotebook",
                   background=colors["bg"],
                   tabmargins=[2, 5, 2, 0])
    style.configure("TNotebook.Tab",
                   background=colors["button_bg"],
                   foreground=colors["button_fg"],
                   padding=[10, 5],
                   font=("Segoe UI", 10))
    style.map("TNotebook.Tab",
              background=[("selected", colors["accent"]), 
                          ("active", colors["highlight_bg"])],
              foreground=[("selected", colors["highlight_fg"]), 
                          ("active", colors["highlight_fg"])])
    
    # Configura frames
    style.configure("TFrame",
                   background=colors["bg"])
    
    # Configura progressbar
    style.configure("Horizontal.TProgressbar",
                   troughcolor=colors["bg"],
                   background=colors["accent"],
                   borderwidth=0)
    
    # Configura scrollbars
    style.configure("Vertical.TScrollbar",
                   background=colors["button_bg"],
                   troughcolor=colors["bg"],
                   arrowcolor=colors["fg"],
                   borderwidth=1)
    style.configure("Horizontal.TScrollbar",
                   background=colors["button_bg"],
                   troughcolor=colors["bg"],
                   arrowcolor=colors["fg"],
                   borderwidth=1)
    
    # Configura treeview (tabela)
    style.configure("Treeview",
                   background=colors["table_row_even"],
                   fieldbackground=colors["table_row_even"],
                   foreground=colors["fg"])
    style.configure("Treeview.Heading",
                   background=colors["table_header"],
                   foreground=colors["fg"],
                   font=("Segoe UI", 10, "bold"))
    style.map("Treeview",
              background=[("selected", colors["accent"])],
              foreground=[("selected", colors["highlight_fg"])])
    
    # Configurações específicas do tema escuro
    if theme_name == "dark":
        # Ajusta cores do treeview para dark theme
        style.map("Treeview",
                 background=[("selected", colors["accent"]), 
                             ("!selected", colors["table_row_even"])],
                 foreground=[("selected", colors["highlight_fg"])])
        
        # Configura treeview tags para linhas alternadas
        style.map("Treeview",
                 background=[("selected", colors["accent"]), 
                             ("!selected", colors["table_row_even"])])
    
    return style

def apply_theme_to_widgets(root, theme_name):
    """
    Aplica as cores do tema a widgets nativos do tkinter.
    
    Args:
        root: Widget raiz ou container
        theme_name: Nome do tema ("light" ou "dark")
    """
    import tkinter as tk
    
    # Seleciona o tema de cores
    colors = LIGHT_THEME if theme_name == "light" else DARK_THEME
    
    # Aplica cores aos widgets filhos recursivamente
    for widget in root.winfo_children():
        widget_type = widget.winfo_class()
        
        # Aplica cores baseado no tipo de widget
        if widget_type in ("Frame", "Labelframe", "Toplevel"):
            widget.configure(bg=colors["bg"])
            # Continua recursivamente
            apply_theme_to_widgets(widget, theme_name)
        
        elif widget_type == "Label":
            widget.configure(bg=colors["bg"], fg=colors["fg"])
        
        elif widget_type == "Button":
            widget.configure(
                bg=colors["button_bg"],
                fg=colors["button_fg"],
                activebackground=colors["accent"],
                activeforeground=colors["highlight_fg"]
            )
        
        elif widget_type == "Entry":
            widget.configure(
                bg=colors["text_bg"],
                fg=colors["text_fg"],
                selectbackground=colors["accent"],
                selectforeground=colors["highlight_fg"],
                insertbackground=colors["fg"]  # cursor color
            )
        
        elif widget_type == "Text":
            widget.configure(
                bg=colors["text_bg"],
                fg=colors["text_fg"],
                selectbackground=colors["accent"],
                selectforeground=colors["highlight_fg"],
                insertbackground=colors["fg"]  # cursor color
            )
        
        elif widget_type == "Listbox":
            widget.configure(
                bg=colors["text_bg"],
                fg=colors["text_fg"],
                selectbackground=colors["accent"],
                selectforeground=colors["highlight_fg"]
            )
        
        elif widget_type == "Canvas":
            widget.configure(bg=colors["bg"])
        
        # Para outros widgets, continua recursivamente
        elif hasattr(widget, "winfo_children"):
            apply_theme_to_widgets(widget, theme_name) 