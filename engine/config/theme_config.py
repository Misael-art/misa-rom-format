#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Theme Config
Configuração de temas da interface
"""

import re
import json
import os
from typing import Dict, List, Optional, Union
from pathlib import Path

def is_valid_hex_color(color: str) -> bool:
    """
    Valida se uma cor está em formato hexadecimal válido.
    
    Args:
        color: Cor em formato hex (#RRGGBB)
    
    Returns:
        bool: True se válida
    """
    if not color:
        return False
    
    # Remove # se presente
    color = color.lstrip('#')
    
    # Valida formato
    return bool(re.match(r'^[0-9A-Fa-f]{6}$', color))

def validate_theme_colors(colors: Dict[str, str]) -> Dict[str, str]:
    """
    Valida cores de um tema.
    
    Args:
        colors: Dicionário de cores
    
    Returns:
        Dict[str, str]: Cores validadas
    """
    validated = {}
    for key, color in colors.items():
        if not is_valid_hex_color(color.lstrip('#')):
            # Usa cor padrão se inválida
            validated[key] = THEMES['light'].get(key, '#000000')
        else:
            validated[key] = color
    return validated

class ThemeManager:
    """Gerenciador de temas."""
    
    def __init__(self, themes_dir: Optional[str] = None):
        """
        Inicializa gerenciador.
        
        Args:
            themes_dir: Diretório de temas personalizados
        """
        self.themes_dir = themes_dir or str(Path.home() / '.megaemu' / 'themes')
        self.themes = THEMES.copy()
        self.load_custom_themes()
    
    def load_custom_themes(self) -> None:
        """Carrega temas personalizados."""
        try:
            if not os.path.exists(self.themes_dir):
                os.makedirs(self.themes_dir)
                return
            
            for file in os.listdir(self.themes_dir):
                if not file.endswith('.json'):
                    continue
                    
                theme_path = os.path.join(self.themes_dir, file)
                theme_name = file[:-5]  # Remove .json
                
                try:
                    with open(theme_path, 'r') as f:
                        theme_colors = json.load(f)
                    
                    # Valida cores
                    theme_colors = validate_theme_colors(theme_colors)
                    
                    # Adiciona tema
                    self.themes[theme_name] = theme_colors
                    
                except Exception as e:
                    print(f"Erro ao carregar tema {theme_name}: {str(e)}")
        
        except Exception as e:
            print(f"Erro ao carregar temas personalizados: {str(e)}")
    
    def save_custom_theme(self, name: str, colors: Dict[str, str]) -> bool:
        """
        Salva tema personalizado.
        
        Args:
            name: Nome do tema
            colors: Cores do tema
        
        Returns:
            bool: True se salvo com sucesso
        """
        try:
            # Valida nome
            if not re.match(r'^[a-zA-Z0-9_-]+$', name):
                print("Nome de tema inválido")
                return False
            
            # Valida cores
            colors = validate_theme_colors(colors)
            
            # Salva tema
            theme_path = os.path.join(self.themes_dir, f"{name}.json")
            with open(theme_path, 'w') as f:
                json.dump(colors, f, indent=4)
            
            # Atualiza temas
            self.themes[name] = colors
            return True
            
        except Exception as e:
            print(f"Erro ao salvar tema {name}: {str(e)}")
            return False
    
    def delete_custom_theme(self, name: str) -> bool:
        """
        Remove tema personalizado.
        
        Args:
            name: Nome do tema
        
        Returns:
            bool: True se removido com sucesso
        """
        try:
            # Verifica se é tema padrão
            if name in ['light', 'dark']:
                print("Não é possível remover temas padrão")
                return False
            
            # Remove arquivo
            theme_path = os.path.join(self.themes_dir, f"{name}.json")
            if os.path.exists(theme_path):
                os.remove(theme_path)
            
            # Remove do dicionário
            self.themes.pop(name, None)
            return True
            
        except Exception as e:
            print(f"Erro ao remover tema {name}: {str(e)}")
            return False
    
    def get_theme_colors(self, theme: str = "light") -> Dict[str, str]:
        """
        Obtém cores de um tema.
        
        Args:
            theme: Nome do tema
        
        Returns:
            Dict[str, str]: Cores do tema
        """
        return self.themes.get(theme, self.themes["light"])
    
    def get_available_themes(self) -> Dict[str, str]:
        """
        Obtém temas disponíveis.
        
        Returns:
            Dict[str, str]: Temas disponíveis
        """
        themes = {
            "light": "Tema Claro",
            "dark": "Tema Escuro"
        }
        
        # Adiciona temas personalizados
        for name in self.themes:
            if name not in themes:
                themes[name] = f"Tema Personalizado: {name}"
        
        return themes
    
    def export_theme(self, name: str, path: str) -> bool:
        """
        Exporta tema para arquivo.
        
        Args:
            name: Nome do tema
            path: Caminho do arquivo
        
        Returns:
            bool: True se exportado com sucesso
        """
        try:
            if name not in self.themes:
                return False
                
            with open(path, 'w') as f:
                json.dump(self.themes[name], f, indent=4)
            return True
            
        except Exception:
            return False
    
    def import_theme(self, name: str, path: str) -> bool:
        """
        Importa tema de arquivo.
        
        Args:
            name: Nome do tema
            path: Caminho do arquivo
        
        Returns:
            bool: True se importado com sucesso
        """
        try:
            with open(path, 'r') as f:
                colors = json.load(f)
            return self.save_custom_theme(name, colors)
            
        except Exception:
            return False

# Cores dos temas padrão
THEMES = {
    "light": {
        # Cores principais
        "bg": "#ffffff",
        "fg": "#000000",
        "accent": "#2196F3",
        "error": "#F44336",
        "warning": "#FFC107",
        "success": "#4CAF50",
        
        # Botões
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
        "button_active_bg": "#d0d0d0",
        "button_active_fg": "#000000",
        "button_disabled_bg": "#f0f0f0",
        "button_disabled_fg": "#a0a0a0",
        
        # Texto
        "text_bg": "#ffffff",
        "text_fg": "#000000",
        "text_disabled_fg": "#a0a0a0",
        "text_placeholder_fg": "#808080",
        "text_selection_bg": "#90CAF9",
        "text_selection_fg": "#000000",
        
        # Tabelas
        "table_header_bg": "#f0f0f0",
        "table_header_fg": "#000000",
        "table_row_odd_bg": "#f9f9f9",
        "table_row_even_bg": "#ffffff",
        "table_row_hover_bg": "#f5f5f5",
        "table_row_selected_bg": "#E3F2FD",
        "table_border": "#e0e0e0",
        
        # Menus
        "menu_bg": "#ffffff",
        "menu_fg": "#000000",
        "menu_hover_bg": "#f5f5f5",
        "menu_hover_fg": "#000000",
        "menu_disabled_fg": "#a0a0a0",
        "menu_separator": "#e0e0e0",
        
        # Abas
        "tab_bg": "#f0f0f0",
        "tab_fg": "#000000",
        "tab_active_bg": "#ffffff",
        "tab_active_fg": "#2196F3",
        "tab_hover_bg": "#e0e0e0",
        "tab_disabled_fg": "#a0a0a0",
        
        # Barras de rolagem
        "scrollbar_bg": "#f0f0f0",
        "scrollbar_fg": "#c0c0c0",
        "scrollbar_hover_fg": "#a0a0a0",
        
        # Diálogos
        "dialog_bg": "#ffffff",
        "dialog_fg": "#000000",
        "dialog_title_bg": "#f0f0f0",
        "dialog_button_bg": "#e0e0e0",
        
        # Progresso
        "progress_bg": "#f0f0f0",
        "progress_fg": "#2196F3",
        "progress_text": "#000000",
        
        # Bordas
        "border": "#e0e0e0",
        "focus_border": "#2196F3",
        
        # Links
        "link": "#2196F3",
        "link_hover": "#1976D2",
        "link_visited": "#9C27B0"
    },
    
    "dark": {
        # Cores principais
        "bg": "#2d2d2d",
        "fg": "#ffffff",
        "accent": "#90CAF9",
        "error": "#EF5350",
        "warning": "#FFD54F",
        "success": "#81C784",
        
        # Botões
        "button_bg": "#404040",
        "button_fg": "#ffffff",
        "button_active_bg": "#505050",
        "button_active_fg": "#ffffff",
        "button_disabled_bg": "#353535",
        "button_disabled_fg": "#808080",
        
        # Texto
        "text_bg": "#1e1e1e",
        "text_fg": "#ffffff",
        "text_disabled_fg": "#808080",
        "text_placeholder_fg": "#a0a0a0",
        "text_selection_bg": "#264F78",
        "text_selection_fg": "#ffffff",
        
        # Tabelas
        "table_header_bg": "#404040",
        "table_header_fg": "#ffffff",
        "table_row_odd_bg": "#2a2a2a",
        "table_row_even_bg": "#333333",
        "table_row_hover_bg": "#3a3a3a",
        "table_row_selected_bg": "#264F78",
        "table_border": "#404040",
        
        # Menus
        "menu_bg": "#2d2d2d",
        "menu_fg": "#ffffff",
        "menu_hover_bg": "#3a3a3a",
        "menu_hover_fg": "#ffffff",
        "menu_disabled_fg": "#808080",
        "menu_separator": "#404040",
        
        # Abas
        "tab_bg": "#2d2d2d",
        "tab_fg": "#ffffff",
        "tab_active_bg": "#1e1e1e",
        "tab_active_fg": "#90CAF9",
        "tab_hover_bg": "#3a3a3a",
        "tab_disabled_fg": "#808080",
        
        # Barras de rolagem
        "scrollbar_bg": "#2d2d2d",
        "scrollbar_fg": "#404040",
        "scrollbar_hover_fg": "#505050",
        
        # Diálogos
        "dialog_bg": "#2d2d2d",
        "dialog_fg": "#ffffff",
        "dialog_title_bg": "#404040",
        "dialog_button_bg": "#404040",
        
        # Progresso
        "progress_bg": "#404040",
        "progress_fg": "#90CAF9",
        "progress_text": "#ffffff",
        
        # Bordas
        "border": "#404040",
        "focus_border": "#90CAF9",
        
        # Links
        "link": "#90CAF9",
        "link_hover": "#64B5F6",
        "link_visited": "#CE93D8"
    }
} 