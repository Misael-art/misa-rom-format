#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Container de Injeção de Dependência
Implementa um container para gerenciar as dependências da aplicação
"""

from dependency_injector import containers, providers
from pathlib import Path
import os

from .config.config_manager import AppConfigManager, ThemeConfigManager
from .db import DatabaseManager
from .ui.theme_manager_enhanced import ThemeManager

class CoreContainer(containers.DeclarativeContainer):
    """
    Container principal da aplicação.
    
    Gerencia as dependências principais da aplicação usando injeção de dependência.
    """
    # Configuração do container
    config = providers.Singleton(
        AppConfigManager,
        config_file=Path("config.json")
    )
    
    # Gerenciadores de tema
    light_theme_config = providers.Singleton(
        ThemeConfigManager,
        theme_type="light",
        themes_dir=Path("themes")
    )
    
    dark_theme_config = providers.Singleton(
        ThemeConfigManager,
        theme_type="dark",
        themes_dir=Path("themes")
    )
    
    # Gerenciador de banco de dados
    db_manager = providers.Singleton(
        DatabaseManager,
        config=config
    )
    
    # Gerenciador de temas
    theme_manager = providers.Singleton(
        ThemeManager,
        config=config
    )