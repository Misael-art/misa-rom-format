#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Enhanced Dependency Container
Container de injeção de dependências aprimorado com lazy loading, scopes e performance otimizada
"""

import threading
import weakref
import inspect
import logging
import os
import psutil
from typing import (
    Any, Dict, List, Optional, Type, TypeVar, Generic, Callable, 
    Union, get_type_hints, get_origin, get_args
)
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
from contextlib import contextmanager
from functools import wraps, lru_cache
import uuid
import json
from collections import defaultdict, deque
import time
import gc
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

T = TypeVar('T')
TService = TypeVar('TService')
TImplementation = TypeVar('TImplementation')

class Lifetime(Enum):
    """Tipos de lifetime para dependências."""
    TRANSIENT = auto()    # Nova instância a cada resolução
    SINGLETON = auto()    # Uma única instância global
    SCOPED = auto()       # Uma instância por escopo
    THREAD = auto()       # Uma instância por thread
    POOLED = auto()       # Pool de instâncias reutilizáveis
    LAZY = auto()         # Criação sob demanda

class RegistrationType(Enum):
    """Tipos de registro de dependências."""
    TYPE = auto()         # Registro por tipo
    FACTORY = auto()      # Registro por factory function
    INSTANCE = auto()     # Registro de instância específica
    DECORATOR = auto()    # Registro via decorador
    CONDITIONAL = auto()  # Registro condicional

class ResolutionStrategy(Enum):
    """Estratégias de resolução de dependências."""
    CONSTRUCTOR = auto()  # Injeção via construtor
    PROPERTY = auto()     # Injeção via propriedades
    METHOD = auto()       # Injeção via métodos
    ATTRIBUTE = auto()    # Injeção via atributos

@dataclass
class DependencyMetadata:
    """Metadados de uma dependência."""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: Lifetime = Lifetime.TRANSIENT
    registration_type: RegistrationType = RegistrationType.TYPE
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.CONSTRUCTOR
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[], bool]] = None
    interceptors: List[Callable] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    dependencies: List[Type] = field(default_factory=list)
    optional_dependencies: List[Type] = field(default_factory=list)
    
    def is_conditional_met(self) -> bool:
        """Verifica se a condição é atendida."""
        if not self.condition:
            return True
        try:
            return self.condition()
        except Exception as e:
            logger.warning(f"Erro ao avaliar condição para {self.service_type}: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'service_type': str(self.service_type),
            'implementation_type': str(self.implementation_type) if self.implementation_type else None,
            'lifetime': self.lifetime.name,
            'registration_type': self.registration_type.name,
            'resolution_strategy': self.resolution_strategy.name,
            'tags': self.tags,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'dependencies': [str(dep) for dep in self.dependencies],
            'optional_dependencies': [str(dep) for dep in self.optional_dependencies]
        }

@dataclass
class ResolutionContext:
    """Contexto de resolução de dependências."""
    resolution_chain: List[Type] = field(default_factory=list)
    scope_id: Optional[str] = None
    thread_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    
    def add_to_chain(self, service_type: Type):
        """Adiciona tipo à cadeia de resolução."""
        if service_type in self.resolution_chain:
            chain_str = ' -> '.join(str(t) for t in self.resolution_chain + [service_type])
            raise CircularDependencyError(f"Dependência circular detectada: {chain_str}")
        self.resolution_chain.append(service_type)
    
    def remove_from_chain(self, service_type: Type):
        """Remove tipo da cadeia de resolução."""
        if self.resolution_chain and self.resolution_chain[-1] == service_type:
            self.resolution_chain.pop()

class DependencyResolutionError(Exception):
    """Erro na resolução de dependências."""
    pass

class CircularDependencyError(DependencyResolutionError):
    """Erro de dependência circular."""
    pass

class ServiceNotRegisteredError(DependencyResolutionError):
    """Erro quando serviço não está registrado."""
    pass

class IDependencyScope(ABC):
    """Interface para escopo de dependências."""
    
    @abstractmethod
    def get_instance(self, service_type: Type) -> Optional[Any]:
        """Obtém instância do escopo."""
        pass
    
    @abstractmethod
    def set_instance(self, service_type: Type, instance: Any):
        """Define instância no escopo."""
        pass
    
    @abstractmethod
    def dispose(self):
        """Libera recursos do escopo."""
        pass

class DependencyScope(IDependencyScope):
    """Implementação de escopo de dependências."""
    
    def __init__(self, scope_id: Optional[str] = None):
        self.scope_id = scope_id or str(uuid.uuid4())
        self._instances: Dict[Type, Any] = {}
        self._lock = threading.RLock()
        self._disposed = False
        self.created_at = datetime.now()
    
    def get_instance(self, service_type: Type) -> Optional[Any]:
        if self._disposed:
            raise RuntimeError(f"Escopo {self.scope_id} foi liberado")
        
        with self._lock:
            return self._instances.get(service_type)
    
    def set_instance(self, service_type: Type, instance: Any):
        if self._disposed:
            raise RuntimeError(f"Escopo {self.scope_id} foi liberado")
        
        with self._lock:
            self._instances[service_type] = instance
    
    def dispose(self):
        if self._disposed:
            return
        
        with self._lock:
            # Chama dispose em instâncias que implementam IDisposable
            for instance in self._instances.values():
                if hasattr(instance, 'dispose'):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.warning(f"Erro ao liberar instância {type(instance)}: {e}")
            
            self._instances.clear()
            self._disposed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

class InstancePool:
    """Pool de instâncias reutilizáveis."""
    
    def __init__(self, factory: Callable, max_size: int = 10):
        self.factory = factory
        self.max_size = max_size
        self._pool: deque = deque()
        self._lock = threading.RLock()
        self._created_count = 0
        self._borrowed_count = 0
        self._returned_count = 0
    
    def borrow(self) -> Any:
        """Empresta instância do pool."""
        with self._lock:
            if self._pool:
                instance = self._pool.popleft()
                self._borrowed_count += 1
                return instance
            
            # Cria nova instância
            instance = self.factory()
            self._created_count += 1
            self._borrowed_count += 1
            return instance
    
    def return_instance(self, instance: Any):
        """Retorna instância ao pool."""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Reset da instância se implementa método reset
                if hasattr(instance, 'reset'):
                    try:
                        instance.reset()
                    except Exception as e:
                        logger.warning(f"Erro ao resetar instância: {e}")
                        return
                
                self._pool.append(instance)
                self._returned_count += 1
            else:
                # Pool cheio, libera instância
                if hasattr(instance, 'dispose'):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.warning(f"Erro ao liberar instância: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do pool."""
        with self._lock:
            return {
                'pool_size': len(self._pool),
                'max_size': self.max_size,
                'created_count': self._created_count,
                'borrowed_count': self._borrowed_count,
                'returned_count': self._returned_count,
                'active_instances': self._borrowed_count - self._returned_count
            }

class CacheStrategy(ABC):
    """Estratégia abstrata de cache."""
    
    @abstractmethod
    def get(self, key: Type) -> Optional[Any]:
        """Obtém valor do cache."""
        pass
    
    @abstractmethod
    def set(self, key: Type, value: Any, ttl: Optional[timedelta] = None):
        """Define valor no cache."""
        pass
    
    @abstractmethod
    def remove(self, key: Type):
        """Remove valor do cache."""
        pass
    
    @abstractmethod
    def clear(self):
        """Limpa o cache."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        pass

class MemoryCacheStrategy(CacheStrategy):
    """Estratégia de cache em memória com TTL."""
    
    def __init__(self, max_size: int = 1000, default_ttl: timedelta = timedelta(hours=1)):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[Type, Any] = {}
        self._expiry: Dict[Type, datetime] = {}
        self._access_times: Dict[Type, datetime] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: Type) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            # Verifica expiração
            if key in self._expiry and datetime.now() > self._expiry[key]:
                self.remove(key)
                self._misses += 1
                return None
            
            self._access_times[key] = datetime.now()
            self._hits += 1
            return self._cache[key]
    
    def set(self, key: Type, value: Any, ttl: Optional[timedelta] = None):
        with self._lock:
            # Remove itens expirados se necessário
            if len(self._cache) >= self.max_size:
                self._evict_expired()
                
                # Se ainda está cheio, remove o menos usado recentemente
                if len(self._cache) >= self.max_size:
                    self._evict_lru()
            
            self._cache[key] = value
            self._access_times[key] = datetime.now()
            
            if ttl or self.default_ttl:
                expiry_time = datetime.now() + (ttl or self.default_ttl)
                self._expiry[key] = expiry_time
    
    def remove(self, key: Type):
        with self._lock:
            self._cache.pop(key, None)
            self._expiry.pop(key, None)
            self._access_times.pop(key, None)
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._expiry.clear()
            self._access_times.clear()
    
    def _evict_expired(self):
        """Remove itens expirados."""
        now = datetime.now()
        expired_keys = [k for k, exp in self._expiry.items() if now > exp]
        for key in expired_keys:
            self.remove(key)
    
    def _evict_lru(self):
        """Remove o item menos usado recentemente."""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        self.remove(lru_key)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate_percent': hit_rate,
                'expired_items': len([k for k, exp in self._expiry.items() if datetime.now() > exp])
            }

class DependencyInterceptor(ABC):
    """Interceptador abstrato para dependências."""
    
    @abstractmethod
    def before_resolution(self, service_type: Type, context: ResolutionContext) -> bool:
        """Executado antes da resolução. Retorna False para cancelar."""
        pass
    
    @abstractmethod
    def after_resolution(self, service_type: Type, instance: Any, context: ResolutionContext) -> Any:
        """Executado após a resolução. Pode modificar a instância."""
        pass
    
    @abstractmethod
    def on_error(self, service_type: Type, error: Exception, context: ResolutionContext):
        """Executado quando ocorre erro na resolução."""
        pass

class LoggingInterceptor(DependencyInterceptor):
    """Interceptador para logging de dependências."""
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
    
    def before_resolution(self, service_type: Type, context: ResolutionContext) -> bool:
        self.logger.debug(f"Resolvendo dependência: {service_type.__name__}")
        return True
    
    def after_resolution(self, service_type: Type, instance: Any, context: ResolutionContext) -> Any:
        resolution_time = (datetime.now() - context.start_time).total_seconds()
        self.logger.debug(f"Dependência {service_type.__name__} resolvida em {resolution_time:.3f}s")
        return instance
    
    def on_error(self, service_type: Type, error: Exception, context: ResolutionContext):
        self.logger.error(f"Erro ao resolver {service_type.__name__}: {error}")

class PerformanceInterceptor(DependencyInterceptor):
    """Interceptador para monitoramento de performance."""
    
    def __init__(self):
        self.resolution_times: Dict[Type, List[float]] = defaultdict(list)
        self.error_counts: Dict[Type, int] = defaultdict(int)
        self._lock = threading.RLock()
    
    def before_resolution(self, service_type: Type, context: ResolutionContext) -> bool:
        context.metadata['perf_start'] = time.perf_counter()
        return True
    
    def after_resolution(self, service_type: Type, instance: Any, context: ResolutionContext) -> Any:
        start_time = context.metadata.get('perf_start')
        if start_time:
            resolution_time = time.perf_counter() - start_time
            with self._lock:
                self.resolution_times[service_type].append(resolution_time)
                # Mantém apenas os últimos 100 tempos
                if len(self.resolution_times[service_type]) > 100:
                    self.resolution_times[service_type].pop(0)
        return instance
    
    def on_error(self, service_type: Type, error: Exception, context: ResolutionContext):
        with self._lock:
            self.error_counts[service_type] += 1
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Gera relatório de performance."""
        with self._lock:
            report = {}
            for service_type, times in self.resolution_times.items():
                if times:
                    report[service_type.__name__] = {
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'total_resolutions': len(times),
                        'error_count': self.error_counts[service_type]
                    }
            return report

class AutoRegistrationProvider:
    """Provedor de auto-registro de tipos."""
    
    @staticmethod
    def register_common_types(container: 'EnhancedDependencyContainer'):
        """Registra tipos comuns automaticamente."""
        # Registra tipos básicos do Python
        container.register_instance(str, "")
        container.register_instance(int, 0)
        container.register_instance(float, 0.0)
        container.register_instance(bool, False)
        container.register_instance(list, [])
        container.register_instance(dict, {})
        
        # Registra logger
        container.register_factory(logging.Logger, lambda: logging.getLogger(__name__))
        
        # Registra threading primitives
        container.register_factory(threading.Lock, threading.Lock)
        container.register_factory(threading.RLock, threading.RLock)
        container.register_factory(threading.Event, threading.Event)
        
        logger.info("Tipos comuns registrados automaticamente")
    
    @staticmethod
    def scan_and_register(container: 'EnhancedDependencyContainer', module_path: str, 
                         base_class: Optional[Type] = None):
        """Escaneia módulo e registra tipos automaticamente."""
        try:
            import importlib.util
            import sys
            
            spec = importlib.util.spec_from_file_location("scanned_module", module_path)
            if not spec or not spec.loader:
                return
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            for name in dir(module):
                obj = getattr(module, name)
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    if base_class is None or issubclass(obj, base_class):
                        container.register_type(obj, obj, Lifetime.TRANSIENT)
                        logger.debug(f"Auto-registrado: {obj.__name__}")
        
        except Exception as e:
            logger.warning(f"Erro no auto-registro de {module_path}: {e}")

class EnhancedDependencyContainer:
    """Container de injeção de dependências aprimorado."""
    
    def __init__(self, enable_validation: bool = True, enable_metrics: bool = True,
                 cache_strategy: Optional[CacheStrategy] = None, enable_auto_registration: bool = True):
        self._registrations: Dict[Type, DependencyMetadata] = {}
        self._singletons: Dict[Type, Any] = {}
        self._thread_locals: Dict[Type, threading.local] = {}
        self._pools: Dict[Type, InstancePool] = {}
        self._scopes: Dict[str, DependencyScope] = {}
        self._current_scope: Optional[DependencyScope] = None
        
        self._lock = threading.RLock()
        self._enable_validation = enable_validation
        self._enable_metrics = enable_metrics
        
        # Cache inteligente
        self._cache_strategy = cache_strategy or MemoryCacheStrategy()
        self._cache_enabled = True
        
        # Interceptadores
        self._global_interceptors: List[DependencyInterceptor] = []
        self._performance_interceptor = PerformanceInterceptor()
        self._logging_interceptor = LoggingInterceptor()
        
        # Adiciona interceptadores padrão
        if enable_metrics:
            self.add_interceptor(self._performance_interceptor)
        
        # Métricas aprimoradas
        self._metrics = {
            'total_registrations': 0,
            'total_resolutions': 0,
            'successful_resolutions': 0,
            'failed_resolutions': 0,
            'circular_dependencies_detected': 0,
            'avg_resolution_time': 0.0,
            'max_resolution_time': 0.0,
            'total_resolution_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'active_scopes': 0,
            'total_scopes_created': 0,
            'memory_usage_mb': 0.0,
            'interceptor_calls': 0,
            'auto_registrations': 0
        }
        
        # Cache de resolução (mantido para compatibilidade)
        self._resolution_cache: Dict[Type, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Auto-registro de tipos comuns
        if enable_auto_registration:
            self._auto_register_common_types()
        
        logger.info("Enhanced Dependency Container inicializado com cache inteligente e interceptadores")
    
    def _auto_register_common_types(self):
        """Auto-registra tipos comuns do sistema."""
        # Registra o próprio container
        self.register_instance(EnhancedDependencyContainer, self)
        
        # Registra tipos básicos como factories
        self.register_factory(dict, dict, lifetime=Lifetime.TRANSIENT)
        self.register_factory(list, list, lifetime=Lifetime.TRANSIENT)
        self.register_factory(set, set, lifetime=Lifetime.TRANSIENT)
    
    def register(self, 
                service_type: Type[TService], 
                implementation_type: Type[TImplementation] = None,
                lifetime: Lifetime = Lifetime.TRANSIENT,
                tags: Optional[List[str]] = None,
                condition: Optional[Callable[[], bool]] = None,
                interceptors: Optional[List[Callable]] = None,
                **metadata) -> 'EnhancedDependencyContainer':
        """Registra um serviço no container."""
        
        if implementation_type is None:
            implementation_type = service_type
        
        # Validação
        if self._enable_validation:
            self._validate_registration(service_type, implementation_type)
        
        # Analisa dependências
        dependencies, optional_deps = self._analyze_dependencies(implementation_type)
        
        registration = DependencyMetadata(
            service_type=service_type,
            implementation_type=implementation_type,
            lifetime=lifetime,
            registration_type=RegistrationType.TYPE,
            tags=tags or [],
            condition=condition,
            interceptors=interceptors or [],
            dependencies=dependencies,
            optional_dependencies=optional_deps,
            metadata=metadata
        )
        
        with self._lock:
            self._registrations[service_type] = registration
            self._metrics['total_registrations'] += 1
        
        logger.debug(f"Serviço registrado: {service_type} -> {implementation_type} ({lifetime.name})")
        return self
    
    def register_factory(self,
                        service_type: Type[TService],
                        factory: Callable[..., TService],
                        lifetime: Lifetime = Lifetime.TRANSIENT,
                        tags: Optional[List[str]] = None,
                        condition: Optional[Callable[[], bool]] = None,
                        **metadata) -> 'EnhancedDependencyContainer':
        """Registra um serviço usando factory function."""
        
        # Analisa dependências da factory
        dependencies, optional_deps = self._analyze_factory_dependencies(factory)
        
        registration = DependencyMetadata(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
            registration_type=RegistrationType.FACTORY,
            tags=tags or [],
            condition=condition,
            dependencies=dependencies,
            optional_dependencies=optional_deps,
            metadata=metadata
        )
        
        with self._lock:
            self._registrations[service_type] = registration
            self._metrics['total_registrations'] += 1
        
        logger.debug(f"Factory registrada: {service_type} ({lifetime.name})")
        return self
    
    def register_instance(self,
                         service_type: Type[TService],
                         instance: TService,
                         tags: Optional[List[str]] = None,
                         **metadata) -> 'EnhancedDependencyContainer':
        """Registra uma instância específica."""
        
        registration = DependencyMetadata(
            service_type=service_type,
            instance=instance,
            lifetime=Lifetime.SINGLETON,
            registration_type=RegistrationType.INSTANCE,
            tags=tags or [],
            metadata=metadata
        )
        
        with self._lock:
            self._registrations[service_type] = registration
            self._singletons[service_type] = instance
            self._metrics['total_registrations'] += 1
        
        logger.debug(f"Instância registrada: {service_type}")
        return self
    
    def add_interceptor(self, interceptor: DependencyInterceptor) -> 'EnhancedDependencyContainer':
        """Adiciona interceptador global."""
        with self._lock:
            if interceptor not in self._global_interceptors:
                self._global_interceptors.append(interceptor)
                logger.debug(f"Interceptador adicionado: {type(interceptor).__name__}")
        return self
    
    def remove_interceptor(self, interceptor: DependencyInterceptor) -> 'EnhancedDependencyContainer':
        """Remove interceptador global."""
        with self._lock:
            if interceptor in self._global_interceptors:
                self._global_interceptors.remove(interceptor)
                logger.debug(f"Interceptador removido: {type(interceptor).__name__}")
        return self
    
    def enable_cache(self, enabled: bool = True) -> 'EnhancedDependencyContainer':
        """Habilita/desabilita cache."""
        self._cache_enabled = enabled
        if not enabled:
            self._cache_strategy.clear()
        logger.debug(f"Cache {'habilitado' if enabled else 'desabilitado'}")
        return self
    
    def clear_cache(self) -> 'EnhancedDependencyContainer':
        """Limpa o cache."""
        self._cache_strategy.clear()
        with self._cache_lock:
            self._resolution_cache.clear()
        logger.debug("Cache limpo")
        return self
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        return self._cache_strategy.get_stats()
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Gera relatório de performance completo."""
        report = {
            'container_metrics': self.get_metrics(),
            'cache_stats': self.get_cache_stats(),
            'interceptor_performance': self._performance_interceptor.get_performance_report(),
            'memory_info': self._get_memory_info()
        }
        return report
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Obtém informações de memória."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.warning(f"Erro ao obter informações de memória: {e}")
            return {}
    
    def auto_register_from_module(self, module_path: str, base_class: Optional[Type] = None):
        """Auto-registra tipos de um módulo."""
        AutoRegistrationProvider.scan_and_register(self, module_path, base_class)
        self._metrics['auto_registrations'] += 1
    
    def register_decorator(self, 
                          service_type: Type[TService],
                          decorator: Callable[[TService], TService],
                          tags: Optional[List[str]] = None,
                          **metadata) -> 'EnhancedDependencyContainer':
        """Registra um decorador para um serviço."""
        
        if service_type not in self._registrations:
            raise ServiceNotRegisteredError(f"Serviço {service_type} deve ser registrado antes do decorador")
        
        original_registration = self._registrations[service_type]
        
        # Cria factory que aplica o decorador
        def decorated_factory(*args, **kwargs):
            original_instance = self._create_instance(original_registration, ResolutionContext())
            return decorator(original_instance)
        
        registration = DependencyMetadata(
            service_type=service_type,
            factory=decorated_factory,
            lifetime=original_registration.lifetime,
            registration_type=RegistrationType.DECORATOR,
            tags=tags or [],
            metadata=metadata
        )
        
        with self._lock:
            self._registrations[service_type] = registration
        
        logger.debug(f"Decorador registrado para: {service_type}")
        return self
    
    def add_global_interceptor(self, interceptor: Callable):
        """Adiciona interceptador global."""
        self._global_interceptors.append(interceptor)
    
    def resolve(self, service_type: Type[T], context: Optional[ResolutionContext] = None) -> T:
        """Resolve uma dependência com interceptadores e cache inteligente."""
        start_time = time.time()
        
        if context is None:
            context = ResolutionContext(
                scope_id=self._current_scope.scope_id if self._current_scope else None,
                thread_id=threading.get_ident()
            )
        
        try:
            context.add_to_chain(service_type)
            
            with self._lock:
                self._metrics['total_resolutions'] += 1
            
            # Executa interceptadores before_resolution
            if not self._execute_before_interceptors(service_type, context):
                raise DependencyResolutionError(f"Resolução cancelada por interceptador para {service_type}")
            
            # Verifica cache inteligente primeiro
            if self._cache_enabled:
                cached_instance = self._cache_strategy.get(service_type)
                if cached_instance is not None:
                    with self._lock:
                        self._metrics['cache_hits'] += 1
                    # Executa interceptadores after_resolution para cache
                    return self._execute_after_interceptors(service_type, cached_instance, context)
            
            # Verifica cache legado
            cached_instance = self._get_from_cache(service_type)
            if cached_instance is not None:
                with self._lock:
                    self._metrics['cache_hits'] += 1
                return self._execute_after_interceptors(service_type, cached_instance, context)
            
            with self._lock:
                self._metrics['cache_misses'] += 1
            
            # Resolve dependência
            instance = self._resolve_internal(service_type, context)
            
            # Executa interceptadores after_resolution
            instance = self._execute_after_interceptors(service_type, instance, context)
            
            # Atualiza cache inteligente se aplicável
            if self._cache_enabled and self._should_cache(service_type):
                self._cache_strategy.set(service_type, instance)
            
            # Atualiza cache legado
            self._update_cache(service_type, instance)
            
            with self._lock:
                self._metrics['successful_resolutions'] += 1
            
            return instance
            
        except CircularDependencyError:
            with self._lock:
                self._metrics['circular_dependencies_detected'] += 1
                self._metrics['failed_resolutions'] += 1
            self._execute_error_interceptors(service_type, CircularDependencyError(), context)
            raise
        except Exception as e:
            with self._lock:
                self._metrics['failed_resolutions'] += 1
            self._execute_error_interceptors(service_type, e, context)
            logger.error(f"Erro ao resolver {service_type}: {e}")
            raise DependencyResolutionError(f"Falha ao resolver {service_type}: {e}") from e
        finally:
            context.remove_from_chain(service_type)
            
            # Atualiza métricas de tempo
            resolution_time = time.time() - start_time
            with self._lock:
                self._metrics['total_resolution_time'] += resolution_time
                self._metrics['max_resolution_time'] = max(
                    self._metrics['max_resolution_time'], resolution_time
                )
                
                total_resolutions = self._metrics['total_resolutions']
                if total_resolutions > 0:
                    self._metrics['avg_resolution_time'] = (
                        self._metrics['total_resolution_time'] / total_resolutions
                    )
    
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """Resolve todas as implementações de um tipo."""
        instances = []
        
        with self._lock:
            for reg_type, registration in self._registrations.items():
                if (issubclass(reg_type, service_type) or 
                    (registration.implementation_type and 
                     issubclass(registration.implementation_type, service_type))):
                    
                    if registration.is_conditional_met():
                        try:
                            instance = self.resolve(reg_type)
                            instances.append(instance)
                        except Exception as e:
                            logger.warning(f"Erro ao resolver {reg_type}: {e}")
        
        return instances
    
    def resolve_tagged(self, tag: str) -> List[Any]:
        """Resolve todas as dependências com uma tag específica."""
        instances = []
        
        with self._lock:
            for service_type, registration in self._registrations.items():
                if tag in registration.tags and registration.is_conditional_met():
                    try:
                        instance = self.resolve(service_type)
                        instances.append(instance)
                    except Exception as e:
                        logger.warning(f"Erro ao resolver {service_type} com tag '{tag}': {e}")
        
        return instances
    
    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """Tenta resolver uma dependência sem lançar exceção."""
        try:
            return self.resolve(service_type)
        except Exception:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """Verifica se um tipo está registrado."""
        with self._lock:
            return service_type in self._registrations
    
    def unregister(self, service_type: Type):
        """Remove registro de um tipo."""
        with self._lock:
            if service_type in self._registrations:
                del self._registrations[service_type]
            
            if service_type in self._singletons:
                del self._singletons[service_type]
            
            if service_type in self._thread_locals:
                del self._thread_locals[service_type]
            
            if service_type in self._pools:
                del self._pools[service_type]
        
        # Limpa cache
        self._clear_cache_for_type(service_type)
        
        logger.debug(f"Registro removido: {service_type}")
    
    @contextmanager
    def create_scope(self, scope_id: Optional[str] = None):
        """Cria um novo escopo de dependências."""
        scope = DependencyScope(scope_id)
        
        with self._lock:
            self._scopes[scope.scope_id] = scope
            self._metrics['total_scopes_created'] += 1
            self._metrics['active_scopes'] += 1
        
        old_scope = self._current_scope
        self._current_scope = scope
        
        try:
            yield scope
        finally:
            self._current_scope = old_scope
            
            with self._lock:
                if scope.scope_id in self._scopes:
                    del self._scopes[scope.scope_id]
                self._metrics['active_scopes'] -= 1
            
            scope.dispose()
    
    def _resolve_internal(self, service_type: Type[T], context: ResolutionContext) -> T:
        """Resolução interna de dependência."""
        registration = self._registrations.get(service_type)
        
        if not registration:
            raise ServiceNotRegisteredError(f"Serviço {service_type} não está registrado")
        
        if not registration.is_conditional_met():
            raise DependencyResolutionError(f"Condição não atendida para {service_type}")
        
        # Verifica lifetime e retorna instância existente se aplicável
        existing_instance = self._get_existing_instance(service_type, registration, context)
        if existing_instance is not None:
            return existing_instance
        
        # Cria nova instância
        instance = self._create_instance(registration, context)
        
        # Armazena instância conforme lifetime
        self._store_instance(service_type, registration, instance, context)
        
        return instance
    
    def _get_existing_instance(self, service_type: Type, registration: DependencyMetadata, context: ResolutionContext) -> Optional[Any]:
        """Obtém instância existente baseada no lifetime."""
        if registration.lifetime == Lifetime.SINGLETON:
            return self._singletons.get(service_type)
        
        elif registration.lifetime == Lifetime.THREAD:
            thread_local = self._thread_locals.get(service_type)
            if thread_local and hasattr(thread_local, 'instance'):
                return thread_local.instance
        
        elif registration.lifetime == Lifetime.SCOPED and self._current_scope:
            return self._current_scope.get_instance(service_type)
        
        elif registration.lifetime == Lifetime.POOLED:
            pool = self._pools.get(service_type)
            if pool:
                return pool.borrow()
        
        return None
    
    def _create_instance(self, registration: DependencyMetadata, context: ResolutionContext) -> Any:
        """Cria nova instância."""
        if registration.registration_type == RegistrationType.INSTANCE:
            return registration.instance
        
        elif registration.registration_type == RegistrationType.FACTORY:
            return self._create_from_factory(registration, context)
        
        else:
            return self._create_from_type(registration, context)
    
    def _create_from_factory(self, registration: DependencyMetadata, context: ResolutionContext) -> Any:
        """Cria instância usando factory."""
        factory = registration.factory
        
        # Resolve dependências da factory
        sig = inspect.signature(factory)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                try:
                    dependency = self.resolve(param.annotation, context)
                    kwargs[param_name] = dependency
                except Exception as e:
                    if param.default == inspect.Parameter.empty:
                        raise DependencyResolutionError(
                            f"Não foi possível resolver dependência {param.annotation} para factory de {registration.service_type}"
                        ) from e
        
        return factory(**kwargs)
    
    def _create_from_type(self, registration: DependencyMetadata, context: ResolutionContext) -> Any:
        """Cria instância usando construtor."""
        impl_type = registration.implementation_type
        
        # Resolve dependências do construtor
        sig = inspect.signature(impl_type.__init__)
        args = []
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            if param.annotation != inspect.Parameter.empty:
                try:
                    dependency = self.resolve(param.annotation, context)
                    if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                        args.append(dependency)
                    else:
                        kwargs[param_name] = dependency
                except Exception as e:
                    if param.default == inspect.Parameter.empty:
                        raise DependencyResolutionError(
                            f"Não foi possível resolver dependência {param.annotation} para {impl_type}"
                        ) from e
        
        return impl_type(*args, **kwargs)
    
    def _store_instance(self, service_type: Type, registration: DependencyMetadata, instance: Any, context: ResolutionContext):
        """Armazena instância conforme lifetime."""
        if registration.lifetime == Lifetime.SINGLETON:
            self._singletons[service_type] = instance
        
        elif registration.lifetime == Lifetime.THREAD:
            if service_type not in self._thread_locals:
                self._thread_locals[service_type] = threading.local()
            self._thread_locals[service_type].instance = instance
        
        elif registration.lifetime == Lifetime.SCOPED and self._current_scope:
            self._current_scope.set_instance(service_type, instance)
        
        elif registration.lifetime == Lifetime.POOLED:
            if service_type not in self._pools:
                factory = lambda: self._create_instance(registration, ResolutionContext())
                self._pools[service_type] = InstancePool(factory)
    
    def _apply_interceptors(self, service_type: Type, instance: Any) -> Any:
        """Aplica interceptadores à instância."""
        registration = self._registrations.get(service_type)
        
        # Interceptadores específicos do registro
        if registration and registration.interceptors:
            for interceptor in registration.interceptors:
                try:
                    instance = interceptor(instance)
                except Exception as e:
                    logger.warning(f"Erro em interceptador específico para {service_type}: {e}")
        
        # Interceptadores globais
        for interceptor in self._global_interceptors:
            try:
                instance = interceptor(instance)
            except Exception as e:
                logger.warning(f"Erro em interceptador global para {service_type}: {e}")
        
        return instance
    
    def _get_from_cache(self, service_type: Type) -> Optional[Any]:
        """Obtém instância do cache."""
        with self._cache_lock:
            return self._resolution_cache.get(service_type)
    
    def _update_cache(self, service_type: Type, instance: Any):
        """Atualiza cache de resolução."""
        registration = self._registrations.get(service_type)
        
        # Só cacheia singletons
        if registration and registration.lifetime == Lifetime.SINGLETON:
            with self._cache_lock:
                self._resolution_cache[service_type] = instance
    
    def _clear_cache_for_type(self, service_type: Type):
        """Limpa cache para um tipo específico."""
        with self._cache_lock:
            if service_type in self._resolution_cache:
                del self._resolution_cache[service_type]
    
    def _validate_registration(self, service_type: Type, implementation_type: Type):
        """Valida registro de dependência."""
        if not inspect.isclass(implementation_type):
            raise ValueError(f"Implementation type deve ser uma classe: {implementation_type}")
        
        if not issubclass(implementation_type, service_type):
            raise ValueError(f"{implementation_type} deve implementar {service_type}")
    
    def _analyze_dependencies(self, impl_type: Type) -> tuple[List[Type], List[Type]]:
        """Analisa dependências de um tipo."""
        dependencies = []
        optional_dependencies = []
        
        try:
            sig = inspect.signature(impl_type.__init__)
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                if param.annotation != inspect.Parameter.empty:
                    if param.default == inspect.Parameter.empty:
                        dependencies.append(param.annotation)
                    else:
                        optional_dependencies.append(param.annotation)
        
        except Exception as e:
            logger.warning(f"Erro ao analisar dependências de {impl_type}: {e}")
        
        return dependencies, optional_dependencies
    
    def _analyze_factory_dependencies(self, factory: Callable) -> tuple[List[Type], List[Type]]:
        """Analisa dependências de uma factory."""
        dependencies = []
        optional_dependencies = []
        
        try:
            sig = inspect.signature(factory)
            
            for param_name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    if param.default == inspect.Parameter.empty:
                        dependencies.append(param.annotation)
                    else:
                        optional_dependencies.append(param.annotation)
        
        except Exception as e:
            logger.warning(f"Erro ao analisar dependências da factory: {e}")
        
        return dependencies, optional_dependencies
    
    def get_registrations(self) -> Dict[Type, DependencyMetadata]:
        """Retorna todos os registros."""
        with self._lock:
            return self._registrations.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do container."""
        with self._lock:
            # Atualiza uso de memória
            try:
                import psutil
                process = psutil.Process()
                self._metrics['memory_usage_mb'] = process.memory_info().rss / 1024 / 1024
            except:
                pass
            
            return {
                **self._metrics,
                'total_registrations_current': len(self._registrations),
                'singleton_instances': len(self._singletons),
                'thread_local_instances': len(self._thread_locals),
                'pooled_instances': len(self._pools),
                'cache_size': len(self._resolution_cache),
                'active_scopes': len(self._scopes)
            }
    
    def export_configuration(self, file_path: str):
        """Exporta configuração do container."""
        config = {
            'registrations': {
                str(service_type): registration.to_dict()
                for service_type, registration in self._registrations.items()
            },
            'metrics': self.get_metrics(),
            'exported_at': datetime.now().isoformat()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Configuração exportada para: {file_path}")
    
    def clear_cache(self):
        """Limpa todo o cache de resolução."""
        with self._cache_lock:
            self._resolution_cache.clear()
        logger.debug("Cache de resolução limpo")
    
    def _execute_before_interceptors(self, service_type: Type, context: ResolutionContext) -> bool:
        """Executa interceptadores before_resolution."""
        for interceptor in self._interceptors:
            try:
                if not interceptor.before_resolution(service_type, context):
                    return False
                with self._lock:
                    self._metrics['interceptor_calls'] += 1
            except Exception as e:
                logger.error(f"Erro no interceptador {type(interceptor).__name__}: {e}")
                return False
        return True
    
    def _execute_after_interceptors(self, service_type: Type, instance: Any, context: ResolutionContext) -> Any:
        """Executa interceptadores after_resolution."""
        result = instance
        for interceptor in self._interceptors:
            try:
                result = interceptor.after_resolution(service_type, result, context)
                with self._lock:
                    self._metrics['interceptor_calls'] += 1
            except Exception as e:
                logger.error(f"Erro no interceptador {type(interceptor).__name__}: {e}")
        return result
    
    def _execute_error_interceptors(self, service_type: Type, error: Exception, context: ResolutionContext):
        """Executa interceptadores on_error."""
        for interceptor in self._interceptors:
            try:
                interceptor.on_error(service_type, error, context)
                with self._lock:
                    self._metrics['interceptor_calls'] += 1
            except Exception as e:
                logger.error(f"Erro no interceptador {type(interceptor).__name__}: {e}")
    
    def _should_cache(self, service_type: Type) -> bool:
        """Determina se um tipo deve ser cacheado."""
        if not self._cache_enabled:
            return False
        
        # Verifica se o tipo está registrado
        if service_type not in self._registrations:
            return False
        
        metadata = self._registrations[service_type]
        
        # Não cacheia transientes por padrão
        if metadata.lifetime == Lifetime.TRANSIENT:
            return False
        
        # Cacheia singletons e scoped
        return metadata.lifetime in [Lifetime.SINGLETON, Lifetime.SCOPED]
    
    def dispose(self):
        """Libera recursos do container."""
        # Libera singletons
        for instance in self._singletons.values():
            # Evita recursão - não tenta liberar o próprio container
            if hasattr(instance, 'dispose') and instance is not self:
                try:
                    instance.dispose()
                except Exception as e:
                    logger.warning(f"Erro ao liberar singleton: {e}")
        
        # Libera pools
        for pool in self._pools.values():
            try:
                # Pools não têm método dispose padrão, mas podemos limpar
                pool._pool.clear()
            except Exception as e:
                logger.warning(f"Erro ao liberar pool: {e}")
        
        # Libera escopos
        for scope in list(self._scopes.values()):
            scope.dispose()
        
        # Limpa tudo
        with self._lock:
            self._registrations.clear()
            self._singletons.clear()
            self._thread_locals.clear()
            self._pools.clear()
            self._scopes.clear()
        
        self.clear_cache()
        
        logger.info("Container de dependências liberado")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

# Decoradores de conveniência
def injectable(lifetime: Lifetime = Lifetime.TRANSIENT, 
              tags: Optional[List[str]] = None,
              condition: Optional[Callable[[], bool]] = None):
    """Decorador para marcar classe como injetável."""
    def decorator(cls):
        cls._di_lifetime = lifetime
        cls._di_tags = tags or []
        cls._di_condition = condition
        return cls
    return decorator

def singleton(cls):
    """Decorador para marcar classe como singleton."""
    return injectable(Lifetime.SINGLETON)(cls)

def transient(cls):
    """Decorador para marcar classe como transient."""
    return injectable(Lifetime.TRANSIENT)(cls)

def scoped(cls):
    """Decorador para marcar classe como scoped."""
    return injectable(Lifetime.SCOPED)(cls)

# Função de conveniência
def create_enhanced_container(**kwargs) -> EnhancedDependencyContainer:
    """Cria um container de dependências aprimorado."""
    return EnhancedDependencyContainer(**kwargs)