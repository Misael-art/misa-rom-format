#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Enhanced Connection Pool
Sistema aprimorado de pool de conexões com retry automático, health checks e métricas avançadas
"""

import os
import sqlite3
import logging
import threading
import time
import asyncio
from typing import Optional, Dict, Any, List, Callable, Union
from queue import Queue, Empty, Full
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import contextmanager, asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, Future
import weakref
from enum import Enum, auto
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Estados de uma conexão."""
    IDLE = auto()
    ACTIVE = auto()
    UNHEALTHY = auto()
    CLOSED = auto()

class PoolState(Enum):
    """Estados do pool."""
    INITIALIZING = auto()
    ACTIVE = auto()
    DEGRADED = auto()
    CLOSED = auto()

@dataclass
class ConnectionMetrics:
    """Métricas detalhadas de conexão."""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    last_health_check: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    max_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    state: ConnectionState = ConnectionState.IDLE
    thread_id: Optional[int] = None
    
    def update_usage(self, execution_time: float = 0.0):
        """Atualiza métricas de uso."""
        self.last_used = datetime.now()
        self.usage_count += 1
        
        if execution_time > 0:
            self.total_execution_time += execution_time
            self.avg_execution_time = self.total_execution_time / self.usage_count
            self.max_execution_time = max(self.max_execution_time, execution_time)
            self.min_execution_time = min(self.min_execution_time, execution_time)
    
    def record_error(self):
        """Registra erro."""
        self.error_count += 1
        self.state = ConnectionState.UNHEALTHY
    
    def mark_healthy(self):
        """Marca como saudável."""
        self.state = ConnectionState.IDLE
        self.last_health_check = datetime.now()
    
    def get_idle_time(self) -> float:
        """Retorna tempo ocioso em segundos."""
        return (datetime.now() - self.last_used).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat(),
            'last_health_check': self.last_health_check.isoformat(),
            'usage_count': self.usage_count,
            'error_count': self.error_count,
            'total_execution_time': self.total_execution_time,
            'avg_execution_time': self.avg_execution_time,
            'max_execution_time': self.max_execution_time,
            'min_execution_time': self.min_execution_time if self.min_execution_time != float('inf') else 0,
            'state': self.state.name,
            'thread_id': self.thread_id,
            'idle_time': self.get_idle_time()
        }

@dataclass
class PoolMetrics:
    """Métricas do pool de conexões."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    unhealthy_connections: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_connections': self.total_connections,
            'active_connections': self.active_connections,
            'idle_connections': self.idle_connections,
            'unhealthy_connections': self.unhealthy_connections,
            'pool_hits': self.pool_hits,
            'pool_misses': self.pool_misses,
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'avg_wait_time': self.avg_wait_time,
            'max_wait_time': self.max_wait_time,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class PoolConfig:
    """Configuração avançada do pool de conexões."""
    min_connections: int = 2
    max_connections: int = 20
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0  # 5 minutos
    max_idle_timeout: float = 1800.0  # 30 minutos
    retry_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    health_check_interval: float = 60.0  # 1 minuto
    health_check_timeout: float = 5.0
    enable_metrics: bool = True
    enable_health_checks: bool = True
    enable_auto_scaling: bool = True
    scale_up_threshold: float = 0.8  # 80% de uso
    scale_down_threshold: float = 0.3  # 30% de uso
    metrics_export_interval: float = 300.0  # 5 minutos
    enable_connection_validation: bool = True
    validation_query: str = "SELECT 1"
    enable_statement_caching: bool = True
    statement_cache_size: int = 100
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True
    busy_timeout: int = 30000  # 30 segundos
    
    @classmethod
    def development(cls):
        """Configuração para ambiente de desenvolvimento."""
        return cls(
            min_connections=5,
            max_connections=10,
            connection_timeout=30.0,
            idle_timeout=300.0,
            health_check_interval=30.0,
            enable_metrics=True,
            enable_health_checks=True
        )
    
    @classmethod
    def production(cls):
        """Configuração para ambiente de produção."""
        return cls(
            min_connections=10,
            max_connections=50,
            connection_timeout=60.0,
            idle_timeout=600.0,
            health_check_interval=60.0,
            enable_auto_scaling=True,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
    
    @classmethod
    def testing(cls):
        """Configuração para ambiente de testes."""
        return cls(
            min_connections=1,
            max_connections=3,
            connection_timeout=10.0,
            idle_timeout=60.0,
            health_check_interval=10.0,
            enable_health_checks=True,
            enable_metrics=False
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            'min_connections': self.min_connections,
            'max_connections': self.max_connections,
            'connection_timeout': self.connection_timeout,
            'idle_timeout': self.idle_timeout,
            'max_idle_timeout': self.max_idle_timeout,
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'retry_backoff_factor': self.retry_backoff_factor,
            'health_check_interval': self.health_check_interval,
            'health_check_timeout': self.health_check_timeout,
            'enable_metrics': self.enable_metrics,
            'enable_health_checks': self.enable_health_checks,
            'enable_auto_scaling': self.enable_auto_scaling,
            'scale_up_threshold': self.scale_up_threshold,
            'scale_down_threshold': self.scale_down_threshold,
            'metrics_export_interval': self.metrics_export_interval,
            'enable_connection_validation': self.enable_connection_validation,
            'validation_query': self.validation_query,
            'enable_statement_caching': self.enable_statement_caching,
            'statement_cache_size': self.statement_cache_size,
            'enable_wal_mode': self.enable_wal_mode,
            'enable_foreign_keys': self.enable_foreign_keys,
            'busy_timeout': self.busy_timeout
        }

class EnhancedPooledConnection:
    """Wrapper avançado para conexão do pool."""
    
    def __init__(self, connection: sqlite3.Connection, pool: 'EnhancedDatabaseConnectionPool', connection_id: str):
        self.connection = connection
        self.pool = pool
        self.connection_id = connection_id
        self.metrics = ConnectionMetrics()
        self._lock = threading.RLock()
        self._statement_cache: Dict[str, sqlite3.Cursor] = {}
        self._start_time: Optional[float] = None
        
        # Configura conexão
        self._configure_connection()
    
    def _configure_connection(self):
        """Configura a conexão com otimizações."""
        try:
            # Configura WAL mode se habilitado
            if self.pool.config.enable_wal_mode:
                self.connection.execute("PRAGMA journal_mode=WAL")
            
            # Habilita foreign keys se configurado
            if self.pool.config.enable_foreign_keys:
                self.connection.execute("PRAGMA foreign_keys=ON")
            
            # Configura busy timeout
            self.connection.execute(f"PRAGMA busy_timeout={self.pool.config.busy_timeout}")
            
            # Otimizações de performance
            self.connection.execute("PRAGMA synchronous=NORMAL")
            self.connection.execute("PRAGMA cache_size=10000")
            self.connection.execute("PRAGMA temp_store=MEMORY")
            
            logger.debug(f"Conexão {self.connection_id} configurada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao configurar conexão {self.connection_id}: {e}")
            self.metrics.record_error()
    
    def __enter__(self):
        """Context manager entry."""
        with self._lock:
            self.metrics.state = ConnectionState.ACTIVE
            self.metrics.thread_id = threading.get_ident()
            self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        execution_time = 0.0
        
        with self._lock:
            if self._start_time:
                execution_time = time.time() - self._start_time
                self._start_time = None
            
            self.metrics.update_usage(execution_time)
            
            if exc_type is not None:
                self.metrics.record_error()
                logger.warning(f"Erro na conexão {self.connection_id}: {exc_val}")
            else:
                self.metrics.state = ConnectionState.IDLE
        
        # Retorna conexão ao pool
        self.pool._return_connection(self)
    
    def execute(self, sql: str, parameters=None) -> sqlite3.Cursor:
        """Executa SQL com cache de statements se habilitado."""
        if self.pool.config.enable_statement_caching and parameters is None:
            # Usa cache para statements sem parâmetros
            if sql not in self._statement_cache:
                if len(self._statement_cache) >= self.pool.config.statement_cache_size:
                    # Remove statement mais antigo
                    oldest_key = next(iter(self._statement_cache))
                    del self._statement_cache[oldest_key]
                
                self._statement_cache[sql] = self.connection.cursor()
            
            cursor = self._statement_cache[sql]
            return cursor.execute(sql)
        else:
            # Execução normal
            return self.connection.execute(sql, parameters or [])
    
    def executemany(self, sql: str, parameters) -> sqlite3.Cursor:
        """Executa múltiplos SQLs."""
        return self.connection.executemany(sql, parameters)
    
    def commit(self):
        """Commit da transação."""
        self.connection.commit()
    
    def rollback(self):
        """Rollback da transação."""
        self.connection.rollback()
    
    def is_healthy(self) -> bool:
        """Verifica se a conexão está saudável."""
        try:
            start_time = time.time()
            cursor = self.connection.execute(self.pool.config.validation_query)
            cursor.fetchone()
            
            # Verifica se não demorou muito
            if time.time() - start_time > self.pool.config.health_check_timeout:
                logger.warning(f"Health check da conexão {self.connection_id} demorou muito")
                return False
            
            self.metrics.mark_healthy()
            return True
            
        except Exception as e:
            self.metrics.record_error()
            logger.warning(f"Conexão {self.connection_id} não saudável: {e}")
            return False
    
    def is_idle_expired(self) -> bool:
        """Verifica se a conexão está ociosa há muito tempo."""
        if self.metrics.state == ConnectionState.ACTIVE:
            return False
        
        idle_time = self.metrics.get_idle_time()
        max_idle = self.pool.config.max_idle_timeout
        
        return idle_time > max_idle
    
    def should_be_recycled(self) -> bool:
        """Verifica se a conexão deve ser reciclada."""
        # Recicla se tiver muitos erros
        if self.metrics.error_count > 10:
            return True
        
        # Recicla se estiver ociosa há muito tempo
        if self.is_idle_expired():
            return True
        
        # Recicla se estiver não saudável
        if self.metrics.state == ConnectionState.UNHEALTHY:
            return True
        
        return False
    
    def close(self):
        """Fecha a conexão."""
        try:
            # Limpa cache de statements
            self._statement_cache.clear()
            
            # Fecha conexão
            self.connection.close()
            self.metrics.state = ConnectionState.CLOSED
            
            logger.debug(f"Conexão {self.connection_id} fechada")
            
        except Exception as e:
            logger.warning(f"Erro ao fechar conexão {self.connection_id}: {e}")

class EnhancedDatabaseConnectionPool:
    """Pool de conexões avançado para banco de dados SQLite."""
    
    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        self.db_path = db_path
        self.config = config or PoolConfig()
        
        # Pool de conexões
        self._pool: Queue[EnhancedPooledConnection] = Queue(maxsize=self.config.max_connections)
        self._all_connections: Dict[str, EnhancedPooledConnection] = {}
        self._connections_lock = threading.RLock()
        
        # Controle de estado
        self._state = PoolState.INITIALIZING
        self._is_closed = False
        self._creation_lock = threading.Lock()
        
        # Health check e auto-scaling
        self._health_check_executor: Optional[ThreadPoolExecutor] = None
        self._health_check_future: Optional[Future] = None
        self._auto_scale_executor: Optional[ThreadPoolExecutor] = None
        self._auto_scale_future: Optional[Future] = None
        
        # Métricas globais
        self._global_metrics = {
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'total_requests': 0,
            'total_errors': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'total_wait_time': 0.0,
            'avg_wait_time': 0.0,
            'max_wait_time': 0.0,
            'current_pool_size': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'unhealthy_connections': 0
        }
        
        # Callbacks
        self._on_connection_created: List[Callable] = []
        self._on_connection_closed: List[Callable] = []
        self._on_pool_exhausted: List[Callable] = []
        
        # Inicializa pool
        self._initialize_pool()
        
        # Inicia serviços se habilitados
        if self.config.enable_health_checks:
            self._start_health_check()
        
        if self.config.enable_auto_scaling:
            self._start_auto_scaling()
        
        self._state = PoolState.ACTIVE
        logger.info(f"Pool de conexões inicializado: {self.db_path}")
    
    def _initialize_pool(self):
        """Inicializa o pool com conexões mínimas."""
        for i in range(self.config.min_connections):
            try:
                connection = self._create_connection()
                self._pool.put_nowait(connection)
                logger.debug(f"Conexão inicial {i+1}/{self.config.min_connections} criada")
            except Exception as e:
                logger.error(f"Erro ao criar conexão inicial {i+1}: {e}")
                if i == 0:  # Se não conseguir criar nem a primeira
                    raise
    
    def _create_connection(self) -> EnhancedPooledConnection:
        """Cria uma nova conexão."""
        connection_id = f"conn_{int(time.time() * 1000000)}_{threading.get_ident()}"
        
        try:
            # Verifica se o arquivo de banco existe
            if not os.path.exists(self.db_path):
                # Cria diretório se necessário
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Cria conexão SQLite
            raw_connection = sqlite3.connect(
                self.db_path,
                timeout=self.config.connection_timeout,
                check_same_thread=False
            )
            
            # Cria wrapper
            pooled_connection = EnhancedPooledConnection(raw_connection, self, connection_id)
            
            # Registra conexão
            with self._connections_lock:
                self._all_connections[connection_id] = pooled_connection
                self._global_metrics['total_connections_created'] += 1
                self._global_metrics['current_pool_size'] += 1
            
            # Chama callbacks
            for callback in self._on_connection_created:
                try:
                    callback(pooled_connection)
                except Exception as e:
                    logger.warning(f"Erro em callback de criação: {e}")
            
            logger.debug(f"Conexão {connection_id} criada com sucesso")
            return pooled_connection
            
        except Exception as e:
            logger.error(f"Erro ao criar conexão {connection_id}: {e}")
            self._global_metrics['total_errors'] += 1
            raise
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """Obtém conexão do pool com context manager."""
        connection = None
        wait_start = time.time()
        
        try:
            connection = self._get_connection_internal(timeout)
            wait_time = time.time() - wait_start
            
            # Atualiza métricas de espera
            self._global_metrics['total_wait_time'] += wait_time
            self._global_metrics['avg_wait_time'] = (
                self._global_metrics['total_wait_time'] / 
                max(1, self._global_metrics['total_requests'])
            )
            self._global_metrics['max_wait_time'] = max(
                self._global_metrics['max_wait_time'], wait_time
            )
            
            yield connection
            
        finally:
            if connection:
                self._return_connection(connection)
    
    def _get_connection_internal(self, timeout: Optional[float] = None) -> EnhancedPooledConnection:
        """Obtém conexão do pool (método interno)."""
        if self._is_closed:
            raise RuntimeError("Pool de conexões está fechado")
        
        self._global_metrics['total_requests'] += 1
        timeout = timeout or self.config.connection_timeout
        
        try:
            # Tenta obter do pool
            connection = self._pool.get(timeout=timeout)
            self._global_metrics['pool_hits'] += 1
            
            # Valida conexão se habilitado
            if self.config.enable_connection_validation:
                if not connection.is_healthy():
                    logger.warning(f"Conexão {connection.connection_id} não saudável, criando nova")
                    self._close_connection(connection)
                    connection = self._create_connection()
            
            with self._connections_lock:
                self._global_metrics['active_connections'] += 1
                self._global_metrics['idle_connections'] -= 1
            
            return connection
            
        except Empty:
            # Pool vazio, tenta criar nova conexão
            self._global_metrics['pool_misses'] += 1
            
            with self._creation_lock:
                current_size = len(self._all_connections)
                
                if current_size < self.config.max_connections:
                    connection = self._create_connection()
                    
                    with self._connections_lock:
                        self._global_metrics['active_connections'] += 1
                    
                    return connection
                else:
                    # Pool esgotado
                    for callback in self._on_pool_exhausted:
                        try:
                            callback()
                        except Exception as e:
                            logger.warning(f"Erro em callback de pool esgotado: {e}")
                    
                    raise RuntimeError(f"Pool de conexões esgotado (max: {self.config.max_connections})")
    
    def _return_connection(self, connection: EnhancedPooledConnection):
        """Retorna conexão ao pool."""
        if self._is_closed:
            self._close_connection(connection)
            return
        
        try:
            # Verifica se deve ser reciclada
            if connection.should_be_recycled():
                logger.debug(f"Reciclando conexão {connection.connection_id}")
                self._close_connection(connection)
                
                # Cria nova se necessário
                if len(self._all_connections) < self.config.min_connections:
                    new_connection = self._create_connection()
                    self._pool.put_nowait(new_connection)
            else:
                # Retorna ao pool
                self._pool.put_nowait(connection)
            
            with self._connections_lock:
                self._global_metrics['active_connections'] -= 1
                self._global_metrics['idle_connections'] += 1
                
        except Full:
            # Pool cheio, fecha conexão
            logger.debug(f"Pool cheio, fechando conexão {connection.connection_id}")
            self._close_connection(connection)
        except Exception as e:
            logger.error(f"Erro ao retornar conexão: {e}")
            self._close_connection(connection)
    
    def _close_connection(self, connection: EnhancedPooledConnection):
        """Fecha uma conexão específica."""
        try:
            connection_id = connection.connection_id
            
            # Remove do registro
            with self._connections_lock:
                if connection_id in self._all_connections:
                    del self._all_connections[connection_id]
                    self._global_metrics['total_connections_closed'] += 1
                    self._global_metrics['current_pool_size'] -= 1
            
            # Fecha conexão
            connection.close()
            
            # Chama callbacks
            for callback in self._on_connection_closed:
                try:
                    callback(connection)
                except Exception as e:
                    logger.warning(f"Erro em callback de fechamento: {e}")
            
            logger.debug(f"Conexão {connection_id} fechada")
            
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {e}")
    
    def _start_health_check(self):
        """Inicia health check periódico."""
        if self._health_check_executor:
            return
        
        self._health_check_executor = ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix="pool-health-check"
        )
        
        self._health_check_future = self._health_check_executor.submit(self._health_check_loop)
        logger.debug("Health check iniciado")
    
    def _health_check_loop(self):
        """Loop de health check."""
        while not self._is_closed:
            try:
                time.sleep(self.config.health_check_interval)
                
                if self._is_closed:
                    break
                
                self._perform_health_check()
                
            except Exception as e:
                logger.error(f"Erro no health check: {e}")
    
    def _perform_health_check(self):
        """Executa health check em todas as conexões."""
        unhealthy_connections = []
        
        with self._connections_lock:
            connections_to_check = list(self._all_connections.values())
        
        for connection in connections_to_check:
            if connection.metrics.state == ConnectionState.IDLE:
                if not connection.is_healthy():
                    unhealthy_connections.append(connection)
        
        # Remove conexões não saudáveis
        for connection in unhealthy_connections:
            logger.warning(f"Removendo conexão não saudável: {connection.connection_id}")
            self._close_connection(connection)
        
        # Atualiza métricas
        with self._connections_lock:
            healthy_count = sum(
                1 for conn in self._all_connections.values() 
                if conn.metrics.state != ConnectionState.UNHEALTHY
            )
            unhealthy_count = len(self._all_connections) - healthy_count
            
            self._global_metrics['unhealthy_connections'] = unhealthy_count
        
        if unhealthy_connections:
            logger.info(f"Health check: {len(unhealthy_connections)} conexões removidas")
    
    def _start_auto_scaling(self):
        """Inicia auto-scaling do pool."""
        if self._auto_scale_executor:
            return
        
        self._auto_scale_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="pool-auto-scale"
        )
        
        self._auto_scale_future = self._auto_scale_executor.submit(self._auto_scale_loop)
        logger.debug("Auto-scaling iniciado")
    
    def _auto_scale_loop(self):
        """Loop de auto-scaling."""
        while not self._is_closed:
            try:
                time.sleep(self.config.health_check_interval * 2)  # Menos frequente que health check
                
                if self._is_closed:
                    break
                
                self._perform_auto_scaling()
                
            except Exception as e:
                logger.error(f"Erro no auto-scaling: {e}")
    
    def _perform_auto_scaling(self):
        """Executa auto-scaling baseado na utilização."""
        with self._connections_lock:
            total_connections = len(self._all_connections)
            active_connections = self._global_metrics['active_connections']
            
            if total_connections == 0:
                return
            
            utilization = active_connections / total_connections
        
        # Scale up se utilização alta
        if (utilization > self.config.scale_up_threshold and 
            total_connections < self.config.max_connections):
            
            connections_to_add = min(
                2,  # Adiciona no máximo 2 por vez
                self.config.max_connections - total_connections
            )
            
            for _ in range(connections_to_add):
                try:
                    connection = self._create_connection()
                    self._pool.put_nowait(connection)
                    logger.info(f"Auto-scaling: conexão adicionada (utilização: {utilization:.2%})")
                except Exception as e:
                    logger.error(f"Erro ao adicionar conexão no auto-scaling: {e}")
                    break
        
        # Scale down se utilização baixa
        elif (utilization < self.config.scale_down_threshold and 
              total_connections > self.config.min_connections):
            
            connections_to_remove = min(
                1,  # Remove no máximo 1 por vez
                total_connections - self.config.min_connections
            )
            
            for _ in range(connections_to_remove):
                try:
                    # Tenta obter conexão ociosa para remover
                    connection = self._pool.get_nowait()
                    self._close_connection(connection)
                    logger.info(f"Auto-scaling: conexão removida (utilização: {utilization:.2%})")
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"Erro ao remover conexão no auto-scaling: {e}")
                    break
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do pool."""
        with self._connections_lock:
            # Atualiza métricas de conexões
            idle_count = 0
            active_count = 0
            unhealthy_count = 0
            
            connection_metrics = []
            
            for connection in self._all_connections.values():
                if connection.metrics.state == ConnectionState.IDLE:
                    idle_count += 1
                elif connection.metrics.state == ConnectionState.ACTIVE:
                    active_count += 1
                elif connection.metrics.state == ConnectionState.UNHEALTHY:
                    unhealthy_count += 1
                
                connection_metrics.append(connection.metrics.to_dict())
            
            self._global_metrics.update({
                'current_pool_size': len(self._all_connections),
                'active_connections': active_count,
                'idle_connections': idle_count,
                'unhealthy_connections': unhealthy_count
            })
        
        return {
            'pool_state': self._state.name,
            'config': self.config.to_dict(),
            'global_metrics': self._global_metrics.copy(),
            'connection_metrics': connection_metrics,
            'timestamp': datetime.now().isoformat()
        }
    
    def export_metrics(self, file_path: Optional[str] = None) -> str:
        """Exporta métricas para arquivo JSON."""
        metrics = self.get_metrics()
        
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"pool_metrics_{timestamp}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Métricas exportadas para: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Erro ao exportar métricas: {e}")
            raise
    
    def add_callback(self, event: str, callback: Callable):
        """Adiciona callback para eventos do pool."""
        if event == 'connection_created':
            self._on_connection_created.append(callback)
        elif event == 'connection_closed':
            self._on_connection_closed.append(callback)
        elif event == 'pool_exhausted':
            self._on_pool_exhausted.append(callback)
        else:
            raise ValueError(f"Evento desconhecido: {event}")
    
    def remove_callback(self, event: str, callback: Callable):
        """Remove callback de eventos do pool."""
        try:
            if event == 'connection_created':
                self._on_connection_created.remove(callback)
            elif event == 'connection_closed':
                self._on_connection_closed.remove(callback)
            elif event == 'pool_exhausted':
                self._on_pool_exhausted.remove(callback)
        except ValueError:
            pass
    
    def close(self):
        """Fecha o pool e todas as conexões."""
        if self._is_closed:
            return
        
        logger.info("Fechando pool de conexões...")
        self._is_closed = True
        self._state = PoolState.CLOSED
        
        # Para health check
        if self._health_check_future:
            self._health_check_future.cancel()
        if self._health_check_executor:
            self._health_check_executor.shutdown(wait=True)
        
        # Para auto-scaling
        if self._auto_scale_future:
            self._auto_scale_future.cancel()
        if self._auto_scale_executor:
            self._auto_scale_executor.shutdown(wait=True)
        
        # Fecha todas as conexões
        with self._connections_lock:
            connections_to_close = list(self._all_connections.values())
        
        for connection in connections_to_close:
            self._close_connection(connection)
        
        # Limpa pool
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except Empty:
                break
        
        logger.info("Pool de conexões fechado")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor."""
        if not self._is_closed:
            self.close()

# Função de conveniência
def create_enhanced_pool(db_path: str, **config_kwargs) -> EnhancedDatabaseConnectionPool:
    """Cria um pool de conexões aprimorado com configuração personalizada."""
    config = PoolConfig(**config_kwargs)
    return EnhancedDatabaseConnectionPool(db_path, config)