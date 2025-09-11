#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Constants
Constantes globais da aplicação
"""

import re
from typing import Dict, List, Pattern
from pathlib import Path

# Versão da aplicação
APP_VERSION = "1.0.0"

# Configurações de compressão
COMPRESSION_LEVEL_LZ4 = 1

# Informações da aplicação
APP_INFO = {
    "name": "MegaEmu DataBase ROMs",
    "version": APP_VERSION,
    "description": "Gerenciador de ROMs com suporte a temas claro e escuro",
    "author": "Seu Nome",
    "license": "MIT",
    "homepage": "https://github.com/seu-usuario/megaemu-database"
}

# Diretórios da aplicação
APP_DIRS = {
    "config": str(Path.home() / ".megaemu" / "config"),
    "data": str(Path.home() / ".megaemu" / "data"),
    "cache": str(Path.home() / ".megaemu" / "cache"),
    "logs": str(Path.home() / ".megaemu" / "logs"),
    "temp": str(Path.home() / ".megaemu" / "temp"),
    "backup": str(Path.home() / ".megaemu" / "backup"),
    "themes": str(Path.home() / ".megaemu" / "themes")
}

# Configurações de banco de dados
DB_CONFIG = {
    "timeout": 30,
    "max_connections": 5,
    "backup": {
        "enabled": True,
        "interval": 86400,  # 24h
        "max_files": 5
    }
}

# Configurações de importação
IMPORT_CONFIG = {
    "batch_size": 1000,
    "supported_formats": [".dat", ".xml"],
    "chunk_size": 8192,
    "max_workers": 4
}

# Configurações de verificação
VERIFY_CONFIG = {
    "chunk_size": 100,
    "max_workers": 4,
    "hash_types": ["md5", "sha1", "sha256"],
    "supported_formats": [
        # Nintendo
        ".nes", ".smc", ".sfc", ".gba", ".gb", ".gbc", ".n64",
        ".z64", ".v64",
        
        # Sega
        ".md", ".smd", ".gen", ".32x", ".cue", ".gdi",
        
        # Sony
        ".bin", ".iso", ".img", ".mdf", ".nrg",
        
        # Outros
        ".rom", ".zip", ".7z", ".rar"
    ]
}

# Configurações de interface
UI_CONFIG = {
    "window_size": "1024x768",
    "min_window_size": "800x600",
    "max_window_size": "1920x1080",
    "font_family": "Segoe UI",
    "font_size": 10,
    "icon_size": 16,
    "padding": 5,
    "spacing": 2,
    "border_width": 1,
    "scrollbar_width": 12
}

# Configurações de logging
LOG_CONFIG = {
    "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "level": "INFO",
    "file": "megaemu.log",
    "max_bytes": 10485760,  # 10MB
    "backup_count": 5
}

# Configurações de cache
CACHE_CONFIG = {
    "enabled": True,
    "max_size": 1000,
    "ttl": 3600,  # 1h
    "cleanup_interval": 300  # 5min
}

# Configurações de rede
NETWORK_CONFIG = {
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 5,
    "user_agent": f"MegaEmu/{APP_VERSION}"
}

# Configurações de segurança
SECURITY_CONFIG = {
    "hash_algorithm": "sha256",
    "salt_size": 16,
    "iterations": 100000
}

# Configurações de debug
DEBUG_CONFIG = {
    "enabled": False,
    "log_sql": False,
    "profile": False,
    "trace": False
}

# Mensagens de erro
ERROR_MESSAGES = {
    # Banco de dados
    "db_not_found": "Banco de dados não encontrado",
    "db_invalid": "Banco de dados inválido",
    "db_version": "Versão do banco incompatível",
    "db_locked": "Banco de dados bloqueado",
    "db_corrupt": "Banco de dados corrompido",
    
    # Arquivos
    "file_not_found": "Arquivo não encontrado",
    "file_invalid": "Arquivo inválido",
    "file_locked": "Arquivo bloqueado",
    "file_corrupt": "Arquivo corrompido",
    
    # Diretórios
    "dir_not_found": "Diretório não encontrado",
    "dir_invalid": "Diretório inválido",
    "dir_locked": "Diretório bloqueado",
    "dir_not_empty": "Diretório não está vazio",
    
    # Formatos
    "invalid_format": "Formato não suportado",
    "invalid_encoding": "Codificação inválida",
    "invalid_structure": "Estrutura inválida",
    
    # Operações
    "parse_error": "Erro ao analisar arquivo",
    "import_error": "Erro ao importar dados",
    "verify_error": "Erro ao verificar arquivo",
    "backup_error": "Erro ao fazer backup",
    "restore_error": "Erro ao restaurar backup",
    
    # Rede
    "network_error": "Erro de conexão",
    "timeout_error": "Tempo limite excedido",
    "connection_refused": "Conexão recusada",
    
    # Permissões
    "permission_error": "Permissão negada",
    "access_denied": "Acesso negado",
    "insufficient_rights": "Direitos insuficientes"
}

# Mensagens de sucesso
SUCCESS_MESSAGES = {
    # Banco de dados
    "db_created": "Banco de dados criado com sucesso",
    "db_opened": "Banco de dados aberto com sucesso",
    "db_closed": "Banco de dados fechado com sucesso",
    "db_optimized": "Banco de dados otimizado com sucesso",
    
    # Operações
    "import_complete": "Importação concluída com sucesso",
    "verify_complete": "Verificação concluída com sucesso",
    "backup_complete": "Backup concluído com sucesso",
    "restore_complete": "Restauração concluída com sucesso",
    "cleanup_complete": "Limpeza concluída com sucesso",
    
    # Configurações
    "settings_saved": "Configurações salvas com sucesso",
    "settings_loaded": "Configurações carregadas com sucesso",
    "settings_reset": "Configurações redefinidas com sucesso"
}

# Mensagens de confirmação
CONFIRM_MESSAGES = {
    # Banco de dados
    "delete_db": "Deseja excluir o banco de dados?",
    "recreate_db": "Deseja recriar o banco de dados?",
    "optimize_db": "Deseja otimizar o banco de dados?",
    
    # ROMs
    "delete_rom": "Deseja excluir a ROM selecionada?",
    "delete_roms": "Deseja excluir as ROMs selecionadas?",
    "verify_rom": "Deseja verificar a ROM selecionada?",
    "verify_roms": "Deseja verificar as ROMs selecionadas?",
    
    # Backup
    "create_backup": "Deseja criar um backup?",
    "restore_backup": "Deseja restaurar o backup selecionado?",
    "delete_backup": "Deseja excluir o backup selecionado?",
    
    # Aplicativo
    "exit_app": "Deseja sair do aplicativo?",
    "clear_cache": "Deseja limpar o cache?",
    "reset_settings": "Deseja redefinir as configurações?"
}

# Títulos de diálogos
DIALOG_TITLES = {
    # Tipos de diálogo
    "error": "Erro",
    "warning": "Aviso",
    "info": "Informação",
    "confirm": "Confirmação",
    "input": "Entrada",
    
    # Operações
    "import": "Importar",
    "verify": "Verificar",
    "backup": "Backup",
    "restore": "Restaurar",
    "settings": "Configurações",
    "about": "Sobre",
    
    # Banco de dados
    "create_db": "Criar Banco de Dados",
    "open_db": "Abrir Banco de Dados",
    "optimize_db": "Otimizar Banco de Dados",
    
    # ROMs
    "add_rom": "Adicionar ROM",
    "edit_rom": "Editar ROM",
    "delete_rom": "Excluir ROM",
    "verify_rom": "Verificar ROM"
}

# Estados de ROM
ROM_STATUS = {
    "unverified": "Não verificada",
    "verified": "Verificada",
    "partial": "Match parcial",
    "missing": "Não encontrada",
    "invalid": "Inválida",
    "corrupt": "Corrompida",
    "unknown": "Desconhecido"
}

# Tipos de ROM
ROM_TYPES = {
    "retail": "Versão oficial",
    "proto": "Protótipo",
    "beta": "Beta",
    "demo": "Demonstração",
    "sample": "Sample",
    "test": "Teste",
    "hack": "Hack",
    "trans": "Tradução",
    "unl": "Não licenciada",
    "bios": "BIOS",
    "other": "Outro"
}

# Regiões
REGIONS = {
    "JPN": "Japão",
    "USA": "Estados Unidos",
    "EUR": "Europa",
    "BRA": "Brasil",
    "ASI": "Ásia",
    "KOR": "Coréia",
    "CHN": "China",
    "TWN": "Taiwan",
    "WOR": "Mundial",
    "UNK": "Desconhecida"
}

# Idiomas
LANGUAGES = {
    "en": "Inglês",
    "ja": "Japonês",
    "fr": "Francês",
    "de": "Alemão",
    "es": "Espanhol",
    "it": "Italiano",
    "pt": "Português",
    "ko": "Coreano",
    "zh": "Chinês",
    "nl": "Holandês",
    "ru": "Russo",
    "multi": "Multi-idioma",
    "other": "Outro"
}

# Expressões regulares
REGEX_PATTERNS: Dict[str, Pattern] = {
    # Versões
    "version": re.compile(r'^\d+\.\d+\.\d+$'),
    "version_tag": re.compile(r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?$'),
    
    # Arquivos
    "filename": re.compile(r'^[\w\-. ]+$'),
    "rom_name": re.compile(r'^[\w\-. ()\[\]]+$'),
    "extension": re.compile(r'^\.[a-z0-9]+$'),
    
    # Hashes
    "md5": re.compile(r'^[a-f0-9]{32}$'),
    "sha1": re.compile(r'^[a-f0-9]{40}$'),
    "sha256": re.compile(r'^[a-f0-9]{64}$'),
    
    # Outros
    "email": re.compile(r'^[\w\-.]+@[\w\-.]+\.\w+$'),
    "url": re.compile(r'^https?://[\w\-./]+$'),
    "hex_color": re.compile(r'^#[0-9A-Fa-f]{6}$')
}

# Validadores
def is_valid_version(version: str) -> bool:
    """Valida uma string de versão."""
    return bool(REGEX_PATTERNS["version"].match(version))

def is_valid_filename(filename: str) -> bool:
    """Valida um nome de arquivo."""
    return bool(REGEX_PATTERNS["filename"].match(filename))

def is_valid_rom_name(name: str) -> bool:
    """Valida um nome de ROM."""
    return bool(REGEX_PATTERNS["rom_name"].match(name))

def is_valid_extension(ext: str) -> bool:
    """Valida uma extensão de arquivo."""
    return bool(REGEX_PATTERNS["extension"].match(ext))

def is_valid_hash(hash_str: str, hash_type: str) -> bool:
    """Valida um hash."""
    pattern = REGEX_PATTERNS.get(hash_type.lower())
    return bool(pattern and pattern.match(hash_str))

def is_valid_email(email: str) -> bool:
    """Valida um endereço de email."""
    return bool(REGEX_PATTERNS["email"].match(email))

def is_valid_url(url: str) -> bool:
    """Valida uma URL."""
    return bool(REGEX_PATTERNS["url"].match(url))

def is_valid_hex_color(color: str) -> bool:
    """Valida uma cor hexadecimal."""
    return bool(REGEX_PATTERNS["hex_color"].match(color))

def is_valid_rom_type(rom_type: str) -> bool:
    """Valida um tipo de ROM."""
    return rom_type in ROM_TYPES

def is_valid_region(region: str) -> bool:
    """Valida uma região."""
    return region in REGIONS

def is_valid_language(language: str) -> bool:
    """Valida um idioma."""
    return language in LANGUAGES

def is_valid_rom_status(status: str) -> bool:
    """Valida um estado de ROM."""
    return status in ROM_STATUS

def get_supported_formats() -> List[str]:
    """Retorna formatos suportados."""
    return VERIFY_CONFIG["supported_formats"]

def get_supported_hash_types() -> List[str]:
    """Retorna tipos de hash suportados."""
    return VERIFY_CONFIG["hash_types"]

def get_app_dirs() -> Dict[str, str]:
    """Retorna diretórios da aplicação."""
    return APP_DIRS

def create_app_dirs() -> None:
    """Cria diretórios da aplicação."""
    for dir_path in APP_DIRS.values():
        Path(dir_path).mkdir(parents=True, exist_ok=True) 