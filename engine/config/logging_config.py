#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Logging Config
Configuração do sistema de logging
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List
from datetime import datetime

# Níveis de log válidos
VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

def validate_log_level(level: str) -> str:
    """
    Valida e retorna um nível de log válido.
    
    Args:
        level: Nível de log para validar
    
    Returns:
        str: Nível de log válido
    """
    level = level.upper()
    if level not in VALID_LOG_LEVELS:
        print(f"Nível de log inválido: {level}. Usando INFO como padrão.")
        return 'INFO'
    return level

def validate_log_format(fmt: str) -> str:
    """
    Valida e retorna um formato de log válido.
    
    Args:
        fmt: Formato para validar
    
    Returns:
        str: Formato válido
    """
    required_fields = ['%(levelname)s', '%(message)s']
    for field in required_fields:
        if field not in fmt:
            fmt += f" {field}"
    return fmt

def setup_logging(
    log_file: str = "megaemu.log",
    log_level: str = "INFO",
    log_format: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> Dict[str, str]:
    """
    Configura o sistema de logging.
    
    Args:
        log_file: Caminho do arquivo de log
        log_level: Nível de log
        log_format: Formato do log
        max_bytes: Tamanho máximo do arquivo
        backup_count: Número de backups
    
    Returns:
        Dict[str, str]: Configurações aplicadas
    """
    try:
        # Valida nível de log
        log_level = validate_log_level(log_level)
        
        # Cria diretório se não existir
        log_dir = os.path.dirname(os.path.abspath(log_file))
        os.makedirs(log_dir, exist_ok=True)
        
        # Formato padrão
        if not log_format:
            log_format = (
                "%(asctime)s [%(levelname)s] "
                "%(name)s:%(lineno)d - %(message)s"
            )
        
        # Valida formato
        log_format = validate_log_format(log_format)
        
        # Configura formato
        formatter = logging.Formatter(
            fmt=log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Handler para arquivo com rotação
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max(1024, max_bytes),  # Mínimo 1KB
            backupCount=max(1, backup_count),  # Mínimo 1 backup
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configura root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        
        # Remove handlers existentes
        root_logger.handlers.clear()
        
        # Adiciona handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Registra início do logging
        root_logger.info(
            f"Logging iniciado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"com nível {log_level}"
        )
        
        # Retorna configurações
        return {
            "file": log_file,
            "level": log_level,
            "format": log_format,
            "max_bytes": str(max_bytes),
            "backup_count": str(backup_count),
            "status": "success"
        }
        
    except Exception as e:
        error_msg = f"Erro ao configurar logging: {str(e)}"
        print(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_log_files(log_dir: str) -> List[str]:
    """
    Retorna lista de arquivos de log.
    
    Args:
        log_dir: Diretório dos logs
    
    Returns:
        List[str]: Lista de arquivos
    """
    try:
        if not os.path.exists(log_dir):
            return []
            
        files = []
        for f in os.listdir(log_dir):
            if f.endswith('.log'):
                files.append(os.path.join(log_dir, f))
        return sorted(files)
        
    except Exception:
        return [] 