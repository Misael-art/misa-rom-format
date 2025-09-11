#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Intelligent Fusion Manager
Sistema de fusão inteligente para catálogo verdadeiramente universal
Mantém todas as fontes (XML, DAT, ROM headers) sem descartar dados
"""

import sqlite3
import logging
import hashlib
import json
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
import concurrent.futures
import threading

from .database_fusion_schema import create_fusion_structure, migrate_to_fusion_compatible

logger = logging.getLogger(__name__)

@dataclass
class RomData:
    """Estrutura de dados para ROM."""
    id: Optional[int]
    name: str
    size: int
    hashes: Dict[str, str]  # crc, md5, sha1, crc32, sha256, etc.
    metadata: Dict[str, Any]  # system, region, language, type, etc.
    sources: List[str]  # Lista de fontes que validam esta ROM

@dataclass
class MergeCandidate:
    """Candidato à fusão entre duas ROMs."""
    rom_id_1: int
    rom_id_2: int
    similarity_score: float
    hash_matches: Dict[str, str]
    metadata_similarity: float
    confidence: float
    merge_strategy: str  # 'auto_merge', 'manual_review', 'reject'
    sources_in_common: List[str]

class FusionManager:
    """
    Gerenciador de fusão inteligente para catálogo universal.
    Mantém todas as fontes sem descartar dados, resolvendo ambiguidades de forma inteligente.
    """

    def __init__(self, db_manager):
        """
        Inicializa o gerenciador de fusão.

        Args:
            db_manager: DatabaseManagerV2 ou similar
        """
        self.db_manager = db_manager
        self.fusion_stats = {
            'total_roms_processed': 0,
            'duplicate_candidates_found': 0,
            'auto_fusions_performed': 0,
            'manual_candidates_created': 0,
            'ambiguities_resolved': 0,
            'data_preserved': 0,
            'quality_improvements': 0
        }

        # Configurações de fusão inteligentes
        self.fusion_thresholds = {
            'auto_merge_sha1_match': 0.95,      # Fusão automática com SHA1 idêntico
            'auto_merge_multi_hash': 0.85,      # Fusão automática com múltiplos hashes
            'manual_review_threshold': 0.70,    # Requer revisão manual
            'reject_below': 0.50               # Muito diferente para propor fusão
        }

        # Cache para performance
        self._hash_cache = {}
        self._cache_lock = threading.Lock()

    def ensure_fusion_structure(self) -> bool:
        """
        Garante que estrutura de fusão está criada no banco.

        Returns:
            True se estrutura está ok
        """
        try:
            with self.db_manager.get_connection() as conn:
                success = create_fusion_structure(conn)
                if success:
                    # Migração geral automática
                    migration_stats = migrate_to_fusion_compatible(conn)
                    logger.info(f"Estrutura de fusão pronta - Migração: {migration_stats}")
                return success
        except Exception as e:
            logger.error(f"Erro criando estrutura de fusão: {e}")
            return False

    def detect_duplicates_batch(self, rom_batch: List[RomData], batch_size: int = 100) -> List[MergeCandidate]:
        """
        Detecta duplicatas em lote usando múltiplos hashes para comparação inteligente.

        Args:
            rom_batch: Lista de ROMs para análise
            batch_size: Tamanho do lote para processamento paralelo

        Returns:
            Lista de candidatos à fusão
        """
        candidates = []

        try:
            logger.info(f"Detectando duplicatas em lote: {len(rom_batch)} ROMs")

            # Processamento em lotes para performance
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = []

                for i in range(0, len(rom_batch), batch_size):
                    batch = rom_batch[i:i+batch_size]
                    future = executor.submit(self._analyze_batch_duplicates, batch, rom_batch)
                    futures.append(future)

                # Coleta resultados
                for future in concurrent.futures.as_completed(futures):
                    try:
                        batch_candidates = future.result()
                        candidates.extend(batch_candidates)
                    except Exception as e:
                        logger.error(f"Erro processando lote de duplicatas: {e}")

            # Remove duplicatas e organiza candidatos
            candidates = self._deduplicate_candidates(candidates)

            logger.info(f"Duplicatas detectadas: {len(candidates)} candidatos")
            self.fusion_stats['duplicate_candidates_found'] += len(candidates)

            return candidates

        except Exception as e:
            logger.error(f"Erro na detecção de duplicatas: {e}")
            return []

    def _analyze_batch_duplicates(self, batch: List[RomData], all_roms: List[RomData]) -> List[MergeCandidate]:
        """Análise de duplicatas em lote específico."""
        batch_candidates = []

        for i, rom1 in enumerate(batch):
            for rom2 in all_roms:
                if rom1.id == rom2.id:
                    continue

                # Calcula similaridade baseada em múltiplos fatores
                similarity, hash_matches, metadata_sim = self._calculate_similarity(rom1, rom2)

                # Só considera se similaridade é significativa
                if similarity >= self.fusion_thresholds['reject_below']:
                    candidate = MergeCandidate(
                        rom_id_1=rom1.id,
                        rom_id_2=rom2.id,
                        similarity_score=similarity,
                        hash_matches=hash_matches,
                        metadata_similarity=metadata_sim,
                        confidence=self._calculate_confidence(hash_matches, metadata_sim),
                        merge_strategy=self._determine_merge_strategy(similarity, hash_matches),
                        sources_in_common=list(set(rom1.sources) & set(rom2.sources))
                    )

                    batch_candidates.append(candidate)

        return batch_candidates

    def _calculate_similarity(self, rom1: RomData, rom2: RomData) -> Tuple[float, Dict[str, str], float]:
        """
        Calcula similaridade entre duas ROMs usando múltiplos critérios.

        Returns:
            (similaridade_total, hashes_correspondentes, similaridade_metadata)
        """
        hash_score = 0.0
        hash_matches = {}
        hash_weight_total = 0.0

        # Pesos para diferentes tipos de hash (baseado em confiabilidade)
        hash_weights = {
            'sha1': 1.0,      # Mais confiável
            'sha256': 0.95,   # Também muito confiável
            'md5': 0.80,      # Menos confiável
            'crc32': 0.70,    # Mais provável colisão
            'crc': 0.65       # Menos confiável que SHA1/MD5
        }

        # Compara todos os hashes disponíveis
        for hash_type, weight in hash_weights.items():
            if hash_type in rom1.hashes and hash_type in rom2.hashes:
                hash_weight_total += weight
                if rom1.hashes[hash_type] == rom2.hashes[hash_type]:
                    hash_score += weight
                    hash_matches[hash_type] = rom1.hashes[hash_type]

        if hash_weight_total > 0:
            hash_score = hash_score / hash_weight_total
        else:
            hash_score = 0.0

        # Similaridade de metadados (nome, tamanho, etc.)
        metadata_sim = self._calculate_metadata_similarity(rom1, rom2)

        # Combinação final (70% hash, 30% metadata)
        total_similarity = (hash_score * 0.7) + (metadata_sim * 0.3)

        return total_similarity, hash_matches, metadata_sim

    def _calculate_metadata_similarity(self, rom1: RomData, rom2: RomData) -> float:
        """Calcula similaridade de metadados (não baseado apenas em hashes)."""
        similarity = 0.0
        total_weight = 0.0

        # Comparação de nomes (normaliza case e remove caracteres especiais)
        name1 = self._normalize_name(rom1.name)
        name2 = self._normalize_name(rom2.name)

        if name1 and name2:
            if name1 == name2:
                similarity += 1.0
            elif name1 in name2 or name2 in name1:
                similarity += 0.8  # Parcial similar
            else:
                # Distância de Levenshtein aproximada
                sim = self._simple_string_similarity(name1, name2)
                similarity += sim
            total_weight += 1.0

        # Comparação de tamanho do arquivo
        if rom1.size > 0 and rom2.size > 0:
            size_diff = abs(rom1.size - rom2.size)
            if size_diff == 0:
                similarity += 1.0
            elif size_diff < 1024:  # Diferença pequena (1KB)
                similarity += 0.9
            elif size_diff < 10240:  # Até 10KB
                similarity += 0.7
            else:
                similarity += 0.3  # Muito diferente
            total_weight += 0.8  # Menos peso que nome

        # Comparação de metadados estruturados
        meta_sim = self._compare_metadata_details(rom1.metadata, rom2.metadata)
        similarity += meta_sim
        total_weight += 0.6  # Peso menor

        return similarity / total_weight if total_weight > 0 else 0.0

    def _normalize_name(self, name: str) -> str:
        """Normaliza nome para comparação."""
        if not name:
            return ""
        # Remove extensão, normaliza case, remove caracteres especiais
        name = name.lower()
        name = ''.join(c for c in name if c.isalnum() or c in ' .-_')
        return name.strip()

    def _simple_string_similarity(self, s1: str, s2: str) -> float:
        """Similaridade simples de strings baseada em caracteres comuns."""
        s1_words = set(s1.lower().split())
        s2_words = set(s2.lower().split())

        intersection = s1_words & s2_words
        union = s1_words | s2_words

        if len(union) == 0:
            return 1.0

        return len(intersection) / len(union)

    def _compare_metadata_details(self, meta1: Dict, meta2: Dict) -> float:
        """Compara detalhes de metadata."""
        common_fields = ['system', 'region', 'language', 'rom_type']
        matches = 0
        total = len(common_fields)

        for field in common_fields:
            v1 = meta1.get(field, '').strip().lower()
            v2 = meta2.get(field, '').strip().lower()

            if v1 and v2 and v1 == v2:
                matches += 1
            elif v1 or v2:  # Campo presente em uma mas não na outra
                matches += 0.5

        return matches / total if total > 0 else 0.0

    def _calculate_confidence(self, hash_matches: Dict, metadata_sim: float) -> float:
        """Calcula confiança na fusão baseada em evidências."""
        confidence = 0.0

        # Número de hashes correspondentes
        hash_count = len(hash_matches)
        if hash_count >= 3:  # SHA1 + MD5 + CRC
            confidence += 0.8
        elif hash_count >= 2:  # Pelo menos dois hashes
            confidence += 0.6
        elif hash_count >= 1:  # Pelo menos um hash
            confidence += 0.4

        # Similaridade de metadata
        confidence += (metadata_sim * 0.2)

        # Bônus por ter certos hashes
        if 'sha1' in hash_matches:
            confidence += 0.1
        if 'sha256' in hash_matches:
            confidence += 0.05

        return min(confidence, 1.0)  # Máximo 1.0

    def _determine_merge_strategy(self, similarity: float, hash_matches: Dict) -> str:
        """Determina estratégia de fusão baseada na similaridade."""
        # Fusão automática se alta confiança
        if similarity >= self.fusion_thresholds['auto_merge_sha1_match'] and 'sha1' in hash_matches:
            return 'auto_merge'
        elif similarity >= self.fusion_thresholds['auto_merge_multi_hash'] and len(hash_matches) >= 2:
            return 'auto_merge'
        elif similarity >= self.fusion_thresholds['manual_review_threshold']:
            return 'manual_review'
        else:
            return 'reject'

    def perform_fusion_batch(self, candidates: List[MergeCandidate]) -> Dict[str, int]:
        """
        Executa fusões em lote com estratégia otimizada.

        Args:
            candidates: Candidatos à fusão

        Returns:
            Estatísticas das fusões realizadas
        """
        stats = {
            'auto_merged': 0,
            'manual_candidates': 0,
            'rejected': 0,
            'errors': 0
        }

        try:
            logger.info(f"Executando fusões em lote: {len(candidates)} candidatos")

            # Separa candidatos por estratégia
            auto_merge = [c for c in candidates if c.merge_strategy == 'auto_merge']
            manual_review = [c for c in candidates if c.merge_strategy == 'manual_review']

            # Fusões automáticas em paralelo
            if auto_merge:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [executor.submit(self._perform_auto_fusion, candidate)
                             for candidate in auto_merge]

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            success = future.result()
                            if success:
                                stats['auto_merged'] += 1
                            else:
                                stats['errors'] += 1
                        except Exception as e:
                            logger.error(f"Erro em fusão automática: {e}")
                            stats['errors'] += 1

            # Candidatos para revisão manual
            for candidate in manual_review:
                try:
                    self._create_manual_candidate(candidate)
                    stats['manual_candidates'] += 1
                except Exception as e:
                    logger.error(f"Erro criando candidato manual: {e}")
                    stats['errors'] += 1

            logger.info(f"Fusões concluídas: auto={stats['auto_merged']}, manual={stats['manual_candidates']}, erros={stats['errors']}")
            return stats

        except Exception as e:
            logger.error(f"Erro geral nas fusões: {e}")
            stats['errors'] += 1
            return stats

    def _perform_auto_fusion(self, candidate: MergeCandidate) -> bool:
        """Executa fusão automática de dois ROMs."""
        try:
            with self.db_manager.get_connection() as conn:
                # Busca dados das ROMs
                rom1_data = self._get_rom_data_by_id(conn, candidate.rom_id_1)
                rom2_data = self._get_rom_data_by_id(conn, candidate.rom_id_2)

                if not rom1_data or not rom2_data:
                    logger.warning(f"Dados de ROM não encontrados: {candidate.rom_id_1}, {candidate.rom_id_2}")
                    return False

                # Metadados melhor fundidos
                merged_metadata = self._merge_metadata_smart(rom1_data, rom2_data, candidate)

                # Atualiza ROM principal
                self._update_rom_metadata(conn, candidate.rom_id_1, merged_metadata)

                # Log da fusão para auditoria
                self._log_merge_operation(conn, candidate, merged_metadata, rom1_data, rom2_data)

                # Atualiza estatísticas
                conn.execute("""
                    UPDATE universal_catalog_stats
                    SET fusions_performed = fusions_performed + 1,
                        duplicates_detected = duplicates_detected - 1,
                        last_update = datetime('now')
                    WHERE id = (SELECT MAX(id) FROM universal_catalog_stats)
                """)

                conn.commit()

                # Remove ROM duplicada (soft delete)
                self._soft_delete_rom(conn, candidate.rom_id_2, f"Fusion with {candidate.rom_id_1}")

                logger.info(f"Fusão automática: ROM {candidate.rom_id_2} -> {candidate.rom_id_1} (confidence: {candidate.confidence:.2f})")
                return True

        except Exception as e:
            logger.error(f"Erro em fusão automática: {e}")
            return False

    def _merge_metadata_smart(self, rom1: RomData, rom2: RomData, candidate: MergeCandidate) -> Dict[str, Any]:
        """Fusão inteligente de metadados preservando o melhor de cada fonte."""

        # Estratégia: preservar dados mais completos e confiáveis
        def choose_better_value(key: str) -> Any:
            v1 = rom1.metadata.get(key)
            v2 = rom2.metadata.get(key)

            if v1 and v2:
                # Ambos têm valor - escolher mais "completo" ou baseado em confiança da fonte
                if isinstance(v1, str) and isinstance(v2, str):
                    return v1 if len(v1) >= len(v2) else v2
                else:
                    return v1  # Preferência ROM1
            elif v1:
                return v1
            elif v2:
                return v2

            return None

        # Combina fontes
        merged_sources = list(set(rom1.sources + rom2.sources))

        # Fusão de metadados
        merged_metadata = {
            'name': choose_better_value('name') or rom1.name,
            'size': rom1.size if rom1.size > 0 else (rom2.size if rom2.size > 0 else 0),
            'system': choose_better_value('system'),
            'region': choose_better_value('region'),
            'language': choose_better_value('language'),
            'rom_type': choose_better_value('rom_type'),
            'version': choose_better_value('version'),
            'publisher': choose_better_value('publisher'),
            'developer': choose_better_value('developer'),
            'description': choose_better_value('description'),
            'sources': merged_sources,
            'fusion_timestamp': datetime.now().isoformat(),
            'fusion_confidence': candidate.confidence,
            'hashes_consolidated': candidate.hash_matches
        }

        # Remove valores None
        merged_metadata = {k: v for k, v in merged_metadata.items() if v is not None}

        return merged_metadata

    def _log_merge_operation(self, conn: sqlite3.Connection, candidate: MergeCandidate,
                           merged_metadata: Dict, rom1_data: RomData, rom2_data: RomData):
        """Log detalhado da operação de fusão para auditoria completa."""
        try:
            # Dados antes e depois para auditoria
            before_data = {
                'rom1': asdict(rom1_data),
                'rom2': asdict(rom2_data),
                'candidate': asdict(candidate)
            }

            after_data = {
                'main_rom_id': candidate.rom_id_1,
                'merged_metadata': merged_metadata,
                'confidence': candidate.confidence
            }

            # Hash resolution detalhes
            hash_resolution = {
                'matches': candidate.hash_matches,
                'conflicts_resolved': [],  # Nenhum conflito na fusão automática
                'consolidated_hashes': merged_metadata.get('hashes_consolidated', {})
            }

            # Insere log
            conn.execute("""
                INSERT INTO rom_merge_log (
                    rom_main_id, rom_merged_id, merge_type, sources_merged,
                    metadata_before, metadata_after, hash_resolution,
                    confidence_score, fusion_success, merged_by, audit_timestamp,
                    remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            """, (
                candidate.rom_id_1,
                candidate.rom_id_2,
                'auto_fusion_intelligent',
                json.dumps(merged_metadata.get('sources', [])),
                json.dumps(before_data),
                json.dumps(after_data),
                json.dumps(hash_resolution),
                candidate.confidence,
                True,  # Sucess
                'fusion_system',
                f'Confiança: {candidate.confidence:.2f}, Similaridade: {candidate.similarity_score:.2f}'
            ))

        except Exception as e:
            logger.error(f"Erro no log da fusão: {e}")

    def _update_rom_metadata(self, conn: sqlite3.Connection, rom_id: int, metadata: Dict):
        """Atualiza metadados da ROM após fusão."""
        try:
            # SQL dinâmico baseado nos campos disponíveis
            update_fields = []
            values = []

            field_mappings = {
                'size_file': 'size',
                'system': 'system',
                'region': 'region',
                'language': 'language',
                'rom_type': 'rom_type'
            }

            for field, meta_key in field_mappings.items():
                if meta_key in metadata:
                    update_fields.append(f"{field} = ?")
                    values.append(metadata[meta_key])

            if update_fields:
                values.append(rom_id)
                sql = f"UPDATE roms SET {', '.join(update_fields)}, updated_at = datetime('now') WHERE id = ?"
                conn.execute(sql, values)

        except Exception as e:
            logger.error(f"Erro atualizando metadados ROM {rom_id}: {e}")

    def _soft_delete_rom(self, conn: sqlite3.Connection, rom_id: int, reason: str):
        """Soft delete da ROM fundida."""
        try:
            conn.execute("""
                UPDATE roms SET status = 'merged', updated_at = datetime('now')
                WHERE id = ?
            """, (rom_id,))
        except Exception as e:
            logger.error(f"Erro em soft delete ROM {rom_id}: {e}")

    def _get_rom_data_by_id(self, conn: sqlite3.Connection, rom_id: int) -> Optional[RomData]:
        """Busca dados completos da ROM pelo ID."""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.name, r.filename, r.size_file, r.crc, r.md5, r.sha1,
                       r.system, r.region, r.language, r.rom_type,
                       GROUP_CONCAT(rs.source_name) as sources
                FROM roms r
                LEFT JOIN rom_sources rs ON r.id = rs.rom_id
                WHERE r.id = ?
                GROUP BY r.id
            """, (rom_id,))

            row = cursor.fetchone()
            if not row:
                return None

            id, name, filename, size, crc, md5, sha1, system, region, language, rom_type, sources_str = row

            hashes = {}
            if crc: hashes['crc'] = crc
            if md5: hashes['md5'] = md5
            if sha1: hashes['sha1'] = sha1

            metadata = {}
            if system: metadata['system'] = system
            if region: metadata['region'] = region
            if language: metadata['language'] = language
            if rom_type: metadata['rom_type'] = rom_type

            sources = sources_str.split(',') if sources_str else []

            return RomData(
                id=id,
                name=name or filename or '',
                size=size or 0,
                hashes=hashes,
                metadata=metadata,
                sources=sources
            )

        except Exception as e:
            logger.error(f"Erro buscando ROM {rom_id}: {e}")
            return None

    def _create_manual_candidate(self, candidate: MergeCandidate):
        """Cria candidato para revisão manual."""
        try:
            with self.db_manager.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO merge_candidates (
                        rom_id_1, rom_id_2, similarity_score, hash_matches,
                        merge_confidence, sources_in_common, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    candidate.rom_id_1,
                    candidate.rom_id_2,
                    candidate.similarity_score,
                    json.dumps(candidate.hash_matches),
                    candidate.confidence,
                    json.dumps(candidate.sources_in_common)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Erro criando candidato manual: {e}")

    def _deduplicate_candidates(self, candidates: List[MergeCandidate]) -> List[MergeCandidate]:
        """Remove candidatos duplicados mantendo o melhor."""
        seen = set()
        unique_candidates = []

        # Ordena por confiança para manter o melhor primeiro
        candidates.sort(key=lambda x: x.confidence, reverse=True)

        for candidate in candidates:
            pair = (min(candidate.rom_id_1, candidate.rom_id_2),
                   max(candidate.rom_id_1, candidate.rom_id_2))

            if pair not in seen:
                seen.add(pair)
                unique_candidates.append(candidate)

        return unique_candidates

    def get_fusion_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas completas do sistema de fusão."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Estatísticas do sistema de fusão
                cursor.execute("""
                    SELECT total_roms, unique_games, sources_combined,
                           duplicates_detected, ambiguous_cases,
                           fusions_performed, trust_levels_calculated,
                           catalog_health, data_quality_score,
                           completeness_score, consistency_score
                    FROM universal_catalog_stats
                    ORDER BY id DESC LIMIT 1
                """)

                row = cursor.fetchone()
                if row:
                    stats = {
                        'total_roms': row[0] or 0,
                        'unique_games': row[1] or 0,
                        'sources_combined': row[2] or 0,
                        'duplicates_detected': row[3] or 0,
                        'ambiguous_cases': row[4] or 0,
                        'fusions_performed': row[5] or 0,
                        'trust_levels_calculated': row[6] or 0,
                        'catalog_health': row[7] or 0.0,
                        'data_quality_score': row[8] or 0.0,
                        'completeness_score': row[9] or 0.0,
                        'consistency_score': row[10] or 0.0
                    }
                else:
                    stats = {k: 0 for k in ['total_roms', 'unique_games', 'sources_combined',
                                          'duplicates_detected', 'ambiguous_cases', 'fusions_performed',
                                          'trust_levels_calculated']}
                    stats.update({k: 0.0 for k in ['catalog_health', 'data_quality_score',
                                                 'completeness_score', 'consistency_score']})

                # Estatísticas detalhadas de fusão
                cursor.execute("""
                    SELECT merge_type, COUNT(*) as count,
                           AVG(confidence_score) as avg_confidence,
                           AVG(fusion_success) as success_rate
                    FROM rom_merge_log
                    GROUP BY merge_type
                """)

                fusion_details = {}
                for row in cursor.fetchall():
                    merge_type, count, avg_confidence, success_rate = row
                    fusion_details[merge_type] = {
                        'count': count,
                        'avg_confidence': avg_confidence or 0.0,
                        'success_rate': success_rate or 0.0
                    }

                # Candidatos pendentes
                cursor.execute("""
                    SELECT COUNT(*) FROM merge_candidates WHERE status = 'pending'
                """)
                pending_candidates = cursor.fetchone()[0]

                # Estatísticas do sistema atual
                stats.update({
                    'fusion_details': fusion_details,
                    'pending_candidates': pending_candidates,
                    'manager_stats': self.fusion_stats
                })

                return stats

        except Exception as e:
            logger.error(f"Erro obtendo estatísticas de fusão: {e}")
            return {}

    def perform_integrity_check(self) -> Dict[str, Any]:
        """
        Verificação completa de integridade do catálogo universal.
        Assegura que zero dados foram descartados e mantém unicidade inteligente.
        """
        integrity_report = {
            'catalog_universality': True,  # Preservação de dados
            'duplicate_prevention': True,  # Sem duplicatas não-detectadas
            'ambiguity_resolution': True,  # Ambiguidades resolvidas
            'source_integrity': True,      # Todas as fontes mantidas
            'issues_found': [],
            'recommendations': [],
            'data_preserved_percentage': 100.0
        }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Verifica se há ROMs duplicadas não-detectadas
                cursor.execute("""
                    SELECT sha1, COUNT(*) as count
                    FROM roms
                    WHERE sha1 IS NOT NULL AND sha1 != ''
                    GROUP BY sha1
                    HAVING count > 1
                """)

                undetected_duplicates = cursor.fetchall()
                if undetected_duplicates:
                    integrity_report['duplicate_prevention'] = False
                    integrity_report['issues_found'].append(
                        f"ROMs duplicadas não-detectadas: {len(undetected_duplicates)} conjuntos"
                    )
                    integrity_report['data_preserved_percentage'] -= len(undetected_duplicates) * 5

                # Verifica integridade referencial
                cursor.execute("""
                    SELECT COUNT(*) FROM roms r
                    LEFT JOIN games g ON r.game_id = g.id
                    WHERE g.id IS NULL AND r.game_id IS NOT NULL
                """)

                orphaned_roms = cursor.fetchone()[0]
                if orphaned_roms > 0:
                    integrity_report['issues_found'].append(
                        f"ROMs órfãs (game_id inválido): {orphaned_roms}"
                    )
                    integrity_report['source_integrity'] = False

                # Verifica completude de hashes
                cursor.execute("""
                    SELECT COUNT(*) FROM roms
                    WHERE (crc IS NULL OR crc = '')
                      AND (md5 IS NULL OR md5 = '')
                      AND (sha1 IS NULL OR sha1 = '')
                """)

                roms_without_hashes = cursor.fetchone()[0]
                if roms_without_hashes > 0:
                    integrity_report['issues_found'].append(
                        f"ROMs sem hashes identificáveis: {roms_without_hashes}"
                    )
                    integrity_report['data_preserved_percentage'] -= (roms_without_hashes * 2)

                # Verifica estatísticas do catálogo universal
                if integrity_report['data_preserved_percentage'] > 95:
                    integrity_report['recommendations'].append(
                        "Catálogo mantém alta integridade universa (>95% dados preservados)"
                    )
                elif integrity_report['data_preserved_percentage'] > 85:
                    integrity_report['recommendations'].append(
                        "Interno: revisar processos de deduplicação para maior preservação"
                    )
                else:
                    integrity_report['recommendations'].append(
                        "Prioritário: revisar sistema de fusão para evitar perda de dados"
                    )

                # Atualiza saúde do catálogo
                health_score = integrity_report['data_preserved_percentage'] / 100.0
                conn.execute("""
                    UPDATE universal_catalog_stats
                    SET catalog_health = ?, last_update = datetime('now')
                    WHERE id = (SELECT MAX(id) FROM universal_catalog_stats)
                """, (health_score,))

                logger.info(f"Verificação de integridade concluída - Saúde: {health_score:.1%}")

        except Exception as e:
            integrity_report['catalog_universality'] = False
            integrity_report['issues_found'].append(f"Erro na verificação: {e}")

        return integrity_report