#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Constantes da Aplicação
Define todas as constantes usadas no projeto para evitar números mágicos.
"""

# =============================================================================
# CONFIGURAÇÕES DE JANELA E INTERFACE
# =============================================================================

# Tamanhos de janela padrão
DEFAULT_WINDOW_SIZE = "1024x768"
WELCOME_WINDOW_SIZE = "800x600"
WELCOME_MIN_SIZE = "700x500"
PROGRESS_DIALOG_SIZE = "400x150"
DETAILS_DIALOG_SIZE = "500x400"
SETTINGS_DIALOG_SIZE = "600x500"

# Resoluções de tela
SCREEN_RESOLUTION_HD = "1920x1080"
SCREEN_RESOLUTION_DEFAULT = "1200x800"

# Configurações de layout
NAVIGATION_PANEL_WIDTH = 250
STATUS_BAR_HEIGHT = 25
TOOLBAR_ICON_SIZE = 24
BUTTON_PADDING = 2
GROUP_SPACING = 10

# =============================================================================
# TIMEOUTS E INTERVALOS
# =============================================================================

# Timeouts de conexão e operações
DB_CONNECTION_TIMEOUT = 30.0
DB_CONNECTION_TIMEOUT_SHORT = 10.0
NETWORK_TIMEOUT = 10
HTTP_TIMEOUT = 10

# Intervalos de monitoramento
TASK_MONITOR_INTERVAL = 5000  # ms
MEMORY_MONITOR_INTERVAL = 60000  # ms (1 minuto)
BACKUP_INTERVAL_HOURS = 24
BACKUP_INTERVAL_MAX_HOURS = 168  # 1 semana

# Timeouts para UI
WELCOME_SCREEN_DELAY = 1000  # ms
MESSAGE_DURATION_DEFAULT = 5.0  # segundos
PROGRESS_ANIMATION_INTERVAL = 10  # ms

# =============================================================================
# CONFIGURAÇÕES DE BANCO DE DADOS
# =============================================================================

# Pool de conexões
DB_MAX_CONNECTIONS = 20
DB_MIN_CONNECTIONS = 5
DB_MAX_CONNECTIONS_CONFIG = 5
DB_MIN_CONNECTIONS_CONFIG = 2
DB_CONNECTION_RETRY_ATTEMPTS = 3
DB_CONNECTION_RETRY_DELAY = 0.5  # segundos

# Timeouts de banco
DB_IDLE_TIMEOUT = 300.0  # segundos
DB_HEALTH_CHECK_INTERVAL = 60.0  # segundos
DB_OPERATION_TIMEOUT = 30.0  # segundos

# Configurações de importação
IMPORT_BATCH_SIZE = 1000
IMPORT_BATCH_SIZE_MAX = 10000
IMPORT_RETRY_ATTEMPTS = 3
IMPORT_RETRY_BACKOFF = 1.0  # segundos

# Limites de dados
MAX_RECORDS_DISPLAY = 1000
MAX_RECORDS_PER_PAGE = 50
MAX_STATUS_MESSAGES = 100
MAX_RECENT_DATABASES = 10

# =============================================================================
# TAMANHOS DE BUFFER E ARQUIVOS
# =============================================================================

# Tamanhos de buffer
BUFFER_SIZE_1KB = 1024
BUFFER_SIZE_4KB = 4096
BUFFER_SIZE_8KB = 8192

# Tamanhos de arquivo
MIN_DISK_SPACE_MB = 100
MAX_FILE_SIZE_MB = 1024
TEMP_FILE_SIZE_MB = 10

# =============================================================================
# CONFIGURAÇÕES DE SISTEMA
# =============================================================================

# Versão mínima do Python
PYTHON_MIN_VERSION = (3, 8)

# Configurações de logging
LOG_ROTATION_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_ROTATION_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# CONFIGURAÇÕES DE PERFORMANCE
# =============================================================================

# Threading
MAX_WORKERS_DEFAULT = 4
MAX_WORKERS_UI = 2
THREAD_POOL_TIMEOUT = 5.0  # segundos

# Cache
CACHE_TTL_SECONDS = 3600  # 1 hora
CACHE_MAX_SIZE_MB = 100
CACHE_CLEANUP_INTERVAL = 300  # segundos

# =============================================================================
# CONFIGURAÇÕES DE UI E TEMAS
# =============================================================================

# Cores de tema (valores hexadecimais)
THEME_LIGHT_BG = "#f5f5f5"
THEME_LIGHT_FG = "#212121"
THEME_LIGHT_ACCENT = "#2196F3"

THEME_DARK_BG = "#333333"
THEME_DARK_FG = "#f5f5f5"
THEME_DARK_ACCENT = "#64B5F6"

# Fontes
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 10
DEFAULT_FONT_SIZE_LARGE = 12
DEFAULT_FONT_SIZE_TITLE = 24
DEFAULT_FONT_SIZE_LOGO = 48

# Padding e margens
DEFAULT_PADDING = 10
DEFAULT_PADDING_SMALL = 5
DEFAULT_MARGIN = 5

# =============================================================================
# CONFIGURAÇÕES DE VALIDAÇÃO E LIMITES
# =============================================================================

# Limites de entrada
MAX_PATH_LENGTH = 260  # Windows MAX_PATH
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 1000
MAX_QUERY_LENGTH = 10000

# Limites de processamento
MAX_CONCURRENT_IMPORTS = 5
MAX_CONCURRENT_VERIFICATIONS = 10
MAX_BATCH_SIZE = 10000

# =============================================================================
# CONSTANTES DE STATUS E FLAGS
# =============================================================================

# Status de operações
STATUS_SUCCESS = 0
STATUS_ERROR = 1
STATUS_WARNING = 2
STATUS_INFO = 3

# Estados de conexão
CONNECTION_CONNECTED = "connected"
CONNECTION_DISCONNECTED = "disconnected"
CONNECTION_CONNECTING = "connecting"
CONNECTION_ERROR = "error"

# Tipos de arquivo
FILE_TYPE_DATABASE = ".db"
FILE_TYPE_DAT = ".dat"
FILE_TYPE_XML = ".xml"
FILE_TYPE_INI = ".ini"
FILE_TYPE_TXT = ".txt"

# =============================================================================
# CONSTANTES DE MENSAGENS E TEXTOS
# =============================================================================

# Títulos de janelas
APP_TITLE = "MegaEmu DataBase ROMs"
APP_VERSION = "1.0.0"
WELCOME_TITLE = "Bem-vindo ao MegaEmu DataBase ROMs"
PROGRESS_TITLE = "Processando..."
ERROR_TITLE = "Erro"
WARNING_TITLE = "Aviso"
INFO_TITLE = "Informação"

# Mensagens padrão
MSG_READY = "Pronto"
MSG_LOADING = "Carregando..."
MSG_PROCESSING = "Processando..."
MSG_COMPLETED = "Concluído"
MSG_CANCELLED = "Cancelado"
MSG_ERROR_GENERIC = "Ocorreu um erro inesperado"
MSG_SUCCESS = "Operação realizada com sucesso"

# =============================================================================
# CONFIGURAÇÕES DE DIRETÓRIOS
# =============================================================================

# Diretórios padrão
DIR_LOGS = "logs"
DIR_DATA = "data"
DIR_CONFIG = "config"
DIR_BACKUP = "backup"
DIR_TEMP = "temp"
DIR_ASSETS = "assets"
DIR_META = "meta"

# Arquivos padrão
FILE_CONFIG_DEFAULT = "config/default.json"
FILE_DATABASE_DEFAULT = "data/default.db"
FILE_DATABASE_GAME_DATA = "data/game_data.db"
FILE_LOG_FORMAT = "app_%Y%m%d_%H%M%S.log"

# =============================================================================
# CONFIGURAÇÕES DE API E REDE
# =============================================================================

# User agent para requests HTTP
DEFAULT_USER_AGENT = "MegaEmu-DataBase/1.0.0"

# Configurações de rate limiting
RATE_LIMIT_REQUESTS_PER_SECOND = 1.0
RATE_LIMIT_DELAY_SECONDS = 1.0

# Configurações de retry
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_MULTIPLIER = 2.0
RETRY_MAX_DELAY = 60.0  # segundos

# =============================================================================
# CONSTANTES DE VALIDAÇÃO DE ARQUIVOS
# =============================================================================

# Extensões de arquivo suportadas
SUPPORTED_EXTENSIONS = {
    'database': ['.db', '.sqlite', '.sqlite3'],
    'dat': ['.dat', '.xml'],
    'config': ['.ini', '.cfg', '.json'],
    'archive': ['.zip', '.rar', '.7z', '.tar.gz'],
    'image': ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
}

# Tamanhos de hash
HASH_MD5_LENGTH = 32
HASH_SHA1_LENGTH = 40
HASH_SHA256_LENGTH = 64
HASH_CRC32_LENGTH = 8

# =============================================================================
# OUTRAS CONSTANTES
# =============================================================================

# Valores booleanos como inteiros (para SQL)
BOOL_TRUE = 1
BOOL_FALSE = 0

# Valores de progresso
PROGRESS_MIN = 0.0
PROGRESS_MAX = 100.0
PROGRESS_COMPLETE = 100.0

# Fatores de conversão
BYTES_TO_KB = 1024
BYTES_TO_MB = 1024 * 1024
BYTES_TO_GB = 1024 * 1024 * 1024

# Códigos de saída
EXIT_SUCCESS = 0
EXIT_ERROR = 1

# Prioridades de tarefa
TASK_PRIORITY_LOW = 0
TASK_PRIORITY_NORMAL = 1
TASK_PRIORITY_HIGH = 2
TASK_PRIORITY_CRITICAL = 3

# =============================================================================
# CONFIGURAÇÕES DE MONITORAMENTO MCP
# =============================================================================

CHECK_INTERVAL = 86400  # segundos (diário)
MCP_LOG_LEVEL = "INFO"