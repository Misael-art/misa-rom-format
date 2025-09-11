#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Utilitários de Arquivos Compactados
Responsável por lidar com arquivos ZIP, 7Z, RAR e outros formatos
"""

import os
import zipfile
import logging
import tempfile
import shutil
from typing import List, Dict, Optional, Callable, Tuple, Set, Any

# Logger
logger = logging.getLogger(__name__)

class ArchiveUtils:
    """
    Classe de utilidades para trabalhar com arquivos compactados.
    """
    
    @staticmethod
    def is_zipfile(file_path: str) -> bool:
        """
        Verifica se um arquivo é um ZIP válido.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se for um arquivo ZIP válido
        """
        return zipfile.is_zipfile(file_path)
    
    @staticmethod
    def is_7zfile(file_path: str) -> bool:
        """
        Verifica se um arquivo é um 7Z válido.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se for um arquivo 7Z válido
        """
        # Verifica a extensão e os primeiros bytes do arquivo
        try:
            if not file_path.lower().endswith('.7z'):
                return False
                
            with open(file_path, 'rb') as f:
                signature = f.read(6)
                # Assinatura do 7z: '7z\xBC\xAF\x27\x1C'
                return signature == b'7z\xBC\xAF\x27\x1C'
        except Exception as e:
            logger.error(f"Erro ao verificar arquivo 7Z: {e}")
            return False
    
    @staticmethod
    def list_zip_contents(file_path: str) -> List[Dict[str, Any]]:
        """
        Lista o conteúdo de um arquivo ZIP.
        
        Args:
            file_path: Caminho do arquivo ZIP
            
        Returns:
            Lista de dicionários com informações dos arquivos
        """
        result = []
        
        try:
            if not zipfile.is_zipfile(file_path):
                logger.error(f"Arquivo não é um ZIP válido: {file_path}")
                return result
                
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for info in zip_ref.infolist():
                    # Pula diretórios
                    if info.filename.endswith('/'):
                        continue
                        
                    result.append({
                        'filename': info.filename,
                        'size': info.file_size,
                        'compressed_size': info.compress_size,
                        'date_time': "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*info.date_time)
                    })
        except Exception as e:
            logger.error(f"Erro ao listar conteúdo do ZIP: {e}")
            
        return result
    
    @staticmethod
    def list_7z_contents(file_path: str) -> List[Dict[str, Any]]:
        """
        Lista o conteúdo de um arquivo 7Z.
        
        Args:
            file_path: Caminho do arquivo 7Z
            
        Returns:
            Lista de dicionários com informações dos arquivos
        """
        result = []
        
        try:
            # Tenta importar o módulo py7zr
            import py7zr
            
            if not ArchiveUtils.is_7zfile(file_path):
                logger.error(f"Arquivo não é um 7Z válido: {file_path}")
                return result
                
            with py7zr.SevenZipFile(file_path, 'r') as archive:
                for filename, info in archive.files.items():
                    # Pula diretórios
                    if info.is_directory:
                        continue
                        
                    result.append({
                        'filename': filename,
                        'size': info.uncompressed,
                        'compressed_size': info.compressed or 0,
                        'date_time': info.creationtime.strftime("%Y-%m-%d %H:%M:%S") 
                            if info.creationtime else "Unknown"
                    })
        except ImportError:
            logger.error("Módulo py7zr não encontrado. Instale com: pip install py7zr")
        except Exception as e:
            logger.error(f"Erro ao listar conteúdo do 7Z: {e}")
            
        return result
    
    @staticmethod
    def extract_file_from_zip(
        zip_path: str, 
        file_name: str, 
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extrai um arquivo específico de um ZIP.
        
        Args:
            zip_path: Caminho do arquivo ZIP
            file_name: Nome do arquivo a extrair
            output_path: Caminho de saída (opcional)
            
        Returns:
            Caminho do arquivo extraído ou None se falhar
        """
        try:
            if not zipfile.is_zipfile(zip_path):
                logger.error(f"Arquivo não é um ZIP válido: {zip_path}")
                return None
            
            # Se output_path não foi especificado, cria um diretório temporário
            temp_dir = None
            if not output_path:
                temp_dir = tempfile.mkdtemp()
                output_path = temp_dir
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Verifica se o arquivo existe no ZIP
                found = False
                for info in zip_ref.infolist():
                    if info.filename == file_name or os.path.basename(info.filename) == file_name:
                        found = True
                        # Extrai o arquivo
                        zip_ref.extract(info, output_path)
                        extracted_path = os.path.join(output_path, info.filename)
                        return extracted_path
                
                if not found:
                    logger.warning(f"Arquivo '{file_name}' não encontrado no ZIP: {zip_path}")
                    if temp_dir:
                        shutil.rmtree(temp_dir)
                    return None
                
        except Exception as e:
            logger.error(f"Erro ao extrair arquivo do ZIP: {e}")
            return None
    
    @staticmethod
    def extract_file_from_7z(
        archive_path: str, 
        file_name: str, 
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extrai um arquivo específico de um 7Z.
        
        Args:
            archive_path: Caminho do arquivo 7Z
            file_name: Nome do arquivo a extrair
            output_path: Caminho de saída (opcional)
            
        Returns:
            Caminho do arquivo extraído ou None se falhar
        """
        try:
            # Tenta importar o módulo py7zr
            import py7zr
            
            if not ArchiveUtils.is_7zfile(archive_path):
                logger.error(f"Arquivo não é um 7Z válido: {archive_path}")
                return None
            
            # Se output_path não foi especificado, cria um diretório temporário
            temp_dir = None
            if not output_path:
                temp_dir = tempfile.mkdtemp()
                output_path = temp_dir
            
            with py7zr.SevenZipFile(archive_path, 'r') as archive:
                # Obtém a lista de arquivos
                file_list = archive.getnames()
                
                # Encontra o arquivo solicitado
                target_file = None
                for f in file_list:
                    if f == file_name or os.path.basename(f) == file_name:
                        target_file = f
                        break
                
                if not target_file:
                    logger.warning(f"Arquivo '{file_name}' não encontrado no 7Z: {archive_path}")
                    if temp_dir:
                        shutil.rmtree(temp_dir)
                    return None
                
                # Extrai apenas o arquivo solicitado
                archive.extract(output_path, [target_file])
                extracted_path = os.path.join(output_path, target_file)
                return extracted_path
                
        except ImportError:
            logger.error("Módulo py7zr não encontrado. Instale com: pip install py7zr")
            return None
        except Exception as e:
            logger.error(f"Erro ao extrair arquivo do 7Z: {e}")
            return None
    
    @staticmethod
    def create_zip_file(
        output_path: str, 
        files_to_add: List[str],
        base_dir: Optional[str] = None,
        compression_level: int = 9,
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Cria um arquivo ZIP com os arquivos especificados.
        
        Args:
            output_path: Caminho do arquivo ZIP a ser criado
            files_to_add: Lista de arquivos a adicionar
            base_dir: Diretório base para manter estrutura relativa (opcional)
            compression_level: Nível de compressão (0-9)
            progress_callback: Função para relatório de progresso
                Parâmetros: (float percentual, int processados, int total)
                Retorno: True para continuar, False para cancelar
                
        Returns:
            True se o arquivo foi criado com sucesso
        """
        try:
            # Cria o diretório de saída se não existir
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Normaliza o diretório base
            if base_dir:
                base_dir = os.path.normpath(base_dir)
            
            with zipfile.ZipFile(
                output_path, 'w', 
                compression=zipfile.ZIP_DEFLATED, 
                compresslevel=compression_level
            ) as zip_file:
                
                total_files = len(files_to_add)
                
                for i, file_path in enumerate(files_to_add):
                    if not os.path.isfile(file_path):
                        logger.warning(f"Pulando arquivo inexistente: {file_path}")
                        continue
                    
                    # Determina o nome do arquivo no ZIP
                    if base_dir and file_path.startswith(base_dir):
                        # Usa caminho relativo ao base_dir
                        arcname = os.path.relpath(file_path, base_dir)
                    else:
                        # Usa apenas o nome do arquivo
                        arcname = os.path.basename(file_path)
                    
                    # Adiciona o arquivo ao ZIP
                    zip_file.write(file_path, arcname=arcname)
                    
                    # Atualiza o progresso
                    if progress_callback:
                        progress = (i + 1) / total_files * 100
                        if not progress_callback(progress, i + 1, total_files):
                            logger.info("Criação de ZIP cancelada pelo usuário")
                            return False
            
            logger.info(f"Arquivo ZIP criado com sucesso: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar arquivo ZIP: {e}")
            return False
    
    @staticmethod
    def extract_all_from_zip(
        zip_path: str,
        output_dir: str,
        overwrite: bool = True,
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Extrai todos os arquivos de um ZIP.
        
        Args:
            zip_path: Caminho do arquivo ZIP
            output_dir: Diretório de saída
            overwrite: Se True, sobrescreve arquivos existentes
            progress_callback: Função para relatório de progresso
                Parâmetros: (float percentual, int processados, int total)
                Retorno: True para continuar, False para cancelar
                
        Returns:
            True se a extração foi bem-sucedida
        """
        try:
            if not zipfile.is_zipfile(zip_path):
                logger.error(f"Arquivo não é um ZIP válido: {zip_path}")
                return False
            
            # Cria o diretório de saída se não existir
            os.makedirs(output_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Obtém a lista de arquivos
                file_list = zip_ref.infolist()
                total_files = len(file_list)
                
                # Extrai os arquivos
                for i, file_info in enumerate(file_list):
                    # Pula diretórios
                    if file_info.filename.endswith('/'):
                        continue
                    
                    # Caminho completo do arquivo extraído
                    extract_path = os.path.join(output_dir, file_info.filename)
                    
                    # Verifica se o arquivo já existe e se deve sobrescrever
                    if not overwrite and os.path.exists(extract_path):
                        logger.info(f"Pulando arquivo existente: {file_info.filename}")
                        continue
                    
                    # Cria o diretório pai do arquivo se não existir
                    os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                    
                    # Extrai o arquivo
                    zip_ref.extract(file_info, output_dir)
                    
                    # Atualiza o progresso
                    if progress_callback:
                        progress = (i + 1) / total_files * 100
                        if not progress_callback(progress, i + 1, total_files):
                            logger.info("Extração de ZIP cancelada pelo usuário")
                            return False
            
            logger.info(f"Arquivo ZIP extraído com sucesso para: {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao extrair arquivo ZIP: {e}")
            return False
    
    @staticmethod
    def get_supported_archive_extensions() -> List[str]:
        """
        Retorna a lista de extensões de arquivo suportadas.
        
        Returns:
            Lista de extensões (por exemplo, ['.zip', '.7z'])
        """
        extensions = ['.zip']
        
        # Verifica se o módulo py7zr está disponível
        try:
            import py7zr
            extensions.append('.7z')
        except ImportError:
            logger.debug("Módulo py7zr não disponível - suporte a arquivos .7z desabilitado")
            
        return extensions