#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Database Configuration
Configurações centralizadas para o sistema de banco de dados
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from .pool_config import PoolConfig
from .retry_manager import RetryConfig

@dataclass
class DatabaseConfig:
    """Configuração completa do sistema de banco de dados."""
    
    # Configurações básicas
    database_path: str = "data/megaemu.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    max_backups: int = 10
    
    # Configurações do pool
    pool: PoolConfig = None
    retry: RetryConfig = None
    
    # Configurações de performance
    cache_size: int = 10000  # Número de páginas de cache
    page_size: int = 4096    # Tamanho da página
    temp_store: str = "memory"  # memory ou file
    synchronous: str = "normal"  # off, normal, full, extra
    
    # Configurações de segurança
    foreign_keys: bool = True
    secure_delete: bool = False
    auto_vacuum: bool = True
    
    # Configurações de logging
    log_queries: bool = False
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0
    
    # Configurações de monitoramento
    metrics_enabled: bool = True
    health_check_interval: int = 300  # segundos
    
    def __post_init__(self):
        """Inicializa configurações padrão se não fornecidas."""
        if self.pool is None:
            self.pool = PoolConfig.default()
        if self.retry is None:
            self.retry = RetryConfig()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DatabaseConfig':
        """Cria configuração a partir de dicionário."""
        # Processa configurações aninhadas
        pool_config = None
        retry_config = None
        
        if 'pool' in config_dict:
            pool_config = PoolConfig.from_dict(config_dict['pool'])
            del config_dict['pool']
        
        if 'retry' in config_dict:
            retry_config = RetryConfig(**config_dict['retry'])
            del config_dict['retry']
        
        config = cls(**config_dict)
        if pool_config:
            config.pool = pool_config
        if retry_config:
            config.retry = retry_config
        
        return config
    
    @classmethod
    def from_file(cls, config_path: str) -> 'DatabaseConfig':
        """Carrega configuração de arquivo JSON."""
        if not os.path.exists(config_path):
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            return cls.from_dict(config_dict)
        except Exception as e:
            raise ValueError(f"Erro ao carregar configuração: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte configuração para dicionário."""
        result = asdict(self)
        result['pool'] = asdict(self.pool) if self.pool else None
        result['retry'] = {
            'max_attempts': self.retry.max_attempts,
            'base_delay': self.retry.base_delay,
            'max_delay': self.retry.max_delay,
            'exponential_base': self.retry.exponential_base,
            'jitter': self.retry.jitter
        } if self.retry else None
        return result
    
    def save_to_file(self, config_path: str):
        """Salva configuração em arquivo JSON."""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def get_sqlite_pragmas(self) -> Dict[str, Any]:
        """Obtém pragmas SQLite baseados na configuração."""
        return {
            'cache_size': self.cache_size,
            'page_size': self.page_size,
            'temp_store': self.temp_store,
            'synchronous': self.synchronous,
            'foreign_keys': 1 if self.foreign_keys else 0,
            'secure_delete': 1 if self.secure_delete else 0,
            'auto_vacuum': 1 if self.auto_vacuum else 0,
            'journal_mode': 'WAL'  # Write-Ahead Logging para melhor performance
        }
    
    @classmethod
    def development(cls) -> 'DatabaseConfig':
        """Configuração para ambiente de desenvolvimento."""
        return cls(
            database_path="data/dev_megaemu.db",
            pool=PoolConfig.development(),
            retry=RetryConfig(max_attempts=2, base_delay=0.1),
            log_queries=True,
            log_slow_queries=True,
            slow_query_threshold=0.5
        )
    
    @classmethod
    def production(cls) -> 'DatabaseConfig':
        """Configuração para ambiente de produção."""
        return cls(
            database_path="data/megaemu.db",
            pool=PoolConfig.production(),
            retry=RetryConfig(max_attempts=5, base_delay=0.5),
            cache_size=20000,
            synchronous="normal",
            log_queries=False,
            log_slow_queries=True,
            slow_query_threshold=2.0,
            backup_enabled=True,
            backup_interval_hours=6
        )
    
    @classmethod
    def testing(cls) -> 'DatabaseConfig':
        """Configuração para ambiente de testes."""
        return cls(
            database_path=":memory:",
            pool=PoolConfig.testing(),
            retry=RetryConfig(max_attempts=1, base_delay=0.01),
            log_queries=True,
            log_slow_queries=True,
            slow_query_threshold=0.1,
            backup_enabled=False
        )

# Configurações padrão
DEFAULT_CONFIG = DatabaseConfig()
DEV_CONFIG = DatabaseConfig.development()
PROD_CONFIG = DatabaseConfig.production()
TEST_CONFIG = DatabaseConfig.testing()

# Carregador de configuração
class ConfigLoader:
    """Carregador de configurações com suporte a múltiplos ambientes."""
    
    @staticmethod
    def load_config(env: str = None, config_path: Optional[str] = None) -> DatabaseConfig:
        """Carrega configuração baseada no ambiente."""
        
        # Determina ambiente
        if env is None:
            env = os.getenv('MEGAEMU_ENV', 'development').lower()
        
        # Tenta carregar de arquivo
        if config_path and os.path.exists(config_path):
            return DatabaseConfig.from_file(config_path)
        
        # Configurações por ambiente
        configs = {
            'development': DEV_CONFIG,
            'production': PROD_CONFIG,
            'testing': TEST_CONFIG,
            'dev': DEV_CONFIG,
            'prod': PROD_CONFIG,
            'test': TEST_CONFIG
        }
        
        return configs.get(env, DEFAULT_CONFIG)
    
    @staticmethod
    def find_config_file() -> Optional[str]:
        """Procura arquivo de configuração em locais padrão."""
        search_paths = [
            'config/database.json',
            'data/database.json',
            '~/.megaemu/database.json',
            '/etc/megaemu/database.json'
        ]
        
        for path in search_paths:
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                return expanded
        
        return None

# Instância global
config = ConfigLoader.load_config()