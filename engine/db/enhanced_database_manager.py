# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Enhanced Database Manager
Gerenciador de banco de dados aprimorado com pool de conexões, retry logic e métricas
"""

import os
import sqlite3
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from functools import wraps
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager

from .connection_pool import DatabaseConnectionPool, PoolConfig
from .database_schema import (
    validate_database_structure,
    create_database_structure,
    get_database_version,
    SCHEMA_VERSION
)

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    """Configuração para retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_backoff: bool = True
    retry_on_exceptions: Tuple[type, ...] = (sqlite3.OperationalError, sqlite3.DatabaseError)

def retry_on_database_error(retry_config: Optional[RetryConfig] = None):
    """Decorator para retry automático em operações de banco."""
    config = retry_config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        # Última tentativa, propaga a exceção
                        break
                    
                    # Calcula delay
                    if config.exponential_backoff:
                        delay = min(
                            config.base_delay * (2 ** attempt),
                            config.max_delay
                        )
                    else:
                        delay = config.base_delay
                    
                    logger.warning(
                        f"Tentativa {attempt + 1}/{config.max_attempts} falhou para {func.__name__}: {e}. "
                        f"Tentando novamente em {delay:.2f}s"
                    )
                    
                    time.sleep(delay)
                except Exception as e:
                    # Exceções não configuradas para retry
                    raise e
            
            # Se chegou aqui, todas as tentativas falharam
            logger.error(f"Todas as {config.max_attempts} tentativas falharam para {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator

class EnhancedDatabaseManager:
    """Gerenciador de banco de dados aprimorado com pool de conexões."""
    
    def __init__(self, config=None, pool_config: Optional[PoolConfig] = None, retry_config: Optional[RetryConfig] = None):
        """Inicializa o gerenciador aprimorado.
        
        Args:
            config: Gerenciador de configuração
            pool_config: Configuração do pool de conexões
            retry_config: Configuração de retry
        """
        self.config = config
        self.pool_config = pool_config or PoolConfig()
        self.retry_config = retry_config or RetryConfig()
        
        # Pool de conexões
        self._connection_pool: Optional[DatabaseConnectionPool] = None
        self._current_db: Optional[str] = None
        
        # Locks para thread safety
        self._pool_lock = threading.RLock()
        
        # Métricas de operações
        self._operation_metrics = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
            'retry_attempts': 0,
            'last_operation': None
        }
        self._metrics_lock = threading.Lock()
    
    @property
    def current_db(self) -> Optional[str]:
        """Retorna o banco de dados atual."""
        return self._current_db
    
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado a um banco."""
        return self._connection_pool is not None and not self._connection_pool._is_closed
    
    def connect(self, db_path: str) -> bool:
        """Conecta ao banco de dados com pool de conexões.
        
        Args:
            db_path: Caminho do banco de dados
            
        Returns:
            True se conectou com sucesso
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
            
            if not file_exists:
                logger.error(f"Arquivo de banco não encontrado: {db_path}")
                return False
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
            # Cria pool de conexões
            with self._pool_lock:
                self._connection_pool = DatabaseConnectionPool(db_path, self.pool_config)
                self._current_db = db_path
            
            # Testa conexão
            with self.get_connection() as conn:
                conn.execute("SELECT 1")
            
            # Valida schema se arquivo já existia
            if file_exists:
                self._validate_and_migrate_schema(db_path)
            
            logger.info(f"Conectado ao banco com pool: {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco: {e}", exc_info=True)
            self.close()
            return False
    
    def _validate_and_migrate_schema(self, db_path: str):
        """Valida e migra schema se necessário."""
        try:
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
    def get_connection(self, timeout: Optional[float] = None):
        """Obtém conexão do pool.
        
        Args:
            timeout: Timeout para obter conexão
            
        Yields:
            sqlite3.Connection: Conexão do banco
        """
        if not self.is_connected:
            raise RuntimeError("Não conectado a nenhum banco de dados")
        
        with self._connection_pool.get_connection(timeout) as conn:
            yield conn
    
    @retry_on_database_error()
    def execute_query(self, query: str, params: Optional[Union[tuple, dict]] = None) -> Optional[List[sqlite3.Row]]:
        """Executa uma query com retry automático.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Resultados da query ou None se falhar
        """
        start_time = time.time()
        
        try:
            with self._metrics_lock:
                self._operation_metrics['total_queries'] += 1
                self._operation_metrics['last_operation'] = datetime.now()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                results = cursor.fetchall()
                conn.commit()
                
                with self._metrics_lock:
                    self._operation_metrics['successful_queries'] += 1
                
                execution_time = time.time() - start_time
                logger.debug(f"Query executada em {execution_time:.3f}s: {query[:100]}...")
                
                return results
                
        except Exception as e:
            with self._metrics_lock:
                self._operation_metrics['failed_queries'] += 1
            
            logger.error(f"Erro ao executar query: {e}", exc_info=True)
            raise
    
    @retry_on_database_error()
    def execute_many(self, query: str, params_list: List[Union[tuple, dict]]) -> bool:
        """Executa múltiplas queries com retry automático.
        
        Args:
            query: Query SQL
            params_list: Lista de parâmetros
            
        Returns:
            True se executado com sucesso
        """
        start_time = time.time()
        
        try:
            with self._metrics_lock:
                self._operation_metrics['total_queries'] += len(params_list)
                self._operation_metrics['last_operation'] = datetime.now()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                
                with self._metrics_lock:
                    self._operation_metrics['successful_queries'] += len(params_list)
                
                execution_time = time.time() - start_time
                logger.debug(f"Batch query executada em {execution_time:.3f}s: {len(params_list)} registros")
                
                return True
                
        except Exception as e:
            with self._metrics_lock:
                self._operation_metrics['failed_queries'] += len(params_list)
            
            logger.error(f"Erro ao executar batch query: {e}", exc_info=True)
            raise
    
    @contextmanager
    def transaction(self):
        """Context manager para transações.
        
        Yields:
            sqlite3.Connection: Conexão para a transação
        """
        start_time = time.time()
        
        with self._metrics_lock:
            self._operation_metrics['total_transactions'] += 1
            self._operation_metrics['last_operation'] = datetime.now()
        
        try:
            with self.get_connection() as conn:
                # Inicia transação explícita
                conn.execute("BEGIN")
                
                try:
                    yield conn
                    conn.commit()
                    
                    with self._metrics_lock:
                        self._operation_metrics['successful_transactions'] += 1
                    
                    execution_time = time.time() - start_time
                    logger.debug(f"Transação concluída em {execution_time:.3f}s")
                    
                except Exception:
                    conn.rollback()
                    raise
                    
        except Exception as e:
            with self._metrics_lock:
                self._operation_metrics['failed_transactions'] += 1
            
            logger.error(f"Erro na transação: {e}", exc_info=True)
            raise
    
    def create_new_database(self, db_path: str, app_info: Dict[str, str]) -> bool:
        """Cria um novo banco de dados.
        
        Args:
            db_path: Caminho do banco
            app_info: Informações do aplicativo
            
        Returns:
            True se criado com sucesso
        """
        try:
            # Remove arquivo se existir
            if os.path.exists(db_path):
                os.remove(db_path)
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Cria banco temporário para estrutura inicial
            temp_conn = sqlite3.connect(db_path)
            temp_conn.row_factory = sqlite3.Row
            
            try:
                with temp_conn:
                    # Cria estrutura básica
                    self._create_basic_structure(temp_conn, app_info)
                
                logger.info(f"Estrutura básica criada em: {db_path}")
                
            except Exception as e:
                logger.error(f"Erro em create_new_database: {e}", exc_info=True)
                raise
            finally:
                temp_conn.close()
            
            # Conecta usando o pool
            return self.connect(db_path)
            
        except Exception as e:
            logger.error(f"Erro ao criar banco: {e}", exc_info=True)
            return False
    
    def _create_basic_structure(self, conn: sqlite3.Connection, app_info: Dict[str, str]):
        """Cria estrutura básica do banco."""
        # Tabela de informações
        conn.execute("""
            CREATE TABLE app_info (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Insere informações
        for key, value in app_info.items():
            conn.execute("INSERT INTO app_info VALUES (?, ?)", (key, value))
        
        # Tabela de jogos
        conn.execute("""
            CREATE TABLE games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                platform TEXT,
                year TEXT,
                manufacturer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela de ROMs
        conn.execute("""
            CREATE TABLE roms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                crc32 TEXT NOT NULL,
                md5 TEXT NOT NULL,
                sha1 TEXT NOT NULL,
                status TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (id)
                    ON DELETE CASCADE
            )
        """)
        
        # Índices
        conn.execute("CREATE INDEX idx_games_name ON games (name)")
        conn.execute("CREATE INDEX idx_roms_game_id ON roms (game_id)")
        conn.execute("CREATE INDEX idx_roms_name ON roms (name)")
        conn.execute("CREATE INDEX idx_roms_status ON roms (status)")
    
    # Métodos de compatibilidade com DatabaseManager original
    def connection(self) -> Optional[sqlite3.Connection]:
        """Método de compatibilidade - não recomendado para uso direto."""
        logger.warning("Método connection() é deprecated. Use get_connection() context manager.")
        if not self.is_connected:
            return None
        
        # Retorna uma conexão temporária (não gerenciada pelo pool)
        try:
            temp_conn = sqlite3.connect(self._current_db)
            temp_conn.row_factory = sqlite3.Row
            return temp_conn
        except Exception as e:
            logger.error(f"Erro ao criar conexão temporária: {e}")
            return None
    
    def get_tables(self) -> List[str]:
        """Obtém lista de tabelas."""
        try:
            query = """
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """
            
            results = self.execute_query(query)
            return [row[0] for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Erro ao obter tabelas: {e}")
            return []
    
    def get_table_info(self, table: str) -> List[sqlite3.Row]:
        """Obtém informações de uma tabela."""
        try:
            query = f"PRAGMA table_info({table})"
            return self.execute_query(query) or []
            
        except Exception as e:
            logger.error(f"Erro ao obter informações da tabela: {e}")
            return []
    
    def table_exists(self, table: str) -> bool:
        """Verifica se uma tabela existe."""
        try:
            query = """
                SELECT COUNT(*) FROM sqlite_master
                WHERE type='table' AND name=?
            """
            
            result = self.execute_query(query, (table,))
            return result[0][0] > 0 if result else False
            
        except Exception as e:
            logger.error(f"Erro ao verificar tabela: {e}")
            return False
    
    def get_row_count(self, table: str) -> int:
        """Obtém número de registros em uma tabela."""
        try:
            query = f"SELECT COUNT(*) FROM {table}"
            result = self.execute_query(query)
            return result[0][0] if result else 0
            
        except Exception as e:
            logger.error(f"Erro ao contar registros: {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtém métricas completas do gerenciador."""
        with self._metrics_lock:
            operation_metrics = self._operation_metrics.copy()
        
        metrics = {
            'database_info': {
                'current_db': self._current_db,
                'is_connected': self.is_connected
            },
            'operation_metrics': operation_metrics,
            'pool_metrics': None
        }
        
        if self._connection_pool:
            metrics['pool_metrics'] = self._connection_pool.get_metrics()
        
        return metrics
    
    def close(self):
        """Fecha o pool de conexões."""
        with self._pool_lock:
            if self._connection_pool:
                self._connection_pool.close()
                self._connection_pool = None
            
            self._current_db = None
        
        logger.info("Enhanced Database Manager fechado")
    
    def close_all(self):
        """Alias para close() para compatibilidade."""
        self.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor."""
        try:
            self.close()
        except Exception:
            pass