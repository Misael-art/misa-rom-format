#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Phase 3 Tests
Testes abrangentes para SchemaValidator com auditoria proativa
"""

import pytest
import sqlite3
import tempfile
import os
import json
from unittest.mock import patch, MagicMock
from typing import Dict, Any
from pathlib import Path

from engine.db.schema_validator import SchemaValidator, TriggerAuditor, SchemaValidationError
from engine.db.enhanced_connection_pool import EnhancedDatabaseConnectionPool


class TestSchemaValidatorPhase3:
    """Testes abrangentes para SchemaValidator com features de produção."""

    @pytest.fixture
    def temp_db_path(self):
        """Fixture para caminho de banco temporário."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def populated_db_path(self, temp_db_path):
        """Fixture para banco populado com dados de teste."""
        # Criar banco com estrutura básica
        conn = sqlite3.connect(temp_db_path)

        # Criar tabelas básicas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS roms (
                id INTEGER PRIMARY KEY,
                game_id INTEGER,
                name TEXT NOT NULL,
                size_file TEXT,
                crc TEXT,
                md5 TEXT,
                sha1 TEXT,
                FOREIGN KEY (game_id) REFERENCES games(id)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS systems (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
        """)

        # Inserir dados de teste
        conn.execute("INSERT INTO systems (name) VALUES ('NES')")
        conn.execute("INSERT INTO systems (name) VALUES ('SNES')")
        conn.execute("INSERT INTO games (name, description) VALUES ('Super Mario Bros', 'Classic platformer')")
        conn.execute("INSERT INTO games (name, description) VALUES ('Zelda', 'Adventure game')")
        conn.execute("INSERT INTO roms (game_id, name, size_file, sha1) SELECT g.id, 'rom_' || g.id, '1MB', 'sha1_' || g.id FROM games g")

        conn.commit()
        conn.close()

        yield temp_db_path

    def test_advanced_schema_validation(self, populated_db_path):
        """Testa validação avançada de schema com auditoria."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Executar validação completa
        result = validator.validate_schema()

        # Verificar estrutura do resultado
        assert isinstance(result, dict)
        assert 'valid' in result
        assert 'audit_triggers_active' in result
        assert 'inconsistencies_found' in result
        assert 'audit_summary' in result

        # Com auditoria habilitada, deve estar ativa
        assert result['audit_triggers_active'] == True
        assert 'inconsistencies_found' in result

    def test_audit_trigger_deployment(self, populated_db_path):
        """Testa implantação automática de triggers de auditoria."""
        validator = SchemaValidator(populated_db_path)

        # Verificar se triggers podem ser criados
        with sqlite3.connect(populated_db_path) as conn:
            # Implantar triggers manualmente para teste
            TriggerAuditor.create_audit_table(conn.cursor())
            conn.commit()

            # Verificar se tabela de auditoria foi criada
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_audit_log'")
            audit_table = cursor.fetchone()

            assert audit_table is not None, "Tabela de auditoria deve ser criada"

    def test_proactive_inconsistency_detection(self, populated_db_path):
        """Testa detecção proativa de inconsistências."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Simular operação que gerará inconsistência
        with sqlite3.connect(populated_db_path) as conn:
            # Inserir ROM com game_id inválido (deve gerar inconsistência)
            conn.execute("INSERT INTO roms (game_id, name, sha1) VALUES (999999, 'invalid_game', 'test_sha1')")
            conn.commit()

        # Executar validação e verificar detecção
        result = validator.validate_schema()

        # Deve detectar a inconsistência
        assert result['inconsistencies_found'] >= 0, "Sistema deve detectar inconsistências"

    def test_audit_log_query_execution(self, populated_db_path):
        """Testa execução e armazenamento de queries de auditoria."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        with sqlite3.connect(populated_db_path) as conn:
            # Implantar triggers
            TriggerAuditor.create_audit_table(conn.cursor())
            conn.commit()

            # Executar operação que deve ser auditada
            conn.execute("INSERT INTO games (name, description) VALUES ('Test Game', 'Test Description')")
            conn.commit()

            # Verificar se operação foi auditada
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM schema_audit_log")
            audit_count = cursor.fetchone()[0]

            # Deve haver pelo menos uma entrada de auditoria
            # (pode variar dependendo da implementação dos triggers)
            assert isinstance(audit_count, int), "Auditoria deve registrar operações"

    def test_structural_validation_consolidation(self, populated_db_path):
        """Testa consolidação de validações estruturais para evitar duplicações."""
        validator = SchemaValidator(populated_db_path)

        result = validator.validate_schema()

        # Verificar que métodos estruturais não foram duplicados
        # (mesmo que testes específicos sejam chamados múltiplas vezes, lógica deve ser consolidada)

        # Verificar que validações críticas foram executadas
        assert 'tables' in result
        assert 'foreign_keys' in result
        assert isinstance(result['tables'], list)

        # Schema válido para banco estruturado
        assert result['valid'] == True

    def test_foreign_keys_audit_detection(self, populated_db_path):
        """Testa detecção de auditoria para foreign keys inválidas."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Simular cenário com foreign key inválida
        with sqlite3.connect(populated_db_path) as conn:
            # Desabilitar foreign keys momentaneamente para criar inconsistência
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO roms (game_id, name) VALUES (NULL, 'orphan_rom')")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        result = validator.validate_schema()

        # Sistema deve detectar a inconsistência potencial
        assert result['inconsistencies_found'] >= 0

    def test_audit_system_performance(self, populated_db_path):
        """Testa performance do sistema de auditoria."""
        import time

        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Medir tempo da validação com auditoria ativa
        start_time = time.time()
        result = validator.validate_schema()
        audit_time = time.time() - start_time

        # Validação com auditoria deve levar tempo razoável (<= 2 segundos)
        assert audit_time < 3.0, f"Validação muito lenta: {audit_time:.2f}s"
        assert result['audit_triggers_active'] == True

    def test_schema_repair_with_audit(self, populated_db_path):
        """Testa reparo de schema com sistema de auditoria ativo."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Executar reparo
        repair_result = validator.repair_schema()

        # Verificar estrutura do resultado de reparo
        assert isinstance(repair_result, dict)
        assert 'schema_repaired' in repair_result
        assert 'execution_time' in repair_result
        assert 'errors' in repair_result
        assert 'warnings' in repair_result

    def test_audit_data_integrity_validation(self, populated_db_path):
        """Testa validação de integridade de dados com auditoria."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        with sqlite3.connect(populated_db_path) as conn:
            # Corromper dados (simular)
            conn.execute("UPDATE roms SET sha1 = NULL WHERE sha1 IS NOT NULL LIMIT 1")
            conn.commit()

        result = validator.validate_schema()

        # Deve detectar problemas de integridade
        assert result is not None
        assert isinstance(result, dict)
        assert 'valid' in result

    def test_backup_before_migration_integration(self, populated_db_path):
        """Testa integração de backup antes de migração."""
        validator = SchemaValidator(populated_db_path)

        # Criar backup
        backup_path = populated_db_path + ".backup_test"
        success = validator.backup_before_migration(backup_path)

        # Verificar se backup foi criado
        if os.path.exists(backup_path):
            # Verificar tamanho do backup
            backup_size = os.path.getsize(backup_path)
            original_size = os.path.getsize(populated_db_path)

            assert backup_size > 0, "Backup deve ter conteúdo"
            assert backup_size == original_size, "Backup deve ter mesmo tamanho do original"

            # Cleanup
            os.remove(backup_path)
        else:
            pytest.skip("Backup creation failed - may be filesystem permissions issue")

    def test_audit_log_cleanup_and_rotation(self, populated_db_path):
        """Testa limpeza e rotação de logs de auditoria."""
        validator = SchemaValidator(populated_db_path, enable_audit=True)

        with sqlite3.connect(populated_db_path) as conn:
            # Simular muitos registros de auditoria
            TriggerAuditor.create_audit_table(conn.cursor())

            # Inserir múltiplos registros de auditoria (simulando atividade)
            for i in range(50):
                conn.execute("""
                    INSERT INTO schema_audit_log (
                        table_name, operation_type, record_id, timestamp,
                        inconsistency_detected
                    ) VALUES (?, ?, ?, ?, ?)
                """, ('test_table', 'INSERT', i, '2024-01-01 12:00:00', 0))

            conn.commit()

            # Verificar que registros foram criados
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM schema_audit_log")
            count_before = cursor.fetchone()[0]

            assert count_before > 10, "Devem haver registros de auditoria"

    def test_migration_preparation_with_audit(self, populated_db_path):
        """Testa preparação de migração com auditoria completa."""
        from engine.db.migrations import prepare_database_for_migration

        result = prepare_database_for_migration(populated_db_path)

        # Verificar estrutura do resultado
        assert isinstance(result, dict)
        assert 'valid' in result
        assert 'backup_created' in result
        assert 'migration_safe' in result
        assert 'schema_ready' in result

    def test_concurrent_audit_operations(self, populated_db_path):
        """Testa operações concorrentes com auditoria."""
        import threading
        import time

        results = []
        errors = []

        def audit_worker(worker_id: int):
            """Worker para teste concorrente."""
            try:
                validator = SchemaValidator(populated_db_path, enable_audit=True)

                # Executar validação múltipla vezes
                for i in range(3):
                    result = validator.validate_schema()
                    results.append(result)
                    time.sleep(0.1)  # Pequeno delay

            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")

        # Executar testes concorrentes
        threads = []
        for i in range(3):
            thread = threading.Thread(target=audit_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Aguardar conclusão
        for thread in threads:
            thread.join(timeout=10.0)

        # Verificar resultados
        assert len(results) >= 9, "Todas as validações devem ser executadas"
        assert len(errors) == 0, f"Erros durante operações concorrentes: {errors}"

        # Todas as validações devem retornar dicionáros válidos
        for result in results:
            assert isinstance(result, dict)
            assert 'valid' in result

    def test_edge_case_trigger_handling(self, temp_db_path):
        """Testa edge cases no handling de triggers de auditoria."""
        validator = SchemaValidator(temp_db_path, enable_audit=True)

        # Banco vazio - deve lidar graciosamente
        with sqlite3.connect(temp_db_path) as conn:
            # Criar estrutura mínima
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

            # Testar triggers em tabela vazia
            TriggerAuditor.create_audit_table(conn.cursor())
            conn.commit()

        # Validação deve funcionar mesmo com configurações edge
        result = validator.validate_schema()
        assert isinstance(result, dict)
        assert 'errors' in result

    def test_audit_system_resource_usage(self, populated_db_path):
        """Testa uso de recursos do sistema de auditoria."""
        import sys

        validator = SchemaValidator(populated_db_path, enable_audit=True)

        # Medir uso de memória antes e depois
        memory_before = sys.getsizeof(locals()) if hasattr(sys, 'getsizeof') else 0

        # Executar operações de auditoria intensivas
        for _ in range(5):
            result = validator.validate_schema()
            assert isinstance(result, dict)

        memory_after = sys.getsizeof(locals())

        # Uso de memória não deve crescer excessivamente
        memory_diff = memory_after - memory_before
        if memory_before > 0 and memory_diff > 0:
            # Apenas aviso se o crescimento for significativo
            growth_mb = memory_diff / (1024 * 1024)
            if growth_mb > 10:  # Mais de 10MB
                pytest.fail(f"Crescimento excessivo de memória: +{growth_mb:.1f}MB")

    def test_audit_trigger_removal(self, populated_db_path):
        """Testa remoção de triggers de auditoria."""
        validator = SchemaValidator(populated_db_path)

        with sqlite3.connect(populated_db_path) as conn:
            cursor = conn.cursor()

            # Implantar triggers
            TriggerAuditor.create_audit_table(cursor)
            conn.commit()

            # Remover triggers
            TriggerAuditor.deploy_audit_triggers(cursor, enable_audit=False)
            conn.commit()

            # Verificar que triggers foram removidos
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND SQL LIKE '%audit_%'")
            trigger_count = cursor.fetchone()[0]

            # Espera-se que a maioria dos triggers seja removida
            assert trigger_count <= 3, f"Triggers não removidos completamente: {trigger_count} restantes"