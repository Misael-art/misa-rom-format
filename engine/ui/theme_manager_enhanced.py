#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Theme Manager Enhanced
Gerenciador de temas da interface gráfica com validação Pydantic
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Optional, Any, List, Tuple
from pathlib import Path

from ..errors import ThemeError
from ..config.theme_model import ThemeModel, ThemeColorModel, create_light_theme, create_dark_theme
from ..config.config_manager import ThemeConfigManager

class ThemeManager:
    """Gerenciador de temas da interface com validação Pydantic."""
    
    def __init__(self, config=None):
        """
        Inicializa o gerenciador de temas.
        
        Args:
            config: Gerenciador de configuração
        """
        self.config = config
        self.current_theme = "light"
        self.style = ttk.Style()
        
        # Gerenciadores de temas com validação
        self.light_theme_manager = ThemeConfigManager("light", Path("themes"))
        self.dark_theme_manager = ThemeConfigManager("dark", Path("themes"))
        
        # Carrega os temas
        self._light_theme = self.light_theme_manager.get()
        self._dark_theme = self.dark_theme_manager.get()
        
        # Configura temas
        self._configure_light_theme()
        self._configure_dark_theme()
    
    def _configure_light_theme(self):
        """Configura tema claro."""
        try:
            # Obtém cores do tema
            colors = self._light_theme.colors.dict()
            
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
            # Obtém cores do tema
            colors = self._dark_theme.colors.dict()
            
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
    
    def apply_theme(self, theme_name: str) -> bool:
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
    
    def update_theme(self, theme_type: str, colors: Dict[str, str]) -> bool:
        """
        Atualiza um tema com novas cores.
        
        Args:
            theme_type: Tipo do tema ("light" ou "dark")
            colors: Dicionário com as novas cores
            
        Returns:
            True se o tema foi atualizado com sucesso
        """
        try:
            # Valida o tipo de tema
            if theme_type not in ["light", "dark"]:
                raise ThemeError(f"Tipo de tema inválido: {theme_type}")
                
            # Obtém o gerenciador de tema correto
            theme_manager = self.light_theme_manager if theme_type == "light" else self.dark_theme_manager
            
            # Atualiza o tema
            theme = theme_manager.get()
            
            # Cria um novo modelo de cores com as cores atualizadas
            updated_colors = theme.colors.dict()
            updated_colors.update(colors)
            
            # Atualiza o tema
            theme_manager.update(
                colors=ThemeColorModel(**updated_colors)
            )
            
            # Recarrega e reconfigura o tema
            if theme_type == "light":
                self._light_theme = theme_manager.get()
                self._configure_light_theme()
            else:
                self._dark_theme = theme_manager.get()
                self._configure_dark_theme()
                
            # Reaplicar o tema atual se necessário
            if self.current_theme == theme_type:
                self.apply_theme(theme_type)
                
            return True
            
        except Exception as e:
            logging.error(f"Erro ao atualizar tema: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao atualizar tema: {str(e)}")
    
    def reset_theme(self, theme_type: str) -> bool:
        """
        Restaura um tema para as configurações padrão.
        
        Args:
            theme_type: Tipo do tema ("light" ou "dark")
            
        Returns:
            True se o tema foi restaurado com sucesso
        """
        try:
            # Cria um tema padrão
            if theme_type == "light":
                default_theme = create_light_theme()
                self.light_theme_manager.update(**default_theme.dict())
                self._light_theme = self.light_theme_manager.get()
                self._configure_light_theme()
            else:
                default_theme = create_dark_theme()
                self.dark_theme_manager.update(**default_theme.dict())
                self._dark_theme = self.dark_theme_manager.get()
                self._configure_dark_theme()
                
            # Reaplicar o tema atual se necessário
            if self.current_theme == theme_type:
                self.apply_theme(theme_type)
                
            return True
            
        except Exception as e:
            logging.error(f"Erro ao restaurar tema: {str(e)}", exc_info=True)
            raise ThemeError(f"Erro ao restaurar tema: {str(e)}")
    
    def get_available_themes(self) -> List[Tuple[str, str]]:
        """
        Obtém a lista de temas disponíveis.
        
        Returns:
            Lista de tuplas (id, nome) dos temas disponíveis
        """
        return [
            ("light", self._light_theme.name),
            ("dark", self._dark_theme.name)
        ]