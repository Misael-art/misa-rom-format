#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Common Utils
Funções utilitárias comuns
"""

import os
import re
import hashlib
import logging
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Tipos MIME suportados
SUPPORTED_MIME_TYPES = {
    # ROMs
    'application/x-nes-rom',
    'application/x-gameboy-rom',
    'application/x-gba-rom',
    'application/x-n64-rom',
    'application/x-genesis-rom',
    'application/x-sega-cd-rom',
    
    # Arquivos
    'application/x-iso9660-image',
    'application/x-cd-image',
    'application/x-raw-disk-image',
    
    # Compactados
    'application/zip',
    'application/x-7z-compressed',
    'application/x-rar-compressed'
}

def is_valid_file_path(file_path: str) -> bool:
    """
    Valida um caminho de arquivo.
    
    Args:
        file_path: Caminho para validar
    
    Returns:
        bool: True se válido
    """
    try:
        path = Path(file_path)
        return path.is_file()
    except Exception:
        return False

def is_valid_dir_path(dir_path: str) -> bool:
    """
    Valida um caminho de diretório.
    
    Args:
        dir_path: Caminho para validar
    
    Returns:
        bool: True se válido
    """
    try:
        path = Path(dir_path)
        return path.is_dir()
    except Exception:
        return False

def is_valid_mime_type(file_path: str) -> bool:
    """
    Verifica se o tipo MIME é suportado.
    
    Args:
        file_path: Caminho do arquivo
    
    Returns:
        bool: True se suportado
    """
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type in SUPPORTED_MIME_TYPES
    except Exception:
        return False

def calculate_file_hash(
    file_path: str,
    algorithms: List[str] = ["md5", "sha1", "sha256"],
    chunk_size: int = 8192
) -> Dict[str, str]:
    """
    Calcula hashes de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
        algorithms: Lista de algoritmos
        chunk_size: Tamanho do chunk de leitura
    
    Returns:
        Dict[str, str]: Dicionário com os hashes
    """
    try:
        # Valida caminho
        if not is_valid_file_path(file_path):
            raise ValueError("Caminho de arquivo inválido")
        
        # Valida algoritmos
        valid_algos = []
        for algo in algorithms:
            if hasattr(hashlib, algo):
                valid_algos.append(algo)
            else:
                logger.warning(f"Algoritmo não suportado: {algo}")
        
        if not valid_algos:
            raise ValueError("Nenhum algoritmo válido fornecido")
        
        # Inicializa hashers
        hashers = {
            algo: getattr(hashlib, algo)()
            for algo in valid_algos
        }
        
        # Valida tamanho do chunk
        chunk_size = max(1024, min(chunk_size, 1024 * 1024))  # Entre 1KB e 1MB
        
        # Calcula hashes
        file_size = os.path.getsize(file_path)
        processed = 0
        
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                    
                for hasher in hashers.values():
                    hasher.update(chunk)
                
                processed += len(chunk)
                if processed % (1024 * 1024) == 0:  # Log a cada 1MB
                    progress = (processed / file_size) * 100
                    logger.debug(f"Progresso do hash: {progress:.1f}%")
        
        # Retorna resultados
        return {
            algo: hasher.hexdigest()
            for algo, hasher in hashers.items()
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash de {file_path}: {str(e)}")
        return {}

def format_file_size(size: int) -> str:
    """
    Formata tamanho de arquivo.
    
    Args:
        size: Tamanho em bytes
    
    Returns:
        str: Tamanho formatado
    """
    try:
        if not isinstance(size, (int, float)) or size < 0:
            raise ValueError("Tamanho inválido")
            
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(size)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        # Ajusta precisão decimal
        if unit_index == 0:  # Bytes
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
            
    except Exception as e:
        logger.error(f"Erro ao formatar tamanho: {str(e)}")
        return "0 B"

def parse_rom_name(name: str) -> Dict[str, str]:
    """
    Extrai informações do nome da ROM.
    
    Args:
        name: Nome da ROM
    
    Returns:
        Dict[str, str]: Informações extraídas
    """
    try:
        if not name or not isinstance(name, str):
            raise ValueError("Nome inválido")
        
        info = {
            "title": "",
            "region": "",
            "language": "",
            "version": "",
            "type": "",
            "flags": []
        }
        
        # Remove extensão
        name = os.path.splitext(name)[0].strip()
        if not name:
            return info
        
        # Extrai flags entre () e []
        for pattern in [r"\((.*?)\)", r"\[(.*?)\]"]:
            flags = re.findall(pattern, name)
            if flags:
                # Filtra flags vazias
                valid_flags = [f.strip() for f in flags if f.strip()]
                info["flags"].extend(valid_flags)
                
                # Remove flags do nome
                for flag in flags:
                    name = name.replace(
                        f"({pattern[1]}{flag}{pattern[1]})",
                        ""
                    )
        
        # Remove caracteres especiais
        name = re.sub(r"[^\w\s-]", " ", name)
        
        # Divide em partes
        parts = [p.strip() for p in name.split() if p.strip()]
        if not parts:
            return info
        
        # Primeira parte é o título
        info["title"] = parts[0]
        
        # Dicionários de classificação
        regions = {"USA", "EUR", "JPN", "BRA", "ASI", "KOR", "CHN", "TWN"}
        languages = {"EN", "JP", "FR", "DE", "ES", "IT", "PT", "KO", "ZH"}
        types = {"PROTO", "BETA", "DEMO", "SAMPLE", "BIOS", "HACK", "UNL"}
        
        # Analisa outras partes
        for part in parts[1:]:
            part = part.upper()
            
            # Região
            if part in regions:
                info["region"] = part
            
            # Idioma
            elif part in languages:
                info["language"] = part
            
            # Versão
            elif re.match(r"^(V\d+|REV[A-Z]|\d+\.\d+)$", part):
                info["version"] = part
            
            # Tipo
            elif part in types:
                info["type"] = part
            
            # Adiciona ao título se não classificado
            else:
                info["title"] += f" {part}"
        
        # Limpa título
        info["title"] = info["title"].strip()
        
        return info
        
    except Exception as e:
        logger.error(f"Erro ao analisar nome da ROM: {str(e)}")
        return {
            "title": name,
            "region": "",
            "language": "",
            "version": "",
            "type": "",
            "flags": []
        }

def clean_rom_name(name: str) -> str:
    """
    Limpa nome da ROM.
    
    Args:
        name: Nome original
    
    Returns:
        str: Nome limpo
    """
    try:
        if not name or not isinstance(name, str):
            raise ValueError("Nome inválido")
        
        # Remove extensão
        name = os.path.splitext(name)[0]
        
        # Remove tags entre () e []
        name = re.sub(r"\(.*?\)|\[.*?\]", "", name)
        
        # Remove caracteres especiais mantendo alguns
        name = re.sub(r"[^\w\s\-&+']", " ", name)
        
        # Remove espaços extras e caracteres de controle
        name = " ".join(
            part for part in name.split()
            if part and not part.isspace()
        )
        
        # Limita tamanho
        if len(name) > 100:
            name = name[:97] + "..."
        
        return name.strip()
        
    except Exception as e:
        logger.error(f"Erro ao limpar nome da ROM: {str(e)}")
        return name if isinstance(name, str) else ""

def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Obtém informações de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
    
    Returns:
        Dict[str, Any]: Informações do arquivo
    """
    try:
        # Valida caminho
        if not is_valid_file_path(file_path):
            raise ValueError("Caminho de arquivo inválido")
        
        # Obtém informações básicas
        path = Path(file_path)
        stat = path.stat()
        
        info = {
            "name": path.name,
            "path": str(path.absolute()),
            "size": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "extension": path.suffix.lower(),
            "mime_type": mimetypes.guess_type(file_path)[0],
            "is_hidden": path.name.startswith("."),
            "is_readonly": not os.access(file_path, os.W_OK),
            "parent_dir": str(path.parent)
        }
        
        # Verifica permissões
        try:
            info["permissions"] = oct(stat.st_mode)[-3:]
        except Exception:
            info["permissions"] = "000"
        
        # Calcula hashes em thread separada
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(calculate_file_hash, file_path)
            hashes = future.result(timeout=30)  # Timeout de 30s
            info.update(hashes)
        
        return info
        
    except Exception as e:
        logger.error(f"Erro ao obter informações do arquivo: {str(e)}")
        return {}

def validate_rom_file(
    file_path: str,
    expected_hash: Optional[str] = None,
    hash_type: str = "sha1"
) -> Tuple[bool, str]:
    """
    Valida um arquivo ROM.
    
    Args:
        file_path: Caminho do arquivo
        expected_hash: Hash esperado
        hash_type: Tipo de hash
    
    Returns:
        Tuple[bool, str]: (válido, mensagem)
    """
    try:
        # Valida caminho
        if not is_valid_file_path(file_path):
            return False, "Arquivo não encontrado"
        
        # Valida extensão
        ext = Path(file_path).suffix.lower()
        if not ext:
            return False, "Arquivo sem extensão"
        
        # Valida tipo MIME
        if not is_valid_mime_type(file_path):
            return False, "Tipo de arquivo não suportado"
        
        # Valida tamanho
        size = os.path.getsize(file_path)
        if size == 0:
            return False, "Arquivo vazio"
        if size > 10 * 1024 * 1024 * 1024:  # 10GB
            return False, "Arquivo muito grande"
        
        # Valida hash se fornecido
        if expected_hash:
            if not isinstance(expected_hash, str):
                return False, "Hash esperado inválido"
                
            if hash_type not in ["md5", "sha1", "sha256"]:
                return False, "Tipo de hash não suportado"
                
            # Calcula hash
            hashes = calculate_file_hash(file_path, [hash_type])
            if not hashes:
                return False, "Erro ao calcular hash"
                
            actual_hash = hashes.get(hash_type, "")
            if not actual_hash:
                return False, "Hash não calculado"
                
            if actual_hash.lower() != expected_hash.lower():
                return False, "Hash não corresponde"
        
        return True, "Arquivo válido"
        
    except Exception as e:
        logger.error(f"Erro ao validar arquivo: {str(e)}")
        return False, f"Erro ao validar: {str(e)}"

def scan_directory(
    directory: str,
    extensions: Optional[List[str]] = None,
    recursive: bool = True,
    max_files: int = 10000,
    max_size: int = 100 * 1024 * 1024 * 1024  # 100GB
) -> List[Dict[str, Any]]:
    """
    Escaneia um diretório em busca de arquivos.
    
    Args:
        directory: Diretório para escanear
        extensions: Lista de extensões
        recursive: Busca recursiva
        max_files: Número máximo de arquivos
        max_size: Tamanho máximo total
    
    Returns:
        List[Dict[str, Any]]: Lista de arquivos
    """
    try:
        # Valida diretório
        if not is_valid_dir_path(directory):
            raise ValueError("Diretório inválido")
        
        # Normaliza extensões
        if extensions:
            extensions = [ext.lower() if ext.startswith(".") else f".{ext.lower()}"
                      for ext in extensions]
        
        # Inicializa contadores
        total_files = 0
        total_size = 0
        processed_files: List[Dict[str, Any]] = []
        errors: List[str] = []
        
        def process_file(file_path: str) -> Optional[Dict[str, Any]]:
            """Processa um arquivo."""
            try:
                # Verifica extensão
                if extensions and Path(file_path).suffix.lower() not in extensions:
                    return None
                
                # Obtém informações
                info = get_file_info(file_path)
                if not info:
                    return None
                
                return info
                
            except Exception as e:
                errors.append(f"Erro ao processar {file_path}: {str(e)}")
                return None
        
        # Escaneia diretório
        for root, _, files in os.walk(directory):
            # Verifica limite de arquivos
            if total_files >= max_files:
                logger.warning("Limite de arquivos atingido")
                break
            
            # Processa arquivos
            for file in files:
                file_path = os.path.join(root, file)
                
                # Verifica tamanho
                try:
                    size = os.path.getsize(file_path)
                    if total_size + size > max_size:
                        logger.warning("Limite de tamanho atingido")
                        break
                except Exception:
                    continue
                
                # Processa arquivo
                info = process_file(file_path)
                if info:
                    processed_files.append(info)
                    total_files += 1
                    total_size += size
            
            # Continua recursivamente
            if not recursive:
                break
        
        # Registra erros
        if errors:
            for error in errors[:10]:  # Limita número de erros
                logger.error(error)
            if len(errors) > 10:
                logger.error(f"Mais {len(errors) - 10} erros omitidos")
        
        return processed_files
        
    except Exception as e:
        logger.error(f"Erro ao escanear diretório: {str(e)}")
        return [] 