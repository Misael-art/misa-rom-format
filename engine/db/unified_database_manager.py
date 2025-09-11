#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Unified Database Manager
Gerenciador de banco de dados consolidado com pool de conexões, retry automático,
monitoramento de saúde e métricas de performance.

Este módulo consolida as funcionalidades dos DatabaseManager, DatabaseManagerV2
e EnhancedDatabaseManager em uma única implementação robusta e production-ready.
"""

import os
import sqlite3
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from dataclasses import dataclass, field

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from .connection_pool import ConnectionPool, PooledConnection, PoolMetrics
from .pool_config import PoolConfig, DatabaseConfig
from .retry_manager import RetryManager, RetryConfig, retryable
from .database_schema import (
    validate_database_structure,
    create_database_structure,
    get_database_version,
    SCHEMA_VERSION
)
from ..errors import DatabaseError, ValidationError, TimeoutError

# Logger configurado para o módulo
logger = logging.getLogger(__name__)


@dataclass
class DatabaseMetrics:
    """Métricas de operações do banco de dados."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    retry_attempts: int = 0
    slow_queries_count: int = 0
    average_query_time: float = 0.0
    longest_query_time: float = 0.0
    last_operation: Optional[str] = None
    last_operation_time: Optional[datetime] = None
    connection_errors: int = 0
    timeout_errors: int = 0
    integrity_errors: int = 0
    
    def reset(self):
        """Reseta todas as métricas."""
        self.__dict__.update(DatabaseMetrics().__dict__)


@dataclass
class SystemHealth:
    """Status de saúde do sistema."""
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    available_connections: int = 0
    active_connections: int = 0
    last_check: Optional[datetime] = None
    alerts: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Verifica se o sistema está saudável."""
        return len(self.alerts) == 0


class SystemMonitor:
    """Monitor de recursos do sistema para detecção de problemas de performance."""
    
    def __init__(self):
        self.psutil_available = PSUTIL_AVAILABLE
        self.alert_thresholds = {
            'cpu_percent': 80.0,      # Alerta se CPU > 80%
            'memory_percent': 85.0,   # Alerta se memória > 85%
            'memory_mb': 1024.0,      # Alerta se uso de memória > 1GB
            'disk_usage': 90.0        # Alerta se disco > 90%
        }
    
    def get_system_health(self) -> SystemHealth:
        """Coleta métricas atuais do sistema e retorna status de saúde."""
        health = SystemHealth(last_check=datetime.now())
        
        if not self.psutil_available:
            health.alerts.append("Monitoramento psutil não disponível")
            return health
        
        try:
            # CPU
            health.cpu_percent = psutil.cpu_percent(interval=0.1)
            if health.cpu_percent > self.alert_thresholds['cpu_percent']:
                health.alerts.append(f"CPU alta: {health.cpu_percent:.1f}%")
            
            # Memória
            memory = psutil.virtual_memory()
            health.memory_percent = memory.percent
            health.memory_mb = memory.used / (1024 * 1024)
            
            if health.memory_percent > self.alert_thresholds['memory_percent']:
                health.alerts.append(f"Memória alta: {health.memory_percent:.1f}%")
            
            # Disco (onde está o banco)
            disk = psutil.disk_usage('/')
            health.disk_usage_percent = disk.percent
            if health.disk_usage_percent > self.alert_thresholds['disk_usage']:
                health.alerts.append(f"Disco cheio: {health.disk_usage_percent:.1f}%")
                
        except Exception as e:
            health.alerts.append(f"Erro ao coletar métricas: {str(e)}")
            logger.warning(f"Erro ao coletar métricas do sistema: {e}")
        
        return health


class ConnectionHealthManager:
    """Gerenciador de saúde das conexões com recovery automático."""
    
    def __init__(self, recovery_retries: int = 3):
        self.recovery_retries = recovery_retries
        self.recovery_stats = {
            'recovered_connections': 0,
            'failed_recoveries': 0,
            'total_recovery_attempts': 0
        }
    
    def check_connection_health(self, connection: sqlite3.Connection) -> Dict[str, Any]:
        """Verifica saúde de uma conexão específica."""
        health_status = {
            'healthy': True,
            'issues': [],
            'last_check': datetime.now().isoformat()
        }
        
        try:
            # Testa conexão básica
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            
            # Verifica se foreign keys estão habilitadas
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            if not fk_status:
                health_status['issues'].append("foreign_keys_disabled")
                health_status['healthy'] = False
            
            # Verifica integridade básica
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            if integrity_result != 'ok':
                health_status['issues'].append("integrity_check_failed")
                health_status['healthy'] = False
                
        except sqlite3.OperationalError as e:
            health_status['healthy'] = False
            health_status['issues'].append(f"operational_error: {str(e)}")
        except sqlite3.DatabaseError as e:
            health_status['healthy'] = False
            health_status['issues'].append(f"database_error: {str(e)}")
        except Exception as e:
            health_status['healthy'] = False
            health_status['issues'].append(f"unexpected_error: {str(e)}")
        
        return health_status
    
    def attempt_connection_recovery(self, connection: sqlite3.Connection, db_path: str) -> bool:
        """Tenta recovery automático de conexão perdida."""
        self.recovery_stats['total_recovery_attempts'] += 1
        
        for attempt in range(self.recovery_retries):
            try:
                logger.info(f"Tentativa de recovery {attempt + 1}/{self.recovery_retries} para {db_path}")
                
                # Testa conexão básica
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                
                # Reabilita configurações críticas
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA journal_mode = WAL")
                
                # Verifica se recovery funcionou
                health = self.check_connection_health(connection)
                if health['healthy']:
                    self.recovery_stats['recovered_connections'] += 1
                    logger.info(f"Conexão recuperada com sucesso após {attempt + 1} tentativas")
                    return True
                    
            except Exception as e:
                logger.warning(f"Falha na tentativa {attempt + 1}: {str(e)}")
                time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
        
        self.recovery_stats['failed_recoveries'] += 1
        logger.error(f"Falha em todas as tentativas de recovery para {db_path}")
        return False


class UnifiedDatabaseManager:
    """
    Gerenciador de banco de dados unificado e production-ready.
    
    Combina as melhores funcionalidades dos DatabaseManager, DatabaseManagerV2
    e EnhancedDatabaseManager em uma única implementação robusta.
    
    Funcionalidades:
    - Pool de conexões com configuração flexível
    - Retry automático com backoff exponencial
    - Monitoramento de saúde do sistema e conexões
    - Métricas detalhadas de performance
    - Validação e migração automática de schema
    - Context managers para transações seguras
    - Thread-safe operations
    """
    
    def __init__(self, 
                 config: Optional[Union[DatabaseConfig, Dict[str, Any]]] = None,
                 pool_config: Optional[PoolConfig] = None,
                 retry_config: Optional[RetryConfig] = None):
        """
        Inicializa o gerenciador unificado.
        
        Args:
            config: Configuração do banco de dados
            pool_config: Configuração do pool de conexões
            retry_config: Configuração de retry
        """
        # Configurações
        self.config = config
        self.pool_config = pool_config or PoolConfig()
        self.retry_config = retry_config or RetryConfig()
        
        # Estado interno
        self._current_db: Optional[str] = None
        self._connection_pool: Optional[ConnectionPool] = None
        
        # Componentes de monitoramento
        self._metrics = DatabaseMetrics()
        self._system_monitor = SystemMonitor()
        self._health_manager = ConnectionHealthManager()
        self._retry_manager = RetryManager(self.retry_config)
        
        # Locks para thread safety
        self._pool_lock = threading.RLock()
        self._metrics_lock = threading.Lock()
        
        logger.info("UnifiedDatabaseManager inicializado")
    
    @property
    def current_db(self) -> Optional[str]:
        """Retorna o banco de dados atual."""
        return self._current_db
    
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado a um banco."""
        return (self._connection_pool is not None and 
                not getattr(self._connection_pool, '_closed', False))
    
    @property
    def metrics(self) -> DatabaseMetrics:
        """Retorna métricas atuais (cópia)."""
        with self._metrics_lock:
            # Retorna uma cópia para evitar modificações externas
            return DatabaseMetrics(**self._metrics.__dict__)
    
    def get_system_health(self) -> SystemHealth:
        """Retorna status de saúde do sistema."""
        health = self._system_monitor.get_system_health()
        
        # Adiciona informações do pool de conexões
        if self._connection_pool:
            pool_metrics = self._connection_pool.get_metrics()
            health.available_connections = pool_metrics.available_connections
            health.active_connections = pool_metrics.active_connections
        
        return health
    
    def connect(self, db_path: str) -> bool:
        """
        Conecta ao banco de dados com pool de conexões.
        
        Args:
            db_path: Caminho do banco de dados
            
        Returns:
            True se conectou com sucesso
            
        Raises:
            DatabaseError: Se falhar ao conectar
        """
        try:
            # Verifica se já está conectado ao mesmo banco
            if self._current_db == db_path and self.is_connected:
                logger.debug(f"Já conectado ao banco: {db_path}")
                return True
            
            # Fecha conexão anterior
            self.close()
            
            # Verifica se o arquivo existe
            file_exists = os.path.exists(db_path)
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
            # Se arquivo não existe, cria estrutura básica
            if not file_exists:
                logger.info(f"Criando novo banco de dados: {db_path}")
                self._create_initial_database(db_path)
            
            # Cria pool de conexões
            with self._pool_lock:
                self._connection_pool = ConnectionPool(
                    db_path, 
                    max_connections=self.pool_config.max_connections,
                    timeout=self.pool_config.timeout,
                    health_check_interval=self.pool_config.health_check_interval
                )
                self._current_db = db_path
            
            # Testa conexão
            with self.get_connection() as conn:
                conn.connection.execute("SELECT 1")
            
            # Valida e migra schema se necessário
            if file_exists:
                self._validate_and_migrate_schema(db_path)
            
            logger.info(f"Conectado ao banco com pool: {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco: {e}", exc_info=True)
            self.close()
            raise DatabaseError(f"Falha ao conectar ao banco {db_path}: {str(e)}")
    
    def _create_initial_database(self, db_path: str):
        """Cria estrutura inicial do banco de dados."""
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            if not create_database_structure(conn):
                raise DatabaseError("Falha ao criar estrutura inicial do banco")
            
            conn.close()
            logger.info(f"Estrutura inicial criada para: {db_path}")
            
        except Exception as e:
            if os.path.exists(db_path):
                os.remove(db_path)
            raise DatabaseError(f"Erro ao criar banco inicial: {str(e)}")
    
    def _validate_and_migrate_schema(self, db_path: str):
        """Valida e migra schema se necessário."""
        try:
            # Importação dinâmica para evitar dependências circulares
            from ..database.schema_validator import validate_database_schema, ValidationLevel
            
            result = validate_database_schema(db_path, ValidationLevel.BASIC)
            
            if not result.is_valid:
                logger.warning(f"Schema do banco possui problemas:")
                for issue in result.issues:
                    logger.warning(f"  - {issue}")
                
                # Tenta correção automática
                try:
                    from ..database.migration_script import DatabaseMigrator
                    migrator = DatabaseMigrator()
                    if migrator.migrate_database(db_path, create_backup=True):
                        logger.info("Schema corrigido automaticamente.")
                    else:
                        logger.warning("Falha na correção automática do schema.")
                except ImportError:
                    logger.warning("Script de migração não disponível.")
            else:
                logger.info("Schema validado com sucesso.")
                
        except ImportError:
            logger.debug("Validador de schema não disponível.")
        except Exception as e:
            logger.warning(f"Erro durante validação do schema: {e}")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obter conexão do pool.
        
        Yields:
            PooledConnection: Conexão do pool
            
        Raises:
            DatabaseError: Se não estiver conectado ou falhar ao obter conexão
        """
        if not self.is_connected:
            raise DatabaseError("Não conectado a nenhum banco de dados")
        
        try:
            with self._connection_pool.get_connection() as conn:
                yield conn
        except Exception as e:
            with self._metrics_lock:
                self._metrics.connection_errors += 1
            logger.error(f"Erro ao obter conexão: {e}")
            raise DatabaseError(f"Falha ao obter conexão: {str(e)}")
    
    @retryable()
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """
        Executa uma query com retry automático.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Lista de resultados
            
        Raises:
            DatabaseError: Se falhar após todas as tentativas
        """
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.connection.execute(query, params or ())
                results = cursor.fetchall()
            
            # Atualiza métricas de sucesso
            execution_time = time.time() - start_time
            self._update_metrics('execute_query', execution_time, True)
            
            logger.debug(f"Query executada com sucesso: {query[:100]}...")
            return results
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics('execute_query', execution_time, False)
            
            logger.error(f"Erro ao executar query: {e}")
            raise DatabaseError(f"Falha ao executar query: {str(e)}")
    
    @retryable()
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Executa múltiplas queries com retry automático.
        
        Args:
            query: Query SQL
            params_list: Lista de parâmetros
            
        Returns:
            Número de registros afetados
            
        Raises:
            DatabaseError: Se falhar após todas as tentativas
        """
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.connection.executemany(query, params_list)
                affected_rows = cursor.rowcount
                conn.connection.commit()
            
            # Atualiza métricas de sucesso
            execution_time = time.time() - start_time
            self._update_metrics('execute_many', execution_time, True)
            
            logger.debug(f"Execute_many executado: {len(params_list)} registros afetados")
            return affected_rows
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics('execute_many', execution_time, False)
            
            logger.error(f"Erro ao executar execute_many: {e}")
            raise DatabaseError(f"Falha ao executar execute_many: {str(e)}")
    
    @contextmanager
    def transaction(self):
        """
        Context manager para transações seguras.
        
        Yields:
            PooledConnection: Conexão para a transação
        """
        start_time = time.time()
        
        with self.get_connection() as conn:
            try:
                conn.connection.execute("BEGIN")
                yield conn.connection
                conn.connection.commit()
                
                # Atualiza métricas de sucesso
                execution_time = time.time() - start_time
                self._update_metrics('transaction', execution_time, True)
                
            except Exception as e:
                conn.connection.rollback()
                
                # Atualiza métricas de falha
                execution_time = time.time() - start_time
                self._update_metrics('transaction', execution_time, False)
                
                logger.error(f"Erro na transação, rollback executado: {e}")
                raise DatabaseError(f"Falha na transação: {str(e)}")
    
    def _update_metrics(self, operation: str, execution_time: float, success: bool):
        """Atualiza métricas de operação."""
        with self._metrics_lock:
            self._metrics.last_operation = operation
            self._metrics.last_operation_time = datetime.now()
            
            if operation in ['execute_query', 'execute_many']:
                self._metrics.total_queries += 1
                if success:
                    self._metrics.successful_queries += 1
                else:
                    self._metrics.failed_queries += 1
                
                # Atualiza tempo médio
                if self._metrics.total_queries > 0:
                    total_time = (self._metrics.average_query_time * 
                                (self._metrics.total_queries - 1) + execution_time)
                    self._metrics.average_query_time = total_time / self._metrics.total_queries
                
                # Atualiza tempo mais longo
                if execution_time > self._metrics.longest_query_time:
                    self._metrics.longest_query_time = execution_time
                
                # Conta queries lentas (>5s)
                if execution_time > 5.0:
                    self._metrics.slow_queries_count += 1
                    logger.warning(f"Query lenta detectada ({execution_time:.3f}s) em {operation}")
            
            elif operation == 'transaction':
                self._metrics.total_transactions += 1
                if success:
                    self._metrics.successful_transactions += 1
                else:
                    self._metrics.failed_transactions += 1
    
    def create_new_database(self, db_path: str, app_info: Dict[str, str]) -> bool:
        """
        Cria um novo banco de dados com informações da aplicação.
        
        Args:
            db_path: Caminho do novo banco
            app_info: Informações da aplicação
            
        Returns:
            True se criou com sucesso
        """
        try:
            if os.path.exists(db_path):
                logger.warning(f"Banco já existe: {db_path}")
                return False
            
            # Cria estrutura inicial
            self._create_initial_database(db_path)
            
            # Conecta e adiciona informações da aplicação
            if self.connect(db_path):
                with self.transaction() as conn:
                    for key, value in app_info.items():
                        conn.execute(
                            "INSERT INTO app_info (key, value) VALUES (?, ?)",
                            (key, value)
                        )
                
                logger.info(f"Novo banco criado com sucesso: {db_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao criar novo banco: {e}", exc_info=True)
            if os.path.exists(db_path):
                os.remove(db_path)
            return False
    
    def close(self):
        """Fecha todas as conexões e limpa recursos."""
        try:
            with self._pool_lock:
                if self._connection_pool:
                    self._connection_pool.close_all()
                    self._connection_pool = None
                self._current_db = None
            
            logger.info("Conexões fechadas")
            
        except Exception as e:
            logger.error(f"Erro ao fechar conexões: {e}", exc_info=True)
    
    def reset_metrics(self):
        """Reseta todas as métricas."""
        with self._metrics_lock:
            self._metrics.reset()
        logger.info("Métricas resetadas")
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Retorna status detalhado do gerenciador."""
        status = {
            'connected': self.is_connected,
            'current_db': self._current_db,
            'metrics': self.metrics.__dict__,
            'system_health': self.get_system_health().__dict__,
            'timestamp': datetime.now().isoformat()
        }
        
        if self._connection_pool:
            status['pool_metrics'] = self._connection_pool.get_metrics().__dict__
        
        return status
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor para garantir limpeza de recursos."""
        try:
            self.close()
        except:
            pass  # Ignora erros no destructor


# Alias para compatibilidade com código existente
DatabaseManager = UnifiedDatabaseManager