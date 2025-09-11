#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Locks de Thread Safety para DB
Locks para sincronização de acessos concorrentes ao banco de dados
"""

import threading
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lock global para operações de escrita no banco
db_write_lock = threading.Lock()

# Lock para operações de leitura (menos restritivo)
db_read_lock = threading.RLock()

def with_db_write_lock(func):
    """
    Decorator para operações que requerem lock de escrita exclusivo.

    Args:
        func: Função a ser decorada

    Returns:
        Função decorada com lock
    """
    def wrapper(*args, **kwargs):
        with db_write_lock:
            logger.debug(f"Lock de escrita adquirido para {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Lock de escrita liberado para {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Erro com lock de escrita em {func.__name__}: {e}")
                raise
    return wrapper

def with_db_read_lock(func):
    """
    Decorator para operações que requerem lock de leitura.

    Args:
        func: Função a ser decorada

    Returns:
        Função decorada com lock
    """
    def wrapper(*args, **kwargs):
        with db_read_lock:
            logger.debug(f"Lock de leitura adquirido para {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Lock de leitura liberado para {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Erro com lock de leitura em {func.__name__}: {e}")
                raise
    return wrapper

class DatabaseLockManager:
    """
    Gerenciador de locks para operações de banco de dados.
    """

    def __init__(self):
        self._write_lock = threading.Lock()
        self._read_lock = threading.RLock()
        self._lock_timeout = 30.0  # segundos

    def acquire_write_lock(self, timeout: float = None) -> bool:
        """
        Adquire lock de escrita.

        Args:
            timeout: Timeout em segundos

        Returns:
            True se lock adquirido, False se timeout
        """
        actual_timeout = timeout or self._lock_timeout
        acquired = self._write_lock.acquire(timeout=actual_timeout)
        if acquired:
            logger.debug("Lock de escrita adquirido")
        else:
            logger.warning(f"Timeout ao adquirir lock de escrita ({actual_timeout}s)")
        return acquired

    def release_write_lock(self):
        """Libera lock de escrita."""
        try:
            self._write_lock.release()
            logger.debug("Lock de escrita liberado")
        except RuntimeError:
            logger.warning("Tentativa de liberar lock de escrita não adquirido")

    def acquire_read_lock(self, timeout: float = None) -> bool:
        """
        Adquire lock de leitura.

        Args:
            timeout: Timeout em segundos

        Returns:
            True se lock adquirido, False se timeout
        """
        actual_timeout = timeout or self._lock_timeout
        acquired = self._read_lock.acquire(timeout=actual_timeout)
        if acquired:
            logger.debug("Lock de leitura adquirido")
        else:
            logger.warning(f"Timeout ao adquirir lock de leitura ({actual_timeout}s)")
        return acquired

    def release_read_lock(self):
        """Libera lock de leitura."""
        try:
            self._read_lock.release()
            logger.debug("Lock de leitura liberado")
        except RuntimeError:
            logger.warning("Tentativa de liberar lock de leitura não adquirido")

    def __enter__(self):
        """Context manager para lock de escrita."""
        self.acquire_write_lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release_write_lock()