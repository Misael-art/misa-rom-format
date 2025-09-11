#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Scanner de Diretórios
Responsável por escanear diretórios e coletar informações sobre arquivos
"""

import os
import time
import logging
import fnmatch
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable, Set, Tuple

# Import do módulo de compressão
from .compression import compress_rom, compress_hybrid, decompress_hybrid, get_compression_ratio, benchmark_compression
# Import do módulo de compressão
from .compression import compress_rom, compress_hybrid, decompress_hybrid, get_compression_ratio, benchmark_compression, compress_misa
from engine.ai_picker import pick_ultimate_strategy
from engine.config import (
    SUPPORTED_FORMATS, DEFAULT_DB_PATH, MISA_HEADER_SIZE, MISA_META_FMT,
    COMPRESSION_LEVELS, BATCH_SIZE, MAX_WORKERS
)
import sqlite3
# Constantes hardcoded para evitar problemas de importação circular
CONFIG_COMPRESSION_TYPES = {'lz4': 1, 'hybrid': 2, 'none': 0}
CONFIG_HYBRID_RAW_RATIO = 0.333
CONFIG_LARGE_ROM_THRESHOLD_MB = 10
from ..db.db_locks import db_write_lock

# Logger
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

class DirectoryScanner:
    """
    Scanner de diretórios para análise de arquivos.
    
    Fornece métodos para escanear diretórios e coletar informações
    sobre os arquivos encontrados, com opções de filtragem.
    """
    
    def __init__(self):
        """Inicializa o scanner de diretórios."""
        self.cancelled = False
        self.include_patterns = ["*.*"]  # Padrão: todos os arquivos
        self.exclude_patterns = []  # Padrão: não exclui nenhum arquivo
        self.max_file_size = 10 * 1024 * 1024 * 1024  # 10GB
        self.max_files = 100000  # Limite de 100k arquivos
        self.calculate_hashes = False  # Se deve calcular hashes
        self.hash_algorithms = ["md5", "sha1"]  # Algoritmos de hash padrão
        self.check_mime_types = True  # Se deve verificar tipos MIME
        self.max_threads = 4  # Threads para processamento paralelo
        self.errors: List[str] = []  # Lista de erros encontrados

        # Opções de compressão
        self.compress_on_scan = False  # Se deve comprimir arquivos durante scan
        self.compression_type = list(CONFIG_COMPRESSION_TYPES.keys())[list(CONFIG_COMPRESSION_TYPES.values()).index(1)]  # Tipo padrão: lz4
        self.compression_level = 1  # Nível de compressão (1-9)
        self.output_dir = None  # Diretório para salvar arquivos comprimidos
    
    def cancel(self):
        """Cancela a operação de escaneamento em andamento."""
        self.cancelled = True
    
    def reset_cancel(self):
        """Reseta a flag de cancelamento."""
        self.cancelled = False
        self.errors.clear()
    
    def set_patterns(self, include_patterns: List[str]):
        """
        Define os padrões de arquivo a serem incluídos.
        
        Args:
            include_patterns: Lista de padrões glob (ex: ["*.zip", "*.iso"])
        """
        if not include_patterns:
            self.include_patterns = ["*.*"]
            return
            
        # Valida e normaliza padrões
        valid_patterns = []
        for pattern in include_patterns:
            if not isinstance(pattern, str):
                logger.warning(f"Padrão inválido ignorado: {pattern}")
                continue
                
            pattern = pattern.strip().lower()
            if not pattern:
                continue
                
            if not pattern.startswith("*."):
                pattern = f"*.{pattern}"
                
            valid_patterns.append(pattern)
            
        self.include_patterns = valid_patterns if valid_patterns else ["*.*"]
    
    def set_excluded_patterns(self, exclude_patterns: List[str]):
        """
        Define os padrões de arquivo a serem excluídos.
        
        Args:
            exclude_patterns: Lista de padrões glob (ex: ["*.txt", "*.log"])
        """
        if not exclude_patterns:
            self.exclude_patterns = []
            return
            
        # Valida e normaliza padrões
        valid_patterns = []
        for pattern in exclude_patterns:
            if not isinstance(pattern, str):
                logger.warning(f"Padrão de exclusão inválido ignorado: {pattern}")
                continue
                
            pattern = pattern.strip().lower()
            if not pattern:
                continue
                
            if not pattern.startswith("*."):
                pattern = f"*.{pattern}"
                
            valid_patterns.append(pattern)
            
        self.exclude_patterns = valid_patterns
    
    def set_options(self, **options):
        """
        Define opções do scanner.
        
        Args:
            **options: Dicionário de opções
                max_file_size: Tamanho máximo de arquivo em bytes
                max_files: Número máximo de arquivos
                calculate_hashes: Se deve calcular hashes
                hash_algorithms: Lista de algoritmos de hash
                check_mime_types: Se deve verificar tipos MIME
                max_threads: Número máximo de threads
        """
        if "max_file_size" in options:
            size = options["max_file_size"]
            if isinstance(size, (int, float)) and size > 0:
                self.max_file_size = int(size)
            
        if "max_files" in options:
            files = options["max_files"]
            if isinstance(files, int) and files > 0:
                self.max_files = files
                
        if "calculate_hashes" in options:
            self.calculate_hashes = bool(options["calculate_hashes"])
            
        if "hash_algorithms" in options:
            algos = options["hash_algorithms"]
            if isinstance(algos, (list, tuple)):
                valid_algos = []
                for algo in algos:
                    if isinstance(algo, str) and hasattr(hashlib, algo):
                        valid_algos.append(algo)
                    else:
                        logger.warning(f"Algoritmo de hash inválido ignorado: {algo}")
                if valid_algos:
                    self.hash_algorithms = valid_algos
                    
        if "check_mime_types" in options:
            self.check_mime_types = bool(options["check_mime_types"])
            
        if "max_threads" in options:
            threads = options["max_threads"]
            if isinstance(threads, int) and 1 <= threads <= 16:
                self.max_threads = threads

        # Opções de compressão
        if "compress_on_scan" in options:
            self.compress_on_scan = bool(options["compress_on_scan"])

        if "compression_type" in options:
            comp_type = options["compression_type"]
            if comp_type in ["lz4", "none"]:
                self.compression_type = comp_type

        if "compression_level" in options:
            level = options["compression_level"]
            if isinstance(level, int) and 1 <= level <= 9:
                self.compression_level = level

        if "output_dir" in options:
            out_dir = options["output_dir"]
            if isinstance(out_dir, str) and out_dir.strip():
                self.output_dir = out_dir.strip()
    
    def scan_directory(
        self, 
        directory_path: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Escaneia um diretório e coleta informações sobre os arquivos.
        
        Args:
            directory_path: Caminho do diretório a ser escaneado
            progress_callback: Função para relatório de progresso
                Parâmetros: (float percentual, str mensagem, str status)
                Retorno: True para continuar, False para cancelar
        
        Returns:
            Dicionário com informações sobre os arquivos encontrados
        """
        self.reset_cancel()
        
        logger.info(f"Iniciando escaneamento do diretório: {directory_path}")
        start_time = time.time()
        
        # Estatísticas
        stats = {
            "start_time": start_time,
            "directory": directory_path,
            "files": [],
            "directories": [],
            "total_size": 0,
            "total_files": 0,
            "extensions": {},
            "mime_types": {},
            "errors": [],
            "options": {
                "max_file_size": self.max_file_size,
                "max_files": self.max_files,
                "calculate_hashes": self.calculate_hashes,
                "hash_algorithms": self.hash_algorithms,
                "check_mime_types": self.check_mime_types,
                "max_threads": self.max_threads,
                "include_patterns": self.include_patterns,
                "exclude_patterns": self.exclude_patterns,
                "compress_on_scan": self.compress_on_scan,
                "compression_type": self.compression_type,
                "compression_level": self.compression_level,
                "output_dir": self.output_dir
            }
        }
        
        try:
            # Valida diretório
            directory = Path(directory_path)
            if not directory.exists():
                raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
            if not directory.is_dir():
                raise NotADirectoryError(f"Caminho não é um diretório: {directory_path}")
            
            # Verifica permissões
            if not os.access(directory_path, os.R_OK):
                raise PermissionError(f"Sem permissão de leitura no diretório: {directory_path}")
            
            # Lista todos os arquivos e diretórios recursivamente
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                for root, dirs, files in os.walk(directory_path):
                    if self.cancelled:
                        logger.warning("Escaneamento cancelado pelo usuário.")
                        stats["cancelled"] = True
                        break
                    
                    # Adiciona diretórios à lista
                    rel_path = os.path.relpath(root, directory_path)
                    if rel_path != ".":
                        dir_info = self._get_directory_info(root)
                        if dir_info:
                            stats["directories"].append(dir_info)
                    
                    # Processa os arquivos em paralelo
                    futures = []
                    for file in files:
                        if self.cancelled or stats["total_files"] >= self.max_files:
                            break
                            
                        file_path = os.path.join(root, file)
                        if not self._matches_patterns(file):
                            continue
                            
                        future = executor.submit(self._process_file, file_path)
                        futures.append((future, file_path))
                    
                    # Coleta resultados
                    for future, file_path in futures:
                        try:
                            result = future.result(timeout=30)  # 30s timeout
                            if result:
                                self._update_stats(stats, result)
                                
                                # Reporta progresso
                                if progress_callback and stats["total_files"] % 10 == 0:
                                    progress = min(95, (stats["total_files"] / self.max_files) * 100)
                                    message = f"Escaneando: {rel_path}"
                                    status = (f"{stats['total_files']} arquivos, "
                                            f"{self._format_size(stats['total_size'])}")
                                    
                                    if not progress_callback(progress, message, status):
                                        self.cancel()
                                        stats["cancelled"] = True
                                        break
                                        
                        except Exception as e:
                            error = f"Erro ao processar {file_path}: {str(e)}"
                            logger.error(error)
                            self.errors.append(error)
                            
                    if self.cancelled:
                        break
            
        except Exception as e:
            error = f"Erro ao escanear diretório: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            
        finally:
            # Finaliza estatísticas
            end_time = time.time()
            stats["end_time"] = end_time
            stats["duration"] = end_time - start_time
            stats["errors"] = self.errors
            
            logger.info(f"Escaneamento concluído em {stats['duration']:.2f}s: "
                       f"{stats['total_files']} arquivos, "
                       f"{self._format_size(stats['total_size'])} total")
            
            # Relatório final de progresso
            if progress_callback and not self.cancelled:
                progress_callback(100, "Escaneamento concluído", 
                                 f"{stats['total_files']} arquivos, "
                                 f"{self._format_size(stats['total_size'])}")
            
            return stats
    
    def _get_directory_info(self, dir_path: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações sobre um diretório.
        
        Args:
            dir_path: Caminho do diretório
            
        Returns:
            Dicionário com informações ou None se erro
        """
        try:
            path = Path(dir_path)
            stat = path.stat()
            
            return {
                "path": str(path),
                "name": path.name,
                "parent": str(path.parent),
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "is_hidden": path.name.startswith("."),
                "is_readonly": not os.access(dir_path, os.W_OK),
                "permissions": oct(stat.st_mode)[-3:]
            }
            
        except Exception as e:
            error = f"Erro ao obter informações do diretório {dir_path}: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            return None
    
    def _process_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Processa um arquivo e coleta suas informações.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Dicionário com informações ou None se erro
        """
        try:
            # Obtém informações básicas
            path = Path(file_path)
            stat = path.stat()
            
            # Verifica tamanho
            if stat.st_size > self.max_file_size:
                logger.warning(f"Arquivo muito grande ignorado: {file_path}")
                return None
            
            # Informações do arquivo
            info = {
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "size_formatted": self._format_size(stat.st_size),
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "extension": path.suffix.lower(),
                "is_hidden": path.name.startswith("."),
                "is_readonly": not os.access(file_path, os.W_OK),
                "permissions": oct(stat.st_mode)[-3:],
                "parent_dir": str(path.parent)
            }
            
            # Verifica tipo MIME
            if self.check_mime_types:
                mime_type, encoding = mimetypes.guess_type(file_path)
                info["mime_type"] = mime_type
                info["mime_encoding"] = encoding
                
                if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
                    logger.debug(f"Tipo MIME não suportado: {mime_type} ({file_path})")
            
            # Calcula hashes se necessário
            if self.calculate_hashes:
                hashes = self._calculate_file_hash(file_path)
                if hashes:
                    info.update(hashes)

            # Comprime arquivo se necessário
            if self.compress_on_scan and self.compression_type != "none":
                compressed_info = self._compress_file(file_path, info)
                if compressed_info:
                    info.update(compressed_info)

            return info
            
        except Exception as e:
            error = f"Erro ao processar arquivo {file_path}: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            return None

    def _compress_file(self, file_path: str, file_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Comprime um arquivo e salva como .misa com detecção automática de tipo.

        Args:
            file_path: Caminho do arquivo original
            file_info: Informações do arquivo

        Returns:
            Dicionário com informações de compressão ou None se erro
        """
        try:
            # Lê o conteúdo do arquivo
            with open(file_path, "rb") as f:
                data = f.read()

            if not data:
                logger.warning(f"Arquivo vazio, pulando compressão: {file_path}")
                return None

            # Calcula hash original para validação
            hash_original = hashlib.md5(data).hexdigest()

            # Determina tipo de compressão baseado no tamanho
            file_size_mb = len(data) / (1024 * 1024)
            if file_size_mb >= CONFIG_LARGE_ROM_THRESHOLD_MB:
                compression_type = 'hybrid'
                logger.info(f"Arquivo grande detectado ({file_size_mb:.1f}MB), usando compressão híbrida: {file_path}")
            else:
                compression_type = self.compression_type

            # Comprime baseado no tipo determinado
            if compression_type == 'hybrid':
                # Compressão híbrida para ROMs grandes
                offset = int(len(data) * CONFIG_HYBRID_RAW_RATIO)
                hybrid_data = compress_hybrid(data, CONFIG_HYBRID_RAW_RATIO)
                compression_ratio = get_compression_ratio(data, hybrid_data)
                compressed_data = hybrid_data
                hybrid_ratio = CONFIG_HYBRID_RAW_RATIO
            elif compression_type in CONFIG_COMPRESSION_TYPES:
                # Compressão LZ4 padrão
                compressed_data = compress_rom(data, self.compression_level)
                compression_ratio = get_compression_ratio(data, compressed_data)
                offset = 0
                hybrid_ratio = 0.0
            else:
                logger.warning(f"Tipo de compressão inválido: {compression_type}")
                return None

            # Define caminho de saída
            output_path = self._get_compressed_output_path(file_path)

            # Cria diretório se necessário
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Salva arquivo comprimido
            with open(output_path, "wb") as f:
                f.write(compressed_data)

            # Retorna informações de compressão
            result = {
                "compression_type": compression_type,
                "compression_ratio": compression_ratio,
                "compressed_size": len(compressed_data),
                "compressed_path": output_path,
                "compression_level": self.compression_level if compression_type != 'hybrid' else 1,
                "hash_original": hash_original
            }

            # Campos específicos para compressão híbrida
            if compression_type == 'hybrid':
                result.update({
                    "compression_offset": offset,
                    "hybrid_ratio": hybrid_ratio
                })

            logger.info(
                f"Compressão {compression_type} concluída: {len(compressed_data)} bytes "
                f"(ratio: {compression_ratio:.3f}) para {file_path}"
            )

            return result

        except Exception as e:
            error = f"Erro ao comprimir {file_path}: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            return None

    def _get_compressed_output_path(self, original_path: str) -> str:
        """
        Gera caminho de saída para arquivo comprimido.

        Args:
            original_path: Caminho do arquivo original

        Returns:
            Caminho do arquivo comprimido
        """
        if self.output_dir:
            # Usa diretório de saída especificado
            base_name = os.path.basename(original_path)
            name_without_ext = os.path.splitext(base_name)[0]
            return os.path.join(self.output_dir, f"{name_without_ext}.misa")
        else:
            # Salva no mesmo diretório com extensão .misa
            name_without_ext = os.path.splitext(original_path)[0]
            return f"{name_without_ext}.misa"
    
    def _update_stats(self, stats: Dict[str, Any], file_info: Dict[str, Any]):
        """
        Atualiza as estatísticas com informações de um arquivo.
        
        Args:
            stats: Dicionário de estatísticas
            file_info: Informações do arquivo
        """
        # Adiciona arquivo à lista
        stats["files"].append(file_info)
        
        # Atualiza contadores
        stats["total_files"] += 1
        stats["total_size"] += file_info["size"]
        
        # Atualiza estatísticas de extensão
        ext = file_info["extension"]
        if ext not in stats["extensions"]:
            stats["extensions"][ext] = {
                "count": 0,
                "size": 0
            }
        stats["extensions"][ext]["count"] += 1
        stats["extensions"][ext]["size"] += file_info["size"]
        
        # Atualiza estatísticas de tipo MIME
        mime_type = file_info.get("mime_type")
        if mime_type:
            if mime_type not in stats["mime_types"]:
                stats["mime_types"][mime_type] = {
                    "count": 0,
                    "size": 0
                }
            stats["mime_types"][mime_type]["count"] += 1
            stats["mime_types"][mime_type]["size"] += file_info["size"]
    
    def _matches_patterns(self, filename: str) -> bool:
        """
        Verifica se o nome do arquivo corresponde aos padrões de inclusão e exclusão.
        
        Args:
            filename: Nome do arquivo a verificar
            
        Returns:
            True se o arquivo deve ser incluído, False caso contrário
        """
        filename = filename.lower()
        
        # Primeiro verifica exclusões
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False
        
        # Depois verifica inclusões
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        
        return False
    
    def _calculate_file_hash(self, file_path: str, chunk_size: int = 8192) -> Dict[str, str]:
        """
        Calcula hashes de um arquivo.
        
        Args:
            file_path: Caminho do arquivo
            chunk_size: Tamanho do chunk de leitura
            
        Returns:
            Dicionário com os hashes calculados
        """
        try:
            # Inicializa hashers
            hashers = {
                algo: getattr(hashlib, algo)()
                for algo in self.hash_algorithms
                if hasattr(hashlib, algo)
            }
            
            if not hashers:
                return {}
            
            # Ajusta tamanho do chunk
            chunk_size = max(1024, min(chunk_size, 1024 * 1024))
            
            # Calcula hashes
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    for hasher in hashers.values():
                        hasher.update(chunk)
            
            return {
                algo: hasher.hexdigest()
                for algo, hasher in hashers.items()
            }
            
        except Exception as e:
            error = f"Erro ao calcular hash de {file_path}: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            return {}
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Formata um tamanho em bytes para exibição amigável.
        
        Args:
            size_bytes: Tamanho em bytes
            
        Returns:
            String formatada (ex: "1.23 MB")
        """
        try:
            if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
                return "0 B"
                
            units = ["B", "KB", "MB", "GB", "TB", "PB"]
            size = float(size_bytes)
            unit_index = 0
            
            while size >= 1024 and unit_index < len(units) - 1:
                size /= 1024
                unit_index += 1
            
            # Ajusta precisão decimal
            if unit_index == 0:
                return f"{int(size)} {units[unit_index]}"
            else:
    def _format_size(self, size_bytes: int) -> str:
        """
        Formata um tamanho em bytes para exibição amigável.

        Args:
            size_bytes: Tamanho em bytes

        Returns:
            String formatada (ex: "1.23 MB")
        """
        try:
            if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
                return "0 B"

            units = ["B", "KB", "MB", "GB", "TB", "PB"]
            size = float(size_bytes)
            unit_index = 0

            while size >= 1024 and unit_index < len(units) - 1:
                size /= 1024
                unit_index += 1

            # Ajusta precisão decimal
            if unit_index == 0:
                return f"{int(size)} {units[unit_index]}"
            else:
                return f"{size:.2f} {units[unit_index]}"

        except Exception as e:
            error = f"Erro ao formatar tamanho: {str(e)}"
            logger.error(error)
            self.errors.append(error)
            return "0 B"

def get_console_from_db(file_path: str) -> str:
    """
    Detecta console baseado no path e extensão do arquivo.
    Mock para proto - implementar consulta real ao DB.
    """
    path_lower = file_path.lower()

    # Mapeamento baseado em extensões comuns
    ext_map = {
        '.nes': 'nes',
        '.snes': 'snes',
        '.n64': 'n64',
        '.gba': 'gba',
        '.gbc': 'gbc',
        '.gb': 'gb',
        '.iso': 'ps1',
        '.bin': 'ps1',
        '.pbp': 'psp',
        '.cso': 'psp',
        '.iso': 'ps2' if 'ps2' in path_lower else 'ps1'
    }

    # Detecta por extensão
    for ext, console in ext_map.items():
        if file_path.lower().endswith(ext):
            return console

    # Detecta por diretório
    if 'nes' in path_lower or 'nintendo' in path_lower:
        return 'nes'
    elif 'snes' in path_lower:
        return 'snes'
    elif 'n64' in path_lower:
        return 'n64'
    elif 'gba' in path_lower or 'gameboy' in path_lower:
        return 'gba'
    elif 'ps1' in path_lower or 'playstation' in path_lower:
        return 'ps1'
    elif 'psp' in path_lower:
        return 'psp'

    return 'unknown'
