#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - XML Parser
Parser para arquivos DAT/XML do No-Intro e Redump
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from lxml import etree

from ..utils.common import clean_rom_name, parse_rom_name

logger = logging.getLogger(__name__)

class XMLParser:
    """Parser para arquivos DAT/XML."""
    
    def __init__(self):
        """Inicializa o parser."""
        self.current_file = None
        self.current_game = None
    
    def parse_file(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Faz parse de um arquivo DAT/XML.
        
        Args:
            file_path: Caminho do arquivo
        
        Returns:
            Tuple[bool, Dict[str, Any]]: (sucesso, informações)
        """
        try:
            # Verifica arquivo
            if not os.path.exists(file_path):
                return False, {"error": "Arquivo não encontrado"}
            
            # Salva arquivo atual
            self.current_file = file_path
            
            # Faz parse do XML
            tree = etree.parse(file_path)
            root = tree.getroot()
            
            # Obtém informações do cabeçalho
            header = self.parse_header(root)
            if not header:
                return False, {"error": "Cabeçalho inválido"}
            
            # Obtém lista de jogos
            games = self.parse_games(root)
            if not games:
                return False, {"error": "Nenhum jogo encontrado"}
            
            return True, {
                "header": header,
                "games": games,
                "file": os.path.basename(file_path)
            }
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse do arquivo: {str(e)}")
            return False, {"error": str(e)}
        
        finally:
            self.current_file = None
            self.current_game = None
    
    def parse_header(self, root: etree.Element) -> Optional[Dict[str, str]]:
        """
        Faz parse do cabeçalho.
        
        Args:
            root: Elemento raiz do XML
        
        Returns:
            Optional[Dict[str, str]]: Informações do cabeçalho
        """
        try:
            header = root.find("header")
            if header is None:
                return None
            
            info = {}
            
            # Nome
            name = header.find("name")
            if name is not None:
                info["name"] = name.text
            
            # Descrição
            description = header.find("description")
            if description is not None:
                info["description"] = description.text
            
            # Versão
            version = header.find("version")
            if version is not None:
                info["version"] = version.text
            
            # Autor
            author = header.find("author")
            if author is not None:
                info["author"] = author.text
            
            # Data
            date = header.find("date")
            if date is not None:
                info["date"] = date.text
            
            # Homepage
            homepage = header.find("homepage")
            if homepage is not None:
                info["homepage"] = homepage.text
            
            # URL
            url = header.find("url")
            if url is not None:
                info["url"] = url.text
            
            return info
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse do cabeçalho: {str(e)}")
            return None
    
    def parse_games(self, root: etree.Element) -> List[Dict[str, Any]]:
        """
        Faz parse dos jogos.
        
        Args:
            root: Elemento raiz do XML
        
        Returns:
            List[Dict[str, Any]]: Lista de jogos
        """
        try:
            games = []
            
            # Processa cada jogo
            for game in root.findall(".//game"):
                try:
                    # Salva jogo atual
                    self.current_game = game
                    
                    # Obtém atributos
                    game_info = {
                        "name": game.get("name", ""),
                        "description": "",
                        "roms": []
                    }
                    
                    # Descrição
                    description = game.find("description")
                    if description is not None:
                        game_info["description"] = description.text
                    
                    # Processa ROMs
                    for rom in game.findall("rom"):
                        rom_info = self.parse_rom(rom)
                        if rom_info:
                            game_info["roms"].append(rom_info)
                    
                    # Adiciona jogo se tem ROMs
                    if game_info["roms"]:
                        games.append(game_info)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar jogo: {str(e)}")
                    continue
                
                finally:
                    self.current_game = None
            
            return games
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse dos jogos: {str(e)}")
            return []
    
    def parse_rom(self, rom: etree.Element) -> Optional[Dict[str, Any]]:
        """
        Faz parse de uma ROM.
        
        Args:
            rom: Elemento ROM do XML
        
        Returns:
            Optional[Dict[str, Any]]: Informações da ROM
        """
        try:
            # Obtém atributos básicos
            name = rom.get("name", "")
            size = rom.get("size", "0")
            
            # Ignora se não tem nome ou tamanho
            if not name or not size:
                return None
            
            # Informações da ROM
            info = {
                "name": name,
                "size": int(size),
                "crc32": rom.get("crc", ""),
                "md5": rom.get("md5", ""),
                "sha1": rom.get("sha1", ""),
                "status": rom.get("status", ""),
                "bios": rom.get("bios", "no") == "yes"
            }
            
            # Informações adicionais do nome
            if name:
                parsed_name = parse_rom_name(name)
                info.update(parsed_name)
            
            return info
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse da ROM: {e}")
            return None
    
    def parse_nointro_xml(self, file_path: str, progress_callback=None) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Faz parse de um arquivo XML do No-Intro.
        
        Args:
            file_path: Caminho do arquivo XML
            progress_callback: Callback para progresso (opcional)
        
        Returns:
            Tuple[List[Dict[str, Any]], Dict[str, int]]: (dados das ROMs, estatísticas)
        """
        try:
            # Estatísticas
            stats = {
                'processed_games': 0,
                'processed_roms': 0,
                'skipped_roms': 0,
                'errors': 0
            }
            
            # Parse do arquivo
            success, info = self.parse_file(file_path)
            if not success:
                logger.error(f"Erro ao fazer parse do arquivo: {info.get('error', 'Erro desconhecido')}")
                return [], stats
            
            roms_data = []
            games = info.get('games', [])
            
            for game_idx, game in enumerate(games):
                if progress_callback:
                    progress = (game_idx / len(games)) * 100
                    progress_callback(progress, f"Processando jogo {game_idx + 1} de {len(games)}", game.get('name', 'Desconhecido'))
                
                stats['processed_games'] += 1
                
                # Processa ROMs do jogo
                for rom in game.get('roms', []):
                    try:
                        # Cria dados da ROM compatíveis com o esquema do banco
                        rom_data = {
                            'title': clean_rom_name(rom.get('name', '')),
                            'description': game.get('description', ''),
                            'name_nointro': rom.get('name', ''),
                            'name_goodtools': '',
                            'name_TOSEC': '',
                            'name_redump': '',
                            'name_ROM_Header': '',
                            'name_progetto_EMU': '',
                            'name_custom': '',
                            'name_unofficial_dumps': '',
                            'flag': rom.get('status', ''),
                            'language': rom.get('language', ''),
                            'distribution': '',
                            'versions': rom.get('version', ''),
                            'region': rom.get('region', ''),
                            'platform': info.get('header', {}).get('name', ''),
                            'name': rom.get('name', ''),
                            'path_file': '',
                            'path_image': '',
                            'size_file': str(rom.get('size', 0)),
                            'crc': rom.get('crc32', ''),
                            'md5': rom.get('md5', ''),
                            'sha1': rom.get('sha1', ''),
                            'sha256': '',
                            'serial': rom.get('serial', ''),
                            'BIOS': 1 if rom.get('bios', False) else 0,
                            'source_file': file_path
                        }
                        
                        roms_data.append(rom_data)
                        stats['processed_roms'] += 1
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar ROM {rom.get('name', 'Desconhecida')}: {e}")
                        stats['errors'] += 1
            
            logger.info(f"Parse concluído: {stats['processed_games']} jogos, {stats['processed_roms']} ROMs")
            return roms_data, stats
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse do arquivo {file_path}: {e}")
            return [], {'processed_games': 0, 'processed_roms': 0, 'skipped_roms': 0, 'errors': 1}