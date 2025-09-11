#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Database Manager v2
Gerenciador de banco de dados com pool de conexões, timeout e retry automático
"""

import os
import sqlite3
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from contextlib import contextmanager
from datetime import datetime
import time
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from .connection_pool import ConnectionPool, PoolMetrics
from .pool_config import PoolConfig
from .retry_manager import RetryManager, RetryConfig, retryable
from .database_schema import (
    validate_database_structure,
    create_database_structure,
    get_database_version,
    SCHEMA_VERSION
)
from .prometheus_exports import global_exporter, get_global_exporter

# Logger específico com configuração robusta
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class SystemMonitor:
    """Monitor de recursos do sistema para detecção de problemas de performance."""

    def __init__(self):
        self.psutil_available = PSUTIL_AVAILABLE
        self.baseline_cpu = 0.0
        self.baseline_memory = 0.0
        self.last_measurement = {}
        self.alert_thresholds = {
            'cpu_percent': 80.0,      # Alerta se CPU > 80%
            'memory_percent': 85.0,   # Alerta se memória > 85%
            'memory_mb': 1024.0       # Alerta se uso de memória > 1GB
        }

    def get_system_metrics(self) -> Dict[str, Any]:
        """Coleta métricas atuais do sistema."""
        if not self.psutil_available:
            return {
                'available': False,
                'cpu_percent': None,
                'memory_percent': None,
                'memory_mb': None,
                'timestamp': datetime.now().isoformat()
            }

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            metrics = {
                'available': True,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_mb': memory.used / (1024 * 1024),
                'cpu_alert': cpu_percent > self.alert_thresholds['cpu_percent'],
                'memory_alert': (memory.percent > self.alert_thresholds['memory_percent'] or
                               memory.used > self.alert_thresholds['memory_mb'] * 1024 * 1024),
                'timestamp': datetime.now().isoformat()
            }

            self.last_measurement = metrics
            return metrics

        except Exception as e:
            logger.warning(f"Erro ao coletar métricas do sistema: {e}")
            return {
                'available': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def check_performance_alerts(self) -> List[str]:
        """Verifica alertas de performance baseados nos thresholds."""
        if not self.psutil_available:
            return ["Monitoramento psutil não disponível"]

        metrics = self.get_system_metrics()
        alerts = []

        if not metrics.get('available', False):
            return ["Métricas indisponíveis"]

        if metrics.get('cpu_alert'):
            alerts.append(".1f")

        if metrics.get('memory_alert'):
            alerts.append(".1f")

        return alerts

class ConnectionHealthManager:
    """Gerenciador de saúde das conexões com recovery automático."""

    def __init__(self, recovery_retries: int = 3):
        self.recovery_retries = recovery_retries
        self.connection_failures = {}
        self.recovery_stats = {
            'recovered_connections': 0,
            'failed_recoveries': 0,
            'total_recovery_attempts': 0
        }

    def check_connection_health(self, connection) -> Dict[str, Any]:
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

    def attempt_connection_recovery(self, connection, db_path: str) -> bool:
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

    def get_recovery_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de recovery."""
        return self.recovery_stats.copy()

class DatabaseManagerV2:
    """Gerenciador de banco de dados com pool de conexões."""
    
    def __init__(self, config=None):
        """Inicializa o gerenciador com pool de conexões e retry robusto.

        Args:
            config: Configuração do pool ou dicionário de configuração
        """
        self.current_db = None
        self.pool = None
        self.config = config

        # Configuração do pool
        if isinstance(config, dict) and 'pool' in config:
            self.pool_config = PoolConfig.from_dict(config['pool'])
        elif isinstance(config, PoolConfig):
            self.pool_config = config
        else:
            self.pool_config = PoolConfig.default()

        # Configuração de retry inteligente baseada no ambiente
        if isinstance(config, dict) and 'retry' in config:
            self.retry_config = RetryConfig(**config['retry'])
        else:
            self.retry_config = RetryConfig.conservative()  # Mais seguro para operações críticas

        # Gerenciador de retry com métricas
        self.retry_manager = RetryManager(self.retry_config)

        # Gestor de saúde das conexões para recovery automático
        self.health_manager = ConnectionHealthManager()

        # Monitor de recursos do sistema para alertas de performance
        self.system_monitor = SystemMonitor()

        # Métricas avançadas de performance
        self._performance_metrics = {
            'total_queries': 0,
            'total_transactions': 0,
            'average_query_time': 0.0,
            'longest_query_time': 0.0,
            'slow_queries_count': 0,
            'system_alerts_detected': 0,
            'warnings_logged': 0,
            'last_performance_check': None
        }

        self._lock = threading.RLock()
        self._closed = False
        self._error_stats = {
            'connection_errors': 0,
            'query_errors': 0,
            'integrity_errors': 0,
            'timeout_errors': 0,
            'last_error': None,
            'last_error_time': None,
            'connection_recoveries': 0,
            'system_performance_alerts': 0,
            'long_running_queries': 0
        }
        
    def connect(self, db_path: str) -> bool:
        """Conecta ao banco de dados usando pool de conexões.
        
        Args:
            db_path: Caminho do banco de dados
            
        Returns:
            True se conectou com sucesso
        """
        try:
            with self._lock:
                if self.current_db == db_path and self.pool is not None:
                    return True
                
                # Fecha pool anterior se existir
                self.close_all()
                
                # Verifica e cria diretório se necessário
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
                
                # Cria novo pool
                self.pool = ConnectionPool(
                    db_path=db_path,
                    max_connections=self.pool_config.max_connections,
                    timeout=self.pool_config.timeout,
                    health_check_interval=self.pool_config.health_check_interval
                )
                
                # Verifica se é um novo banco
                is_new_db = not os.path.exists(db_path)
                
                # Cria estrutura se for novo banco
                if is_new_db:
                    logger.info(f"Criando nova estrutura de banco em: {db_path}")
                    with self.pool.get_connection() as conn:
                        if not create_database_structure(conn.connection):
                            logger.warning("Erro ao criar estrutura do banco")
                            return False
                
                # Valida estrutura do banco existente
                else:
                    logger.info(f"Conectando a banco existente: {db_path}")
                    with self.pool.get_connection() as conn:
                        try:
                            # Configurações de performance
                            cursor = conn.connection.cursor()
                            cursor.execute("PRAGMA foreign_keys = ON")
                            
                            # Verifica se há tabelas
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                            tables = cursor.fetchall()
                            
                            if not tables:
                                logger.warning("Banco vazio, criando estrutura")
                                if not create_database_structure(conn.connection):
                                    logger.warning("Erro ao criar estrutura do banco")
                                    
                        except sqlite3.Error as e:
                            logger.error(f"Erro ao verificar estrutura: {e}")
                            return False
                
                self.current_db = db_path
                logger.info(f"Conectado ao banco via pool: {db_path}")
                return True
                
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco: {e}", exc_info=True)
            self.close_all()
            return False
    
    def close_all(self):
        """Fecha o pool de conexões."""
        try:
            with self._lock:
                if self.pool:
                    self.pool.close_all()
                    self.pool = None
                self.current_db = None
                self._closed = True
                logger.info("Pool de conexões fechado")
        except Exception as e:
            logger.error(f"Erro ao fechar pool: {e}")
    
    def close(self):
        """Alias para close_all()."""
        self.close_all()
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[sqlite3.Row]]:
        """Executa query com retry automático e tratamento robusto de erros.

        Args:
            query: Query SQL
            params: Parâmetros da query

        Returns:
            Resultados da query ou None se falhar
        """
        if not self.pool:
            logger.error("Pool não inicializado - execute_query abortado")
            self._track_error('connection_errors')
            return None

        # Validar parâmetros para evitar ValueError
        if params is not None and not isinstance(params, (tuple, list)):
            logger.error(f"Parâmetros inválidos para query: {type(params)} - deve ser tuple ou list")
            self._track_error('query_errors')
            return None

        try:
            # Executar com retry automático para operações críticas
            result = self._execute_with_error_handling(
                self._execute_query_impl,
                query=query,
                params=params,
                operation_name="execute_query"
            )
            return result

        except sqlite3.IntegrityError as e:
            error_msg = f"Violação de integridade na query: {self._sanitize_sql(query)}"
            logger.error(error_msg)
            logger.error(f"Detalhes: {str(e)}")
            self._track_error('integrity_errors', e)
            return None

        except sqlite3.OperationalError as e:
            error_msg = "Erro operacional na query (possível deadlock ou tabela bloqueada)"
            logger.error(f"{error_msg}: {str(e)}")
            self._track_error('query_errors', e)
            return None

        except ValueError as e:
            error_msg = "Erro de valor na query (parâmetros inválidos)"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Query: {self._sanitize_sql(query)}")
            logger.error(f"Params: {params}")
            return None

        except sqlite3.DatabaseError as e:
            error_msg = "Erro crítico de banco de dados"
            logger.error(f"{error_msg}: {str(e)}", exc_info=True)
            self._track_error('query_errors', e)
            return None

        except Exception as e:
            error_msg = "Erro inesperado durante execução da query"
            logger.error(f"{error_msg}: {str(e)}", exc_info=True)
            self._track_error('query_errors', e)
            return None

    def _execute_query_impl(self, query: str, params: tuple) -> Optional[List[sqlite3.Row]]:
        """Implementação interna da execução de query."""
        with self.pool.get_connection() as conn:
            cursor = conn.connection.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            results = cursor.fetchall()
            conn.connection.commit()

            logger.debug(f"Query executada com sucesso: {query[:100]}...")
            return results
    
    def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Executa múltiplas queries com retry automático e validações robustas.

        Args:
            query: Query SQL
            params_list: Lista de parâmetros

        Returns:
            True se executou com sucesso
        """
        if not self.pool:
            logger.error("Pool não inicializado - execute_many abortado")
            self._track_error('connection_errors')
            return False

        # Validações de entrada para evitar ValueError
        if not isinstance(params_list, list):
            logger.error(f"params_list deve ser uma lista, recebido: {type(params_list)}")
            return False

        if not params_list:
            logger.warning("Lista de parâmetros vazia fornecida para execute_many")
            return True  # Não é um erro, apenas nenhuma operação

        # Validar estrutura dos parâmetros
        try:
            self._validate_params_list(params_list)
        except ValueError as e:
            logger.error(f"Parâmetros inválidos: {str(e)}")
            return False

        try:
            # Executar com retry automático
            result = self._execute_with_error_handling(
                self._execute_many_impl,
                query=query,
                params_list=params_list,
                operation_name="execute_many"
            )
            return result is not None

        except sqlite3.IntegrityError as e:
            logger.error(f"Violação de integridade no execute_many: {str(e)}")
            logger.error(f"Query: {self._sanitize_sql(query)}")
            self._track_error('integrity_errors', e)
            return False

        except sqlite3.OperationalError as e:
            logger.error(f"Erro operacional no execute_many: {str(e)}")
            self._track_error('query_errors', e)
            return False

        except ValueError as e:
            logger.error(f"Erro de valor no execute_many: {str(e)}")
            logger.error(f"Primeiro param da lista: {params_list[0] if params_list else 'N/A'}")
            return False

        except Exception as e:
            logger.error(f"Erro inesperado no execute_many: {str(e)}", exc_info=True)
            self._track_error('query_errors', e)
            return False

    def _execute_many_impl(self, query: str, params_list: List[tuple]) -> bool:
        """Implementação interna do execute_many."""
        with self.pool.get_connection() as conn:
            cursor = conn.connection.cursor()
            cursor.executemany(query, params_list)
            conn.connection.commit()

            logger.debug(f"Execute_many executado com sucesso: {len(params_list)} registros afetados")
            return True
    
    def execute_transaction(self, queries: List[Tuple[str, Optional[tuple]]]) -> bool:
        """Executa múltiplas queries em uma transação com retry e validações robustas.

        Args:
            queries: Lista de (query, params) tuples

        Returns:
            True se executou com sucesso
        """
        if not self.pool:
            logger.error("Pool não inicializado - execute_transaction abortado")
            self._track_error('connection_errors')
            return False

        # Validações de entrada
        if not isinstance(queries, list) or not queries:
            logger.error("Queries deve ser uma lista não vazia")
            return False

        # Validar estrutura das queries
        try:
            self._validate_queries_structure(queries)
        except ValueError as e:
            logger.error(f"Estrutura de queries inválida: {str(e)}")
            return False

        try:
            # Executar com retry automático para transações críticas
            result = self._execute_with_error_handling(
                self._execute_transaction_impl,
                queries=queries,
                operation_name="execute_transaction"
            )
            return result is not None

        except sqlite3.IntegrityError as e:
            logger.error(f"Violação de integridade na transação: {str(e)}")
            logger.error(f"Número de queries na transação: {len(queries)}")
            self._track_error('integrity_errors', e)
            return False

        except sqlite3.OperationalError as e:
            logger.error(f"Erro operacional na transação: {str(e)}")
            self._track_error('query_errors', e)
            return False

        except ValueError as e:
            logger.error(f"Erro de valor na transação: {str(e)}")
            return False

        except Exception as e:
            logger.error(f"Erro inesperado na transação: {str(e)}", exc_info=True)
            self._track_error('query_errors', e)
            return False

    def _execute_transaction_impl(self, queries: List[Tuple[str, Optional[tuple]]]) -> bool:
        """Implementação interna da transação."""
        with self.pool.get_connection() as conn:
            cursor = conn.connection.cursor()

            # Inicia transação
            cursor.execute("BEGIN TRANSACTION")

            try:
                for i, (query, params) in enumerate(queries):
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)

                    logger.debug(f"Query {i+1}/{len(queries)} na transação executada")

                conn.connection.commit()
                logger.info(f"Transação executada com sucesso: {len(queries)} queries")
                return True

            except Exception as e:
                conn.connection.rollback()
                logger.error(f"Transação revertida devido a: {str(e)}")
                raise
    
    def create_new_database(self, db_path: str, app_info: Dict[str, str]) -> bool:
        """Cria novo banco de dados com estrutura completa.
        
        Args:
            db_path: Caminho do novo banco
            app_info: Informações do aplicativo
            
        Returns:
            True se criou com sucesso
        """
        try:
            if os.path.exists(db_path):
                logger.error(f"Banco já existe: {db_path}")
                return False
            
            # Cria novo banco
            if not self.connect(db_path):
                return False
            
            # Insere informações do aplicativo
            with self.pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                
                cursor.execute("""
                    INSERT INTO app_info (key, value) VALUES (?, ?)
                """, ("created_at", datetime.now().isoformat()))
                
                for key, value in app_info.items():
                    cursor.execute("""
                        INSERT INTO app_info (key, value) VALUES (?, ?)
                    """, (key, value))
                
                conn.connection.commit()
                
            logger.info(f"Novo banco criado: {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar novo banco: {e}", exc_info=True)
            return False
    
    def get_tables(self) -> List[str]:
        """Obtém lista de tabelas no banco."""
        if not self.pool:
            return []
            
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Erro ao listar tabelas: {e}")
            return []
    
    def get_table_info(self, table: str) -> List[tuple]:
        """Obtém informações sobre uma tabela."""
        if not self.pool:
            return []
            
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"Erro ao obter info da tabela {table}: {e}")
            return []
    
    def table_exists(self, table: str) -> bool:
        """Verifica se uma tabela existe."""
        return table in self.get_tables()
    
    def get_row_count(self, table: str) -> int:
        """Obtém número de registros em uma tabela."""
        if not self.pool or not self.table_exists(table):
            return 0
            
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                return cursor.fetchone()[0]
                
        except Exception as e:
            logger.error(f"Erro ao contar registros: {e}")
            return 0
    
    def get_metrics(self) -> Optional[PoolMetrics]:
        """Obtém métricas do pool de conexões."""
        if not self.pool:
            return None
        return self.pool.get_metrics()
    
    def is_connected(self) -> bool:
        """Verifica se está conectado ao banco."""
        return self.pool is not None and self.current_db is not None
    
    def get_database_path(self) -> Optional[str]:
        """Obtém caminho do banco atual."""
        return self.current_db
    
    @contextmanager
    def get_connection(self):
        """Context manager para obter conexão do pool."""
        if not self.pool:
            raise RuntimeError("Pool não inicializado")

        with self.pool.get_connection() as conn:
            yield conn.connection

    def _execute_with_error_handling(self, func: Callable, operation_name: str, **kwargs) -> Any:
        """Executa função com tratamento de erros padronizado, retry automático e monitoring de recursos."""
        start_time = time.time()
        operation_id = f"{operation_name}_{int(start_time * 1000)}"

        # Monitoramento inicial de recursos do sistema
        pre_metrics = self.system_monitor.get_system_metrics()
        system_alerts = self.system_monitor.check_performance_alerts()

        if system_alerts:
            self._performance_metrics['system_alerts_detected'] += len(system_alerts)
            logger.warning(f"Alertas de sistema detectados antes da operação {operation_name}: {system_alerts}")

        try:
            # Usa retry automático para operações críticas
            result = self.retry_manager.execute_with_retry(func, **kwargs)

            # Monitoramento pós-execução
            execution_time = time.time() - start_time
            self._update_performance_metrics(operation_name, execution_time, pre_metrics)

            return result

        except sqlite3.OperationalError as e:
            # Verificar se é erro de conexão perdida e tentar recovery
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['connection', 'disconnected', 'timeout']):
                if self.current_db:
                    logger.warning(f"Tentando recovery automático para {operation_name} devido a: {str(e)}")
                    success = self.health_manager.attempt_connection_recovery(
                        self.pool._get_connection_for_health_check() if self.pool else None,
                        self.current_db
                    )
                    if success:
                        self._error_stats['connection_recoveries'] += 1
                        logger.info(f"Recovery automático bem-sucedido para {operation_name}")
                        return self.retry_manager.execute_with_retry(func, **kwargs)

            raise

        except Exception as e:
            # Log detalhado com contexto da operação e métricas
            execution_time = time.time() - start_time
            logger.error(
                f"Falha crítica em {operation_name}: {str(e)}, "
                f"tempo execução: {execution_time:.3f}s, "
                f"pool: {self.pool is not None}, "
                f"db: {self.current_db}, "
                f"alertas sistema: {len(system_alerts) if system_alerts else 0}"
            )
            raise

    def _update_performance_metrics(self, operation_name: str, execution_time: float, pre_metrics: Dict[str, Any]):
        """Atualiza métricas de performance com dados detalhados."""
        if operation_name in ['execute_query', 'execute_many']:
            self._performance_metrics['total_queries'] += 1

            if execution_time > 5.0:  # Query lenta (>5s)
                self._performance_metrics['slow_queries_count'] += 1
                logger.warning(f"Query lenta detectada ({execution_time:.3f}s) em {operation_name}")

            # Atualizar tempo médio
            total_queries = self._performance_metrics['total_queries']
            current_avg = self._performance_metrics['average_query_time']
            self._performance_metrics['average_query_time'] = (current_avg * (total_queries - 1) + execution_time) / total_queries

            # Atualizar tempo máximo
            if execution_time > self._performance_metrics['longest_query_time']:
                self._performance_metrics['longest_query_time'] = execution_time
                logger.info(f"Novo recorde de tempo de query: {execution_time:.3f}s")

        elif operation_name == 'execute_transaction':
            self._performance_metrics['total_transactions'] += 1

        self._performance_metrics['last_performance_check'] = datetime.now().isoformat()

    def _track_error(self, error_type: str, exception: Optional[Exception] = None):
        """Registra estatísticas de erro para monitoramento."""
        if error_type in self._error_stats:
            self._error_stats[error_type] += 1

        self._error_stats['last_error'] = str(exception) if exception else None
        self._error_stats['last_error_time'] = datetime.now()

        # Log de erro crítico se muitos erros do mesmo tipo
        threshold = 5  # Limite para alertas
        if self._error_stats[error_type] >= threshold:
            logger.warning(
                f"Muitos erros do tipo {error_type} detectados: "
                f"{self._error_stats[error_type]} ocorrências"
            )

    def _validate_params_list(self, params_list: List[tuple]):
        """Valida estrutura da lista de parâmetros para execute_many."""
        if not all(isinstance(params, (tuple, list)) for params in params_list):
            raise ValueError("Todos os parâmetros devem ser tuples ou lists")

        # Verificar consistência de tamanho
        if params_list:
            first_size = len(params_list[0])
            for i, params in enumerate(params_list[1:], 1):
                if len(params) != first_size:
                    raise ValueError(
                        f"Parâmetro {i} tem tamanho diferente: "
                        f"esperado {first_size}, encontrado {len(params)}"
                    )

    def _validate_queries_structure(self, queries: List[Tuple[str, Optional[tuple]]]):
        """Valida estrutura das queries para transação."""
        for i, query_data in enumerate(queries):
            if len(query_data) != 2:
                raise ValueError(f"Query {i} deve ter exatamente 2 elementos (query, params)")

            query, params = query_data
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"Query {i} deve ser uma string não vazia")

            if params is not None and not isinstance(params, (tuple, list)):
                raise ValueError(f"Params da query {i} deve ser tuple, list ou None")

    def _sanitize_sql(self, query: str) -> str:
        """Sanitiza query SQL para logging seguro."""
        # Remove quebras de linha e espaços extras
        sanitized = ' '.join(query.split())
        # Limita tamanho para evitar logs muito longos
        if len(sanitized) > 200:
            sanitized = sanitized[:200] + "..."
        return sanitized

    def get_error_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de erros para monitoramento."""
        return self._error_stats.copy()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtém métricas avançadas de performance."""
        current_system_metrics = self.system_monitor.get_system_metrics()
        recovery_stats = self.health_manager.get_recovery_stats()

        return {
            'performance_metrics': self._performance_metrics.copy(),
            'system_metrics': current_system_metrics,
            'recovery_stats': recovery_stats,
            'error_stats': self.get_error_stats(),
            'pool_metrics': self.get_metrics().to_dict() if self.get_metrics() else None
        }

    def check_system_health(self) -> Dict[str, Any]:
        """Verificação completa da saúde do sistema."""
        health_report = {
            'system_status': 'healthy',
            'issues': [],
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }

        # Verificar alertas de sistema
        system_alerts = self.system_monitor.check_performance_alerts()
        if system_alerts:
            health_report['issues'].extend(system_alerts)
            health_report['system_status'] = 'warning'

        # Verificar métricas de erro
        error_stats = self.get_error_stats()
        high_error_types = [k for k, v in error_stats.items()
                          if isinstance(v, int) and v >= 10 and k != 'last_error_time']

        if high_error_types:
            health_report['issues'].append(f"Alto volume de erros: {', '.join(high_error_types)}")
            health_report['recommendations'].append("Considerar verificar configuração do pool ou saúde do sistema")

        # Verificar métricas de performance
        if self._performance_metrics.get('slow_queries_count', 0) > 5:
            health_report['issues'].append("Alto número de queries lentas detectadas")
            health_report['recommendations'].append("Verificar índices e otimizar queries")

        return health_report

    def reset_error_stats(self):
        """Reseta estatísticas de erros."""
        self._error_stats = {
            'connection_errors': 0,
            'query_errors': 0,
            'integrity_errors': 0,
            'timeout_errors': 0,
            'last_error': None,
            'last_error_time': None,
            'connection_recoveries': 0,
            'system_performance_alerts': 0,
            'long_running_queries': 0
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()