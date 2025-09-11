#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - App Config
Gerencia configurações da aplicação
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class AppConfig:
    """Gerenciador de configurações do aplicativo."""
    
    # Constantes da aplicação
    APP_NAME = "MegaEmu DataBase ROMs"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Sistema para gerenciamento de ROMs de jogos"
    APP_AUTHOR = "Seu Nome"
    APP_LICENSE = "MIT"
    
    def __init__(self, config_file: str = None):
        """
        Inicializa o gerenciador de configurações.
        
        Args:
            config_file: Caminho do arquivo de configuração
        """
        if not config_file:
            # Define caminho padrão
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
            config_file = os.path.join(config_dir, "app_config.json")
            
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Carrega as configurações do arquivo.
        
        Returns:
            Dicionário com as configurações
        """
        try:
            # Verifica se arquivo existe
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            
            # Retorna configurações padrão
            return self._get_default_config()
            
        except Exception as e:
            logging.error(f"Erro ao carregar configurações: {str(e)}", exc_info=True)
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Retorna configurações padrão.
        
        Returns:
            Dicionário com configurações padrão
        """
        return {
            # Interface
            "theme": "light",
            "show_welcome": True,
            "show_navigation": True,
            "window_size": "1024x768",
            "recent_databases": [],
            "max_recent_databases": 10,
            "last_import_dir": "",
            "last_roms_dir": "",
            
            # Logging
            "log_level": "INFO",
            "log_format": "%(asctime)s [%(levelname)s] %(message)s",
            
            # Banco de dados
            "db_timeout": 30,
            "db_max_connections": 5,
            
            # Interface
            "ui_padding": 5,
            "ui_font_family": "Segoe UI",
            "ui_font_size": 10,
            
            # Importação
            "import_batch_size": 1000,
            "import_supported_formats": {
                "dat": ["dat", "xml"],
                "ini": ["ini", "txt"],
                "csv": ["csv"]
            },
            
            # Verificação
            "verify_chunk_size": 8192,
            "verify_max_workers": 4,
            
            # Cache
            "cache_enabled": True,
            "cache_max_size": 1000,
            "cache_ttl": 3600,
            
            # Backup
            "backup_enabled": True,
            "backup_interval": 86400,
            "backup_max_files": 5,
            
            # Rede
            "network_timeout": 30,
            "network_max_retries": 3,
            
            # Segurança
            "security_hash_algorithm": "sha1",
            "security_salt_size": 16,
            
            # Performance
            "performance_max_memory": 1024 * 1024 * 1024,
            "performance_cleanup_interval": 300,
            
            # Debug
            "debug_enabled": False,
            "debug_log_sql": False,
            "debug_profile": False
        }
    
    def save(self) -> bool:
        """
        Salva as configurações no arquivo.
        
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        try:
            # Cria diretório se não existir
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Salva arquivo
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            
            return True
            
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {str(e)}", exc_info=True)
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de uma configuração.
        
        Args:
            key: Chave da configuração
            default: Valor padrão caso não exista
            
        Returns:
            Valor da configuração ou valor padrão
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Define valor de uma configuração.
        
        Args:
            key: Chave da configuração
            value: Valor a ser definido
        """
        self.config[key] = value
    
    def add_recent_database(self, db_path: str):
        """
        Adiciona banco de dados à lista de recentes.
        
        Args:
            db_path: Caminho do banco de dados
        """
        try:
            # Obtém lista atual
            recent = self.get("recent_databases", [])
            max_recent = self.get("max_recent_databases", 10)
            
            # Remove se já existe
            if db_path in recent:
                recent.remove(db_path)
            
            # Adiciona no início
            recent.insert(0, db_path)
            
            # Limita tamanho
            if len(recent) > max_recent:
                recent = recent[:max_recent]
            
            # Atualiza e salva
            self.set("recent_databases", recent)
            
        except Exception as e:
            logging.error(f"Erro ao adicionar banco recente: {str(e)}", exc_info=True)
    
    def get_app_info(self) -> Dict[str, str]:
        """
        Retorna informações básicas do aplicativo.
        
        Returns:
            Dicionário com informações do aplicativo
        """
        return {
            "app_name": "MegaEmu DataBase ROMs",
            "app_version": "1.0.0",
            "description": "Sistema para gerenciamento de ROMs de jogos",
            "author": "Seu Nome",
            "license": "MIT",
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def get_theme_colors(self, theme: str = "light") -> Dict[str, str]:
        """
        Retorna cores do tema.
        
        Args:
            theme: Nome do tema (light ou dark)
            
        Returns:
            Dicionário com cores
        """
        if theme == "dark":
            return {
                "background": "#2d2d2d",
                "foreground": "#ffffff",
                "accent": "#007acc",
                "button": "#3d3d3d",
                "button_hover": "#4d4d4d",
                "border": "#1d1d1d",
                "selection": "#264f78",
                "error": "#f44336",
                "warning": "#ff9800",
                "success": "#4caf50"
            }
        else:
            return {
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
    
    def validate_value(self, key: str, value: Any) -> tuple[bool, str]:
        """
        Valida um valor de configuração.
        
        Args:
            key: Chave da configuração
            value: Valor a validar
        
        Returns:
            tuple: (válido, mensagem de erro)
        """
        if key not in self.CONFIG_VALIDATION:
            return True, ""
            
        validation = self.CONFIG_VALIDATION[key]
        
        # Valida tipo
        if isinstance(validation["type"], list):
            valid_type = any(isinstance(value, t) for t in validation["type"])
        else:
            valid_type = isinstance(value, validation["type"])
            
        if not valid_type:
            return False, f"Tipo inválido para {key}"
        
        # Valida valores permitidos
        if "values" in validation and value not in validation["values"]:
            return False, f"Valor inválido para {key}"
        
        # Valida padrão
        if "pattern" in validation and isinstance(value, str):
            if not re.match(validation["pattern"], value):
                return False, f"Formato inválido para {key}"
        
        # Valida campos obrigatórios
        if "required_fields" in validation and isinstance(value, str):
            for field in validation["required_fields"]:
                if field not in value:
                    return False, f"Campo obrigatório ausente em {key}: {field}"
        
        # Valida limites numéricos
        if isinstance(value, (int, float)):
            if "min" in validation and value < validation["min"]:
                return False, f"Valor muito baixo para {key}"
            if "max" in validation and value > validation["max"]:
                return False, f"Valor muito alto para {key}"
        
        # Valida listas
        if isinstance(value, list):
            if "max_length" in validation and len(value) > validation["max_length"]:
                return False, f"Lista muito longa para {key}"
            if "element_type" in validation:
                for item in value:
                    if not isinstance(item, validation["element_type"]):
                        return False, f"Tipo de elemento inválido em {key}"
                    if "pattern" in validation and isinstance(item, str):
                        if not re.match(validation["pattern"], item):
                            return False, f"Formato de elemento inválido em {key}"
        
        return True, ""
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, str]:
        """
        Valida todas as configurações.
        
        Args:
            config: Configurações para validar
        
        Returns:
            Dict[str, str]: Erros encontrados
        """
        errors = {}
        
        for key, value in config.items():
            valid, message = self.validate_value(key, value)
            if not valid:
                errors[key] = message
        
        return errors
    
    def load_config(self) -> bool:
        """
        Carrega configurações do arquivo.
        
        Returns:
            bool: True se carregado com sucesso
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    
                    # Verifica versão
                    if "config_version" not in saved_config:
                        logger.warning("Arquivo de configuração sem versão")
                        saved_config["config_version"] = "0.0.0"
                    
                    # Valida configurações
                    errors = self.validate_config(saved_config)
                    if errors:
                        for key, error in errors.items():
                            logger.warning(f"Configuração inválida - {key}: {error}")
                            # Remove configuração inválida
                            saved_config.pop(key)
                    
                    # Atualiza configurações
                    self.config.update(saved_config)
                    
                    # Atualiza versão se necessário
                    if saved_config["config_version"] != self.CONFIG_VERSION:
                        logger.info(f"Atualizando versão do arquivo de configuração de {saved_config['config_version']} para {self.CONFIG_VERSION}")
                        self.config["config_version"] = self.CONFIG_VERSION
                        self.save_config()
                
                return True
            
            # Cria arquivo com configurações padrão
            return self.save_config()
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {str(e)}")
            return False
    
    def save_config(self) -> bool:
        """
        Salva configurações no arquivo.
        
        Returns:
            bool: True se salvo com sucesso
        """
        try:
            # Valida antes de salvar
            errors = self.validate_config(self.config)
            if errors:
                for key, error in errors.items():
                    logger.error(f"Configuração inválida - {key}: {error}")
                return False
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True)
            
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {str(e)}")
            return False
    
    def clear_recent_databases(self):
        """Limpa lista de bancos recentes."""
        self.set("recent_databases", [])
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """
        Retorna configurações de logging.
        
        Returns:
            Dicionário com configurações
        """
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': self.get('log_format', '%(asctime)s [%(levelname)s] %(message)s')
                },
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO',
                    'formatter': 'standard',
                    'stream': 'ext://sys.stdout'
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'detailed',
                    'filename': self.get('log_file', 'megaemu.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5,
                    'encoding': 'utf8'
                }
            },
            'loggers': {
                '': {  # root logger
                    'handlers': ['console', 'file'],
                    'level': self.get('log_level', 'INFO'),
                    'propagate': True
                }
            }
        }
    
    @property
    def import_config(self) -> Dict[str, Any]:
        """
        Retorna configurações de importação.
        
        Returns:
            Dicionário com configurações
        """
        return {
            'batch_size': self.get('import_batch_size', 1000),
            'supported_formats': self.get('import_supported_formats', ['.dat', '.xml']),
            'max_workers': self.get('verify_max_workers', 4),
            'chunk_size': self.get('verify_chunk_size', 100),
            'timeout': self.get('network_timeout', 30)
        }
    
    @property
    def database_config(self) -> Dict[str, Any]:
        """
        Retorna configurações do banco de dados.
        
        Returns:
            Dicionário com configurações
        """
        return {
            'timeout': self.get('network_timeout', 30),
            'max_connections': 5,
            'backup': {
                'enabled': self.get('backup_enabled', True),
                'interval': self.get('backup_interval', 86400),  # 24h
                'max_files': self.get('backup_max_files', 5)
            },
            'verify': {
                'chunk_size': self.get('verify_chunk_size', 100),
                'max_workers': self.get('verify_max_workers', 4)
            }
        } 