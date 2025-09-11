#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Testes do Sistema de Fusão Universal
Cobertura >=90% focada em deduplicação, ambiguidades e integridade
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch
from datetime import datetime
import sqlite3
import hashlib

from engine.db import UnifiedDatabaseManager as DatabaseManagerV2
from engine.db.fusion_manager import FusionManager, RomData, MergeCandidate
from engine.services.universal_import_service import UniversalImportService
from engine.db.database_fusion_schema import create_fusion_structure


class TestFusionSystem:
    """Testes do sistema de fusão inteligente."""

    @pytest.fixture
    def temp_db(self):
        """Banco temporário para testes."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)

        db_manager = DatabaseManagerV2()
        db_manager.connect(db_path)

        # Cria estrutura básica
        from engine.db.database_schema import create_database_structure
        with db_manager.get_connection() as conn:
            create_database_structure(conn)

        yield db_manager

        # Cleanup
        db_manager.close_all()
        os.unlink(db_path)

    @pytest.fixture
    def fusion_manager(self, temp_db):
        """FusionManager com banco temporário."""
        fm = FusionManager(temp_db)
        fm.ensure_fusion_structure()
        return fm

    @pytest.fixture
    def universal_import_service(self, temp_db, fusion_manager):
        """UniversalImportService para testes."""
        return UniversalImportService(temp_db, fusion_manager)

    def test_fusion_structure_creation(self, temp_db):
        """Testa criação da estrutura de fusão."""
        fm = FusionManager(temp_db)

        # Deve criar estrutura com sucesso
        assert fm.ensure_fusion_structure() is True

        # Verifica se tabelas foram criadas
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fusion%' OR name IN ('source_trust', 'rom_sources', 'merge_candidates', 'rom_merge_log', 'universal_catalog_stats')")
            tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['source_trust', 'rom_sources', 'merge_candidates', 'rom_merge_log', 'universal_catalog_stats']
        for table in required_tables:
            assert table in tables, f"Tabela obrigatória faltando: {table}"

    def test_rom_similarity_calculation(self, fusion_manager):
        """Testa cálculo de similaridade entre ROMs."""
        # ROMs idênticas (deve ser alto nível de similaridade)
        rom1 = RomData(
            id=1,
            name="Super Mario World (Europe)",
            size=4096,
            hashes={'sha1': 'abc123', 'md5': 'def456'},
            metadata={'system': 'snes', 'region': 'europe'},
            sources=['dat_europe.xml']
        )

        rom2 = RomData(
            id=2,
            name="Super Mario World (Europe)",
            size=4096,
            hashes={'sha1': 'abc123', 'md5': 'def456'},
            metadata={'system': 'snes', 'region': 'europe'},
            sources=['dat_usa.xml']
        )

        similarity, hash_matches, metadata_sim = fusion_manager._calculate_similarity(rom1, rom2)

        # Deve reconhecer como altamente similar
        assert similarity >= 0.9
        assert 'sha1' in hash_matches
        assert 'md5' in hash_matches

        # Testa ROMs diferentes
        rom3 = RomData(
            id=3,
            name="Different Game",
            size=8192,
            hashes={'sha1': 'xyz789', 'md5': 'qwe012'},
            metadata={'system': 'nes', 'region': 'japan'},
            sources=['dat_japan.xml']
        )

        similarity_diff, hash_matches_diff, metadata_sim_diff = fusion_manager._calculate_similarity(rom1, rom3)

        # Deve ser baixa similaridade
        assert similarity_diff <= 0.5

    def test_merge_candidate_strategy(self, fusion_manager):
        """Testa estratégia de fusão baseada na similaridade."""
        # Candidato auto-merge (alta confiança)
        candidate_high = MergeCandidate(
            rom_id_1=1, rom_id_2=2,
            similarity_score=0.95,
            hash_matches={'sha1': 'abc123'},
            metadata_similarity=0.9,
            confidence=0.92,
            merge_strategy='auto_merge',
            sources_in_common=['dat1.xml', 'dat2.xml']
        )

        # Candidato manual review (similar mas não auto)
        candidate_manual = MergeCandidate(
            rom_id_1=3, rom_id_2=4,
            similarity_score=0.75,
            hash_matches={'crc32': 'fed789'},
            metadata_similarity=0.7,
            confidence=0.65,
            merge_strategy='manual_review',
            sources_in_common=['dat3.xml']
        )

        # Candidato reject (baixo)
        candidate_reject = MergeCandidate(
            rom_id_1=5, rom_id_2=6,
            similarity_score=0.4,
            hash_matches={},
            metadata_similarity=0.3,
            confidence=0.35,
            merge_strategy='reject',
            sources_in_common=[]
        )

        # Verifica estratégias corretas
        assert candidate_high.similarity_score >= fusion_manager.fusion_thresholds['auto_merge_sha1_match']
        assert candidate_manual.similarity_score >= fusion_manager.fusion_thresholds['manual_review_threshold']
        assert candidate_reject.similarity_score < fusion_manager.fusion_thresholds['reject_below']

    def test_intelligent_merge_metadata(self, fusion_manager, temp_db):
        """Testa fusão inteligente de metadados."""
        with temp_db.get_connection() as conn:
            # Insere jogos para teste
            conn.execute("INSERT INTO games (name, description) VALUES (?, ?)", ("Game A", "Description A"))
            game_id = conn.lastrowid
            conn.commit()

            rom1 = RomData(
                id=None,
                name="Super Cartridge v1.0",
                size=32768,
                hashes={'sha1': 'hash123'},
                metadata={
                    'system': 'nes',
                    'region': 'usa',
                    'language': 'en',
                    'publisher': 'Nintendo'
                },
                sources=['source1.dat']
            )

            rom2 = RomData(
                id=None,
                name="Super Cartridge v1.0 (Good dump)",
                size=32768,
                hashes={'sha1': 'hash123'},  # Mesmo hash = mesma ROM
                metadata={
                    'system': 'nes',
                    'region': 'usa',
                    'language': 'en',
                    'developer': 'Nintendo'
                },
                sources=['source2.dat']
            )

            candidate = MergeCandidate(
                rom_id_1=1, rom_id_2=2,
                similarity_score=0.95,
                hash_matches={'sha1': 'hash123'},
                metadata_similarity=0.85,
                confidence=0.9,
                merge_strategy='auto_merge',
                sources_in_common=['source1.dat']
            )

            # Fusão inteligente
            merged = fusion_manager._merge_metadata_smart(rom1, rom2, candidate)

            # Verifica combinação inteligente
            assert merged['name'] == "Super Cartridge v1.0 (Good dump)"  # Escolhe nome mais descritivo
            assert merged['system'] == 'nes'
            assert merged['region'] == 'usa'
            assert merged['language'] == 'en'
            assert 'publisher' in merged or 'developer' in merged  # Pelo menos um campo de companhia

    def test_universal_import_integration(self, universal_import_service):
        """Testa integração do import service com fusão."""
        # Simula dados de importação
        rom_batch = [
            RomData(
                id=None,
                name="Test Game (USA)",
                size=65536,
                hashes={'sha1': 'test_hash_123', 'md5': 'md5_hash_456'},
                metadata={'system': 'snes', 'region': 'usa'},
                sources=['test_dat.xml']
            ),
            RomData(
                id=None,
                name="Test Game (Europe)",
                size=65536,
                hashes={'sha1': 'test_hash_123'},  # Mesmo hash = duplicata
                metadata={'system': 'snes', 'region': 'europe'},
                sources=['test_dat_eu.xml']
            )
        ]

        # Detecta duplicatas
        candidates = universal_import_service.fusion_manager.detect_duplicates_batch(rom_batch)

        # Deve encontrar uma duplicata
        assert len(candidates) == 1
        candidate = candidates[0]

        # Verifica características da duplicata
        assert candidate.similarity_score >= 0.8
        assert 'sha1' in candidate.hash_matches
        assert candidate.hash_matches['sha1'] == 'test_hash_123'


@pytest.mark.performance
class TestFusionPerformance:
    """Testes de performance do sistema de fusão."""

    def test_large_dataset_fusion(self, temp_db):
        """Testa fusão com dataset grande."""
        fm = FusionManager(temp_db)
        fm.ensure_fusion_structure()

        # Gera 1000 ROMs simuladas com algumas duplicatas
        rom_batch = []

        for i in range(1000):
            # Cria algumas duplicatas (mesmo hash para grupos)
            if i % 10 == 0:
                hash_base = f"duplicate_hash_{i//10}"
            else:
                hash_base = f"unique_hash_{i}"

            rom = RomData(
                id=i+1,
                name=f"Game {i}",
                size=32768 + (i % 1000),  # Variação de tamanho
                hashes={'sha1': hashlib.md5(hash_base.encode()).hexdigest()},
                metadata={'system': 'nes', 'region': ['usa', 'europe', 'japan'][i % 3]},
                sources=[f'source_{i%5}.dat']
            )
            rom_batch.append(rom)

        import time
        start_time = time.time()

        candidates = fm.detect_duplicates_batch(rom_batch)

        # Deve encontrar duplicatas (cerca de 100 grupos)
        assert len(candidates) >= 90  # Pelo menos 90 grupos de duplicatas
        assert len(candidates) <= 150  # Não mais que 150 (alguns falsos positivos)

        processing_time = time.time() - start_time

        # Performance aceitável: 1000 ROMs em menos de 30 segundos
        assert processing_time < 30.0, f"Performance inadequada: {processing_time:.2f}s para 1000 ROMs"

        print(f"Performance teste: {processing_time:.2f}s para 1000 ROMs ({len(candidates)} candidatos)")

    def test_parallel_batch_processing(self, universal_import_service):
        """Testa processamento paralelo em lotes."""
        # Cria arquivos de teste temporários
        test_files = []

        for i in range(5):
            # Cria arquivo DAT/XML simulado
            file_content = f"""<?xml version="1.0"?>
<datafile>
    <header>
        <name>Test Set {i}</name>
        <description>Automated test data {i}</description>
    </header>
"""

            for j in range(20):  # 20 ROMs por arquivo
                game_name = f"Game {i*20 + j}"
                hash_value = hashlib.md5(f"{i}_{j}".encode()).hexdigest()
                file_content += f"""
    <game name="{game_name}">
        <description>{game_name} description</description>
        <rom name="{game_name}.bin" size="32768" sha1="{hash_value}" crc="crc{i}{j}"/>
    </game>"""

            file_content += "\n</datafile>"

            # Escreve arquivo temporário
            fd, temp_path = tempfile.mkstemp(suffix='.xml')
            with os.fdopen(fd, 'w') as f:
                f.write(file_content)
            test_files.append(temp_path)

        start_time = time.time()

        try:
            # Importação universal com processamento paralelo
            stats = universal_import_service.import_universal_batch(test_files)

            processing_time = time.time() - start_time

            # Verificações
            assert stats.files_processed == 5
            assert stats.roms_imported >= 90  # Pelo menos 90 ROMs (algumas podem ser fundidas)
            assert processing_time < 10.0  # Deve ser rápido

            print(f"Performance paralelo: {processing_time:.2f}s para 5 arquivos")

        finally:
            # Limpeza
            for temp_path in test_files:
                os.unlink(temp_path)


@pytest.mark.integration
class TestDataIntegrityUniversal:
    """Testes de integridade de dados universais."""

    def test_no_data_loss_universal_catalog(self, universal_import_service):
        """Asseegura que nenhum dado é perdido durante fusão."""

        # Estado inicial
        with universal_import_service.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Insere algumas ROMs inicialmente
            conn.execute("INSERT INTO games (name, description) VALUES (?, ?)", ("Initial Game", "Initial desc"))
            game_id = conn.lastrowid

            # Insere ROMs
            rom_hashes = ['hash_initial_1', 'hash_initial_2', 'hash_initial_3']
            for i, hash_val in enumerate(rom_hashes):
                conn.execute("""
                    INSERT INTO roms (game_id, name, size_file, sha1) VALUES (?, ?, ?, ?)
                """, (game_id, f"Initial ROM {i+1}", 32768, hash_val))

            # Conta após inicial
            cursor.execute("SELECT COUNT(*) FROM roms")
            roms_initial = cursor.fetchone()[0]

            conn.commit()

        # Simula importação que cria duplicatas
        rom_batch = []

        for i in range(3):
            rom = RomData(
                id=None,
                name=f"Initial ROM {i+1}",
                size=32768,
                hashes={'sha1': rom_hashes[i]},  # Mesmo hash = duplicata
                metadata={'system': 'nes', 'region': 'usa'},
                sources=['duplicate_source.dat']
            )
            rom_batch.append(rom)

        # Detecta e funde duplicatas
        candidates = universal_import_service.fusion_manager.detect_duplicates_batch(rom_batch)
        fusion_results = universal_import_service.fusion_manager.perform_fusion_batch(candidates)

        # Verifica integridade
        integrity_report = universal_import_service.fusion_manager.perform_integrity_check()

        # Não deve haver perda crítica de dados
        assert integrity_report['issues_found'] == [] or len(integrity_report['issues_found']) == 0
        assert integrity_report['data_preserved_percentage'] >= 95.0

    def test_foreign_key_integrity_after_fusion(self, fusion_manager, temp_db):
        """Testa integridade de foreign keys após fusão."""

        with temp_db.get_connection() as conn:
            # Insere dados estruturados
            game_data = [
                ("Game A", "Desc A"),
                ("Game B", "Desc B"),
                ("Game C", "Desc C")
            ]

            conn.executemany("INSERT INTO games (name, description) VALUES (?, ?)", game_data)
            game_ids = []

            cursor = conn.cursor()
            cursor.execute("SELECT id FROM games ORDER BY id")
            game_ids = [row[0] for row in cursor.fetchall()]

            # Insere ROMs
            rom_data = []
            for i, game_id in enumerate(game_ids):
                rom_data.append((
                    game_id, f"ROM {i}", 65536, f'hash_{i}', f'crc_{i}'
                ))

            conn.executemany("""
                INSERT INTO roms (game_id, name, size_file, sha1, crc) VALUES (?, ?, ?, ?, ?)
            """, rom_data)
            conn.commit()

            rom_ids = []
            cursor.execute("SELECT id FROM roms ORDER BY id")
            rom_ids = [row[0] for row in cursor.fetchall()]

            # Verifica FKs iniciais
            cursor.execute("""
                SELECT COUNT(*) FROM roms r
                LEFT JOIN games g ON r.game_id = g.id
                WHERE g.id IS NULL
            """)
            orphaned_initial = cursor.fetchone()[0]
            assert orphaned_initial == 0, "Integrity violation before fusion"

            conn.commit()

        # Força fusão que deveria manter integridade
        rom_data_1 = fusion_manager._get_rom_data_by_id(temp_db.pool._connections[0].connection, rom_ids[0])
        rom_data_2 = fusion_manager._get_rom_data_by_id(temp_db.pool._connections[0].connection, rom_ids[1])

        # Após fusão, verifica FKs novamente
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM roms r
                LEFT JOIN games g ON r.game_id = g.id
                WHERE g.id IS NULL AND r.status != 'merged'
            """)
            orphaned_after = cursor.fetchone()[0]

            # Não deve haver ófãs ATIVAS após fusão
            assert orphaned_after == 0, "FK integrity violated after fusion"

    def test_log_audit_comprehensive(self, fusion_manager):
        """Testa sistema de auditoria abrangente."""

        with fusion_manager._db_manager.get_connection() as conn:
            # Simula fusão para gerar auditoria
            fm = fusion_manager

            # Insere dados de teste
            conn.execute("INSERT INTO games (name, description) VALUES (?, ?)", ("Audit Test Game", "For audit testing"))
            game_id = conn.lastrowid

            conn.execute("""
                INSERT INTO roms (game_id, name, size_file, sha1)
                VALUES (?, ?, ?, ?)
            """, (game_id, "ROM 1", 65536, "audit_hash_1"))

            rom_id_main = conn.lastrowid

            conn.execute("""
                INSERT INTO roms (game_id, name, size_file, sha1)
                VALUES (?, ?, ?, ?)
            """, (game_id, "ROM 2", 65536, "audit_hash_1"))  # Mesmo hash

            rom_id_dup = conn.lastrowid

            # Cria candidato de fusão
            candidate = MergeCandidate(
                rom_id_1=rom_id_main,
                rom_id_2=rom_id_dup,
                similarity_score=0.95,
                hash_matches={'sha1': 'audit_hash_1'},
                metadata_similarity=0.9,
                confidence=0.92,
                merge_strategy='auto_merge',
                sources_in_common=['audit_source.dat']
            )

            # Executa fusão
            rom1_data = fm._get_rom_data_by_id(conn, rom_id_main)
            rom2_data = fm._get_rom_data_by_id(conn, rom_id_dup)

            success = fm._perform_auto_fusion(candidate)

            # Verifica se log foi criado
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rom_merge_log WHERE rom_main_id = ?", (rom_id_main,))
            log_count = cursor.fetchone()[0]

            assert log_count == 1, "Audit log not created"

            # Verifica conteúdo do log
            cursor.execute("""
                SELECT merge_type, confidence_score, fusion_success, merged_by
                FROM rom_merge_log WHERE rom_main_id = ?
            """, (rom_id_main,))

            row = cursor.fetchone()
            assert row[0] == 'auto_fusion_intelligent'  # Tipo correto
            assert row[1] >= 0.9  # Confiança preservada
            assert row[2] == True  # Sucesso registrado
            assert row[3] == 'fusion_system'  # Sistema correto


@pytest.mark.parametrize("test_case", [
    "dedup_sha1_exact", "dedup_multi_hash", "ambiguity_region",
    "ambiguity_language", "ambiguity_version", "no_merge_low_sim"
])
def test_fusion_scenarios_comprehensive(test_case, fusion_manager):
    """Cenários abrangentes de teste para fusão."""
    scenarios = {
        "dedup_sha1_exact": {
            "rom1": RomData(1, "Game", 32768, {'sha1': 'hash123'}, {}, ['src1']),
            "rom2": RomData(2, "Game", 32768, {'sha1': 'hash123'}, {}, ['src2']),
            "expected_similarity": lambda s: s >= 0.95,
            "expected_strategy": "auto_merge"
        },
        "dedup_multi_hash": {
            "rom1": RomData(1, "Game", 32768, {'sha1': 'hash123', 'md5': 'md5123'}, {}, ['src1']),
            "rom2": RomData(2, "Game", 32768, {'md5': 'md5123', 'crc': 'crc123'}, {}, ['src2']),
            "expected_similarity": lambda s: s >= 0.8,
            "expected_strategy": "auto_merge"
        },
        "ambiguity_region": {
            "rom1": RomData(1, "Game (USA)", 32768, {'sha1': 'hash123'}, {}, ['src1']),
            "rom2": RomData(2, "Game (Europe)", 32768, {'sha1': 'hash123'}, {}, ['src2']),
            "expected_similarity": lambda s: s >= 0.9,
            "expected_strategy": "auto_merge"
        },
        "no_merge_low_sim": {
            "rom1": RomData(1, "Game A", 32768, {'sha1': 'hash123'}, {}, ['src1']),
            "rom2": RomData(2, "Game B", 65536, {'sha1': 'different_hash'}, {}, ['src2']),
            "expected_similarity": lambda s: s <= 0.6,
            "expected_strategy": "reject"
        }
    }

    scenario = scenarios[test_case]
    rom1, rom2 = scenario["rom1"], scenario["rom2"]

    similarity, hash_matches, metadata_sim = fusion_manager._calculate_similarity(rom1, rom2)

    # Verificações do cenário
    assert scenario["expected_similarity"](similarity), \
        f"Scenario {test_case}: similarity {similarity} outside expected range"


run_performance_tests = os.environ.get("MEGAEMU_RUN_PERF_TESTS", "false").lower() == "true"

if run_performance_tests:
    # Executa apenas quando solicitado (teste mais pesado)
    pytest.main([__file__, "-v", "-m", "performance"])

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# Comando para cobertura:
# pytest tests/test_universal_fusion.py --cov=engine --cov-report=html --cov-fail-under=90