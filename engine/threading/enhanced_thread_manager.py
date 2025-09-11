# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Enhanced Thread Manager
Sistema de threading aprimorado com ThreadPoolExecutor, comunicação thread-safe e gerenciamento de tarefas
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from queue import Queue, PriorityQueue, Empty
from typing import Any, Callable, Dict, List, Optional, Union, Set, TypeVar
from functools import wraps
import weakref
from collections import defaultdict, deque
import psutil
import gc
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

T = TypeVar('T')

class TaskPriority(Enum):
    """Prioridades de tarefas."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0

class TaskStatus(Enum):
    """Status de tarefas."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass
class TaskResult:
    """Resultado de uma tarefa."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    @property
    def is_success(self) -> bool:
        """Verifica se a tarefa foi bem-sucedida."""
        return self.status == TaskStatus.COMPLETED and self.error is None
    
    @property
    def is_finished(self) -> bool:
        """Verifica se a tarefa terminou (sucesso, falha ou cancelada)."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

@dataclass
class Task:
    """Representa uma tarefa a ser executada."""
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    callback: Optional[Callable[[TaskResult], None]] = None
    timeout: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other):
        """Comparação para PriorityQueue."""
        if not isinstance(other, Task):
            return NotImplemented
        return (self.priority.value, self.created_at) < (other.priority.value, other.created_at)

class ThreadSafeEventEmitter:
    """Emissor de eventos thread-safe."""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def on(self, event: str, callback: Callable):
        """Registra um listener para um evento."""
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)
    
    def off(self, event: str, callback: Callable):
        """Remove um listener de um evento."""
        with self._lock:
            if event in self._listeners:
                try:
                    self._listeners[event].remove(callback)
                    if not self._listeners[event]:
                        del self._listeners[event]
                except ValueError:
                    pass
    
    def emit(self, event: str, *args, **kwargs):
        """Emite um evento para todos os listeners."""
        with self._lock:
            listeners = self._listeners.get(event, []).copy()
        
        for listener in listeners:
            try:
                listener(*args, **kwargs)
            except Exception as e:
                logger.error(f"Erro no listener do evento '{event}': {e}")

class TaskQueue:
    """Fila de tarefas com prioridade e thread-safe."""
    
    def __init__(self, maxsize: int = 0):
        self._queue = PriorityQueue(maxsize=maxsize)
        self._task_count = 0
        self._lock = threading.Lock()
    
    def put(self, task: Task, block: bool = True, timeout: Optional[float] = None):
        """Adiciona uma tarefa à fila."""
        self._queue.put(task, block=block, timeout=timeout)
        with self._lock:
            self._task_count += 1
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Task:
        """Obtém uma tarefa da fila."""
        return self._queue.get(block=block, timeout=timeout)
    
    def task_done(self):
        """Marca uma tarefa como concluída."""
        self._queue.task_done()
    
    def qsize(self) -> int:
        """Retorna o tamanho da fila."""
        return self._queue.qsize()
    
    def empty(self) -> bool:
        """Verifica se a fila está vazia."""
        return self._queue.empty()
    
    @property
    def total_tasks_added(self) -> int:
        """Retorna o total de tarefas adicionadas."""
        with self._lock:
            return self._task_count

class AdaptiveThreadPool:
    """Pool de threads adaptativo que ajusta o número de workers baseado na carga."""
    
    def __init__(self, min_workers: int = 2, max_workers: int = 32, 
                 scale_factor: float = 1.5, scale_down_delay: float = 30.0):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_factor = scale_factor
        self.scale_down_delay = scale_down_delay
        
        self._current_workers = min_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._last_scale_time = datetime.now()
        self._lock = threading.RLock()
        
        self._create_executor()
    
    def _create_executor(self):
        """Cria novo executor com número atual de workers."""
        if self._executor:
            self._executor.shutdown(wait=False)
        
        self._executor = ThreadPoolExecutor(
            max_workers=self._current_workers,
            thread_name_prefix="AdaptiveThread"
        )
        
        logger.debug(f"Pool adaptativo criado com {self._current_workers} workers")
    
    def scale_up(self, target_workers: Optional[int] = None):
        """Aumenta o número de workers."""
        with self._lock:
            if target_workers is None:
                target_workers = min(self.max_workers, 
                                   int(self._current_workers * self.scale_factor))
            
            if target_workers > self._current_workers:
                self._current_workers = min(target_workers, self.max_workers)
                self._create_executor()
                self._last_scale_time = datetime.now()
                logger.info(f"Pool escalado para {self._current_workers} workers")
    
    def scale_down(self, target_workers: Optional[int] = None):
        """Diminui o número de workers."""
        with self._lock:
            # Verifica delay para scale down
            if (datetime.now() - self._last_scale_time).total_seconds() < self.scale_down_delay:
                return
            
            if target_workers is None:
                target_workers = max(self.min_workers, 
                                   int(self._current_workers / self.scale_factor))
            
            if target_workers < self._current_workers:
                self._current_workers = max(target_workers, self.min_workers)
                self._create_executor()
                self._last_scale_time = datetime.now()
                logger.info(f"Pool reduzido para {self._current_workers} workers")
    
    def submit(self, fn, *args, **kwargs) -> Future:
        """Submete tarefa ao pool."""
        return self._executor.submit(fn, *args, **kwargs)
    
    def shutdown(self, wait: bool = True):
        """Encerra o pool."""
        if self._executor:
            self._executor.shutdown(wait=wait)
    
    @property
    def current_workers(self) -> int:
        return self._current_workers

class PerformanceMonitor:
    """Monitor de performance do sistema de threading."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._execution_times = deque(maxlen=window_size)
        self._cpu_usage_history = deque(maxlen=window_size)
        self._memory_usage_history = deque(maxlen=window_size)
        self._lock = threading.RLock()
        
        # Thread de monitoramento
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Inicia thread de monitoramento."""
        self._monitor_thread = threading.Thread(
            target=self._monitor_system,
            name="PerformanceMonitor",
            daemon=True
        )
        self._monitor_thread.start()
    
    def _monitor_system(self):
        """Monitora uso de CPU e memória."""
        while not self._stop_monitoring.wait(1.0):
            try:
                cpu_percent = psutil.cpu_percent(interval=None)
                memory_info = psutil.virtual_memory()
                
                with self._lock:
                    self._cpu_usage_history.append(cpu_percent)
                    self._memory_usage_history.append(memory_info.percent)
                    
            except Exception as e:
                logger.warning(f"Erro no monitoramento de performance: {e}")
    
    def record_execution_time(self, execution_time: float):
        """Registra tempo de execução de uma tarefa."""
        with self._lock:
            self._execution_times.append(execution_time)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de performance."""
        with self._lock:
            metrics = {
                'avg_execution_time': 0.0,
                'max_execution_time': 0.0,
                'min_execution_time': 0.0,
                'avg_cpu_usage': 0.0,
                'max_cpu_usage': 0.0,
                'avg_memory_usage': 0.0,
                'max_memory_usage': 0.0,
                'samples_count': len(self._execution_times)
            }
            
            if self._execution_times:
                metrics['avg_execution_time'] = sum(self._execution_times) / len(self._execution_times)
                metrics['max_execution_time'] = max(self._execution_times)
                metrics['min_execution_time'] = min(self._execution_times)
            
            if self._cpu_usage_history:
                metrics['avg_cpu_usage'] = sum(self._cpu_usage_history) / len(self._cpu_usage_history)
                metrics['max_cpu_usage'] = max(self._cpu_usage_history)
            
            if self._memory_usage_history:
                metrics['avg_memory_usage'] = sum(self._memory_usage_history) / len(self._memory_usage_history)
                metrics['max_memory_usage'] = max(self._memory_usage_history)
            
            return metrics
    
    def should_scale_up(self, threshold_cpu: float = 80.0, threshold_queue: int = 10) -> bool:
        """Determina se deve aumentar o pool de threads."""
        with self._lock:
            if not self._cpu_usage_history:
                return False
            
            recent_cpu = list(self._cpu_usage_history)[-5:]  # Últimas 5 amostras
            avg_recent_cpu = sum(recent_cpu) / len(recent_cpu)
            
            return avg_recent_cpu > threshold_cpu
    
    def should_scale_down(self, threshold_cpu: float = 30.0, min_idle_time: float = 60.0) -> bool:
        """Determina se deve diminuir o pool de threads."""
        with self._lock:
            if not self._cpu_usage_history:
                return False
            
            recent_cpu = list(self._cpu_usage_history)[-10:]  # Últimas 10 amostras
            avg_recent_cpu = sum(recent_cpu) / len(recent_cpu)
            
            return avg_recent_cpu < threshold_cpu
    
    def stop(self):
        """Para o monitoramento."""
        self._stop_monitoring.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

class LoadBalancer:
    """Balanceador de carga para distribuição inteligente de tarefas."""
    
    def __init__(self):
        self._worker_loads: Dict[str, float] = {}
        self._worker_last_task: Dict[str, datetime] = {}
        self._lock = threading.RLock()
    
    def update_worker_load(self, worker_id: str, load: float):
        """Atualiza carga de um worker."""
        with self._lock:
            self._worker_loads[worker_id] = load
            self._worker_last_task[worker_id] = datetime.now()
    
    def get_best_worker(self) -> Optional[str]:
        """Retorna o worker com menor carga."""
        with self._lock:
            if not self._worker_loads:
                return None
            
            # Remove workers inativos (mais de 5 minutos sem tarefa)
            cutoff_time = datetime.now() - timedelta(minutes=5)
            inactive_workers = [
                worker_id for worker_id, last_task in self._worker_last_task.items()
                if last_task < cutoff_time
            ]
            
            for worker_id in inactive_workers:
                self._worker_loads.pop(worker_id, None)
                self._worker_last_task.pop(worker_id, None)
            
            if not self._worker_loads:
                return None
            
            # Retorna worker com menor carga
            return min(self._worker_loads.items(), key=lambda x: x[1])[0]
    
    def get_load_distribution(self) -> Dict[str, float]:
        """Retorna distribuição de carga atual."""
        with self._lock:
            return self._worker_loads.copy()

class EnhancedThreadManager:
    """Gerenciador de threads aprimorado com pool adaptativo e monitoramento."""
    
    def __init__(
        self,
        min_workers: int = 2,
        max_workers: Optional[int] = None,
        thread_name_prefix: str = "EnhancedThread",
        task_queue_size: int = 1000,
        enable_metrics: bool = True,
        enable_adaptive_scaling: bool = True,
        enable_performance_monitoring: bool = True
    ):
        import os
        self.min_workers = min_workers
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) * 4)
        self.thread_name_prefix = thread_name_prefix
        self.enable_metrics = enable_metrics
        self.enable_adaptive_scaling = enable_adaptive_scaling
        self.enable_performance_monitoring = enable_performance_monitoring
        
        # Pool adaptativo
        self._adaptive_pool = AdaptiveThreadPool(
            min_workers=self.min_workers,
            max_workers=self.max_workers
        )
        
        # Monitor de performance
        self._performance_monitor: Optional[PerformanceMonitor] = None
        if self.enable_performance_monitoring:
            self._performance_monitor = PerformanceMonitor()
        
        # Balanceador de carga
        self._load_balancer = LoadBalancer()
        
        # Estado
        self._is_shutdown = False
        
        # Fila de tarefas
        self._task_queue = TaskQueue(maxsize=task_queue_size)
        
        # Controle de tarefas
        self._active_tasks: Dict[str, Future] = {}
        self._task_results: Dict[str, TaskResult] = {}
        self._tasks_lock = threading.RLock()
        
        # Event emitter
        self._event_emitter = ThreadSafeEventEmitter()
        
        # Métricas aprimoradas
        self._metrics = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_cancelled': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0,
            'peak_concurrent_tasks': 0,
            'current_active_tasks': 0,
            'pool_scale_ups': 0,
            'pool_scale_downs': 0,
            'current_pool_size': self.min_workers,
            'queue_wait_time': 0.0,
            'throughput_per_second': 0.0
        }
        self._metrics_lock = threading.Lock()
        
        # Worker threads para processar fila
        self._queue_workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        
        # Thread de auto-scaling
        self._scaling_thread: Optional[threading.Thread] = None
        if self.enable_adaptive_scaling:
            self._start_auto_scaling()
        
        # Inicializa
        self._start()
    
    def _start_auto_scaling(self):
        """Inicia thread de auto-scaling."""
        self._scaling_thread = threading.Thread(
            target=self._auto_scaling_worker,
            name="AutoScalingWorker",
            daemon=True
        )
        self._scaling_thread.start()
        logger.info("Auto-scaling habilitado")
    
    def _auto_scaling_worker(self):
        """Worker que monitora e ajusta o pool automaticamente."""
        while not self._stop_event.wait(10.0):  # Verifica a cada 10 segundos
            try:
                if not self._performance_monitor:
                    continue
                
                # Verifica se deve escalar
                if self._performance_monitor.should_scale_up():
                    current_queue_size = self._task_queue.qsize()
                    if current_queue_size > 5:  # Fila com muitas tarefas
                        self._adaptive_pool.scale_up()
                        with self._metrics_lock:
                            self._metrics['pool_scale_ups'] += 1
                            self._metrics['current_pool_size'] = self._adaptive_pool.current_workers
                        
                        self._event_emitter.emit('pool_scaled_up', {
                            'new_size': self._adaptive_pool.current_workers,
                            'queue_size': current_queue_size
                        })
                
                elif self._performance_monitor.should_scale_down():
                    current_queue_size = self._task_queue.qsize()
                    if current_queue_size < 2:  # Fila quase vazia
                        self._adaptive_pool.scale_down()
                        with self._metrics_lock:
                            self._metrics['pool_scale_downs'] += 1
                            self._metrics['current_pool_size'] = self._adaptive_pool.current_workers
                        
                        self._event_emitter.emit('pool_scaled_down', {
                            'new_size': self._adaptive_pool.current_workers,
                            'queue_size': current_queue_size
                        })
                
                # Força garbage collection periodicamente
                if self._metrics['tasks_completed'] % 100 == 0:
                    gc.collect()
                    
            except Exception as e:
                logger.warning(f"Erro no auto-scaling: {e}")
    
    def _start(self):
        """Inicia o gerenciador de threads."""
        # Inicia workers da fila
        num_queue_workers = min(4, self.max_workers)
        for i in range(num_queue_workers):
            worker = threading.Thread(
                target=self._queue_worker,
                name=f"{self.thread_name_prefix}-QueueWorker-{i}",
                daemon=True
            )
            worker.start()
            self._queue_workers.append(worker)
        
        logger.info(f"Enhanced Thread Manager iniciado com {self.max_workers} workers")
    
    def _queue_worker(self):
        """Worker que processa a fila de tarefas."""
        while not self._stop_event.is_set():
            try:
                # Obtém tarefa da fila
                task = self._task_queue.get(timeout=1.0)
                
                if task is None:  # Sinal de parada
                    break
                
                # Submete tarefa ao executor
                self._submit_task_to_executor(task)
                
                # Marca tarefa como processada na fila
                self._task_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Erro no queue worker: {e}")
    
    def _submit_task_to_executor(self, task: Task):
        """Submete uma tarefa ao pool adaptativo."""
        try:
            # Registra tempo de entrada na fila
            queue_start_time = datetime.now()
            
            # Cria wrapper para a tarefa
            def task_wrapper():
                return self._execute_task(task, queue_start_time)
            
            # Submete ao pool adaptativo
            future = self._adaptive_pool.submit(task_wrapper)
            
            # Registra tarefa ativa
            with self._tasks_lock:
                self._active_tasks[task.id] = future
            
            # Atualiza métricas
            with self._metrics_lock:
                self._metrics['current_active_tasks'] = len(self._active_tasks)
                self._metrics['peak_concurrent_tasks'] = max(
                    self._metrics['peak_concurrent_tasks'],
                    self._metrics['current_active_tasks']
                )
                self._metrics['current_pool_size'] = self._adaptive_pool.current_workers
            
            # Adiciona callback para limpeza
            future.add_done_callback(lambda f: self._task_completed(task.id, f))
            
        except Exception as e:
            logger.error(f"Erro ao submeter tarefa {task.id}: {e}")
            self._mark_task_failed(task.id, e)
    
    def _execute_task(self, task: Task, queue_start_time: datetime) -> TaskResult:
        """Executa uma tarefa com monitoramento aprimorado."""
        execution_start_time = datetime.now()
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.RUNNING,
            start_time=execution_start_time
        )
        
        # Calcula tempo de espera na fila
        queue_wait_time = (execution_start_time - queue_start_time).total_seconds()
        
        # Atualiza métricas de fila
        with self._metrics_lock:
            if self._metrics['tasks_submitted'] > 0:
                self._metrics['queue_wait_time'] = (
                    (self._metrics['queue_wait_time'] * self._metrics['tasks_submitted'] + queue_wait_time) /
                    (self._metrics['tasks_submitted'] + 1)
                )
            else:
                self._metrics['queue_wait_time'] = queue_wait_time
        
        try:
            # Emite evento de início
            self._event_emitter.emit('task_started', task, result)
            
            # Executa a função com timeout se especificado
            if task.timeout:
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Task {task.id} timed out after {task.timeout} seconds")

                # Define o handler de timeout
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(task.timeout))

                try:
                    function_result = task.func(*task.args, **task.kwargs)
                except TimeoutError as e:
                    logger.warning(f"Tarefa {task.id} cancelada por timeout: {e}")
                    raise
                finally:
                    # Restaura o handler original e desarma o alarme
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                function_result = task.func(*task.args, **task.kwargs)
            
            # Sucesso
            end_time = datetime.now()
            result.status = TaskStatus.COMPLETED
            result.result = function_result
            result.end_time = end_time
            result.execution_time = (end_time - execution_start_time).total_seconds()
            
            # Registra no monitor de performance
            if self._performance_monitor:
                self._performance_monitor.record_execution_time(result.execution_time)
            
            # Atualiza balanceador de carga
            worker_id = threading.current_thread().name
            self._load_balancer.update_worker_load(worker_id, result.execution_time)
            
            # Atualiza métricas
            with self._metrics_lock:
                self._metrics['tasks_completed'] += 1
                self._metrics['total_execution_time'] += result.execution_time
                self._metrics['average_execution_time'] = (
                    self._metrics['total_execution_time'] / 
                    self._metrics['tasks_completed']
                )
            
            # Emite evento de sucesso
            self._event_emitter.emit('task_completed', task, result)
            
        except Exception as e:
            # Falha
            end_time = datetime.now()
            result.status = TaskStatus.FAILED
            result.error = e
            result.end_time = end_time
            result.execution_time = (end_time - execution_start_time).total_seconds()
            
            # Atualiza métricas
            with self._metrics_lock:
                self._metrics['tasks_failed'] += 1
            
            # Emite evento de falha
            self._event_emitter.emit('task_failed', task, result)
            
            logger.error(f"Erro na execução da tarefa {task.id}: {e}")
        
        # Armazena resultado
        with self._tasks_lock:
            self._task_results[task.id] = result
        
        # Chama callback se definido
        if task.callback:
            try:
                task.callback(result)
            except Exception as e:
                logger.error(f"Erro no callback da tarefa {task.id}: {e}")
        
        return result
    
    def _task_completed(self, task_id: str, future: Future):
        """Callback chamado quando uma tarefa é concluída."""
        with self._tasks_lock:
            # Remove da lista de tarefas ativas
            self._active_tasks.pop(task_id, None)
            
            # Atualiza métricas
            with self._metrics_lock:
                self._metrics['current_active_tasks'] = len(self._active_tasks)
    
    def _mark_task_failed(self, task_id: str, error: Exception):
        """Marca uma tarefa como falhada."""
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=error,
            end_time=datetime.now()
        )
        
        with self._tasks_lock:
            self._task_results[task_id] = result
        
        with self._metrics_lock:
            self._metrics['tasks_failed'] += 1
    
    def submit_task(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        callback: Optional[Callable[[TaskResult], None]] = None,
        timeout: Optional[float] = None,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Submete uma tarefa para execução.
        
        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            priority: Prioridade da tarefa
            callback: Callback chamado quando a tarefa termina
            timeout: Timeout para a tarefa
            task_id: ID personalizado da tarefa
            **kwargs: Argumentos nomeados
            
        Returns:
            ID da tarefa
        """
        if self._is_shutdown:
            raise RuntimeError("Thread manager foi encerrado")
        
        # Gera ID se não fornecido
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Cria tarefa
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            callback=callback,
            timeout=timeout
        )
        
        # Adiciona à fila
        try:
            self._task_queue.put(task, timeout=5.0)  # Timeout para evitar bloqueio
            
            # Atualiza métricas
            with self._metrics_lock:
                self._metrics['tasks_submitted'] += 1
            
            # Emite evento
            self._event_emitter.emit('task_submitted', task)
            
            logger.debug(f"Tarefa {task_id} submetida com prioridade {priority.name}")
            return task_id
            
        except Exception as e:
            logger.error(f"Erro ao submeter tarefa: {e}")
            raise
    
    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Obtém o resultado de uma tarefa.
        
        Args:
            task_id: ID da tarefa
            timeout: Timeout para aguardar resultado
            
        Returns:
            Resultado da tarefa ou None se não encontrada
        """
        start_time = time.time()
        
        while True:
            with self._tasks_lock:
                if task_id in self._task_results:
                    return self._task_results[task_id]
            
            # Verifica timeout
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            # Aguarda um pouco antes de verificar novamente
            time.sleep(0.1)
    
    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> bool:
        """Aguarda uma tarefa terminar.
        
        Args:
            task_id: ID da tarefa
            timeout: Timeout para aguardar
            
        Returns:
            True se a tarefa terminou, False se timeout
        """
        result = self.get_task_result(task_id, timeout)
        return result is not None and result.is_finished
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancela uma tarefa.
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            True se cancelada com sucesso
        """
        with self._tasks_lock:
            # Verifica se está ativa
            if task_id in self._active_tasks:
                future = self._active_tasks[task_id]
                if future.cancel():
                    # Marca como cancelada
                    result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                        end_time=datetime.now()
                    )
                    self._task_results[task_id] = result
                    
                    # Atualiza métricas
                    with self._metrics_lock:
                        self._metrics['tasks_cancelled'] += 1
                    
                    logger.info(f"Tarefa {task_id} cancelada")
                    return True
        
        return False
    
    def get_active_tasks(self) -> List[str]:
        """Retorna lista de IDs de tarefas ativas."""
        with self._tasks_lock:
            return list(self._active_tasks.keys())
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas completas do gerenciador."""
        with self._metrics_lock:
            metrics = self._metrics.copy()
        
        with self._tasks_lock:
            metrics.update({
                'queue_size': self._task_queue.qsize(),
                'total_tasks_queued': self._task_queue.total_tasks_added,
                'active_tasks_count': len(self._active_tasks),
                'completed_tasks_count': len(self._task_results),
                'is_shutdown': self._is_shutdown,
                'min_pool_size': self._adaptive_pool.min_workers,
                'max_pool_size': self._adaptive_pool.max_workers
            })
        
        # Adiciona métricas de performance se disponível
        if self._performance_monitor:
            perf_metrics = self._performance_monitor.get_performance_metrics()
            metrics['performance'] = perf_metrics
        
        # Adiciona distribuição de carga
        load_distribution = self._load_balancer.get_load_distribution()
        metrics['load_distribution'] = load_distribution
        
        return metrics
    
    def get_pool_info(self) -> Dict[str, Any]:
        """Retorna informações detalhadas do pool de threads."""
        return {
            'current_workers': self._adaptive_pool.current_workers,
            'min_workers': self._adaptive_pool.min_workers,
            'max_workers': self._adaptive_pool.max_workers,
            'scale_factor': self._adaptive_pool.scale_factor,
            'scale_down_delay': self._adaptive_pool.scale_down_delay,
            'adaptive_scaling_enabled': self.enable_adaptive_scaling,
            'performance_monitoring_enabled': self.enable_performance_monitoring
        }
    
    def force_scale_up(self, target_workers: Optional[int] = None) -> bool:
        """Força o aumento do pool de threads."""
        try:
            self._adaptive_pool.scale_up(target_workers)
            with self._metrics_lock:
                self._metrics['pool_scale_ups'] += 1
                self._metrics['current_pool_size'] = self._adaptive_pool.current_workers
            
            self._event_emitter.emit('pool_manually_scaled_up', {
                'new_size': self._adaptive_pool.current_workers,
                'target_workers': target_workers
            })
            
            logger.info(f"Pool manualmente escalado para {self._adaptive_pool.current_workers} workers")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escalar pool: {e}")
            return False
    
    def force_scale_down(self, target_workers: Optional[int] = None) -> bool:
        """Força a redução do pool de threads."""
        try:
            self._adaptive_pool.scale_down(target_workers)
            with self._metrics_lock:
                self._metrics['pool_scale_downs'] += 1
                self._metrics['current_pool_size'] = self._adaptive_pool.current_workers
            
            self._event_emitter.emit('pool_manually_scaled_down', {
                'new_size': self._adaptive_pool.current_workers,
                'target_workers': target_workers
            })
            
            logger.info(f"Pool manualmente reduzido para {self._adaptive_pool.current_workers} workers")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao reduzir pool: {e}")
            return False
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Gera relatório completo de performance."""
        metrics = self.get_metrics()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tasks': metrics['tasks_submitted'],
                'completed_tasks': metrics['tasks_completed'],
                'failed_tasks': metrics['tasks_failed'],
                'success_rate': (
                    metrics['tasks_completed'] / max(1, metrics['tasks_submitted']) * 100
                ),
                'average_execution_time': metrics['average_execution_time'],
                'throughput_per_second': metrics['throughput_per_second'],
                'current_pool_size': metrics['current_pool_size']
            },
            'pool_scaling': {
                'scale_ups': metrics['pool_scale_ups'],
                'scale_downs': metrics['pool_scale_downs'],
                'current_size': metrics['current_pool_size'],
                'min_size': metrics['min_pool_size'],
                'max_size': metrics['max_pool_size']
            },
            'queue_performance': {
                'current_queue_size': metrics['queue_size'],
                'average_wait_time': metrics['queue_wait_time']
            }
        }
        
        # Adiciona métricas de performance do sistema se disponível
        if 'performance' in metrics:
            report['system_performance'] = metrics['performance']
        
        # Adiciona distribuição de carga
        if 'load_distribution' in metrics:
            report['load_distribution'] = metrics['load_distribution']
        
        return report
    
    def on(self, event: str, callback: Callable):
        """Registra listener para eventos.
        
        Eventos disponíveis:
        - task_submitted: Quando uma tarefa é submetida
        - task_started: Quando uma tarefa inicia execução
        - task_completed: Quando uma tarefa é concluída com sucesso
        - task_failed: Quando uma tarefa falha
        """
        self._event_emitter.on(event, callback)
    
    def off(self, event: str, callback: Callable):
        """Remove listener de eventos."""
        self._event_emitter.off(event, callback)
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """Encerra o gerenciador de threads.
        
        Args:
            wait: Se deve aguardar tarefas terminarem
            timeout: Timeout para aguardar
        """
        if self._is_shutdown:
            return
        
        logger.info("Encerrando Enhanced Thread Manager...")
        self._is_shutdown = True
        
        # Para workers da fila
        self._stop_event.set()
        
        # Não adiciona None na fila, apenas sinaliza parada
        # Os workers vão parar quando _stop_event for setado
        
        # Aguarda workers da fila
        for worker in self._queue_workers:
            worker.join(timeout=5.0)
        
        # Encerra pool adaptativo
        self._adaptive_pool.shutdown(wait=wait)
        
        # Para thread de auto-scaling
        if self._scaling_thread:
            self._scaling_thread.join(timeout=5.0)
        
        # Para monitor de performance
        if self._performance_monitor:
            self._performance_monitor.stop()
        
        logger.info("Enhanced Thread Manager encerrado")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
    
    def __del__(self):
        """Destructor."""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass

# Decorators utilitários
def async_task(priority: TaskPriority = TaskPriority.NORMAL, timeout: Optional[float] = None):
    """Decorator para executar função como tarefa assíncrona."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtém thread manager do contexto ou cria um global
            thread_manager = getattr(wrapper, '_thread_manager', None)
            if not thread_manager:
                # Cria um gerenciador global se não existir
                if not hasattr(async_task, '_global_manager'):
                    async_task._global_manager = EnhancedThreadManager()
                thread_manager = async_task._global_manager
            
            return thread_manager.submit_task(
                func, *args, priority=priority, timeout=timeout, **kwargs
            )
        
        # Permite definir thread manager personalizado
        def set_thread_manager(manager: EnhancedThreadManager):
            wrapper._thread_manager = manager
        
        wrapper.set_thread_manager = set_thread_manager
        return wrapper
    
    return decorator

def thread_safe(func: Callable) -> Callable:
    """Decorator para tornar função thread-safe com lock."""
    lock = threading.RLock()
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    
    return wrapper