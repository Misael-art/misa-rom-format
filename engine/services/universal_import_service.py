#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Universal Import Service
Serviço de importação que mantém catálogo verdadeiramente UNIVERSAL
Integra detecção de duplicatas, resolução de ambiguidades e fusão inteligente
"""

import os
import logging
import hashlib
import json
from lxml import etree as ET
from lxml.etree import XMLSyntaxError
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import concurrent.futures
import threading
import tempfile

from ..db.database_manager_v2 import DatabaseManagerV2
from ..db.fusion_manager import FusionManager, RomData

logger = logging.getLogger(__name__)

@dataclass
class ImportBatch:
    """Lote de dados para importação otimizada."""
    games: List[Tuple[str, str]]  # [(name, description), ...]
    roms: List[Tuple[RomData, int]]  # [(rom_data, game_index), ...]
    sources: List[Dict[str, Any]]  # Metadados de fontes
    batch_size: int

@dataclass
class ImportStatistics:
    """Estatísticas detalhadas da importação."""
    files_processed: int = 0
    games_imported: int = 0
    roms_imported: int = 0
    duplicates_found: int = 0
    fusions_performed: int = 0
    sources_added: int = 0
    errors_encountered: int = 0
    processing_time: float = 0.0
    data_preserved: int = 0
    ambiguities_resolved: int = 0

class UniqueROM:
    """Representa uma ROM única com múltiplas fontes de validação."""
    def __init__(self, hash_fingerprint: str):
        self.hash_fingerprint = hash_fingerprint
        self.rom_data = None
        self.sources = []
        self.confidence_scores = []

    def add_source(self, source_data: Dict[str, Any], confidence: float):
        """Adiciona fonte de validação para esta ROM."""
        self.sources.append(source_data)
        self.confidence_scores.append(confidence)

        # Atualiza dados com informações mais confiáveis
        if self.rom_data is None:
            self.rom_data = source_data
        else:
            self.rom_data = self._merge_with_best_confidence(source_data, confidence)

    def _merge_with_best(self, new_data: Dict[str, Any], new_confidence: float) -> Dict[str, Any]:
        """Fusão inteligente preservando os melhores dados."""
        if not self.rom_data:
            return new_data

        merged = self.rom_data.copy()

        # Estratégia: preservar dados mais completos e confiáveis
        for key, new_value in new_data.items():
            current_value = merged.get(key)

            # Se não tem valor atual, usa novo
            if not current_value:
                merged[key] = new_value
            # Se ambos têm valor, escolher baseado em confiança
            elif new_value and new_value != current_value:
                # Prefere valores mais longos/informativos se confiança similar
                if len(str(new_value)) > len(str(current_value)) and new_confidence >= 0.8:
                    merged[key] = new_value

        return merged

    def _merge_with_best_confidence(self, new_data: Dict[str, Any], new_confidence: float) -> Dict[str, Any]:
        """Fusão inteligente preservando os melhores dados baseada em confiança."""
        if not self.rom_data:
            return new_data

        merged = self.rom_data.copy()

        # Estratégia: preservar dados mais completos e confiáveis
        for key, new_value in new_data.items():
            current_value = merged.get(key)

            # Se não tem valor atual, usa novo
            if not current_value:
                merged[key] = new_value
            # Se ambos têm valor, escolher baseado em confiança
            elif new_value and new_value != current_value:
                # Prefere valores mais longos/informativos se confiança similar
                current_confidence = sum(self.confidence_scores) / len(self.confidence_scores)

                if new_confidence > current_confidence:
                    # Nova fonte mais confiável
                    merged[key] = new_value
                elif len(str(new_value)) > len(str(current_value)) and abs(new_confidence - current_confidence) < 0.2:
                    # Mesmo nível de confiança, mas valor mais informativo
                    merged[key] = new_value

        return merged

class UniversalImportService:
    """
    Serviço de importação universal que mantém todos os dados (XML, DAT, ROM headers)
    e resolve duplicatas/amiguidades de forma inteligente através do FusionManager.
    """

    def __init__(self, db_manager: DatabaseManagerV2, fusion_manager: FusionManager):
        """
        Inicializa serviço de importação universal.

        Args:
            db_manager: DatabaseManagerV2 com pool de conexões
            fusion_manager: FusionManager para resolução inteligente
        """
        self.db_manager = db_manager
        self.fusion_manager = fusion_manager

        # Cache de ROMs únicas para processamento otimizado
        self.unique_roms_cache = {}
        self.cache_lock = threading.Lock()

        # Configuração de processamento paralelo
        self.max_workers = min(8, os.cpu_count() or 4)
        self.batch_size = 500

        # Estatísticas globais
        self.stats = ImportStatistics()

        # Source trackers para confiança
        self.source_conformity = {}

    def import_universal_batch(self, files: List[str], progress_callback: Optional[Callable] = None) -> ImportStatistics:
        """
        Importação universal de arquivos mantendo verdadeiro catálogo universal.

        Args:
            files: Lista de arquivos (DAT/XML) para importação
            progress_callback: Callback para progresso (current, total, message)

        Returns:
            Estatísticas detalhadas da importação
        """
        start_time = datetime.now()
        logger.info(f"Iniciando importação universal: {len(files)} arquivos")

        try:
            # Garante estrutura de fusão
            if not self.fusion_manager.ensure_fusion_structure():
                raise RuntimeError("Falha ao configurar estrutura de fusão inteligente")

            # Processamento paralelo por arquivo
            all_batches = []

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self._process_file_universal, file_path, i+1, len(files))
                          for i, file_path in enumerate(files)]

                for future in concurrent.futures.as_completed(futures):
                    try:
                        if progress_callback:
                            current_idx = len(all_batches) + 1
                            progress_callback(current_idx, len(files), f"Processando arquivo {current_idx}/{len(files)}...")

                        batch_result = future.result()
                        if batch_result:
                            all_batches.append(batch_result)

                    except Exception as e:
                        logger.error(f"Erro processando arquivo: {e}")
                        self.stats.errors_encountered += 1

            # Consolidação e fusão inteligente
            if all_batches:
                consolidation_result = self._consolidate_and_fuse_batches(all_batches)

                if consolidation_result and progress_callback:
                    progress_callback(len(files), len(files), "Consolidando dados e resolvendo ambiguidades...")

            # Atualiza estatísticas finais
            self.stats.processing_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"Importação universal concluída: {self.stats.games_imported} jogos, {self.stats.roms_imported} ROMs")
            logger.info(".2f")

            return self.stats

        except Exception as e:
            logger.error(f"Erro crítico na importação universal: {e}")
            raise

    def _process_file_universal(self, file_path: str, file_idx: int, total_files: int) -> Optional[ImportBatch]:
        """
        Processa arquivo individual para extração universal de dados.
        Mantém todas as informações de fonte sem descartes.
        """
        try:
            logger.debug(f"Processando arquivo {file_idx}/{total_files}: {os.path.basename(file_path)}")

            # Parse do arquivo
            tree = ET.parse(file_path)
            root = tree.getroot()
            source_name = os.path.basename(file_path)

            # Extrai dados mantendo todas as fontes
            games_data = []
            roms_data = []

            for game_elem in root.findall(".//game"):
                game_name = game_elem.get("name", "")
                description_elem = game_elem.find("description")
                description = description_elem.text if description_elem is not None else game_name

                rom_elements = game_elem.findall("rom")

                if rom_elements:
                    games_data.append((game_name, description))

                    for rom_elem in rom_elements:
                        rom_data = self._extract_rom_with_sources(rom_elem, source_name)
                        if rom_data:
                            roms_data.append((rom_data, len(games_data) - 1))

            if not games_data:
                logger.warning(f"Nenhum dado encontrado no arquivo: {file_path}")
                return None

            # Cria lote otimizado
            batch = ImportBatch(
                games=games_data,
                roms=roms_data,
                sources=[{"filename": source_name, "timestamp": datetime.now().isoformat()}],
                batch_size=len(roms_data)
            )

            return batch

        except XMLSyntaxError as xml_err:
            logger.error(f"Erro XML no arquivo {file_path}: {xml_err}")
            return None
        except Exception as e:
            logger.error(f"Erro processando {file_path}: {e}")
            return None

    def _extract_rom_with_sources(self, rom_elem: ET.Element, source_name: str) -> Optional[RomData]:
        """
        Extrai dados completos da ROM incluindo todas as fontes de validação.
        Mantém todos os hashes disponíveis sem descartar nenhum.
        """
        try:
            # Extrai informações básicas
            name = rom_elem.get("name", "")
            size_str = rom_elem.get("size", "0")
            size = int(size_str) if size_str.isdigit() else 0

            # Extrai TODOS os hashes disponíveis
            hashes = {}
            hash_fields = ['crc', 'md5', 'sha1', 'crc32', 'sha256', 'ripemd160']
            for hash_type in hash_fields:
                hash_value = rom_elem.get(hash_type)
                if hash_value and hash_value.strip():
                    hashes[hash_type] = hash_value.strip()

            if not hashes and size == 0 and not name:
                logger.debug("ROM sem dados identificáveis, pulando")
                return None

            # Metadados adicionais (mantém compatibilidade futura)
            metadata = {
                'filename': name,
                'size': size,
                'source_file': source_name,
                'extraction_timestamp': datetime.now().isoformat()
            }

            # Cria fingerprint para identificação universal
            hash_fingerprint = self._create_universal_fingerprint(hashes, size)

            # Cria estrutura RomData
            rom_data = RomData(
                id=None,  # Será atribuído na inserção
                name=name,
                size=size,
                hashes=hashes,
                metadata=metadata,
                sources=[source_name]
            )

            # Adiciona ao cache de ROMs únicas
            with self.cache_lock:
                if hash_fingerprint not in self.unique_roms_cache:
                    self.unique_roms_cache[hash_fingerprint] = UniqueROM(hash_fingerprint)
                    self.stats.data_preserved += 1

                self.unique_roms_cache[hash_fingerprint].add_source(
                    {'rom_data': rom_data, 'metadata': metadata},
                    confidence=1.0  # Confiança total na fonte original
                )

            return rom_data

        except Exception as e:
            logger.error(f"Erro extraindo ROM: {e}")
            return None

    def _create_universal_fingerprint(self, hashes: Dict[str, str], size: int) -> str:
        """Cria fingerprint universal baseado em todos os hashes disponíveis."""
        fingerprint_components = []

        # Ordena hashes por prioridade (SHA1 primeiro, depois MD5, etc.)
        hash_priority = ['sha1', 'sha256', 'md5', 'crc32', 'ripemd160', 'crc']
        for hash_type in hash_priority:
            if hash_type in hashes:
                fingerprint_components.append(f"{hash_type}:{hashes[hash_type]}")

        # Adiciona tamanho como fallback
        if size > 0:
            fingerprint_components.append(f"size:{size}")

        # Cria hash do fingerprint
        fingerprint_str = "|".join(fingerprint_components)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()

    def _consolidate_and_fuse_batches(self, batches: List[ImportBatch]) -> bool:
        """
        Consolidação inteligente com fusão automática.
        Mantém todas as fontes sem perder dados.
        """
        try:
            logger.info("Iniciando consolidação inteligente de lotes...")

            # Coleta todas as ROMs únicas do cache
            all_unique_roms = []
            with self.cache_lock:
                for unique_rom in self.unique_roms_cache.values():
                    if unique_rom.sources:
                        # Seleciona a melhor representação
                        best_source = unique_rom.sources[0]  # Simplificado
                        rom_data = best_source.get('rom_data')
                        if rom_data:
                            all_unique_roms.append(rom_data)

            # Detecta duplicatas usando FusionManager
            if all_unique_roms:
                candidates = self.fusion_manager.detect_duplicates_batch(all_unique_roms, self.batch_size)

                if candidates:
                    self.stats.duplicates_found = len(candidates)
                    fusion_results = self.fusion_manager.perform_fusion_batch(candidates)
                    self.stats.fusions_performed = fusion_results.get('auto_merged', 0)

            # Importação em lote das ROMs restantes (não duplicadas)
            for batch in batches:
                success = self._import_batch_optimized(batch)
                if success:
                    self.stats.games_imported += len(batch.games)
                    self.stats.roms_imported += len(batch.roms)

            # Limpa cache para próxima importação
            with self.cache_lock:
                self.unique_roms_cache.clear()

            logger.info("Consolidação inteligente concluída")
            return True

        except Exception as e:
            logger.error(f"Erro na consolidação: {e}")
            return False

    def _import_batch_optimized(self, batch: ImportBatch) -> bool:
        """
        Importação otimizada do lote com prepared statements e transaction.
        """
        if not batch.games and not batch.roms:
            return True

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Inicia transação
                cursor.execute("BEGIN TRANSACTION")

                # Insere jogos
                game_ids = []
                if batch.games:
                    cursor.executemany("""
                        INSERT INTO games (name, description) VALUES (?, ?)
                    """, batch.games)

                    # Recupera IDs dos jogos inseridos
                    game_ids = []
                    for i in range(len(batch.games)):
                        game_ids.append(cursor.lastrowid - len(batch.games) + i + 1)

                # Insere ROMs com relationships corretas
                rom_insert_data = []
                source_insert_data = []

                for rom_data, game_idx in batch.roms:
                    if game_idx < len(game_ids):
                        game_id = game_ids[game_idx]
                        rom_insert_data.append((
                            game_id, rom_data.name, rom_data.size,
                            rom_data.hashes.get('crc'), rom_data.hashes.get('md5'), rom_data.hashes.get('sha1')
                        ))

                        # Dados das fontes
                        for source in batch.sources:
                            source_insert_data.append((
                                None,  # rom_id será atribuído
                                source.get('filename', 'batch_import'),
                                'dat_xml',
                                json.dumps(rom_data.hashes),
                                json.dumps(rom_data.metadata)
                            ))

                # Insere ROMs
                if rom_insert_data:
                    cursor.executemany("""
                        INSERT INTO roms (game_id, name, size_file, crc, md5, sha1)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, rom_insert_data)

                    # Atualiza source_insert_data com rom_ids corretos
                    start_id = cursor.lastrowid - len(rom_insert_data) + 1
                    for i, source_data in enumerate(source_insert_data):
                        updated_source = (start_id + i,) + source_data[1:]
                        cursor.execute("""
                            INSERT INTO rom_sources (rom_id, source_name, source_type, hash_data, metadata)
                            VALUES (?, ?, ?, ?, ?)
                        """, updated_source)

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Erro na importação do lote: {e}")
            # Rollback será automático se sair do context
            return False

    def get_import_statistics(self) -> ImportStatistics:
        """Obtém estatísticas detalhadas da importação."""
        return self.stats

    def reset_statistics(self):
        """Reseta estatísticas para nova importação."""
        self.stats = ImportStatistics()
        with self.cache_lock:
            self.unique_roms_cache.clear()

    def bulk_import_from_directory(
        self,
        directory: str,
        file_patterns: List[str] = None,
        max_depth: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> ImportStatistics:
        """
        Importação em massa de diretório com padrões avançados.

        Args:
            directory: Diretório raiz
            file_patterns: Padrões de arquivo (['*.dat', '*.xml'])
            max_depth: Profundidade máxima de busca
            progress_callback: Função de progresso

        Returns:
            Estatísticas da importação
        """
        if file_patterns is None:
            file_patterns = ['*.dat', '*.xml']

        try:
            # Coleta arquivos
            import glob
            all_files = []

            for pattern in file_patterns:
                search_pattern = os.path.join(directory, '**', pattern)
                matching_files = glob.glob(search_pattern, recursive=True)

                # Limita profundidade
                filtered_files = []
                for file_path in matching_files:
                    rel_path = os.path.relpath(file_path, directory)
                    depth = rel_path.count(os.sep)
                    if depth <= max_depth:
                        filtered_files.append(file_path)

                all_files.extend(filtered_files)

            if not all_files:
                logger.warning(f"Nenhum arquivo encontrado em: {directory}")
                return self.stats

            logger.info(f"Encontrados {len(all_files)} arquivos para importação")

            # Executa importação universal
            return self.import_universal_batch(all_files, progress_callback)

        except Exception as e:
            logger.error(f"Erro na importação em massa: {e}")
            raise

    def validate_import_integrity(self) -> Dict[str, Any]:
        """
        Validação completa da integridade pós-importação.
        Assegura que nenhum dado foi perdido no processo.
        """
        integrity_report = {
            'universal_catalog_maintained': True,
            'all_sources_preserved': True,
            'duplicates_handled': True,
            'foreign_keys_valid': True,
            'issues': [],
            'data_loss_percentage': 0.0
        }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Verifica se todas as ROMs foram importadas
                cursor.execute("SELECT COUNT(*) FROM roms")
                total_roms = cursor.fetchone()[0]

                # Verifica se todas as fontes estão representadas
                cursor.execute("SELECT COUNT(*) FROM rom_sources")
                total_sources = cursor.fetchone()[0]

                # Calcula proporção esperada (cada ROM deveria ter pelo menos uma fonte)
                if total_sources < total_roms:
                    integrity_report['all_sources_preserved'] = False
                    integrity_report['issues'].append(f"Faltam fontes: esperado {total_roms}, encontrado {total_sources}")

                # Verifica foreign keys
                cursor.execute("""
                    SELECT COUNT(*) FROM roms r
                    LEFT JOIN games g ON r.game_id = g.id
                    WHERE g.id IS NULL
                """)
                orphaned_count = cursor.fetchone()[0]

                if orphaned_count > 0:
                    integrity_report['foreign_keys_valid'] = False
                    integrity_report['issues'].append(f"ROMs órfãs detectadas: {orphaned_count}")

                # Verifica duplicatas não resolvidas
                cursor.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT sha1, COUNT(*) as count
                        FROM roms
                        WHERE sha1 IS NOT NULL AND sha1 != '' AND status != 'merged'
                        GROUP BY sha1
                        HAVING count > 1
                    )
                """)
                unresolved_duplicates = cursor.fetchone()[0]

                if unresolved_duplicates > 0:
                    integrity_report['duplicates_handled'] = False
                    integrity_report['issues'].append(f"Duplicatas não resolvidas: {unresolved_duplicates}")

                # Calcula taxa de perda de dados (inversa à preservação)
                loss_rate = (total_sources - total_roms) / max(total_roms, 1)
                integrity_report['data_loss_percentage'] = max(0, loss_rate * 100)

                integration_report['universal_catalog_maintained'] = len(integrity_report['issues']) == 0

        except Exception as e:
            integrity_report['issues'].append(f"Erro na validação: {e}")
            integrity_report['universal_catalog_maintained'] = False

        return integrity_report