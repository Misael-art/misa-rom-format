#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Modelo de Configuração
Implementa validação de configuração usando Pydantic
"""

import json
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator

class AppConfigModel(BaseModel):
    """
    Modelo de configuração da aplicação com validação.
    
    Utiliza Pydantic para validar os valores de configuração e garantir
    que estejam dentro dos limites esperados.
    """
    # Configurações de interface
    theme: Literal["light", "dark"] = "light"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    max_log_size_mb: int = Field(10, gt=0, le=100)
    database_path: Path = Path("data/database.db")
    
    # Configurações adicionais
    show_welcome: bool = True
    show_navigation: bool = True
    window_size: str = "1024x768"
    recent_databases: List[str] = []
    max_recent_databases: int = Field(10, gt=0, le=50)
    last_import_dir: str = ""
    last_roms_dir: str = ""
    
    @validator('database_path')
    def validate_db_path(cls, v: Path) -> Path:
        """
        Valida e cria o diretório do banco de dados se não existir.
        
        Args:
            v: Caminho do banco de dados
            
        Returns:
            Caminho validado
        """
        v.parent.mkdir(exist_ok=True, parents=True)
        return v
    
    @validator('window_size')
    def validate_window_size(cls, v: str) -> str:
        """
        Valida o formato do tamanho da janela.
        
        Args:
            v: Tamanho da janela no formato 'WIDTHxHEIGHT'
            
        Returns:
            Tamanho validado
        """
        if not v or 'x' not in v:
            return "1024x768"
        
        try:
            width, height = map(int, v.lower().split('x'))
            if width < 800 or height < 600:
                return "800x600"
            return f"{width}x{height}"
        except ValueError:
            return "1024x768"

class ConfigManager:
    """
    Gerenciador de configuração com validação.
    
    Utiliza o modelo Pydantic para validar as configurações e garantir
    que estejam dentro dos limites esperados.
    """
    
    def __init__(self, config_file: Path = Path("config.json")):
        """
        Inicializa o gerenciador de configuração.
        
        Args:
            config_file: Caminho para o arquivo de configuração
        """
        self.config_file = config_file
        self._config: Optional[AppConfigModel] = None
        
    def load(self) -> AppConfigModel:
        """
        Carrega as configurações do arquivo.
        
        Se o arquivo não existir, cria um novo com valores padrão.
        
        Returns:
            Modelo de configuração validado
        """
        if not self.config_file.exists():
            self._config = AppConfigModel()
            self.save()
            return self._config
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._config = AppConfigModel(**data)
            return self._config
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Aviso: Erro ao carregar configuração ({e}). Usando configuração padrão.")
            self._config = AppConfigModel()
            return self._config
        except Exception as e:
            print(f"Erro inesperado ao carregar configuração: {e}. Usando configuração padrão.")
            self._config = AppConfigModel()
            return self._config
        
    def save(self) -> None:
        """
        Salva as configurações no arquivo.
        
        Raises:
            ValueError: Se as configurações não foram carregadas
        """
        if self._config is None:
            raise ValueError("Config not loaded")
            
        # Garante que o diretório existe
        self.config_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config.dict(), f, indent=4)
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém um valor da configuração.
        
        Args:
            key: Nome da configuração
            default: Valor padrão caso a configuração não exista
            
        Returns:
            Valor da configuração ou valor padrão
        """
        if self._config is None:
            self.load()
        
        return getattr(self._config, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Define um valor na configuração.
        
        Args:
            key: Nome da configuração
            value: Valor a ser definido
            
        Raises:
            AttributeError: Se a configuração não existir no modelo
        """
        if self._config is None:
            self.load()
            
        if not hasattr(self._config, key):
            raise AttributeError(f"Configuração '{key}' não existe no modelo")
            
        setattr(self._config, key, value)
        self.save()