#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Gerenciador de Eventos
Responsável por gerenciar eventos e comunicação entre componentes
"""

import logging
from typing import Dict, Set, Callable, Any, List, Optional

# Logger
logger = logging.getLogger(__name__)

class EventManager:
    """
    Gerencia eventos e comunicação entre componentes.
    
    Implementa um padrão Observer para permitir comunicação desacoplada
    entre diferentes partes da aplicação.
    """
    
    # Instância singleton
    _instance = None
    
    def __new__(cls):
        """
        Cria uma instância singleton do gerenciador de eventos.
        
        Returns:
            A instância do gerenciador de eventos
        """
        if cls._instance is None:
            cls._instance = super(EventManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Inicializa o gerenciador de eventos se ainda não foi inicializado.
        """
        if not self._initialized:
            self._listeners: Dict[str, Set[Callable]] = {}
            self._initialized = True
    
    def subscribe(self, event_type: str, listener: Callable) -> None:
        """
        Adiciona um listener para um tipo de evento.
        
        Args:
            event_type: Tipo de evento
            listener: Função de callback que será chamada quando o evento ocorrer
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = set()
        
        self._listeners[event_type].add(listener)
        logger.debug(f"Listener adicionado para evento '{event_type}'")
    
    def unsubscribe(self, event_type: str, listener: Callable) -> None:
        """
        Remove um listener de um tipo de evento.
        
        Args:
            event_type: Tipo de evento
            listener: Função de callback a ser removida
        """
        if event_type in self._listeners and listener in self._listeners[event_type]:
            self._listeners[event_type].remove(listener)
            logger.debug(f"Listener removido do evento '{event_type}'")
            
            # Remove o tipo de evento se não houver mais listeners
            if not self._listeners[event_type]:
                del self._listeners[event_type]
    
    def publish(self, event_type: str, **kwargs) -> None:
        """
        Publica um evento para todos os listeners registrados.
        
        Args:
            event_type: Tipo de evento
            **kwargs: Dados a serem passados para os listeners
        """
        if event_type not in self._listeners:
            logger.debug(f"Nenhum listener registrado para evento '{event_type}'")
            return
        
        logger.debug(f"Publicando evento '{event_type}' com dados: {kwargs}")
        
        # Obtenha uma cópia dos listeners para evitar problemas se a lista mudar durante a iteração
        listeners = list(self._listeners[event_type])
        
        # Notifica todos os listeners
        for listener in listeners:
            try:
                # Cada listener recebe os dados do evento
                listener(**kwargs)
            except Exception as e:
                logger.exception(f"Erro ao notificar listener para evento '{event_type}': {e}")
    
    def clear_all_listeners(self) -> None:
        """
        Remove todos os listeners de todos os tipos de evento.
        """
        self._listeners.clear()
        logger.debug("Todos os listeners foram removidos")
    
    def clear_event_listeners(self, event_type: str) -> None:
        """
        Remove todos os listeners de um tipo de evento específico.
        
        Args:
            event_type: Tipo de evento
        """
        if event_type in self._listeners:
            del self._listeners[event_type]
            logger.debug(f"Todos os listeners do evento '{event_type}' foram removidos")
    
    def get_event_types(self) -> List[str]:
        """
        Retorna uma lista de todos os tipos de evento registrados.
        
        Returns:
            Lista de tipos de evento
        """
        return list(self._listeners.keys())
    
    def get_listener_count(self, event_type: str) -> int:
        """
        Retorna o número de listeners para um tipo de evento.
        
        Args:
            event_type: Tipo de evento
            
        Returns:
            Número de listeners
        """
        return len(self._listeners.get(event_type, []))


# Constantes para tipos de evento comuns
class EventType:
    """
    Constantes para tipos de evento comuns.
    """
    # Eventos de banco de dados
    DATABASE_OPENED = "database_opened"
    DATABASE_CLOSED = "database_closed"
    DATABASE_CREATED = "database_created"
    TABLE_CREATED = "table_created"
    TABLE_UPDATED = "table_updated"
    
    # Eventos de interface
    THEME_CHANGED = "theme_changed"
    SELECTION_CHANGED = "selection_changed"
    VIEW_REFRESHED = "view_refreshed"
    
    # Eventos de importação
    IMPORT_STARTED = "import_started"
    IMPORT_COMPLETED = "import_completed"
    IMPORT_FAILED = "import_failed"
    IMPORT_CANCELLED = "import_cancelled"
    
    # Eventos de aplicação
    APP_INITIALIZED = "app_initialized"
    APP_CLOSING = "app_closing"
    CONFIG_UPDATED = "config_updated" 