#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Serviço de Verificação de ROMs
Responsável por verificar ROMs contra banco de dados
"""

import os
import time
import hashlib
import logging
import traceback
from typing import Dict, List, Any, Optional, Callable

from engine.db import UnifiedDatabaseManager as DatabaseManager

# Logger
logger = logging.getLogger(__name__)

class RomVerificationService:
    """
    Serviço para verificação de ROMs.
    
    Verifica arquivos de ROMs contra os registros no banco de dados,
    utilizando checksums para identificar correspondências.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializa o serviço de verificação.
        
        Args:
            db_manager: Instância do gerenciador de banco de dados
        """
        self.db_manager = db_manager
    
    def verify_directory(self, 
                       directory_path: str, 
                       progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Verifica ROMs em um diretório.
        
        Args:
            directory_path: Caminho para o diretório de ROMs
            progress_callback: Função de callback para reportar progresso
            
        Returns:
            Dicionário com estatísticas da verificação
        """
        if not self.db_manager or not self.db_manager.get_connection():
            logger.error("Nenhuma conexão de banco de dados válida disponível.")
            return {
                "success": False,
                "error": "Nenhuma conexão de banco de dados válida disponível."
            }
        
        # Verifica se a tabela 'roms' existe
        if not self.db_manager.table_exists('roms'):
            logger.error("A tabela 'roms' não existe no banco de dados.")
            return {
                "success": False,
                "error": "A tabela 'roms' não existe no banco de dados."
            }
        
        # Estatísticas
        stats = {
            "matched": 0,
            "missing": 0,
            "unknown": 0,
            "start_time": time.time(),
            "success": True,
            "total_files": 0,
            "processed_files": 0
        }
        
        # Lista de arquivos a verificar
        files_to_check = []
        
        # Percorre o diretório recursivamente
        for root, _, files in os.walk(directory_path):
            for file in files:
                # Pula diretórios ocultos e arquivos de sistema
                if file.startswith('.') or file.startswith('~$'):
                    continue
                
                file_path = os.path.join(root, file)
                files_to_check.append(file_path)
        
        stats["total_files"] = len(files_to_check)
        
        if progress_callback:
            progress_callback(0, "Iniciando verificação...", f"0/{stats['total_files']} arquivos")
        
        # Verifica cada arquivo
        for i, file_path in enumerate(files_to_check):
            stats["processed_files"] += 1
            
            if progress_callback:
                percent = (i / stats["total_files"]) * 100
                file_name = os.path.basename(file_path)
                if not progress_callback(percent, f"Verificando: {file_name}", 
                                         f"{i+1}/{stats['total_files']} arquivos"):
                    logger.warning("Verificação cancelada pelo usuário.")
                    stats["cancelled"] = True
                    break
            
            # Obtém o SHA1 do arquivo
            try:
                sha1 = self._calculate_sha1(file_path)
                file_name = os.path.basename(file_path)
                logger.debug(f"Verificando arquivo: {file_name} (SHA1: {sha1})")
                
                # Verifica se o SHA1 está no banco
                check_query = "SELECT id, title FROM roms WHERE sha1 = ?"
                result = self.db_manager.execute_query(check_query, (sha1,))
                
                if result and len(result) > 0:
                    # ROM encontrada no banco
                    stats["matched"] += 1
                    rom_id = result[0][0]
                    rom_title = result[0][1]
                    logger.info(f"ROM encontrada: {file_name} -> {rom_title} (ID: {rom_id})")
                else:
                    # ROM não encontrada no banco
                    stats["missing"] += 1
                    logger.warning(f"ROM não encontrada no banco: {file_name} (SHA1: {sha1})")
            except Exception as e:
                stats["unknown"] += 1
                logger.error(f"Erro ao verificar arquivo {file_path}: {e}")
        
        # Calcula duração
        stats["end_time"] = time.time()
        stats["duration"] = stats["end_time"] - stats["start_time"]
        
        # Formata resumo
        stats["summary"] = (
            f"Verificação concluída em {stats['duration']:.2f}s. "
            f"{stats['matched']} ROMs encontradas, "
            f"{stats['missing']} ausentes, "
            f"{stats['unknown']} desconhecidas."
        )
        
        logger.info(stats["summary"])
        return stats
    
    def _calculate_sha1(self, file_path: str) -> str:
        """
        Calcula o hash SHA1 de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo
            
        Returns:
            String com o hash SHA1 em hexadecimal
        """
        sha1_hash = hashlib.sha1()
        
        with open(file_path, "rb") as f:
            # Lê o arquivo em chunks para não sobrecarregar a memória
            for chunk in iter(lambda: f.read(4096), b""):
                sha1_hash.update(chunk)
                
        return sha1_hash.hexdigest()
    
    def verify_single_file(self, 
                         file_path: str) -> Dict[str, Any]:
        """
        Verifica um único arquivo de ROM.
        
        Args:
            file_path: Caminho para o arquivo de ROM
            
        Returns:
            Dicionário com informações sobre a ROM
        """
        try:
            sha1 = self._calculate_sha1(file_path)
            
            # Verifica se o SHA1 está no banco
            check_query = """
            SELECT id, title, platform, name_nointro, name, size_file
            FROM roms WHERE sha1 = ?
            """
            result = self.db_manager.execute_query(check_query, (sha1,))
            
            if result and len(result) > 0:
                # ROM encontrada no banco
                rom_data = result[0]
                return {
                    "found": True,
                    "id": rom_data[0],
                    "title": rom_data[1],
                    "platform": rom_data[2],
                    "name_nointro": rom_data[3],
                    "name": rom_data[4],
                    "size_file": rom_data[5],
                    "sha1": sha1,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path)
                }
            else:
                # ROM não encontrada no banco
                return {
                    "found": False,
                    "sha1": sha1,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path)
                }
        except Exception as e:
            logger.error(f"Erro ao verificar arquivo {file_path}: {e}")
            return {
                "found": False,
                "error": str(e),
                "file_path": file_path,
                "file_name": os.path.basename(file_path)
            }