#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Pool Configuration
Configurações para o pool de conexões SQLite
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """Configurações para o banco de dados e pool de conexões."""
    
    db_path: str = "megaemu.db"
    max_connections: int = 10
    timeout: float = 30.0
    health_check_interval: int = 300  # segundos
    retry_attempts: int = 3
    retry_delay: float = 0.1
    enable_wal: bool = True
    cache_size: int = 10000
    mmap_size: int = 268435456  # 256MB
    
    # Configurações de performance
    synchronous: str = "NORMAL"
    temp_store: str = "memory"
    journal_size_limit: int = 67108864  # 64MB
    
    # Configurações de timeout
    busy_timeout: int = 5000  # milissegundos
    
    @classmethod
    def testing(cls) -> 'DatabaseConfig':
        """Configuração para testes."""
        return cls(
            db_path=":memory:",
            max_connections=1,
            timeout=5.0,
            retry_attempts=1
        )
    
    @classmethod
    def production(cls) -> 'DatabaseConfig':
        """Configuração para produção."""
        return cls()
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'DatabaseConfig':
        """Cria configuração a partir de dicionário."""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            'db_path': self.db_path,
            'max_connections': self.max_connections,
            'timeout': self.timeout,
            'health_check_interval': self.health_check_interval,
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'enable_wal': self.enable_wal,
            'cache_size': self.cache_size,
            'mmap_size': self.mmap_size,
            'synchronous': self.synchronous,
            'temp_store': self.temp_store,
            'journal_size_limit': self.journal_size_limit,
            'busy_timeout': self.busy_timeout
        }

@dataclass
class PoolConfig:
    """Configurações do pool de conexões."""
    
    max_connections: int = 10
    timeout: float = 30.0
    health_check_interval: int = 300  # segundos
    retry_attempts: int = 3
    retry_delay: float = 0.1
    enable_wal: bool = True
    cache_size: int = 10000
    mmap_size: int = 268435456  # 256MB
    
    # Configurações de performance
    synchronous: str = "NORMAL"
    temp_store: str = "memory"
    journal_size_limit: int = 67108864  # 64MB
    
    # Configurações de timeout
    busy_timeout: int = 5000  # milissegundos
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'PoolConfig':
        """Cria configuração a partir de dicionário."""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})
    
    @classmethod
    def default(cls) -> 'PoolConfig':
        """Retorna configuração padrão."""
        return cls()
    
    @classmethod
    def development(cls) -> 'PoolConfig':
        """Configuração para desenvolvimento."""
        return cls(
            max_connections=5,
            timeout=10.0,
            health_check_interval=60,
            retry_attempts=2,
            retry_delay=0.1
        )
    
    @classmethod
    def production(cls) -> 'PoolConfig':
        """Configuração para produção."""
        return cls(
            max_connections=20,
            timeout=30.0,
            health_check_interval=300,
            retry_attempts=5,
            retry_delay=0.5
        )
    
    @classmethod
    def testing(cls) -> 'PoolConfig':
        """Configuração para testes."""
        return cls(
            max_connections=1,
            timeout=5.0,
            health_check_interval=30,
            retry_attempts=1,
            retry_delay=0.01
        )
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            'max_connections': self.max_connections,
            'timeout': self.timeout,
            'health_check_interval': self.health_check_interval,
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'enable_wal': self.enable_wal,
            'cache_size': self.cache_size,
            'mmap_size': self.mmap_size,
            'synchronous': self.synchronous,
            'temp_store': self.temp_store,
            'journal_size_limit': self.journal_size_limit,
            'busy_timeout': self.busy_timeout
        }