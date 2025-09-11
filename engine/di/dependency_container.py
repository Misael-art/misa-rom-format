# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Dependency Injection Container
Container de dependências com injeção, lazy loading, lifetime management e factory patterns
"""

import logging
import threading
import time
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_type_hints
from functools import wraps
import inspect

logger = logging.getLogger(__name__)

T = TypeVar('T')

class Lifetime(Enum):
    """Tipos de lifetime para dependências."""
    TRANSIENT = auto()  # Nova instância a cada resolução
    SINGLETON = auto()  # Uma única instância
    SCOPED = auto()     # Uma instância por escopo
    THREAD = auto()     # Uma instância por thread

class RegistrationType(Enum):
    """Tipos de registro de dependências."""
    TYPE = auto()       # Registro por tipo
    FACTORY = auto()    # Registro por factory
    INSTANCE = auto()   # Registro por instância
    LAMBDA = auto()     # Registro por lambda

@dataclass
class DependencyRegistration:
    """Registro de uma dependência."""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: Lifetime = Lifetime.TRANSIENT
    registration_type: RegistrationType = RegistrationType.TYPE
    dependencies: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    
    def __post_init__(self):
        """Validação pós-inicialização."""
        if self.registration_type == RegistrationType.TYPE and not self.implementation_type:
            self.implementation_type = self.service_type
        elif self.registration_type == RegistrationType.FACTORY and not self.factory:
            raise ValueError("Factory é obrigatório para registro do tipo FACTORY")
        elif self.registration_type == RegistrationType.INSTANCE and self.instance is None:
            raise ValueError("Instance é obrigatória para registro do tipo INSTANCE")

class DependencyResolutionError(Exception):
    """Erro na resolução de dependências."""
    pass

class CircularDependencyError(DependencyResolutionError):
    """Erro de dependência circular."""
    pass

class IDependencyScope(ABC):
    """Interface para escopo de dependências."""
    
    @abstractmethod
    def get_scoped_instance(self, key: str) -> Optional[Any]:
        """Obtém instância do escopo."""
        pass
    
    @abstractmethod
    def set_scoped_instance(self, key: str, instance: Any) -> None:
        """Define instância no escopo."""
        pass
    
    @abstractmethod
    def dispose(self) -> None:
        """Libera recursos do escopo."""
        pass

class DependencyScope(IDependencyScope):
    """Implementação padrão de escopo de dependências."""
    
    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._disposed = False
    
    def get_scoped_instance(self, key: str) -> Optional[Any]:
        """Obtém instância do escopo."""
        if self._disposed:
            raise RuntimeError("Escopo foi liberado")
        
        with self._lock:
            return self._instances.get(key)
    
    def set_scoped_instance(self, key: str, instance: Any) -> None:
        """Define instância no escopo."""
        if self._disposed:
            raise RuntimeError("Escopo foi liberado")
        
        with self._lock:
            self._instances[key] = instance
    
    def dispose(self) -> None:
        """Libera recursos do escopo."""
        with self._lock:
            if self._disposed:
                return
            
            # Chama dispose em instâncias que implementam
            for instance in self._instances.values():
                if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.error(f"Erro ao liberar instância: {e}")
            
            self._instances.clear()
            self._disposed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

class DependencyContainer:
    """Container de injeção de dependências."""
    
    def __init__(self, parent: Optional['DependencyContainer'] = None):
        self._registrations: Dict[Type, DependencyRegistration] = {}
        self._singletons: Dict[Type, Any] = {}
        self._thread_locals = threading.local()
        self._lock = threading.RLock()
        self._parent = parent
        self._resolution_stack: List[Type] = []
        self._scopes: weakref.WeakSet = weakref.WeakSet()
        
        # Registra o próprio container
        self.register_instance(DependencyContainer, self)
    
    def register_transient(self, service_type: Type[T], implementation_type: Optional[Type[T]] = None) -> 'DependencyContainer':
        """Registra um serviço como transient."""
        return self._register(service_type, implementation_type, Lifetime.TRANSIENT, RegistrationType.TYPE)
    
    def register_singleton(self, service_type: Type[T], implementation_type: Optional[Type[T]] = None) -> 'DependencyContainer':
        """Registra um serviço como singleton."""
        return self._register(service_type, implementation_type, Lifetime.SINGLETON, RegistrationType.TYPE)
    
    def register_scoped(self, service_type: Type[T], implementation_type: Optional[Type[T]] = None) -> 'DependencyContainer':
        """Registra um serviço como scoped."""
        return self._register(service_type, implementation_type, Lifetime.SCOPED, RegistrationType.TYPE)
    
    def register_thread(self, service_type: Type[T], implementation_type: Optional[Type[T]] = None) -> 'DependencyContainer':
        """Registra um serviço como thread-local."""
        return self._register(service_type, implementation_type, Lifetime.THREAD, RegistrationType.TYPE)
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T], lifetime: Lifetime = Lifetime.TRANSIENT) -> 'DependencyContainer':
        """Registra um serviço usando factory."""
        registration = DependencyRegistration(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
            registration_type=RegistrationType.FACTORY
        )
        
        with self._lock:
            self._registrations[service_type] = registration
        
        logger.debug(f"Registrado factory para {service_type.__name__} com lifetime {lifetime.name}")
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'DependencyContainer':
        """Registra uma instância específica."""
        registration = DependencyRegistration(
            service_type=service_type,
            instance=instance,
            lifetime=Lifetime.SINGLETON,
            registration_type=RegistrationType.INSTANCE
        )
        
        with self._lock:
            self._registrations[service_type] = registration
            self._singletons[service_type] = instance
        
        logger.debug(f"Registrada instância para {service_type.__name__}")
        return self
    
    def register_lambda(self, service_type: Type[T], factory: Callable[[Any], T], lifetime: Lifetime = Lifetime.TRANSIENT) -> 'DependencyContainer':
        """Registra um serviço usando lambda que recebe o container."""
        registration = DependencyRegistration(
            service_type=service_type,
            factory=lambda: factory(self),
            lifetime=lifetime,
            registration_type=RegistrationType.LAMBDA
        )
        
        with self._lock:
            self._registrations[service_type] = registration
        
        logger.debug(f"Registrado lambda para {service_type.__name__} com lifetime {lifetime.name}")
        return self
    
    def _register(self, service_type: Type[T], implementation_type: Optional[Type[T]], lifetime: Lifetime, reg_type: RegistrationType) -> 'DependencyContainer':
        """Método interno para registro."""
        registration = DependencyRegistration(
            service_type=service_type,
            implementation_type=implementation_type or service_type,
            lifetime=lifetime,
            registration_type=reg_type
        )
        
        with self._lock:
            self._registrations[service_type] = registration
        
        impl_name = getattr(registration.implementation_type, '__name__', str(registration.implementation_type))
        logger.debug(f"Registrado {service_type.__name__} -> {impl_name} com lifetime {lifetime.name}")
        return self
    
    def resolve(self, service_type: Type[T], scope: Optional[IDependencyScope] = None) -> T:
        """Resolve uma dependência."""
        try:
            return self._resolve_internal(service_type, scope)
        except Exception as e:
            if isinstance(e, (DependencyResolutionError, CircularDependencyError)):
                raise
            raise DependencyResolutionError(f"Erro ao resolver {service_type.__name__}: {e}") from e
    
    def _resolve_internal(self, service_type: Type[T], scope: Optional[IDependencyScope] = None) -> T:
        """Resolução interna de dependências."""
        # Verifica dependência circular
        if service_type in self._resolution_stack:
            cycle = ' -> '.join([t.__name__ for t in self._resolution_stack]) + f' -> {service_type.__name__}'
            raise CircularDependencyError(f"Dependência circular detectada: {cycle}")
        
        self._resolution_stack.append(service_type)
        
        try:
            # Busca registro
            registration = self._get_registration(service_type)
            if not registration:
                raise DependencyResolutionError(f"Serviço {service_type.__name__} não registrado")
            
            # Resolve baseado no lifetime
            if registration.lifetime == Lifetime.SINGLETON:
                return self._resolve_singleton(registration)
            elif registration.lifetime == Lifetime.THREAD:
                return self._resolve_thread_local(registration)
            elif registration.lifetime == Lifetime.SCOPED:
                return self._resolve_scoped(registration, scope)
            else:  # TRANSIENT
                return self._create_instance(registration, scope)
        
        except Exception as e:
            logger.error(f"Erro em _resolve_internal: {e}", exc_info=True)
            raise
        finally:
            self._resolution_stack.pop()
    
    def _get_registration(self, service_type: Type) -> Optional[DependencyRegistration]:
        """Obtém registro de um serviço."""
        with self._lock:
            # Busca no container atual
            if service_type in self._registrations:
                return self._registrations[service_type]
            
            # Busca no container pai
            if self._parent:
                return self._parent._get_registration(service_type)
            
            return None
    
    def _resolve_singleton(self, registration: DependencyRegistration) -> Any:
        """Resolve singleton."""
        with self._lock:
            if registration.service_type in self._singletons:
                return self._singletons[registration.service_type]
            
            instance = self._create_instance(registration)
            self._singletons[registration.service_type] = instance
            return instance
    
    def _resolve_thread_local(self, registration: DependencyRegistration) -> Any:
        """Resolve thread-local."""
        if not hasattr(self._thread_locals, 'instances'):
            self._thread_locals.instances = {}
        
        if registration.service_type in self._thread_locals.instances:
            return self._thread_locals.instances[registration.service_type]
        
        instance = self._create_instance(registration)
        self._thread_locals.instances[registration.service_type] = instance
        return instance
    
    def _resolve_scoped(self, registration: DependencyRegistration, scope: Optional[IDependencyScope]) -> Any:
        """Resolve scoped."""
        if not scope:
            raise DependencyResolutionError(f"Escopo é obrigatório para resolver {registration.service_type.__name__}")
        
        key = f"{registration.service_type.__module__}.{registration.service_type.__name__}"
        instance = scope.get_scoped_instance(key)
        
        if instance is None:
            instance = self._create_instance(registration, scope)
            scope.set_scoped_instance(key, instance)
        
        return instance
    
    def _create_instance(self, registration: DependencyRegistration, scope: Optional[IDependencyScope] = None) -> Any:
        """Cria uma nova instância."""
        try:
            if registration.registration_type == RegistrationType.INSTANCE:
                return registration.instance
            
            elif registration.registration_type in (RegistrationType.FACTORY, RegistrationType.LAMBDA):
                return registration.factory()
            
            elif registration.registration_type == RegistrationType.TYPE:
                return self._create_type_instance(registration.implementation_type, scope)
            
            else:
                raise DependencyResolutionError(f"Tipo de registro não suportado: {registration.registration_type}")
        
        except Exception as e:
            logger.error(f"Erro ao criar instância de {registration.service_type.__name__}: {e}")
            raise
    
    def _create_type_instance(self, implementation_type: Type, scope: Optional[IDependencyScope] = None) -> Any:
        """Cria instância de um tipo com injeção de dependências."""
        # Verifica se é um tipo built-in que não pode ser instanciado pelo container
        builtin_types = (dict, list, set, tuple, str, int, float, bool)
        if implementation_type in builtin_types:
            # Para tipos built-in, cria instância simples sem parâmetros
            try:
                return implementation_type()
            except Exception as e:
                raise DependencyResolutionError(
                    f"Não é possível criar instância de tipo built-in {implementation_type.__name__}: {e}"
                )
        
        # Obtém construtor
        constructor = implementation_type.__init__
        
        # Analisa parâmetros do construtor
        sig = inspect.signature(constructor)
        type_hints = get_type_hints(constructor)
        
        # Resolve dependências
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            # Obtém tipo do parâmetro
            param_type = type_hints.get(param_name)
            if not param_type:
                if param.default is not inspect.Parameter.empty:
                    continue  # Parâmetro opcional com valor padrão
                raise DependencyResolutionError(
                    f"Não foi possível determinar o tipo do parâmetro '{param_name}' em {implementation_type.__name__}"
                )
            
            # Resolve dependência
            try:
                dependency = self._resolve_internal(param_type, scope)
                kwargs[param_name] = dependency
            except DependencyResolutionError:
                if param.default is not inspect.Parameter.empty:
                    continue  # Parâmetro opcional
                raise
        
        # Cria instância
        return implementation_type(**kwargs)
    
    def try_resolve(self, service_type: Type[T], scope: Optional[IDependencyScope] = None) -> Optional[T]:
        """Tenta resolver uma dependência sem lançar exceção."""
        try:
            return self.resolve(service_type, scope)
        except DependencyResolutionError:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """Verifica se um serviço está registrado."""
        return self._get_registration(service_type) is not None
    
    def create_scope(self) -> IDependencyScope:
        """Cria um novo escopo."""
        scope = DependencyScope()
        self._scopes.add(scope)
        return scope
    
    def create_child_container(self) -> 'DependencyContainer':
        """Cria um container filho."""
        return DependencyContainer(parent=self)
    
    def get_registrations(self) -> Dict[Type, DependencyRegistration]:
        """Obtém todos os registros."""
        with self._lock:
            registrations = self._registrations.copy()
        
        if self._parent:
            parent_registrations = self._parent.get_registrations()
            # Registros do container atual têm prioridade
            for service_type, registration in parent_registrations.items():
                if service_type not in registrations:
                    registrations[service_type] = registration
        
        return registrations
    
    def clear_singletons(self):
        """Limpa cache de singletons."""
        with self._lock:
            # Cria cópia da lista para evitar 'dictionary changed size during iteration'
            singleton_instances = list(self._singletons.values())
            
        # Chama dispose em singletons que implementam (fora do lock)
        for instance in singleton_instances:
            if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Erro ao liberar singleton: {e}")
        
        with self._lock:
            self._singletons.clear()
    
    def dispose(self):
        """Libera recursos do container."""
        self.clear_singletons()
        
        # Libera thread locals
        if hasattr(self._thread_locals, 'instances'):
            # Cria cópia da lista para evitar 'dictionary changed size during iteration'
            thread_local_instances = list(self._thread_locals.instances.values())
            
            for instance in thread_local_instances:
                if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.error(f"Erro ao liberar thread local: {e}")
            
            self._thread_locals.instances.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

# Decorators para injeção de dependências
def inject(container: DependencyContainer):
    """Decorator para injeção automática de dependências."""
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve dependências não fornecidas
            for param_name, param in sig.parameters.items():
                if param_name in kwargs:
                    continue  # Já fornecido
                
                param_type = type_hints.get(param_name)
                if param_type and container.is_registered(param_type):
                    kwargs[param_name] = container.resolve(param_type)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def injectable(service_type: Optional[Type] = None, lifetime: Lifetime = Lifetime.TRANSIENT):
    """Decorator para marcar classe como injetável."""
    def decorator(cls: Type) -> Type:
        # Adiciona metadados
        cls._injectable_service_type = service_type or cls
        cls._injectable_lifetime = lifetime
        
        return cls
    
    return decorator

# Container global padrão
_default_container: Optional[DependencyContainer] = None
_container_lock = threading.Lock()

def get_default_container() -> DependencyContainer:
    """Obtém o container padrão global."""
    global _default_container
    
    if _default_container is None:
        with _container_lock:
            if _default_container is None:
                _default_container = DependencyContainer()
    
    return _default_container

def set_default_container(container: DependencyContainer):
    """Define o container padrão global."""
    global _default_container
    
    with _container_lock:
        _default_container = container

def resolve(service_type: Type[T], scope: Optional[IDependencyScope] = None) -> T:
    """Resolve uma dependência usando o container padrão."""
    return get_default_container().resolve(service_type, scope)

def try_resolve(service_type: Type[T], scope: Optional[IDependencyScope] = None) -> Optional[T]:
    """Tenta resolver uma dependência usando o container padrão."""
    return get_default_container().try_resolve(service_type, scope)

# Plugin system
class IPlugin(ABC):
    """Interface para plugins."""
    
    @abstractmethod
    def configure(self, container: DependencyContainer) -> None:
        """Configura o plugin no container."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do plugin."""
        pass

class PluginManager:
    """Gerenciador de plugins."""
    
    def __init__(self, container: DependencyContainer):
        self.container = container
        self._plugins: Dict[str, IPlugin] = {}
        self._lock = threading.RLock()
    
    def register_plugin(self, plugin: IPlugin):
        """Registra um plugin."""
        with self._lock:
            if plugin.name in self._plugins:
                raise ValueError(f"Plugin '{plugin.name}' já está registrado")
            
            self._plugins[plugin.name] = plugin
            plugin.configure(self.container)
            
            logger.info(f"Plugin '{plugin.name}' registrado")
    
    def get_plugin(self, name: str) -> Optional[IPlugin]:
        """Obtém um plugin pelo nome."""
        with self._lock:
            return self._plugins.get(name)
    
    def get_plugins(self) -> List[IPlugin]:
        """Obtém todos os plugins."""
        with self._lock:
            return list(self._plugins.values())