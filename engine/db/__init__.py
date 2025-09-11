#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Database Module
"""

# Importa o gerenciador unificado como padrão
from .unified_database_manager import UnifiedDatabaseManager

# Mantém compatibilidade com código existente
DatabaseManager = UnifiedDatabaseManager
DatabaseManagerV2 = UnifiedDatabaseManager

# Importa implementações legadas para referência (deprecated)
from .database_manager import DatabaseManager as LegacyDatabaseManager
from .database_manager_v2 import DatabaseManagerV2 as LegacyDatabaseManagerV2
from .database_schema import (
    validate_database_structure,
    create_database_structure,
    get_database_version,
    SCHEMA_VERSION
)
from .config import DatabaseConfig
from .connection_pool import ConnectionPool, PooledConnection, PoolMetrics
from .pool_config import PoolConfig
from .metrics import MetricsCollector, MetricsReporter, QueryMetrics, DatabaseStats
from .retry_manager import RetryManager, RetryConfig, retryable, retry_operation
from .migration_manager import MigrationManager

__all__ = [
    # Database Managers (Unified)
    'UnifiedDatabaseManager',
    'DatabaseManager',  # Alias para UnifiedDatabaseManager
    'DatabaseManagerV2',  # Alias para UnifiedDatabaseManager
    
    # Legacy Managers (Deprecated)
    'LegacyDatabaseManager',
    'LegacyDatabaseManagerV2',
    
    # Configuration
    'DatabaseConfig',
    
    # Schema Management
    'validate_database_structure',
    'create_database_structure',
    'get_database_version',
    'SCHEMA_VERSION',
    
    # Connection Pool
    'ConnectionPool',
    'PoolConnection',
    'PoolMetrics',
    'PoolConfig',
    
    # Metrics
    'MetricsCollector',
    'MetricsReporter',
    'QueryMetrics',
    'DatabaseStats',
    
    # Retry System
    'RetryManager',
    'RetryConfig',
    'retryable',
    'retry_operation',

    # Migration System
    'MigrationManager',
]

# Versão do módulo
__version__ = "2.0.0"

# Instâncias globais
default_metrics_collector = MetricsCollector()
default_retry_manager = RetryManager()
