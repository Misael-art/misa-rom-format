#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Theme Manager
Gerenciador de temas da interface gráfica
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Optional, Any
from ..errors import ThemeError

class ThemeManager:
    """Gerenciador de temas da interface."""
    
    def __init__(self, config=None):
        """
        Inicializa o gerenciador de temas.
        
        Args:
            config: Gerenciador de configuração
        """
        self.config = config
        self.current_theme = "light"
        self.style = ttk.Style()
        
        # Configura temas
        self._configure_light_theme()
        self._configure_dark_theme()
    
    def _configure_light_theme(self):
        """Configura tema claro."""
        try:
            # Cores do tema
            colors = {
                "background": "#ffffff",
                "foreground": "#000000",
                "accent": "#007acc",
                "button": "#f0f0f0",
                "button_hover": "#e0e0e0",
                "border": "#d0d0d0",
                "selection": "#cce8ff",
                "error": "#f44336",
                "warning": "#ff9800",
                "success": "#4caf50"
            }
            
            # Configura estilo ttk
            self.style.configure(
                "Light.TFrame",
                background=colors["background"]
            )
            
            self.style.configure(
                "Light.TLabel",
                background=colors["background"],
                foreground=colors["foreground"]
            )
            
            self.style.configure(
                "Light.TButton",
                background=colors["button"],
                foreground=colors["foreground"],
                borderwidth=1,
                relief="solid",
                padding=5
            )
            
            self.style.map(
                "Light.TButton",
                background=[("active", colors["button_hover"])]
            )
            
            self.style.configure(
                "Light.TEntry",
                fieldbackground=colors["background"],
                foreground=colors["foreground"],
                borderwidth=1,
                relief="solid"
            )
            
            self.style.configure(
                "Light.Treeview",
                background=colors["background"],
                foreground=colors["foreground"],
                fieldbackground=colors["background"]
            )
            
            self.style.map(
                "Light.Treeview",
                background=[("selected", colors["selection"])],
                foreground=[("selected", colors["foreground"])]
            )
            
            self.style.configure(
                "Light.TProgressbar",
                background=colors["accent"],
                troughcolor=colors["button"],
                borderwidth=0,
                thickness=10
            )
            
            # Salva cores
            self._light_colors = colors
            
        except Exception as e:
            logging.error(f"Erro ao configurar tema claro: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao configurar tema claro: {str(e)}")
    
    def _configure_dark_theme(self):
        """Configura tema escuro."""
        try:
            # Cores do tema
            colors = {
                "background": "#1e1e1e",
                "foreground": "#ffffff",
                "accent": "#0078d7",
                "button": "#333333",
                "button_hover": "#444444",
                "border": "#555555",
                "selection": "#264f78",
                "error": "#f44336",
                "warning": "#ff9800",
                "success": "#4caf50"
            }
            
            # Configura estilo ttk
            self.style.configure(
                "Dark.TFrame",
                background=colors["background"]
            )
            
            self.style.configure(
                "Dark.TLabel",
                background=colors["background"],
                foreground=colors["foreground"]
            )
            
            self.style.configure(
                "Dark.TButton",
                background=colors["button"],
                foreground=colors["foreground"],
                borderwidth=1,
                relief="solid",
                padding=5
            )
            
            self.style.map(
                "Dark.TButton",
                background=[("active", colors["button_hover"])]
            )
            
            self.style.configure(
                "Dark.TEntry",
                fieldbackground=colors["button"],
                foreground=colors["foreground"],
                borderwidth=1,
                relief="solid"
            )
            
            self.style.configure(
                "Dark.Treeview",
                background=colors["background"],
                foreground=colors["foreground"],
                fieldbackground=colors["background"]
            )
            
            self.style.map(
                "Dark.Treeview",
                background=[("selected", colors["selection"])],
                foreground=[("selected", colors["foreground"])]
            )
            
            self.style.configure(
                "Dark.TProgressbar",
                background=colors["accent"],
                troughcolor=colors["button"],
                borderwidth=0,
                thickness=10
            )
            
            # Salva cores
            self._dark_colors = colors
            
        except Exception as e:
            logging.error(f"Erro ao configurar tema escuro: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao configurar tema escuro: {str(e)}")
    
    def _apply_light_theme(self) -> None:
        """Aplica o tema claro aos widgets."""
        try:
            self.style.theme_use("default")
            
            # Aplica estilo a todos os widgets
            for widget in ["TFrame", "TLabel", "TButton", "TEntry", "Treeview", "TProgressbar"]:
                # Obtém configuração do tema light
                light_widget = f"Light.{widget}"
                
                # Aplica ao widget padrão
                widget_options = self.style.configure(light_widget) or {}
                self.style.configure(widget, **widget_options)
                
                # Aplica mapeamentos se existirem
                try:
                    widget_map = self.style.map(light_widget)
                    if widget_map:
                        self.style.map(widget, **widget_map)
                except Exception:
                    pass  # Ignora erros de mapeamento
        
        except Exception as e:
            logging.error(f"Erro ao aplicar tema claro: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao aplicar tema claro: {str(e)}")
    
    def _apply_dark_theme(self) -> None:
        """Aplica o tema escuro aos widgets."""
        try:
            self.style.theme_use("default")
            
            # Aplica estilo a todos os widgets
            for widget in ["TFrame", "TLabel", "TButton", "TEntry", "Treeview", "TProgressbar"]:
                # Obtém configuração do tema dark
                dark_widget = f"Dark.{widget}"
                
                # Aplica ao widget padrão
                widget_options = self.style.configure(dark_widget) or {}
                self.style.configure(widget, **widget_options)
                
                # Aplica mapeamentos se existirem
                try:
                    widget_map = self.style.map(dark_widget)
                    if widget_map:
                        self.style.map(widget, **widget_map)
                except Exception:
                    pass  # Ignora erros de mapeamento
        
        except Exception as e:
            logging.error(f"Erro ao aplicar tema escuro: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao aplicar tema escuro: {str(e)}")
    
    def apply_theme(self, theme_name):
        """
        Aplica um tema.
        
        Args:
            theme_name: Nome do tema ("light" ou "dark")
            
        Returns:
            True se o tema foi aplicado com sucesso
        """
        try:
            if theme_name not in ["light", "dark"]:
                theme_name = "light"
                
            self.current_theme = theme_name
            
            # Aplica tema ttk
            if theme_name == "light":
                self._apply_light_theme()
            else:
                self._apply_dark_theme()
                
            # Atualiza configuração se disponível
            if self.config and hasattr(self.config, 'set'):
                try:
                    self.config.set("theme", theme_name)
                except Exception as config_error:
                    logging.warning(f"Não foi possível salvar o tema na configuração: {str(config_error)}")
                
            logging.info(f"Tema aplicado: {theme_name}")
            return True
        except Exception as e:
            logging.error(f"Erro ao aplicar tema: {str(e)}", exc_info=True)
            return False
    
    def get_widget_style(self, widget: str) -> Dict[str, str]:
        """Obtém estilo para um widget."""
        theme_prefix = "Light" if self.current_theme == "light" else "Dark"
        widget_name = f"{theme_prefix}.{widget}"
        
        # Obtém configuração do widget
        return self.style.configure(widget_name) or {}
    
    def get_colors(self) -> Dict[str, str]:
        """Obtém cores do tema atual."""
        if self.current_theme == "light":
            return self._light_colors
        return self._dark_colors
    
    def get_color(self, name: str, default: str = "#000000") -> str:
        """Obtém uma cor específica do tema atual."""
        colors = self.get_colors()
        return colors.get(name, default)
    
    def get_current_theme(self) -> str:
        """Obtém o tema atual."""
        return self.current_theme
    
    def get_available_themes(self) -> list:
        """Obtém lista de temas disponíveis."""
        return ["light", "dark"]
    
    def set_theme(self, theme_name: str) -> bool:
        """Define o tema atual."""
        return self.apply_theme(theme_name)