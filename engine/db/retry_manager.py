#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Retry Manager
Sistema de retry automático com backoff exponencial para operações de banco
"""

import time
import logging
import random
from typing import Callable, Any, Optional, Dict, List, Type
from functools import wraps
import sqlite3

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuração para retry automático."""
    
    def __init__(self, 
                 max_attempts: int = 3,
                 base_delay: float = 0.1,
                 max_delay: float = 10.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True,
                 retryable_exceptions: Optional[List[Type[Exception]]] = None):
        """
        Args:
            max_attempts: Número máximo de tentativas
            base_delay: Delay inicial em segundos
            max_delay: Delay máximo em segundos
            exponential_base: Base para cálculo exponencial
            jitter: Adiciona variação aleatória ao delay
            retryable_exceptions: Exceções que devem ser retried
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        
        # Exceções padrão para SQLite
        if retryable_exceptions is None:
            self.retryable_exceptions = [
                sqlite3.OperationalError,
                sqlite3.DatabaseError,
                sqlite3.IntegrityError,
                sqlite3.OperationalError,  # For busy/locked cases
                sqlite3.OperationalError,  # Locked
                sqlite3.OperationalError  # Timeout
            ]
        else:
            self.retryable_exceptions = retryable_exceptions
    
    @classmethod
    def aggressive(cls) -> 'RetryConfig':
        """Configuração agressiva para ambientes instáveis."""
        return cls(
            max_attempts=5,
            base_delay=0.05,
            max_delay=5.0,
            exponential_base=1.5
        )
    
    @classmethod
    def conservative(cls) -> 'RetryConfig':
        """Configuração conservadora para ambientes estáveis."""
        return cls(
            max_attempts=2,
            base_delay=0.5,
            max_delay=2.0,
            exponential_base=2.0
        )

class RetryManager:
    """Gerenciador de retry com backoff exponencial."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'retry_history': []
        }
    
    def execute_with_retry(self, 
                          func: Callable[..., Any], 
                          *args, 
                          **kwargs) -> Any:
        """Executa função com retry automático.
        
        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
            
        Raises:
            Exception: Se todas as tentativas falharem
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                
                # Registra retry bem-sucedido
                if attempt > 0:
                    self._record_success(attempt, func.__name__)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Verifica se deve fazer retry
                if not self._should_retry(e):
                    logger.error(f"Exceção não retryable: {type(e).__name__}: {e}")
                    raise
                
                # Última tentativa, não faz retry
                if attempt == self.config.max_attempts - 1:
                    break
                
                # Calcula delay
                delay = self._calculate_delay(attempt)
                
                logger.warning(
                    f"Retry {attempt + 1}/{self.config.max_attempts} "
                    f"para {func.__name__} após {delay:.2f}s: {e}"
                )
                
                # Registra tentativa
                self._record_attempt(attempt, func.__name__, str(e), delay)
                
                # Aguarda antes de retry
                time.sleep(delay)
        
        # Todas as tentativas falharam
        self._record_failure(self.config.max_attempts, func.__name__, str(last_exception))
        raise last_exception
    
    def _should_retry(self, exception: Exception) -> bool:
        """Verifica se a exceção deve ser retryable."""
        return any(
            isinstance(exception, exc_type) 
            for exc_type in self.config.retryable_exceptions
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calcula delay com backoff exponencial."""
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            # Adiciona jitter de ±25%
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0.01, delay)  # Mínimo de 10ms
        
        return delay
    
    def _record_attempt(self, attempt: int, func_name: str, 
                       error: str, delay: float):
        """Registra tentativa de retry."""
        self._stats['total_retries'] += 1
        self._stats['retry_history'].append({
            'function': func_name,
            'attempt': attempt + 1,
            'error': error,
            'delay': delay,
            'timestamp': time.time()
        })
        
        # Limita histórico
        if len(self._stats['retry_history']) > 1000:
            self._stats['retry_history'] = self._stats['retry_history'][-500:]
    
    def _record_success(self, attempts: int, func_name: str):
        """Registra retry bem-sucedido."""
        self._stats['successful_retries'] += 1
        logger.info(
            f"Retry bem-sucedido após {attempts} tentativas para {func_name}"
        )
    
    def _record_failure(self, attempts: int, func_name: str, error: str):
        """Registra falha após todas as tentativas."""
        self._stats['failed_retries'] += 1
        logger.error(
            f"Falha após {attempts} tentativas para {func_name}: {error}"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de retry."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'retry_history': []
        }

def retryable(config: Optional[RetryConfig] = None):
    """Decorator para adicionar retry automático a funções."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retry_manager = RetryManager(config)
            return retry_manager.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator

# Instâncias globais
default_retry_manager = RetryManager()
aggressive_retry_manager = RetryManager(RetryConfig.aggressive())
conservative_retry_manager = RetryManager(RetryConfig.conservative())

# Funções utilitárias
def retry_operation(func: Callable[..., Any], 
                   max_attempts: int = 3,
                   base_delay: float = 0.1,
                   **kwargs) -> Any:
    """Executa operação com retry simples."""
    config = RetryConfig(max_attempts=max_attempts, base_delay=base_delay)
    manager = RetryManager(config)
    return manager.execute_with_retry(func, **kwargs)

# Exemplo de uso
if __name__ == "__main__":
    # Teste do sistema de retry
    import sqlite3
    
    def test_query():
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        return result
    
    # Usa retry automático
    retry_manager = RetryManager()
    try:
        result = retry_manager.execute_with_retry(test_query)
        print(f"Query bem-sucedida: {result}")
    except Exception as e:
        print(f"Query falhou: {e}")
    
    # Usa decorator
    @retryable()
    def decorated_query():
        return test_query()
    
    try:
        result = decorated_query()
        print(f"Query decorada bem-sucedida: {result}")
    except Exception as e:
        print(f"Query decorada falhou: {e}")