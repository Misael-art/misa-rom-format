#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Import Service
Serviço de importação de ROMs
"""

import os
import logging
from lxml import etree as ET
from lxml.etree import XMLSyntaxError
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class ImportService:
    """Serviço para importação de arquivos DAT/XML."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializa o serviço.
        
        Args:
            db_manager: Gerenciador do banco de dados
        """
        self.db_manager = db_manager
    
    def import_dat_file(self, file_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Importa arquivo DAT/XML.
        
        Args:
            file_path: Caminho do arquivo
            progress_callback: Callback para atualizar progresso
            
        Returns:
            True se importou com sucesso
        """
        try:
            # Verifica conexão
            if not self.db_manager.is_connected:
                raise ValueError("Banco não conectado")
                
            # Abre arquivo com tratamento de erro XML
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
            except XMLSyntaxError as xml_err:
                logger.error(f"Erro de parsing XML no arquivo {file_path}: {str(xml_err)}")
                raise ValueError(f"Arquivo XML inválido: {str(xml_err)}")
            
            # Obtém jogos
            games = root.findall(".//game")
            total = len(games)
            
            if total == 0:
                raise ValueError("Nenhum jogo encontrado no arquivo")
                
            # Coleta dados para batch insert
            games_data = []
            roms_data = []
            processed = 0
            
            for i, game in enumerate(games):
                # Extrai dados do jogo
                name = game.get("name", "")
                description_elem = game.find("description")
                description = description_elem.text if description_elem is not None else name
                
                rom_elements = game.findall("rom")
                if not rom_elements:
                    continue
                
                # Coleta ROMs para este jogo (game_id será atribuído após insert batch)
                temp_roms = []
                for rom in rom_elements:
                    rom_name = rom.get("name", "")
                    size = rom.get("size", "0")
                    crc = rom.get("crc", "")
                    md5 = rom.get("md5", "")
                    sha1 = rom.get("sha1", "")
                    temp_roms.append((None, rom_name, int(size) if size.isdigit() else 0, crc, md5, sha1))  # game_id placeholder
                
                if temp_roms:
                    games_data.append((name, description))
                    roms_data.append(temp_roms)
                
                # Atualiza progresso
                processed += 1
                if progress_callback:
                    progress = (processed / total) * 100
                    progress_callback(progress)
            
            if not games_data:
                return True
            
            # Batch insert games usando transaction
            with self.db_manager.transaction() as conn:
                cursor = conn.cursor()
                
                # Insere games em batch
                cursor.executemany("""
                    INSERT INTO games (name, description)
                    VALUES (?, ?)
                """, games_data)
                game_ids = [cursor.lastrowid - len(games_data) + i + 1 for i in range(len(games_data))]
                
                # Atualiza roms_data com game_ids corretos
                all_roms = []
                for idx, temp_roms in enumerate(roms_data):
                    game_id = game_ids[idx]
                    for rom in temp_roms:
                        all_roms.append((game_id,) + rom[1:])
                
                # Insere roms em batch
                cursor.executemany("""
                    INSERT INTO roms (game_id, name, size_file, crc, md5, sha1)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, all_roms)
                
                # Commit é feito automaticamente pela transação
            
            logger.info(f"Importado {len(games_data)} jogos e {len(all_roms)} ROMs em batch")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao importar DAT: {str(e)}", exc_info=True)
            return False
    
    def import_batch(
        self,
        directory: str,
        progress_callback: Optional[Callable[[int, int, str], bool]] = None
    ) -> Tuple[int, int]:
        """
        Importa múltiplos arquivos DAT de um diretório.
        
        Args:
            directory: Diretório com arquivos DAT
            progress_callback: Função de callback para progresso
                Recebe: (atual, total, status)
                Retorna: True para continuar, False para cancelar
                
        Returns:
            Tupla com (total importado, total com erro)
        """
        try:
            # Verifica diretório
            if not os.path.isdir(directory):
                raise NotADirectoryError(f"Diretório não encontrado: {directory}")
            
            # Lista arquivos DAT
            dat_files = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith((".dat", ".xml")):
                        dat_files.append(os.path.join(root, file))
            
            # Verifica se há arquivos
            if not dat_files:
                raise ValueError(f"Nenhum arquivo DAT/XML encontrado em: {directory}")
            
            # Importa arquivos
            total_files = len(dat_files)
            imported = 0
            errors = 0
            
            for i, file_path in enumerate(dat_files, 1):
                try:
                    # Verifica cancelamento
                    if progress_callback:
                        status = f"Importando {os.path.basename(file_path)}..."
                        if not progress_callback(i, total_files, status):
                            break
                    
                    # Importa arquivo
                    success = self.import_dat_file(file_path)
                    
                    if success:
                        imported += 1
                    else:
                        errors += 1
                        
                except Exception as e:
                    logging.error(f"Erro ao importar {file_path}: {str(e)}", exc_info=True)
                    errors += 1
            
            # Log
            logging.info(f"Importação em lote concluída: {imported} sucesso, {errors} erros")
            
            return imported, errors
            
        except Exception as e:
            logging.error(f"Erro na importação em lote: {str(e)}", exc_info=True)
            raise

    def import_directory(
        self,
        directory: str,
        recursive: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Importa arquivos de um diretório.
        
        Args:
            directory: Diretório a importar
            recursive: Busca recursiva
            progress_callback: Função de progresso
        
        Returns:
            Tuple[bool, Dict[str, int]]: (sucesso, estatísticas)
        """
        try:
            # Verifica diretório
            if not os.path.isdir(directory):
                logger.error(f"Diretório não encontrado: {directory}")
                return False, {}
            
            # Lista arquivos
            files = []
            
            if recursive:
                for root, _, filenames in os.walk(directory):
                    for filename in filenames:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in [".dat", ".xml"]:
                            files.append(os.path.join(root, filename))
            else:
                for filename in os.listdir(directory):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in [".dat", ".xml"]:
                        files.append(os.path.join(directory, filename))
            
            if not files:
                logger.warning("Nenhum arquivo encontrado")
                return False, {}
            
            # Estatísticas
            stats = {
                "imported": 0,
                "skipped": 0,
                "errors": 0
            }
            
            # Processa arquivos
            total_files = len(files)
            
            for i, file_path in enumerate(files, 1):
                if progress_callback:
                    progress = (i / total_files) * 100
                    progress_callback(
                        progress,
                        f"Processando arquivo {i}/{total_files}..."
                    )
                
                # Importa arquivo
                success = self.import_dat_file(file_path)
                
                if success:
                    stats["imported"] += 1
                else:
                    stats["errors"] += 1
            
            return True, stats
            
        except Exception as e:
            logger.error(f"Erro ao importar diretório: {str(e)}")
            return False, {}

    def _insert_game(self, name: str, description: str) -> Optional[int]:
        """Insere jogo no banco."""
        try:
            conn = self.db_manager.connection()
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO games (name, description)
                VALUES (?, ?)
            """, (name, description))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logging.error(f"Erro ao inserir jogo: {str(e)}")
            return None
            
    def _insert_rom(self, game_id: int, rom_element: ET.Element) -> bool:
        """Insere ROM no banco."""
        try:
            name = rom_element.get("name", "")
            size = rom_element.get("size", "0")
            crc = rom_element.get("crc", "")
            md5 = rom_element.get("md5", "")
            sha1 = rom_element.get("sha1", "")
            
            conn = self.db_manager.connection()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO roms (game_id, name, size, crc, md5, sha1)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (game_id, name, size, crc, md5, sha1))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Erro ao inserir ROM: {str(e)}")
            return False