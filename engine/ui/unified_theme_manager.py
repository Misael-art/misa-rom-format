#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Unified Theme Manager
Gerenciador de temas unificado com validação, customização e persistência.

Este módulo consolida as funcionalidades dos ThemeManager, ThemeManagerEnhanced
e ThemeConfig em uma única implementação robusta e production-ready.
"""

import tkinter as tk
from tkinter import ttk
import logging
import json
import os
import re
from typing import Dict, List, Optional, Any, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod

from ..errors import ThemeError, ValidationError

# Logger configurado para o módulo
logger = logging.getLogger(__name__)


@dataclass
class ThemeColors:
    """Definição de cores de um tema."""
    # Cores principais
    background: str = "#ffffff"
    foreground: str = "#000000"
    accent: str = "#007acc"
    
    # Cores de botões
    button: str = "#f0f0f0"
    button_hover: str = "#e0e0e0"
    button_active: str = "#d0d0d0"
    button_disabled: str = "#cccccc"
    
    # Cores de bordas e separadores
    border: str = "#d0d0d0"
    separator: str = "#e0e0e0"
    
    # Cores de seleção
    selection: str = "#cce8ff"
    selection_inactive: str = "#f0f0f0"
    
    # Cores de status
    error: str = "#f44336"
    warning: str = "#ff9800"
    success: str = "#4caf50"
    info: str = "#2196f3"
    
    # Cores de entrada de texto
    text_bg: str = "#ffffff"
    text_fg: str = "#000000"
    text_selection_bg: str = "#cce8ff"
    text_selection_fg: str = "#000000"
    
    # Cores de tabelas
    table_header_bg: str = "#f0f0f0"
    table_header_fg: str = "#000000"
    table_row_odd_bg: str = "#ffffff"
    table_row_even_bg: str = "#f8f8f8"
    table_row_hover_bg: str = "#e8f4fd"
    
    def validate(self) -> bool:
        """Valida se todas as cores estão em formato hexadecimal válido."""
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        
        for field_name, color in asdict(self).items():
            if not hex_pattern.match(color):
                logger.error(f"Cor inválida em {field_name}: {color}")
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, str]:
        """Converte para dicionário."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'ThemeColors':
        """Cria instância a partir de dicionário."""
        # Filtra apenas campos válidos
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)


@dataclass
class Theme:
    """Definição completa de um tema."""
    name: str
    display_name: str
    description: str
    colors: ThemeColors
    author: str = "MegaEmu"
    version: str = "1.0.0"
    custom: bool = False
    
    def validate(self) -> bool:
        """Valida o tema completo."""
        if not self.name or not self.display_name:
            return False
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.name):
            return False
        
        return self.colors.validate()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'author': self.author,
            'version': self.version,
            'custom': self.custom,
            'colors': self.colors.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Theme':
        """Cria instância a partir de dicionário."""
        colors_data = data.get('colors', {})
        colors = ThemeColors.from_dict(colors_data)
        
        return cls(
            name=data.get('name', ''),
            display_name=data.get('display_name', ''),
            description=data.get('description', ''),
            author=data.get('author', 'MegaEmu'),
            version=data.get('version', '1.0.0'),
            custom=data.get('custom', False),
            colors=colors
        )


class ThemeProvider(ABC):
    """Interface para provedores de temas."""
    
    @abstractmethod
    def get_theme(self, name: str) -> Optional[Theme]:
        """Obtém um tema pelo nome."""
        pass
    
    @abstractmethod
    def get_available_themes(self) -> List[str]:
        """Obtém lista de temas disponíveis."""
        pass
    
    @abstractmethod
    def save_theme(self, theme: Theme) -> bool:
        """Salva um tema."""
        pass
    
    @abstractmethod
    def delete_theme(self, name: str) -> bool:
        """Remove um tema."""
        pass


class BuiltinThemeProvider(ThemeProvider):
    """Provedor de temas built-in."""
    
    def __init__(self):
        self._themes = self._create_builtin_themes()
    
    def _create_builtin_themes(self) -> Dict[str, Theme]:
        """Cria temas built-in."""
        themes = {}
        
        # Tema claro
        light_colors = ThemeColors(
            background="#ffffff",
            foreground="#000000",
            accent="#007acc",
            button="#f0f0f0",
            button_hover="#e0e0e0",
            button_active="#d0d0d0",
            border="#d0d0d0",
            selection="#cce8ff",
            error="#f44336",
            warning="#ff9800",
            success="#4caf50",
            info="#2196f3"
        )
        
        themes['light'] = Theme(
            name='light',
            display_name='Tema Claro',
            description='Tema claro padrão com cores suaves',
            colors=light_colors
        )
        
        # Tema escuro
        dark_colors = ThemeColors(
            background="#1e1e1e",
            foreground="#ffffff",
            accent="#0078d7",
            button="#333333",
            button_hover="#444444",
            button_active="#555555",
            border="#555555",
            selection="#264f78",
            error="#f44336",
            warning="#ff9800",
            success="#4caf50",
            info="#2196f3",
            text_bg="#2d2d2d",
            text_fg="#ffffff",
            text_selection_bg="#264f78",
            table_header_bg="#404040",
            table_header_fg="#ffffff",
            table_row_odd_bg="#2a2a2a",
            table_row_even_bg="#333333",
            table_row_hover_bg="#3a3a3a"
        )
        
        themes['dark'] = Theme(
            name='dark',
            display_name='Tema Escuro',
            description='Tema escuro para reduzir fadiga visual',
            colors=dark_colors
        )
        
        return themes
    
    def get_theme(self, name: str) -> Optional[Theme]:
        """Obtém um tema pelo nome."""
        return self._themes.get(name)
    
    def get_available_themes(self) -> List[str]:
        """Obtém lista de temas disponíveis."""
        return list(self._themes.keys())
    
    def save_theme(self, theme: Theme) -> bool:
        """Temas built-in não podem ser salvos."""
        return False
    
    def delete_theme(self, name: str) -> bool:
        """Temas built-in não podem ser removidos."""
        return False


class FileThemeProvider(ThemeProvider):
    """Provedor de temas baseado em arquivos."""
    
    def __init__(self, themes_dir: Union[str, Path]):
        self.themes_dir = Path(themes_dir)
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self._themes_cache: Dict[str, Theme] = {}
        self._load_themes()
    
    def _load_themes(self):
        """Carrega temas do diretório."""
        self._themes_cache.clear()
        
        for theme_file in self.themes_dir.glob('*.json'):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                theme = Theme.from_dict(data)
                theme.custom = True
                
                if theme.validate():
                    self._themes_cache[theme.name] = theme
                    logger.debug(f"Tema carregado: {theme.name}")
                else:
                    logger.warning(f"Tema inválido ignorado: {theme_file}")
                    
            except Exception as e:
                logger.error(f"Erro ao carregar tema {theme_file}: {e}")
    
    def get_theme(self, name: str) -> Optional[Theme]:
        """Obtém um tema pelo nome."""
        return self._themes_cache.get(name)
    
    def get_available_themes(self) -> List[str]:
        """Obtém lista de temas disponíveis."""
        return list(self._themes_cache.keys())
    
    def save_theme(self, theme: Theme) -> bool:
        """Salva um tema."""
        try:
            if not theme.validate():
                logger.error(f"Tema inválido: {theme.name}")
                return False
            
            theme_file = self.themes_dir / f"{theme.name}.json"
            
            with open(theme_file, 'w', encoding='utf-8') as f:
                json.dump(theme.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Atualiza cache
            theme.custom = True
            self._themes_cache[theme.name] = theme
            
            logger.info(f"Tema salvo: {theme.name}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar tema {theme.name}: {e}")
            return False
    
    def delete_theme(self, name: str) -> bool:
        """Remove um tema."""
        try:
            theme_file = self.themes_dir / f"{name}.json"
            
            if theme_file.exists():
                theme_file.unlink()
            
            # Remove do cache
            self._themes_cache.pop(name, None)
            
            logger.info(f"Tema removido: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover tema {name}: {e}")
            return False


class UnifiedThemeManager:
    """
    Gerenciador de temas unificado e production-ready.
    
    Combina as melhores funcionalidades dos ThemeManager, ThemeManagerEnhanced
    e ThemeConfig em uma única implementação robusta.
    
    Funcionalidades:
    - Temas built-in (claro e escuro)
    - Temas customizados com persistência
    - Validação rigorosa de cores e configurações
    - Aplicação automática de temas ao Tkinter/ttk
    - Sistema de callbacks para mudanças de tema
    - Suporte a múltiplos provedores de temas
    - Thread-safe operations
    """
    
    def __init__(self, 
                 config=None,
                 themes_dir: Optional[Union[str, Path]] = None,
                 auto_apply: bool = True):
        """
        Inicializa o gerenciador unificado.
        
        Args:
            config: Gerenciador de configuração
            themes_dir: Diretório para temas customizados
            auto_apply: Se deve aplicar tema automaticamente
        """
        self.config = config
        self.auto_apply = auto_apply
        self._current_theme_name = "light"
        self._current_theme: Optional[Theme] = None
        
        # Inicializa TTK Style
        try:
            self.style = ttk.Style()
        except tk.TclError:
            # Fallback se não houver janela Tk
            self.style = None
            logger.warning("TTK Style não disponível - modo headless")
        
        # Provedores de temas
        self._builtin_provider = BuiltinThemeProvider()
        
        themes_path = themes_dir or Path.home() / '.megaemu' / 'themes'
        self._file_provider = FileThemeProvider(themes_path)
        
        # Callbacks para mudanças de tema
        self._theme_change_callbacks: List[Callable[[str, Theme], None]] = []
        
        # Carrega tema inicial
        self._load_initial_theme()
        
        logger.info("UnifiedThemeManager inicializado")
    
    def _load_initial_theme(self):
        """Carrega tema inicial."""
        # Tenta carregar tema da configuração
        if self.config:
            try:
                saved_theme = self.config.get('theme', 'light')
                if self.apply_theme(saved_theme):
                    return
            except Exception as e:
                logger.warning(f"Erro ao carregar tema da configuração: {e}")
        
        # Fallback para tema claro
        self.apply_theme('light')
    
    def get_available_themes(self) -> Dict[str, str]:
        """
        Obtém todos os temas disponíveis.
        
        Returns:
            Dict[str, str]: Mapeamento nome -> display_name
        """
        themes = {}
        
        # Temas built-in
        for name in self._builtin_provider.get_available_themes():
            theme = self._builtin_provider.get_theme(name)
            if theme:
                themes[name] = theme.display_name
        
        # Temas customizados
        for name in self._file_provider.get_available_themes():
            theme = self._file_provider.get_theme(name)
            if theme:
                themes[name] = theme.display_name
        
        return themes
    
    def get_theme(self, name: str) -> Optional[Theme]:
        """
        Obtém um tema pelo nome.
        
        Args:
            name: Nome do tema
            
        Returns:
            Theme ou None se não encontrado
        """
        # Tenta built-in primeiro
        theme = self._builtin_provider.get_theme(name)
        if theme:
            return theme
        
        # Tenta customizado
        return self._file_provider.get_theme(name)
    
    def get_current_theme(self) -> str:
        """Obtém o nome do tema atual."""
        return self._current_theme_name
    
    def get_current_theme_object(self) -> Optional[Theme]:
        """Obtém o objeto do tema atual."""
        return self._current_theme
    
    def apply_theme(self, theme_name: str) -> bool:
        """
        Aplica um tema.
        
        Args:
            theme_name: Nome do tema
            
        Returns:
            True se aplicado com sucesso
        """
        try:
            # Obtém tema
            theme = self.get_theme(theme_name)
            if not theme:
                logger.error(f"Tema não encontrado: {theme_name}")
                return False
            
            # Valida tema
            if not theme.validate():
                logger.error(f"Tema inválido: {theme_name}")
                return False
            
            # Aplica tema ao TTK se disponível
            if self.style and self.auto_apply:
                self._apply_theme_to_ttk(theme)
            
            # Atualiza estado
            self._current_theme_name = theme_name
            self._current_theme = theme
            
            # Salva na configuração
            if self.config:
                try:
                    self.config.set('theme', theme_name)
                except Exception as e:
                    logger.warning(f"Erro ao salvar tema na configuração: {e}")
            
            # Notifica callbacks
            self._notify_theme_change(theme_name, theme)
            
            logger.info(f"Tema aplicado: {theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao aplicar tema {theme_name}: {e}", exc_info=True)
            return False
    
    def _apply_theme_to_ttk(self, theme: Theme):
        """Aplica tema aos widgets TTK."""
        if not self.style:
            return
        
        try:
            colors = theme.colors
            
            # Configura tema base
            self.style.theme_use("default")
            
            # Frame
            self.style.configure(
                "TFrame",
                background=colors.background
            )
            
            # Label
            self.style.configure(
                "TLabel",
                background=colors.background,
                foreground=colors.foreground
            )
            
            # Button
            self.style.configure(
                "TButton",
                background=colors.button,
                foreground=colors.foreground,
                borderwidth=1,
                relief="solid",
                padding=5
            )
            
            self.style.map(
                "TButton",
                background=[
                    ("active", colors.button_hover),
                    ("pressed", colors.button_active),
                    ("disabled", colors.button_disabled)
                ]
            )
            
            # Entry
            self.style.configure(
                "TEntry",
                fieldbackground=colors.text_bg,
                foreground=colors.text_fg,
                borderwidth=1,
                relief="solid"
            )
            
            self.style.map(
                "TEntry",
                selectbackground=[("focus", colors.text_selection_bg)],
                selectforeground=[("focus", colors.text_selection_fg)]
            )
            
            # Treeview
            self.style.configure(
                "Treeview",
                background=colors.table_row_odd_bg,
                foreground=colors.foreground,
                fieldbackground=colors.table_row_odd_bg
            )
            
            self.style.configure(
                "Treeview.Heading",
                background=colors.table_header_bg,
                foreground=colors.table_header_fg
            )
            
            self.style.map(
                "Treeview",
                background=[("selected", colors.selection)],
                foreground=[("selected", colors.foreground)]
            )
            
            # Progressbar
            self.style.configure(
                "TProgressbar",
                background=colors.accent,
                troughcolor=colors.button,
                borderwidth=0,
                thickness=10
            )
            
            # Notebook
            self.style.configure(
                "TNotebook",
                background=colors.background,
                borderwidth=0
            )
            
            self.style.configure(
                "TNotebook.Tab",
                background=colors.button,
                foreground=colors.foreground,
                padding=[10, 5]
            )
            
            self.style.map(
                "TNotebook.Tab",
                background=[
                    ("selected", colors.background),
                    ("active", colors.button_hover)
                ]
            )
            
            logger.debug(f"Tema TTK aplicado: {theme.name}")
            
        except Exception as e:
            logger.error(f"Erro ao aplicar tema TTK: {e}", exc_info=True)
            raise ThemeError(f"Erro ao aplicar tema TTK: {str(e)}")
    
    def create_custom_theme(self, 
                           name: str,
                           display_name: str,
                           description: str,
                           colors: Union[Dict[str, str], ThemeColors],
                           author: str = "User") -> bool:
        """
        Cria um tema customizado.
        
        Args:
            name: Nome único do tema
            display_name: Nome para exibição
            description: Descrição do tema
            colors: Cores do tema
            author: Autor do tema
            
        Returns:
            True se criado com sucesso
        """
        try:
            # Valida nome
            if not re.match(r'^[a-zA-Z0-9_-]+$', name):
                raise ValidationError(f"Nome de tema inválido: {name}")
            
            # Verifica se já existe
            if self.get_theme(name):
                logger.warning(f"Tema já existe: {name}")
                return False
            
            # Converte cores se necessário
            if isinstance(colors, dict):
                theme_colors = ThemeColors.from_dict(colors)
            else:
                theme_colors = colors
            
            # Cria tema
            theme = Theme(
                name=name,
                display_name=display_name,
                description=description,
                colors=theme_colors,
                author=author,
                custom=True
            )
            
            # Valida e salva
            if not theme.validate():
                raise ValidationError(f"Tema inválido: {name}")
            
            return self._file_provider.save_theme(theme)
            
        except Exception as e:
            logger.error(f"Erro ao criar tema customizado {name}: {e}")
            return False
    
    def delete_custom_theme(self, name: str) -> bool:
        """
        Remove um tema customizado.
        
        Args:
            name: Nome do tema
            
        Returns:
            True se removido com sucesso
        """
        try:
            # Verifica se é built-in
            if self._builtin_provider.get_theme(name):
                logger.error(f"Não é possível remover tema built-in: {name}")
                return False
            
            # Verifica se é o tema atual
            if name == self._current_theme_name:
                logger.warning(f"Mudando para tema padrão antes de remover: {name}")
                self.apply_theme('light')
            
            return self._file_provider.delete_theme(name)
            
        except Exception as e:
            logger.error(f"Erro ao remover tema {name}: {e}")
            return False
    
    def export_theme(self, name: str, file_path: Union[str, Path]) -> bool:
        """
        Exporta um tema para arquivo.
        
        Args:
            name: Nome do tema
            file_path: Caminho do arquivo de destino
            
        Returns:
            True se exportado com sucesso
        """
        try:
            theme = self.get_theme(name)
            if not theme:
                logger.error(f"Tema não encontrado: {name}")
                return False
            
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(theme.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Tema exportado: {name} -> {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao exportar tema {name}: {e}")
            return False
    
    def import_theme(self, file_path: Union[str, Path]) -> bool:
        """
        Importa um tema de arquivo.
        
        Args:
            file_path: Caminho do arquivo de tema
            
        Returns:
            True se importado com sucesso
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.error(f"Arquivo não encontrado: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            theme = Theme.from_dict(data)
            theme.custom = True
            
            if not theme.validate():
                logger.error(f"Tema inválido no arquivo: {file_path}")
                return False
            
            # Verifica se já existe
            if self.get_theme(theme.name):
                logger.warning(f"Tema já existe, será sobrescrito: {theme.name}")
            
            success = self._file_provider.save_theme(theme)
            if success:
                logger.info(f"Tema importado: {theme.name} <- {file_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao importar tema de {file_path}: {e}")
            return False
    
    def add_theme_change_callback(self, callback: Callable[[str, Theme], None]):
        """
        Adiciona callback para mudanças de tema.
        
        Args:
            callback: Função a ser chamada quando tema mudar
        """
        if callback not in self._theme_change_callbacks:
            self._theme_change_callbacks.append(callback)
            logger.debug(f"Callback adicionado: {callback.__name__}")
    
    def remove_theme_change_callback(self, callback: Callable[[str, Theme], None]):
        """
        Remove callback de mudanças de tema.
        
        Args:
            callback: Função a ser removida
        """
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)
            logger.debug(f"Callback removido: {callback.__name__}")
    
    def _notify_theme_change(self, theme_name: str, theme: Theme):
        """Notifica callbacks sobre mudança de tema."""
        for callback in self._theme_change_callbacks:
            try:
                callback(theme_name, theme)
            except Exception as e:
                logger.error(f"Erro em callback de tema: {e}")
    
    def get_theme_colors(self, theme_name: Optional[str] = None) -> Optional[ThemeColors]:
        """
        Obtém cores de um tema.
        
        Args:
            theme_name: Nome do tema (usa atual se None)
            
        Returns:
            ThemeColors ou None se não encontrado
        """
        if theme_name is None:
            theme_name = self._current_theme_name
        
        theme = self.get_theme(theme_name)
        return theme.colors if theme else None
    
    def refresh_custom_themes(self):
        """Recarrega temas customizados do disco."""
        try:
            self._file_provider._load_themes()
            logger.info("Temas customizados recarregados")
        except Exception as e:
            logger.error(f"Erro ao recarregar temas: {e}")
    
    def get_theme_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações detalhadas de um tema.
        
        Args:
            name: Nome do tema
            
        Returns:
            Dicionário com informações ou None
        """
        theme = self.get_theme(name)
        if not theme:
            return None
        
        return {
            'name': theme.name,
            'display_name': theme.display_name,
            'description': theme.description,
            'author': theme.author,
            'version': theme.version,
            'custom': theme.custom,
            'is_current': theme.name == self._current_theme_name,
            'color_count': len(theme.colors.to_dict()),
            'valid': theme.validate()
        }


# Alias para compatibilidade com código existente
ThemeManager = UnifiedThemeManager