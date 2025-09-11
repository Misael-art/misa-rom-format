"""
MegaEmu DataBase ROMs - Config
Configurações do aplicativo
"""

from .app_config import AppConfig

# Import MISA constants from the new config.py file
try:
    from .config import (
        MISA_HEADER_SIZE, MISA_META_FMT, CAPP_TABLE, CODER_TABLE,
        KNOWN_BEST_RATIOS, SMALL_FILE_SIZE, MIN_GAIN_7Z
    )
except ImportError:
    # Fallback se o arquivo config.py não existir
    MISA_HEADER_SIZE = 128
    MISA_META_FMT = '<4sB B B H I I 16s Q 32s'
    CAPP_TABLE = {}
    CODER_TABLE = {}
    KNOWN_BEST_RATIOS = {}
    SMALL_FILE_SIZE = 32 * 1024 * 1024
    MIN_GAIN_7Z = 0.03

__all__ = [
    'AppConfig', 'MISA_HEADER_SIZE', 'MISA_META_FMT', 'CAPP_TABLE',
    'CODER_TABLE', 'KNOWN_BEST_RATIOS', 'SMALL_FILE_SIZE', 'MIN_GAIN_7Z'
]