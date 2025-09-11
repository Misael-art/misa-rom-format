#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Gerenciador de Tarefas
Responsável por gerenciar tarefas assíncronas e operações em segundo plano
"""

import threading
import queue
import time
import uuid
import logging
import traceback
from typing import Dict, List, Callable, Any, Optional, Tuple

# Logger
logger = logging.getLogger(__name__)

class Task:
    """
    Representa uma tarefa assíncrona a ser executada.
    """
    
    def __init__(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_progress: Optional[Callable] = None
    ):
        """
        Inicializa uma tarefa.
        
        Args:
            func: Função a ser executada
            args: Argumentos posicionais para a função
            kwargs: Argumentos nomeados para a função
            on_success: Callback a ser chamado em caso de sucesso
            on_error: Callback a ser chamado em caso de erro
            on_complete: Callback a ser chamado ao completar (sucesso ou erro)
            on_progress: Callback para reportar progresso
        """
        self.id = str(uuid.uuid4())
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.on_success = on_success
        self.on_error = on_error
        self.on_complete = on_complete
        self.on_progress = on_progress
        self.result = None
        self.error = None
        self.traceback = None
        self.start_time = None
        self.end_time = None
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.progress = 0.0
        self.cancellation_requested = False
    
    def run(self) -> None:
        """
        Executa a tarefa, gerenciando os callbacks e capturando erros.
        """
        if self.cancellation_requested:
            self.status = "cancelled"
            if self.on_complete:
                self.on_complete(self)
            return
        
        self.start_time = time.time()
        self.status = "running"
        
        try:
            # Se a função aceita um callback de progresso, passa-o como argumento
            if "progress_callback" in self.kwargs and self.on_progress:
                original_kwargs = self.kwargs.copy()
                
                # Cria um wrapper para o callback de progresso
                def progress_wrapper(percent, message=None, status=None):
                    if self.cancellation_requested:
                        return False
                    
                    self.progress = percent
                    self.on_progress(self, percent, message, status)
                    return True
                
                self.kwargs["progress_callback"] = progress_wrapper
            
            # Executa a função
            self.result = self.func(*self.args, **self.kwargs)
            self.status = "completed"
            
            # Chama o callback de sucesso
            if self.on_success:
                self.on_success(self, self.result)
                
        except Exception as e:
            self.error = e
            self.traceback = traceback.format_exc()
            self.status = "failed"
            
            # Chama o callback de erro
            if self.on_error:
                self.on_error(self, self.error, self.traceback)
                
            logger.error(f"Tarefa {self.id} falhou: {e}\n{self.traceback}")
            
        finally:
            self.end_time = time.time()
            
            # Chama o callback de conclusão
            if self.on_complete:
                self.on_complete(self)
    
    def request_cancellation(self) -> None:
        """
        Solicita o cancelamento da tarefa.
        
        Nota: A tarefa precisa verificar periodicamente o atributo
        cancellation_requested para responder ao cancelamento.
        """
        self.cancellation_requested = True
        logger.info(f"Solicitação de cancelamento para a tarefa {self.id}")
    
    def get_duration(self) -> Optional[float]:
        """
        Retorna a duração da tarefa em segundos.
        
        Returns:
            Duração em segundos ou None se a tarefa ainda não foi concluída
        """
        if self.start_time is None:
            return None
        
        end = self.end_time or time.time()
        return end - self.start_time
    
    def __str__(self) -> str:
        """
        Retorna uma representação string da tarefa.
        
        Returns:
            String representando a tarefa
        """
        duration = self.get_duration()
        duration_str = f"{duration:.2f}s" if duration is not None else "N/A"
        
        return (f"Task {self.id} - Status: {self.status}, "
                f"Progress: {self.progress:.1f}%, Duration: {duration_str}")


class TaskManager:
    """
    Gerencia a execução de tarefas assíncronas.
    
    Implementa um padrão de pool de threads para executar tarefas em segundo plano
    enquanto mantém a interface responsiva.
    """
    
    # Instância singleton
    _instance = None
    
    def __new__(cls, max_workers: int = 4, gui_thread=None):
        """
        Cria uma instância singleton do gerenciador de tarefas.
        
        Args:
            max_workers: Número máximo de threads de trabalho
            gui_thread: Thread da interface gráfica (para callbacks)
            
        Returns:
            A instância do gerenciador de tarefas
        """
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_workers: int = 4, gui_thread=None):
        """
        Inicializa o gerenciador de tarefas se ainda não foi inicializado.
        
        Args:
            max_workers: Número máximo de threads de trabalho
            gui_thread: Thread da interface gráfica (para callbacks)
        """
        if not self._initialized:
            self.max_workers = max_workers
            self.gui_thread = gui_thread
            
            self.task_queue = queue.Queue()
            self.active_tasks: Dict[str, Task] = {}
            self.completed_tasks: Dict[str, Task] = {}
            self.workers: List[threading.Thread] = []
            self.running = True
            
            # Inicia os workers
            self._start_workers()
            
            self._initialized = True
    
    def _start_workers(self) -> None:
        """
        Inicia as threads de trabalho.
        """
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"TaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
        logger.info(f"Iniciados {self.max_workers} workers para execução de tarefas")
    
    def _worker_thread(self) -> None:
        """
        Função executada por cada thread de trabalho.
        Pega tarefas da fila e as executa.
        """
        while self.running:
            try:
                # Pega uma tarefa da fila (com timeout para poder checar self.running)
                task = self.task_queue.get(timeout=0.5)
                
                # Adiciona a tarefa às tarefas ativas
                self.active_tasks[task.id] = task
                
                # Executa a tarefa
                task.run()
                
                # Remove a tarefa das tarefas ativas e a adiciona às completadas
                if task.id in self.active_tasks:
                    del self.active_tasks[task.id]
                self.completed_tasks[task.id] = task
                
                # Marca a tarefa como concluída na fila
                self.task_queue.task_done()
                
            except queue.Empty:
                # Fila vazia, continua o loop
                continue
            except Exception as e:
                logger.exception(f"Erro no worker thread: {e}")
    
    def schedule(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_progress: Optional[Callable] = None
    ) -> Task:
        """
        Agenda uma tarefa para execução.
        
        Args:
            func: Função a ser executada
            args: Argumentos posicionais para a função
            kwargs: Argumentos nomeados para a função
            on_success: Callback a ser chamado em caso de sucesso
            on_error: Callback a ser chamado em caso de erro
            on_complete: Callback a ser chamado ao completar (sucesso ou erro)
            on_progress: Callback para reportar progresso
            
        Returns:
            A tarefa agendada
        """
        # Prepara os callbacks para executar na thread da UI se necessário
        wrapped_callbacks = self._wrap_callbacks_for_gui_thread(
            on_success, on_error, on_complete, on_progress
        )
        
        # Cria a tarefa
        task = Task(
            func,
            args,
            kwargs,
            wrapped_callbacks[0],
            wrapped_callbacks[1],
            wrapped_callbacks[2],
            wrapped_callbacks[3]
        )
        
        # Adiciona a tarefa à fila
        self.task_queue.put(task)
        
        logger.info(f"Tarefa {task.id} agendada para execução")
        return task
    
    def _wrap_callbacks_for_gui_thread(
        self,
        on_success,
        on_error,
        on_complete,
        on_progress
    ) -> Tuple[Optional[Callable], ...]:
        """
        Envolve os callbacks para serem executados na thread da GUI.
        
        Args:
            on_success: Callback de sucesso original
            on_error: Callback de erro original
            on_complete: Callback de conclusão original
            on_progress: Callback de progresso original
            
        Returns:
            Tupla de callbacks envolvidos
        """
        wrapped_on_success = None
        wrapped_on_error = None
        wrapped_on_complete = None
        wrapped_on_progress = None
        
        # Se temos uma thread de GUI e uma função after para agendar na thread principal
        if self.gui_thread and hasattr(self.gui_thread, "after"):
            # Envolve o callback de sucesso
            if on_success:
                def wrapped_success(task, result):
                    self.gui_thread.after(0, lambda: on_success(task, result))
                wrapped_on_success = wrapped_success
            
            # Envolve o callback de erro
            if on_error:
                def wrapped_error(task, error, tb):
                    self.gui_thread.after(0, lambda: on_error(task, error, tb))
                wrapped_on_error = wrapped_error
            
            # Envolve o callback de conclusão
            if on_complete:
                def wrapped_complete(task):
                    self.gui_thread.after(0, lambda: on_complete(task))
                wrapped_on_complete = wrapped_complete
            
            # Envolve o callback de progresso
            if on_progress:
                def wrapped_progress(task, percent, message, status):
                    self.gui_thread.after(0, lambda: on_progress(task, percent, message, status))
                wrapped_on_progress = wrapped_progress
        else:
            # Se não temos uma thread de GUI, usamos os callbacks originais
            wrapped_on_success = on_success
            wrapped_on_error = on_error
            wrapped_on_complete = on_complete
            wrapped_on_progress = on_progress
        
        return wrapped_on_success, wrapped_on_error, wrapped_on_complete, wrapped_on_progress
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Obtém uma tarefa pelo ID.
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            A tarefa encontrada ou None
        """
        # Procura nas tarefas ativas
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        
        # Procura nas tarefas completadas
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Solicita o cancelamento de uma tarefa.
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            True se a tarefa foi encontrada e o cancelamento foi solicitado
        """
        task = self.get_task(task_id)
        if task:
            task.request_cancellation()
            return True
        return False
    
    def cancel_all_tasks(self) -> None:
        """
        Solicita o cancelamento de todas as tarefas ativas.
        """
        for task_id in list(self.active_tasks.keys()):
            self.cancel_task(task_id)
    
    def get_active_tasks(self) -> List[Task]:
        """
        Retorna uma lista de todas as tarefas ativas.
        
        Returns:
            Lista de tarefas ativas
        """
        return list(self.active_tasks.values())
    
    def get_completed_tasks(self, limit: int = 0) -> List[Task]:
        """
        Retorna uma lista de tarefas completadas.
        
        Args:
            limit: Número máximo de tarefas a retornar (0 para todas)
            
        Returns:
            Lista de tarefas completadas
        """
        tasks = list(self.completed_tasks.values())
        
        # Ordena por hora de conclusão, mais recentes primeiro
        tasks.sort(key=lambda t: t.end_time or 0, reverse=True)
        
        if limit > 0 and len(tasks) > limit:
            tasks = tasks[:limit]
            
        return tasks
    
    def clean_completed_tasks(self, max_tasks: int = 100) -> None:
        """
        Limpa tarefas completadas antigas para liberar memória.
        
        Args:
            max_tasks: Número máximo de tarefas completadas a manter
        """
        if len(self.completed_tasks) <= max_tasks:
            return
            
        # Obtém os IDs das tarefas ordenados por hora de conclusão (mais antigas primeiro)
        task_ids = sorted(
            self.completed_tasks.keys(),
            key=lambda tid: self.completed_tasks[tid].end_time or 0
        )
        
        # Remove as tarefas excedentes
        for task_id in task_ids[:(len(task_ids) - max_tasks)]:
            del self.completed_tasks[task_id]
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Desliga o gerenciador de tarefas.
        
        Args:
            wait: Se True, aguarda a conclusão de todas as tarefas
        """
        self.running = False
        
        if wait:
            # Aguarda a conclusão de todas as tarefas
            self.task_queue.join()
            
        # Aguarda o encerramento dos workers
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1.0)
        
        logger.info("Gerenciador de tarefas desligado") 