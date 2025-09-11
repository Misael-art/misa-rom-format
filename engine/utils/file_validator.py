#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Validador de Arquivos
Responsável por verificar integridade e autenticidade de arquivos ROMs
"""

import os
import hashlib
import logging
import threading
from typing import Dict, List, Optional, Callable, Tuple

# Logger
logger = logging.getLogger(__name__)

class FileValidator:
    """
    Classe para validação de arquivos de ROMs.
    Verifica integridade por meio de hash (SHA1, CRC32, MD5).
    """
    
    def __init__(self):
        """
        Inicializa o validador de arquivos.
        """
        self._cache_lock = threading.RLock()
        self._sha1_cache: Dict[str, str] = {}
        self._crc32_cache: Dict[str, str] = {}
        self._md5_cache: Dict[str, str] = {}
    
    def calculate_sha1(self, file_path: str) -> Optional[str]:
        """
        Calcula o hash SHA1 de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo
            
        Returns:
            String hexadecimal do hash SHA1 ou None se falhar
        """
        # Verifica se o hash já está em cache
        with self._cache_lock:
            if file_path in self._sha1_cache:
                return self._sha1_cache[file_path]
        
        try:
            if not os.path.isfile(file_path):
                logger.error(f"Arquivo não encontrado: {file_path}")
                return None
                
            sha1 = hashlib.sha1()
            
            with open(file_path, 'rb') as f:
                # Lê o arquivo em blocos para economizar memória
                for block in iter(lambda: f.read(65536), b''):
                    sha1.update(block)
            
            result = sha1.hexdigest().lower()
            
            # Armazena em cache
            with self._cache_lock:
                self._sha1_cache[file_path] = result
                
            return result
            
        except Exception as e:
            logger.error(f"Erro ao calcular SHA1 para {file_path}: {e}")
            return None
    
    def calculate_crc32(self, file_path: str) -> Optional[str]:
        """
        Calcula o hash CRC32 de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo
            
        Returns:
            String hexadecimal do hash CRC32 ou None se falhar
        """
        # Verifica se o hash já está em cache
        with self._cache_lock:
            if file_path in self._crc32_cache:
                return self._crc32_cache[file_path]
        
        try:
            if not os.path.isfile(file_path):
                logger.error(f"Arquivo não encontrado: {file_path}")
                return None
            
            import zlib
            crc32 = 0
            
            with open(file_path, 'rb') as f:
                # Lê o arquivo em blocos para economizar memória
                for block in iter(lambda: f.read(65536), b''):
                    crc32 = zlib.crc32(block, crc32)
            
            # Formata como hexadecimal de 8 dígitos
            result = f"{crc32 & 0xFFFFFFFF:08x}".lower()
            
            # Armazena em cache
            with self._cache_lock:
                self._crc32_cache[file_path] = result
                
            return result
            
        except Exception as e:
            logger.error(f"Erro ao calcular CRC32 para {file_path}: {e}")
            return None
    
    def calculate_md5(self, file_path: str) -> Optional[str]:
        """
        Calcula o hash MD5 de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo
            
        Returns:
            String hexadecimal do hash MD5 ou None se falhar
        """
        # Verifica se o hash já está em cache
        with self._cache_lock:
            if file_path in self._md5_cache:
                return self._md5_cache[file_path]
        
        try:
            if not os.path.isfile(file_path):
                logger.error(f"Arquivo não encontrado: {file_path}")
                return None
                
            md5 = hashlib.md5()
            
            with open(file_path, 'rb') as f:
                # Lê o arquivo em blocos para economizar memória
                for block in iter(lambda: f.read(65536), b''):
                    md5.update(block)
            
            result = md5.hexdigest().lower()
            
            # Armazena em cache
            with self._cache_lock:
                self._md5_cache[file_path] = result
                
            return result
            
        except Exception as e:
            logger.error(f"Erro ao calcular MD5 para {file_path}: {e}")
            return None
    
    def verify_file(
        self, 
        file_path: str, 
        expected_sha1: Optional[str] = None,
        expected_crc32: Optional[str] = None,
        expected_md5: Optional[str] = None
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Verifica se um arquivo corresponde aos hashes esperados.
        
        Args:
            file_path: Caminho para o arquivo
            expected_sha1: Hash SHA1 esperado (opcional)
            expected_crc32: Hash CRC32 esperado (opcional)
            expected_md5: Hash MD5 esperado (opcional)
            
        Returns:
            Tupla (bool, dict) indicando se o arquivo é válido e os hashes calculados
        """
        if not os.path.isfile(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return False, {}
        
        # Dicionário para armazenar os hashes calculados
        hashes = {}
        
        # Flag para indicar se todos os hashes esperados correspondem
        is_valid = True
        
        # Verifica SHA1 se esperado
        if expected_sha1:
            sha1 = self.calculate_sha1(file_path)
            hashes['sha1'] = sha1
            
            if not sha1 or sha1.lower() != expected_sha1.lower():
                logger.warning(f"SHA1 não corresponde para {file_path}. Esperado: {expected_sha1}, Encontrado: {sha1}")
                is_valid = False
        
        # Verifica CRC32 se esperado
        if expected_crc32:
            crc32 = self.calculate_crc32(file_path)
            hashes['crc32'] = crc32
            
            if not crc32 or crc32.lower() != expected_crc32.lower():
                logger.warning(f"CRC32 não corresponde para {file_path}. Esperado: {expected_crc32}, Encontrado: {crc32}")
                is_valid = False
        
        # Verifica MD5 se esperado
        if expected_md5:
            md5 = self.calculate_md5(file_path)
            hashes['md5'] = md5
            
            if not md5 or md5.lower() != expected_md5.lower():
                logger.warning(f"MD5 não corresponde para {file_path}. Esperado: {expected_md5}, Encontrado: {md5}")
                is_valid = False
        
        return is_valid, hashes
    
    def calculate_all_hashes(self, file_path: str) -> Dict[str, str]:
        """
        Calcula todos os hashes de um arquivo (SHA1, CRC32, MD5).
        
        Args:
            file_path: Caminho para o arquivo
            
        Returns:
            Dicionário com os hashes calculados
        """
        result = {
            'sha1': self.calculate_sha1(file_path),
            'crc32': self.calculate_crc32(file_path),
            'md5': self.calculate_md5(file_path)
        }
        return result
    
    def batch_calculate_sha1(
        self, 
        file_paths: List[str], 
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> Dict[str, str]:
        """
        Calcula o hash SHA1 para múltiplos arquivos.
        
        Args:
            file_paths: Lista de caminhos para os arquivos
            progress_callback: Função de callback para atualizar progresso (opcional)
                Parâmetros: (float porcentagem, int concluídos, int total)
                Retorno: True para continuar, False para cancelar
            
        Returns:
            Dicionário com caminhos de arquivo como chaves e hashes SHA1 como valores
        """
        result = {}
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            # Verifica se deve continuar
            if progress_callback:
                should_continue = progress_callback(i / total * 100.0, i, total)
                if not should_continue:
                    logger.info("Cálculo de SHA1 em lote cancelado")
                    break
            
            # Calcula o hash
            sha1 = self.calculate_sha1(file_path)
            if sha1:
                result[file_path] = sha1
        
        # Atualiza o progresso para 100% se não foi cancelado
        if progress_callback and len(result) == total:
            progress_callback(100.0, total, total)
            
        return result
    
    def clear_cache(self) -> None:
        """
        Limpa o cache de hashes.
        """
        with self._cache_lock:
            self._sha1_cache.clear()
            self._crc32_cache.clear()
            self._md5_cache.clear()
            
        logger.debug("Cache de hashes limpo") 