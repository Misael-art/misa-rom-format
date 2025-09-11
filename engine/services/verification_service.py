#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Verification Service
Serviço de verificação de ROMs
"""

import os
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib
import zlib

from ..db.database_manager import DatabaseManager
from ..utils.common import (
    calculate_file_hash,
    get_file_info,
    parse_rom_name,
    scan_directory
)

logger = logging.getLogger(__name__)

class VerificationService:
    """Serviço para verificação de ROMs."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializa o serviço de verificação.
        
        Args:
            db_manager: Gerenciador de banco de dados
        """
        self.db_manager = db_manager
    
    def verify_rom(
        self,
        file_path: str,
        expected_size: int = None,
        expected_crc: str = None,
        expected_md5: str = None,
        expected_sha1: str = None,
        chunk_size: int = 8192
    ) -> Dict[str, str]:
        """
        Verifica uma ROM.
        
        Args:
            file_path: Caminho do arquivo
            expected_size: Tamanho esperado em bytes
            expected_crc: CRC32 esperado
            expected_md5: MD5 esperado
            expected_sha1: SHA1 esperado
            chunk_size: Tamanho do chunk para leitura
            
        Returns:
            Dicionário com hashes calculados
        """
        try:
            # Verifica arquivo
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
            # Verifica tamanho
            file_size = os.path.getsize(file_path)
            if expected_size and file_size != expected_size:
                raise ValueError(f"Tamanho incorreto: {file_size} (esperado: {expected_size})")
            
            # Inicializa hashes
            crc32 = 0
            md5 = hashlib.md5()
            sha1 = hashlib.sha1()
            
            # Lê arquivo em chunks
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Atualiza hashes
                    if expected_crc:
                        crc32 = zlib.crc32(chunk, crc32)
                    if expected_md5:
                        md5.update(chunk)
                    if expected_sha1:
                        sha1.update(chunk)
            
            # Prepara resultados
            results = {
                "size": file_size,
                "crc": f"{crc32 & 0xFFFFFFFF:08x}" if expected_crc else None,
                "md5": md5.hexdigest() if expected_md5 else None,
                "sha1": sha1.hexdigest() if expected_sha1 else None
            }
            
            # Verifica hashes
            if expected_crc and results["crc"] != expected_crc:
                raise ValueError(f"CRC incorreto: {results['crc']} (esperado: {expected_crc})")
            
            if expected_md5 and results["md5"] != expected_md5:
                raise ValueError(f"MD5 incorreto: {results['md5']} (esperado: {expected_md5})")
            
            if expected_sha1 and results["sha1"] != expected_sha1:
                raise ValueError(f"SHA1 incorreto: {results['sha1']} (esperado: {expected_sha1})")
            
            return results
            
        except Exception as e:
            logging.error(f"Erro ao verificar ROM: {str(e)}", exc_info=True)
            raise
    
    def verify_directory(
        self,
        directory: str,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], bool]] = None
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Verifica ROMs em um diretório.
        
        Args:
            directory: Diretório com ROMs
            recursive: Se deve verificar subdiretórios
            progress_callback: Função de callback para progresso
                Recebe: (atual, total, status)
                Retorna: True para continuar, False para cancelar
                
        Returns:
            Tupla com (ROMs válidas, ROMs inválidas)
        """
        try:
            # Verifica diretório
            if not os.path.isdir(directory):
                raise NotADirectoryError(f"Diretório não encontrado: {directory}")
            
            # Lista arquivos
            files = []
            if recursive:
                for root, dirs, filenames in os.walk(directory):
                    for filename in filenames:
                        files.append(os.path.join(root, filename))
            else:
                files = [
                    os.path.join(directory, f)
                    for f in os.listdir(directory)
                    if os.path.isfile(os.path.join(directory, f))
                ]
            
            # Verifica se há arquivos
            if not files:
                raise ValueError(f"Nenhum arquivo encontrado em: {directory}")
            
            # Obtém ROMs do banco
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT
                    r.name,
                    r.size,
                    r.crc,
                    r.md5,
                    r.sha1,
                    g.name as game_name,
                    g.platform
                FROM roms r
                JOIN games g ON r.game_id = g.id
            """)
            
            roms_db = {}
            for row in cursor.fetchall():
                roms_db[row[0]] = {
                    "name": row[0],
                    "size": row[1],
                    "crc": row[2],
                    "md5": row[3],
                    "sha1": row[4],
                    "game_name": row[5],
                    "platform": row[6]
                }
            
            # Verifica arquivos
            valid_roms = []
            invalid_roms = []
            total_files = len(files)
            
            for i, file_path in enumerate(files, 1):
                try:
                    # Verifica cancelamento
                    if progress_callback:
                        status = f"Verificando {os.path.basename(file_path)}..."
                        if not progress_callback(i, total_files, status):
                            break
                    
                    # Obtém nome do arquivo
                    filename = os.path.basename(file_path)
                    
                    # Procura ROM no banco
                    rom_db = roms_db.get(filename)
                    if not rom_db:
                        invalid_roms.append({
                            "file": file_path,
                            "error": "ROM não encontrada no banco"
                        })
                        continue
                    
                    # Verifica ROM
                    try:
                        results = self.verify_rom(
                            file_path,
                            expected_size=rom_db["size"],
                            expected_crc=rom_db["crc"],
                            expected_md5=rom_db["md5"],
                            expected_sha1=rom_db["sha1"]
                        )
                        
                        # Adiciona informações
                        results.update({
                            "file": file_path,
                            "game_name": rom_db["game_name"],
                            "platform": rom_db["platform"],
                            "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        valid_roms.append(results)
                        
                    except ValueError as e:
                        invalid_roms.append({
                            "file": file_path,
                            "error": str(e),
                            "game_name": rom_db["game_name"],
                            "platform": rom_db["platform"]
                        })
                    
                except Exception as e:
                    logging.error(f"Erro ao verificar {file_path}: {str(e)}", exc_info=True)
                    invalid_roms.append({
                        "file": file_path,
                        "error": str(e)
                    })
            
            # Log
            logging.info(
                f"Verificação concluída: {len(valid_roms)} válidas, "
                f"{len(invalid_roms)} inválidas"
            )
            
            return valid_roms, invalid_roms
            
        except Exception as e:
            logging.error(f"Erro ao verificar diretório: {str(e)}", exc_info=True)
            raise
    
    def update_verification(self, rom_id: int, verification_data: Dict[str, str]):
        """
        Atualiza dados de verificação de uma ROM.
        
        Args:
            rom_id: ID da ROM
            verification_data: Dados de verificação
        """
        try:
            # Obtém conexão
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Atualiza ROM
            cursor.execute("""
                UPDATE roms SET
                    verified_at = ?,
                    verified_size = ?,
                    verified_crc = ?,
                    verified_md5 = ?,
                    verified_sha1 = ?,
                    verified_status = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                verification_data.get("verified_at"),
                verification_data.get("size"),
                verification_data.get("crc"),
                verification_data.get("md5"),
                verification_data.get("sha1"),
                "valid",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                rom_id
            ))
            
            # Commit
            conn.commit()
            
        except Exception as e:
            logging.error(f"Erro ao atualizar verificação: {str(e)}", exc_info=True)
            raise
    
    def verify_file(
        self,
        file_path: str,
        hash_type: str = "sha1"
    ) -> Dict[str, Any]:
        """
        Verifica um arquivo ROM.
        
        Args:
            file_path: Caminho do arquivo
            hash_type: Tipo de hash
        
        Returns:
            Dict[str, Any]: Resultados da verificação
        """
        try:
            # Verifica arquivo
            if not os.path.exists(file_path):
                return {
                    "found": False,
                    "error": "Arquivo não encontrado"
                }
            
            # Verifica banco
            if not self.db_manager.conn:
                return {
                    "found": False,
                    "error": "Nenhum banco de dados aberto"
                }
            
            # Obtém informações do arquivo
            info = get_file_info(file_path)
            if not info:
                return {
                    "found": False,
                    "error": "Erro ao obter informações do arquivo"
                }
            
            # Procura por hash
            query = f"""
                SELECT game_name, rom_name, rom_size,
                       crc32, md5, sha1,
                       status, bios, system,
                       region, language, version, type
                FROM roms
                WHERE {hash_type}=?
            """
            
            results = self.db_manager.execute_query(query, (info[hash_type],))
            
            if results:
                # Match exato
                rom = results[0]
                return {
                    "found": True,
                    "match_type": "exact",
                    "file": info,
                    "rom": {
                        "game_name": rom[0],
                        "rom_name": rom[1],
                        "rom_size": rom[2],
                        "crc32": rom[3],
                        "md5": rom[4],
                        "sha1": rom[5],
                        "status": rom[6],
                        "bios": rom[7],
                        "system": rom[8],
                        "region": rom[9],
                        "language": rom[10],
                        "version": rom[11],
                        "type": rom[12]
                    }
                }
            
            # Procura por nome e tamanho
            query = """
                SELECT game_name, rom_name, rom_size,
                       crc32, md5, sha1,
                       status, bios, system,
                       region, language, version, type
                FROM roms
                WHERE rom_name=? AND rom_size=?
            """
            
            results = self.db_manager.execute_query(
                query,
                (info["name"], info["size"])
            )
            
            if results:
                # Match parcial
                rom = results[0]
                return {
                    "found": True,
                    "match_type": "partial",
                    "file": info,
                    "rom": {
                        "game_name": rom[0],
                        "rom_name": rom[1],
                        "rom_size": rom[2],
                        "crc32": rom[3],
                        "md5": rom[4],
                        "sha1": rom[5],
                        "status": rom[6],
                        "bios": rom[7],
                        "system": rom[8],
                        "region": rom[9],
                        "language": rom[10],
                        "version": rom[11],
                        "type": rom[12]
                    }
                }
            
            # Não encontrado
            return {
                "found": False,
                "file": info
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar arquivo: {str(e)}")
            return {
                "found": False,
                "error": str(e)
            }
    
    def verify_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: List[str] = None,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, Dict[str, int], List[Dict[str, Any]]]:
        """
        Verifica ROMs em um diretório.
        
        Args:
            directory: Diretório a verificar
            recursive: Busca recursiva
            extensions: Lista de extensões
            max_workers: Número máximo de threads
            progress_callback: Função de progresso
        
        Returns:
            Tuple[bool, Dict[str, int], List[Dict[str, Any]]]:
                (sucesso, estatísticas, resultados)
        """
        try:
            # Verifica diretório
            if not os.path.isdir(directory):
                logger.error(f"Diretório não encontrado: {directory}")
                return False, {}, []
            
            # Verifica banco
            if not self.db_manager.conn:
                logger.error("Nenhum banco de dados aberto")
                return False, {}, []
            
            # Lista arquivos
            if progress_callback:
                progress_callback(0, "Listando arquivos...")
            
            files = scan_directory(directory, extensions, recursive)
            if not files:
                logger.warning("Nenhum arquivo encontrado")
                return False, {}, []
            
            # Estatísticas
            stats = {
                "total": len(files),
                "matched": 0,
                "partial": 0,
                "missing": 0,
                "errors": 0
            }
            
            # Resultados
            results = []
            
            # Processa arquivos
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for file_info in files:
                    future = executor.submit(
                        self.verify_file,
                        file_info["path"]
                    )
                    futures.append((file_info, future))
                
                # Processa resultados
                for i, (file_info, future) in enumerate(futures, 1):
                    try:
                        if progress_callback:
                            progress = (i / stats["total"]) * 100
                            progress_callback(
                                progress,
                                f"Verificando {i}/{stats['total']}..."
                            )
                        
                        result = future.result()
                        result["file"] = file_info
                        
                        if result.get("error"):
                            stats["errors"] += 1
                        elif result["found"]:
                            if result["match_type"] == "exact":
                                stats["matched"] += 1
                            else:
                                stats["partial"] += 1
                        else:
                            stats["missing"] += 1
                        
                        results.append(result)
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar resultado: {str(e)}")
                        stats["errors"] += 1
            
            return True, stats, results
            
        except Exception as e:
            logger.error(f"Erro ao verificar diretório: {str(e)}")
            return False, {}, []
    
    def get_missing_roms(self) -> List[Dict[str, Any]]:
        """
        Obtém ROMs não verificadas.
        
        Returns:
            List[Dict[str, Any]]: Lista de ROMs
        """
        try:
            if not self.db_manager.conn:
                return []
            
            query = """
                SELECT game_name, rom_name, rom_size,
                       crc32, md5, sha1,
                       status, bios, system,
                       region, language, version, type
                FROM roms
                WHERE status='unverified'
                ORDER BY game_name, rom_name
            """
            
            results = self.db_manager.execute_query(query)
            
            roms = []
            for row in results:
                roms.append({
                    "game_name": row[0],
                    "rom_name": row[1],
                    "rom_size": row[2],
                    "crc32": row[3],
                    "md5": row[4],
                    "sha1": row[5],
                    "status": row[6],
                    "bios": row[7],
                    "system": row[8],
                    "region": row[9],
                    "language": row[10],
                    "version": row[11],
                    "type": row[12]
                })
            
            return roms
            
        except Exception as e:
            logger.error(f"Erro ao obter ROMs não verificadas: {str(e)}")
            return []
    
    def get_verification_summary(self) -> Dict[str, int]:
        """
        Obtém resumo das verificações.
        
        Returns:
            Dict[str, int]: Resumo das verificações
        """
        try:
            if not self.db_manager.conn:
                return {}
            
            # Total de ROMs
            query = "SELECT COUNT(*) FROM roms"
            result = self.db_manager.execute_query(query)
            total = result[0][0] if result else 0
            
            # ROMs verificadas
            query = "SELECT COUNT(*) FROM roms WHERE status != 'unverified'"
            result = self.db_manager.execute_query(query)
            verified = result[0][0] if result else 0
            
            # Matches exatos
            query = "SELECT COUNT(*) FROM roms WHERE status = 'verified'"
            result = self.db_manager.execute_query(query)
            matched = result[0][0] if result else 0
            
            # Matches parciais
            query = "SELECT COUNT(*) FROM roms WHERE status = 'partial'"
            result = self.db_manager.execute_query(query)
            partial = result[0][0] if result else 0
            
            return {
                "total": total,
                "verified": verified,
                "matched": matched,
                "partial": partial,
                "missing": total - verified
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter resumo: {str(e)}")
            return {} 