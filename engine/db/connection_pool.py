#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Connection Pool
Gerenciamento avançado de conexões SQLite com pool, timeout e retry
"""

import sqlite3
import threading
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import queue

# Importa constantes
from constants import DB_MAX_CONNECTIONS, DB_CONNECTION_TIMEOUT

logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    """Estatísticas de conexão."""
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    total_queries: int = 0
    total_time: float = 0.0
    errors: int = 0

@dataclass
class PoolMetrics:
    """Métricas do pool de conexões."""
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    max_connections: int = 0
    waiting_threads: int = 0
    total_queries: int = 0
    average_query_time: float = 0.0
    error_rate: float = 0.0

class ConnectionPoolError(Exception):
    """Erro no pool de conexões."""
    pass

class ConnectionTimeoutError(ConnectionPoolError):
    """Timeout ao obter conexão."""
    pass

class ConnectionHealthError(ConnectionPoolError):
    """Erro de health check da conexão."""
    pass

class PooledConnection:
    """Conexão gerenciada pelo pool."""
    
    def __init__(self, db_path: str, timeout: float = 5.0):
        self.db_path = db_path
        self.timeout = timeout
        self.connection = None
        self.stats = ConnectionStats(
            created_at=datetime.now(),
            last_used=datetime.now()
        )
        self._lock = threading.Lock()
        self._closed = False
        self._prepared_statements: Dict[str, sqlite3.Cursor] = {}  # Cache de statements preparados
        self._statement_cache_size = 50  # Limite de statements em cache
        self._setup_connection()
    
    def _setup_connection(self):
        """Configura a conexão SQLite."""
        try:
            self.connection = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                isolation_level=None,  # Autocommit mode
                check_same_thread=False
            )
            self.connection.row_factory = sqlite3.Row
            
            # Configurações de performance
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = NORMAL")
            self.connection.execute("PRAGMA cache_size = 10000")
            self.connection.execute("PRAGMA temp_store = memory")
            self.connection.execute("PRAGMA mmap_size = 268435456")  # 256MB
            
        except sqlite3.Error as e:
            raise ConnectionPoolError(f"Erro ao criar conexão: {e}")
    
    def is_healthy(self) -> bool:
        """Verifica se a conexão está saudável."""
        if self._closed or not self.connection:
            return False
            
        try:
            self.connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False
    
    def close(self):
        """Fecha a conexão."""
        with self._lock:
            if not self._closed and self.connection:
                try:
                    self.connection.close()
                except sqlite3.Error as e:
                    logger.warning(f"Erro ao fechar conexão: {e}")
                finally:
                    self.connection = None
                    self._closed = True
    
    def execute_with_retry(self, query: str, params: tuple = None, max_retries: int = 3) -> Any:
        """Executa query com retry automático."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                with self._lock:
                    if not self.is_healthy():
                        self.close()
                        self._setup_connection()
                    
                    cursor = self.connection.cursor()
                    start_time = time.time()
                    
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    
                    execution_time = time.time() - start_time
                    
                    self.stats.total_queries += 1
                    self.stats.total_time += execution_time
                    self.stats.last_used = datetime.now()
                    
                    return cursor
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries:
                    wait_time = 0.1 * (2 ** attempt)  # Backoff exponencial
                    time.sleep(wait_time)
                    continue
                last_error = e
                break
            except sqlite3.Error as e:
                last_error = e
                self.stats.errors += 1
                break
        
        raise last_error

class ConnectionPool:
    """Pool de conexões SQLite com gerenciamento avançado."""

    def __init__(self, db_path: str, max_connections: int = DB_MAX_CONNECTIONS,
                 timeout: float = DB_CONNECTION_TIMEOUT, health_check_interval: int = 300):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.health_check_interval = health_check_interval
        
        self._pool = queue.Queue(maxsize=max_connections)
        self._active_connections: Dict[int, PooledConnection] = {}
        self._lock = threading.RLock()
        self._closed = False
        self._metrics = PoolMetrics(
            max_connections=max_connections
        )
        self._last_health_check = datetime.now()
        
        logger.info(f"Pool de conexões inicializado: max={max_connections}, timeout={timeout}s")
    
    def _create_connection(self) -> PooledConnection:
        """Cria uma nova conexão."""
        conn = PooledConnection(self.db_path, self.timeout)
        
        with self._lock:
            self._active_connections[id(conn)] = conn
            self._metrics.total_connections += 1
            self._metrics.active_connections += 1
            
        return conn
    
    def _get_connection_from_pool(self, timeout: Optional[float] = None) -> Optional[PooledConnection]:
        """Obtém conexão do pool."""
        if timeout is None:
            timeout = self.timeout
            
        try:
            return self._pool.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _return_connection_to_pool(self, conn: PooledConnection):
        """Retorna conexão ao pool."""
        if conn.is_healthy() and not self._closed:
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                # Pool cheio, fecha a conexão
                conn.close()
                with self._lock:
                    self._active_connections.pop(id(conn), None)
                    self._metrics.active_connections -= 1
        else:
            # Conexão não saudável, fecha e remove
            conn.close()
            with self._lock:
                self._active_connections.pop(id(conn), None)
                self._metrics.active_connections -= 1
    
    def _perform_health_check(self):
        """Realiza verificação de saúde das conexões."""
        current_time = datetime.now()
        
        if (current_time - self._last_health_check).seconds < self.health_check_interval:
            return
            
        with self._lock:
            connections_to_remove = []
            
            for conn_id, conn in self._active_connections.items():
                if not conn.is_healthy():
                    connections_to_remove.append(conn_id)
            
            for conn_id in connections_to_remove:
                conn = self._active_connections.pop(conn_id)
                conn.close()
                self._metrics.active_connections -= 1
            
            self._last_health_check = current_time
            
            logger.debug(f"Health check realizado. Conexões ativas: {self._metrics.active_connections}")
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """Context manager para obter conexão do pool."""
        if self._closed:
            raise ConnectionPoolError("Pool está fechado")
        
        self._perform_health_check()
        
        if timeout is None:
            timeout = self.timeout
            
        conn = None
        start_time = time.time()
        
        try:
            # Tenta obter do pool
            conn = self._get_connection_from_pool(timeout)
            
            # Se não conseguiu e ainda temos espaço, cria nova
            if conn is None:
                with self._lock:
                    if len(self._active_connections) < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # Aguarda uma conexão ficar disponível
                        remaining_time = timeout - (time.time() - start_time)
                        if remaining_time <= 0:
                            raise ConnectionTimeoutError(
                                f"Timeout ao aguardar conexão após {timeout}s"
                            )
                        
                        conn = self._get_connection_from_pool(remaining_time)
                        if conn is None:
                            raise ConnectionTimeoutError(
                                f"Pool cheio e timeout expirado após {timeout}s"
                            )
            
            yield conn
            
        except Exception:
            if conn:
                self._return_connection_to_pool(conn)
            raise
            
        else:
            self._return_connection_to_pool(conn)
    
    def close_all(self):
        """Fecha todas as conexões e limpa o pool."""
        with self._lock:
            self._closed = True
            
            # Fecha todas as conexões ativas
            for conn in self._active_connections.values():
                conn.close()
            
            self._active_connections.clear()
            
            # Limpa o pool
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except queue.Empty:
                    break
            
            logger.info("Pool de conexões fechado")
    
    def get_metrics(self) -> PoolMetrics:
        """Obtém métricas do pool."""
        with self._lock:
            self._metrics.idle_connections = self._pool.qsize()
            self._metrics.active_connections = len(self._active_connections)
            self._metrics.total_connections = self._metrics.active_connections + self._metrics.idle_connections
            
            # Calcula métricas avançadas
            total_queries = sum(conn.stats.total_queries for conn in self._active_connections.values())
            total_time = sum(conn.stats.total_time for conn in self._active_connections.values())
            total_errors = sum(conn.stats.errors for conn in self._active_connections.values())

            # Média ponderada do tempo de query
            average_query_time = total_time / total_queries if total_queries > 0 else 0.0

            # Taxa de erro (erros por query)
            error_rate = total_errors / total_queries if total_queries > 0 else 0.0

            # Contador de threads esperando (aproximado pelo tamanho da fila de espera)
            waiting_threads = max(0, self._pool.qsize() - self.max_connections)

            return PoolMetrics(
                active_connections=self._metrics.active_connections,
                idle_connections=self._metrics.idle_connections,
                total_connections=self._metrics.total_connections,
                max_connections=self._metrics.max_connections,
                waiting_threads=waiting_threads,
                total_queries=total_queries,
                average_query_time=average_query_time,
                error_rate=error_rate
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()