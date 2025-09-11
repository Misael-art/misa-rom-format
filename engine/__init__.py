"""
Pacote principal da aplicação.
"""

from .db import DatabaseManager
from .config import AppConfig
from .services import ImportService, VerificationService
from .ui import MainWindow, ThemeManager, ProgressDialog
from .errors import (
    MegaEmuError,
    DatabaseError,
    ValidationError,
    ConfigError,
    ThemeError,
    FileSystemError,
    RomProcessingError,
    NetworkError,
    CacheError,
    SecurityError,
    MigrationError,
    ResourceError,
    PluginError,
    UserCancelledError,
    TimeoutError,
    ConcurrentAccessError
)

__all__ = [
    "DatabaseManager",
    "AppConfig",
    "ImportService",
    "VerificationService",
    "MainWindow",
    "ThemeManager",
    "ProgressDialog",
    # Exceções
    "MegaEmuError",
    "DatabaseError",
    "ValidationError",
    "ConfigError",
    "ThemeError",
    "FileSystemError",
    "RomProcessingError",
    "NetworkError",
    "CacheError",
    "SecurityError",
    "MigrationError",
    "ResourceError",
    "PluginError",
    "UserCancelledError",
    "TimeoutError",
    "ConcurrentAccessError"
]
