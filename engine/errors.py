"""
Sistema de exceções customizadas para MegaEmu DataBase ROMs.

Este módulo define uma hierarquia de exceções específicas para diferentes
tipos de erros que podem ocorrer na aplicação, permitindo tratamento
mais preciso e informativo.
"""

import sqlite3
from typing import Optional, Dict, Any


class MegaEmuError(Exception):
    """Exceção base para todos os erros da aplicação."""
    
    def __init__(self, message: str, error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DatabaseError(MegaEmuError):
    """Erros relacionados ao banco de dados."""
    
    def __init__(self, message: str, sqlite_error: Optional[Exception] = None,
                 query: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="DB_ERROR",
            details={
                "sqlite_error": str(sqlite_error) if sqlite_error else None,
                "query": query,
                **kwargs
            }
        )
        self.sqlite_error = sqlite_error
        self.query = query


class ValidationError(MegaEmuError):
    """Erros de validação de dados."""
    
    def __init__(self, message: str, field: Optional[str] = None,
                 value: Optional[Any] = None, **kwargs):
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            details={
                "field": field,
                "value": value,
                **kwargs
            }
        )
        self.field = field
        self.value = value


class ConfigError(MegaEmuError):
    """Erros de configuração."""
    
    def __init__(self, message: str, config_key: Optional[str] = None,
                 config_file: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            details={
                "config_key": config_key,
                "config_file": config_file,
                **kwargs
            }
        )
        self.config_key = config_key
        self.config_file = config_file


class ThemeError(MegaEmuError):
    """Erros relacionados ao tema/visual."""
    
    def __init__(self, message: str, theme_name: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="THEME_ERROR",
            details={
                "theme_name": theme_name,
                **kwargs
            }
        )
        self.theme_name = theme_name


class FileSystemError(MegaEmuError):
    """Erros de sistema de arquivos."""
    
    def __init__(self, message: str, path: Optional[str] = None,
                 operation: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="FILESYSTEM_ERROR",
            details={
                "path": path,
                "operation": operation,
                **kwargs
            }
        )
        self.path = path
        self.operation = operation


class RomProcessingError(MegaEmuError):
    """Erros durante processamento de ROMs."""
    
    def __init__(self, message: str, rom_path: Optional[str] = None,
                 rom_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="ROM_PROCESSING_ERROR",
            details={
                "rom_path": rom_path,
                "rom_type": rom_type,
                **kwargs
            }
        )
        self.rom_path = rom_path
        self.rom_type = rom_type


class NetworkError(MegaEmuError):
    """Erros de rede (para futuras funcionalidades online)."""
    
    def __init__(self, message: str, url: Optional[str] = None,
                 status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message,
            error_code="NETWORK_ERROR",
            details={
                "url": url,
                "status_code": status_code,
                **kwargs
            }
        )
        self.url = url
        self.status_code = status_code


class CacheError(MegaEmuError):
    """Erros relacionados ao sistema de cache."""
    
    def __init__(self, message: str, cache_key: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="CACHE_ERROR",
            details={
                "cache_key": cache_key,
                **kwargs
            }
        )
        self.cache_key = cache_key


class SecurityError(MegaEmuError):
    """Erros de segurança (validação de entrada, etc.)."""
    
    def __init__(self, message: str, security_issue: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="SECURITY_ERROR",
            details={
                "security_issue": security_issue,
                **kwargs
            }
        )
        self.security_issue = security_issue


class MigrationError(MegaEmuError):
    """Erros durante migração de banco de dados."""
    
    def __init__(self, message: str, migration_version: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="MIGRATION_ERROR",
            details={
                "migration_version": migration_version,
                **kwargs
            }
        )
        self.migration_version = migration_version


class ResourceError(MegaEmuError):
    """Erros de recursos (memória, CPU, etc.)."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None,
                 current_usage: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            error_code="RESOURCE_ERROR",
            details={
                "resource_type": resource_type,
                "current_usage": current_usage,
                **kwargs
            }
        )
        self.resource_type = resource_type
        self.current_usage = current_usage


class PluginError(MegaEmuError):
    """Erros relacionados ao sistema de plugins."""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="PLUGIN_ERROR",
            details={
                "plugin_name": plugin_name,
                **kwargs
            }
        )
        self.plugin_name = plugin_name


class UserCancelledError(MegaEmuError):
    """Erro quando o usuário cancela uma operação."""
    
    def __init__(self, message: str = "Operação cancelada pelo usuário",
                 operation: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="USER_CANCELLED",
            details={
                "operation": operation,
                **kwargs
            }
        )
        self.operation = operation


class TimeoutError(MegaEmuError):
    """Erro de timeout em operações."""
    
    def __init__(self, message: str, timeout_seconds: Optional[float] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="TIMEOUT_ERROR",
            details={
                "timeout_seconds": timeout_seconds,
                **kwargs
            }
        )
        self.timeout_seconds = timeout_seconds


class ConcurrentAccessError(MegaEmuError):
    """Erro de acesso concorrente a recursos."""
    
    def __init__(self, message: str, resource: Optional[str] = None,
                 **kwargs):
        super().__init__(
            message,
            error_code="CONCURRENT_ACCESS_ERROR",
            details={
                "resource": resource,
                **kwargs
            }
        )
        self.resource = resource


# Funções utilitárias para tratamento de erros
def handle_database_error(sqlite_error: sqlite3.Error, query: Optional[str] = None) -> DatabaseError:
    """Converte erro SQLite em DatabaseError com contexto apropriado."""
    error_msg = str(sqlite_error)
    
    if "no such table" in error_msg.lower():
        return DatabaseError(
            f"Tabela não encontrada: {error_msg}",
            sqlite_error=sqlite_error,
            query=query
        )
    elif "no such column" in error_msg.lower():
        return DatabaseError(
            f"Coluna não encontrada: {error_msg}",
            sqlite_error=sqlite_error,
            query=query
        )
    elif "syntax error" in error_msg.lower():
        return DatabaseError(
            f"Erro de sintaxe SQL: {error_msg}",
            sqlite_error=sqlite_error,
            query=query
        )
    elif "constraint" in error_msg.lower():
        return DatabaseError(
            f"Violação de constraint: {error_msg}",
            sqlite_error=sqlite_error,
            query=query
        )
    else:
        return DatabaseError(
            f"Erro de banco de dados: {error_msg}",
            sqlite_error=sqlite_error,
            query=query
        )


def handle_file_error(os_error: OSError, path: str, operation: str) -> FileSystemError:
    """Converte erro OS em FileSystemError com contexto."""
    error_msg = str(os_error)
    
    if os_error.errno == 2:  # No such file or directory
        return FileSystemError(
            f"Arquivo ou diretório não encontrado: {path}",
            path=path,
            operation=operation
        )
    elif os_error.errno == 13:  # Permission denied
        return FileSystemError(
            f"Permissão negada: {path}",
            path=path,
            operation=operation
        )
    elif os_error.errno == 28:  # No space left on device
        return FileSystemError(
            f"Espaço insuficiente no dispositivo: {path}",
            path=path,
            operation=operation
        )
    else:
        return FileSystemError(
            f"Erro de sistema de arquivos: {error_msg}",
            path=path,
            operation=operation
        )