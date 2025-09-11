#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Database Fusion Schema
Extensões de schema para fusão inteligente de metadados e sistema de confiança
Mantém compatibilidade com schema existente para catálogo verdadeiramente universal
"""

import sqlite3
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)

# Extensões do schema para fusão inteligente
FUSION_RULES_VERSION = "1.0.0"

# Tabelas de fusão inteligente e confiança
FUSION_TABLES = {
    "source_trust": """
        CREATE TABLE IF NOT EXISTS source_trust (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,  -- 'dat', 'xml', 'manual', 'user_defined'
            trust_level INTEGER NOT NULL DEFAULT 100,  -- 0-100
            validation_count INTEGER NOT NULL DEFAULT 0,
            accuracy_score REAL NOT NULL DEFAULT 0.0,
            last_validation DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,

    "rom_sources": """
        CREATE TABLE IF NOT EXISTS rom_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rom_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            hash_data TEXT NOT NULL,  -- JSON com todos os hashes (MD5, SHA1, CRC32)
            metadata TEXT NOT NULL,   -- JSON com metadados da fonte
            confidence REAL NOT NULL DEFAULT 1.0,  -- Confiança dessa validação (0.0-1.0)
            validation_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rom_id, source_name, hash_data),
            FOREIGN KEY (rom_id) REFERENCES roms (id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        )
    """,

    "merge_candidates": """
        CREATE TABLE IF NOT EXISTS merge_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rom_id_1 INTEGER NOT NULL,
            rom_id_2 INTEGER NOT NULL,
            similarity_score REAL NOT NULL,  -- 0.0-1.0
            hash_matches TEXT NOT NULL,       -- JSON com hashes que coincidem
            merge_confidence REAL NOT NULL,  -- Confiança na fusão (0.0-1.0)
            sources_in_common TEXT,          -- Fontes que validam ambas ROMs
            status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'auto_merged'
            reviewed_at DATETIME,
            reviewed_by TEXT,
            auto_resolved BOOLEAN DEFAULT FALSE,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rom_id_1, rom_id_2),
            FOREIGN KEY (rom_id_1) REFERENCES roms (id)
                ON DELETE CASCADE,
            FOREIGN KEY (rom_id_2) REFERENCES roms (id)
                ON DELETE CASCADE
        )
    """,

    "rom_merge_log": """
        CREATE TABLE IF NOT EXISTS rom_merge_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rom_main_id INTEGER NOT NULL,      -- ROM que ficou
            rom_merged_id INTEGER,             -- ROM que foi fundida (pode ser NULL em casos especiais)
            merge_type TEXT NOT NULL,          -- 'duplicate_hash', 'metadata_fusion', 'source_consolidation'
            sources_merged TEXT NOT NULL,      -- JSON com fontes envolvidas
            metadata_before TEXT,              -- JSON com estado antes da fusão
            metadata_after TEXT,               -- JSON com estado após fusão
            hash_resolution TEXT,              -- Como conflitos de hash foram resolvidos
            confidence_score REAL NOT NULL,    -- Confiança na fusão (0.0-1.0)
            fusion_success BOOLEAN NOT NULL DEFAULT TRUE,
            audit_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            merged_by TEXT,                    -- Sistema ou usuário que fez fusão
            remarks TEXT,                      -- Observações sobre fusão
            rollback_data TEXT,                -- Dados para possível rollback
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (rom_main_id) REFERENCES roms (id)
                ON DELETE CASCADE,
            FOREIGN KEY (rom_merged_id) REFERENCES roms (id)
                ON DELETE SET NULL
        )
    """,

    "universal_catalog_stats": """
        CREATE TABLE IF NOT EXISTS universal_catalog_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_roms INTEGER NOT NULL DEFAULT 0,
            unique_games INTEGER NOT NULL DEFAULT 0,
            sources_combined INTEGER NOT NULL DEFAULT 0,
            duplicates_detected INTEGER NOT NULL DEFAULT 0,
            ambiguous_cases INTEGER NOT NULL DEFAULT 0,
            fusions_performed INTEGER NOT NULL DEFAULT 0,
            trust_levels_calculated INTEGER NOT NULL DEFAULT 0,
            last_update DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            catalog_health REAL NOT NULL DEFAULT 0.0,  -- Saúde geral (0.0-1.0)
            data_quality_score REAL NOT NULL DEFAULT 0.0,
            completeness_score REAL NOT NULL DEFAULT 0.0,
            consistency_score REAL NOT NULL DEFAULT 0.0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
}

# Índices para fusão inteligente
FUSION_INDEXES = {
    "idx_rom_sources_rom_id": "CREATE INDEX IF NOT EXISTS idx_rom_sources_rom_id ON rom_sources(rom_id)",
    "idx_rom_sources_source": "CREATE INDEX IF NOT EXISTS idx_rom_sources_source ON rom_sources(source_name, source_type)",
    "idx_source_trust_level": "CREATE INDEX IF NOT EXISTS idx_source_trust_level ON source_trust(trust_level DESC, validation_count DESC)",
    "idx_merge_candidates_status": "CREATE INDEX IF NOT EXISTS idx_merge_candidates_status ON merge_candidates(status, similarity_score DESC)",
    "idx_merge_candidates_pairs": "CREATE INDEX IF NOT EXISTS idx_merge_candidates_pairs ON merge_candidates(rom_id_1, rom_id_2)",
    "idx_merge_log_main": "CREATE INDEX IF NOT EXISTS idx_merge_log_main ON rom_merge_log(rom_main_id, merge_type)",
    "idx_merge_log_timestamp": "CREATE INDEX IF NOT EXISTS idx_merge_log_timestamp ON rom_merge_log(audit_timestamp)",
    "idx_universal_stats_update": "CREATE INDEX IF NOT EXISTS idx_universal_stats_update ON universal_catalog_stats(last_update DESC)"
}

# Trigger triggers para auditoria automática
FUSION_TRIGGERS = {
    "audit_merge_candidates_changes": """
        CREATE TRIGGER IF NOT EXISTS audit_merge_candidates_changes
        AFTER INSERT OR UPDATE OR DELETE ON merge_candidates
        BEGIN
            INSERT INTO schema_audit_log (
                table_name, operation_type, record_id, timestamp, user_info,
                old_data, new_data, inconsistency_detected
            ) VALUES (
                'merge_candidates',
                CASE WHEN OLD.id IS NULL THEN 'INSERT'
                     WHEN NEW.id IS NULL THEN 'DELETE'
                     ELSE 'UPDATE' END,
                COALESCE(NEW.id, OLD.id),
                datetime('now'),
                'fusion_system_auto',
                CASE WHEN OLD.id IS NOT NULL THEN json(OLD.*) ELSE NULL END,
                CASE WHEN NEW.id IS NOT NULL THEN json(NEW.*) ELSE NULL END,
                CASE WHEN (NEW.id IS NOT NULL AND NEW.status = 'approved' AND NEW.similarity_score < 0.7)
                     THEN 1 ELSE 0 END
            );
        END;
    """,

    "audit_fusion_operations": """
        CREATE TRIGGER IF NOT EXISTS audit_fusion_operations
        AFTER INSERT ON rom_merge_log
        BEGIN
            INSERT INTO schema_audit_log (
                table_name, operation_type, record_id, timestamp, user_info,
                audit_context, severity_level
            ) VALUES (
                'rom_merge_log',
                'FUSION_COMPLETED',
                NEW.id,
                datetime('now'),
                COALESCE(NEW.merged_by, 'fusion_system'),
                json('{"merge_type": "' || NEW.merge_type || '", "confidence": ' || NEW.confidence_score || ', "success": ' || NEW.fusion_success || '}'),
                CASE WHEN NEW.fusion_success = 0 THEN 'HIGH'
                     WHEN NEW.confidence_score < 0.5 THEN 'MEDIUM'
                     ELSE 'LOW' END
            );
        END;
    """
}

def create_fusion_structure(conn: sqlite3.Connection, enable_audit: bool = True) -> bool:
    """
    Cria estrutura de fusão inteligente mantendo compatibilidade com schema existente.

    Args:
        conn: Conexão com banco de dados
        enable_audit: Habilitar triggers de auditoria

    Returns:
        True se criado com sucesso
    """
    try:
        with conn:
            # Garante foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            # Cria tabelas de fusão
            for table_name, table_sql in FUSION_TABLES.items():
                try:
                    conn.execute(table_sql)
                    logger.debug(f"Tabela de fusão '{table_name}' criada/verificada")
                except sqlite3.Error as e:
                    logger.error(f"Erro ao criar tabela '{table_name}': {e}")
                    raise sqlite3.Error(f"Falha na tabela '{table_name}': {e}")

            # Cria índices de performance
            for index_name, index_sql in FUSION_INDEXES.items():
                try:
                    conn.execute(index_sql)
                    logger.debug(f"Índice de fusão '{index_name}' criado")
                except sqlite3.Error as e:
                    logger.warning(f"Erro ao criar índice '{index_name}': {e}")

            # Criar triggers se audit habilitado
            if enable_audit:
                for trigger_name, trigger_sql in FUSION_TRIGGERS.items():
                    try:
                        conn.execute(trigger_sql)
                        logger.debug(f"Trigger '{trigger_name}' implantado")
                    except sqlite3.Error as e:
                        logger.warning(f"Erro no trigger '{trigger_name}': {e}")

            # Registra versão das regras de fusão
            conn.execute("""
                INSERT OR REPLACE INTO app_info (key, value, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """, ("fusion_rules_version", FUSION_RULES_VERSION))

            # Inicializa estatísticas universais zeradas
            conn.execute("""
                INSERT OR IGNORE INTO universal_catalog_stats (
                    total_roms, unique_games, sources_combined,
                    duplicates_detected, ambiguous_cases, fusions_performed,
                    trust_levels_calculated, last_update,
                    catalog_health, data_quality_score, completeness_score, consistency_score
                ) VALUES (0, 0, 0, 0, 0, 0, 0, datetime('now'), 0.0, 0.0, 0.0, 0.0)
            """)

            logger.info("Estrutura de fusão inteligente criada com sucesso")
            return True

    except sqlite3.Error as e:
        logger.error(f"Erro crítico ao criar estrutura de fusão: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado na criação da estrutura: {e}")
        raise

def migrate_to_fusion_compatible(conn: sqlite3.Connection) -> Dict[str, any]:
    """
    Migração segura para compatibilidade com fusão inteligente.

    Args:
        conn: Conexão com banco

    Returns:
        Estatísticas da migração
    """
    stats = {
        'roms_processed': 0,
        'sources_created': 0,
        'merge_candidates_found': 0,
        'errors': []
    }

    try:
        cursor = conn.cursor()

        # Conta ROMs existentes
        cursor.execute("SELECT COUNT(*) FROM roms")
        total_roms = cursor.fetchone()[0]
        stats['roms_processed'] = total_roms

        if total_roms == 0:
            logger.info("Nenhuma ROM para migrar - estrutura vazia")
            return stats

        # Migração das ROMs existentes para sistema de fontes
        cursor.execute("""
            SELECT id, name, size_file, crc, md5, sha1
            FROM roms
            WHERE (crc IS NOT NULL AND crc != '')
               OR (md5 IS NOT NULL AND md5 != '')
               OR (sha1 IS NOT NULL AND sha1 != '')
        """)

        existing_roms = cursor.fetchall()
        sources_created = 0

        for rom in existing_roms:
            try:
                rom_id, name, size, crc, md5, sha1 = rom

                # Monta dados da fonte como "legacy_database"
                source_data = {
                    'name': 'legacy_database',
                    'type': 'migration',
                    'hashes': {},
                    'metadata': {
                        'original_name': name,
                        'size': size,
                        'migration_timestamp': datetime.now().isoformat()
                    }
                }

                # Adiciona hashes presentes
                if crc: source_data['hashes']['crc'] = crc
                if md5: source_data['hashes']['md5'] = md5
                if sha1: source_data['hashes']['sha1'] = sha1

                # Insere fonte
                cursor.execute("""
                    INSERT OR IGNORE INTO rom_sources (
                        rom_id, source_name, source_type,
                        hash_data, metadata, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rom_id,
                    'legacy_database',
                    'migration',
                    str(source_data['hashes']).replace("'", '"'),
                    str(source_data['metadata']).replace("'", '"'),
                    0.9  # Confiança alta pois vem do banco existente
                ))

                sources_created += 1

            except sqlite3.Error as e:
                stats['errors'].append(f"Erro migrando ROM {rom[0]}: {e}")

        # Atualiza estatísticas
        conn.commit()
        stats['sources_created'] = sources_created

        # Identifica candidatos potenciais para fusão (mesmo hash)
        duplicate_hashes = 0

        # Procura por hashes duplicados para criar candidatos de fusão
        for hash_type in ['crc', 'md5', 'sha1']:
            cursor.execute(f"""
                SELECT {hash_type}, COUNT(*) as count
                FROM roms
                WHERE {hash_type} IS NOT NULL AND {hash_type} != ''
                GROUP BY {hash_type}
                HAVING count > 1
            """)

            duplicates = cursor.fetchall()
            duplicate_hashes += len(duplicates)

            # Criar candidatos de fusão preliminares
            for hash_value, count in duplicates:
                cursor.execute(f"""
                    SELECT id FROM roms
                    WHERE {hash_type} = ? AND {hash_type} IS NOT NULL
                    ORDER BY id ASC
                """, (hash_value,))

                rom_ids = [row[0] for row in cursor.fetchall()]

                # Criar pares para análise posterior
                for i in range(len(rom_ids)):
                    for j in range(i+1, len(rom_ids)):
                        try:
                            similarity = 1.0 if hash_type == 'sha1' else 0.8  # SHA1 mais confiável

                            cursor.execute("""
                                INSERT OR IGNORE INTO merge_candidates (
                                    rom_id_1, rom_id_2, similarity_score,
                                    hash_matches, merge_confidence, sources_in_common
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                rom_ids[i], rom_ids[j], similarity,
                                f'{{"{hash_type}": "{hash_value}"}}',
                                similarity,  # Mesmo nível de confiança
                                '["legacy_database"]'
                            ))
                        except sqlite3.Error as e:
                            logger.debug(f"Pular candidato duplicado: {e}")

        conn.commit()
        stats['merge_candidates_found'] = duplicate_hashes

        # Atualiza estatísticas universais
        cursor.execute("""
            UPDATE universal_catalog_stats
            SET total_roms = ?, sources_combined = ?, duplicates_detected = ?,
                last_update = datetime('now'), updated_at = datetime('now')
            WHERE id = (SELECT MAX(id) FROM universal_catalog_stats)
        """, (total_roms, stats['sources_created'], stats['merge_candidates_found']))

        conn.commit()

        logger.info(f"Migração para fusão concluída: {stats}")
        return stats

    except Exception as e:
        stats['errors'].append(f"Erro crítico na migração: {e}")
        logger.error(f"Erro na migração para fusão: {e}")
        return stats

def get_fusion_rules_version(conn: sqlite3.Connection) -> Optional[str]:
    """
    Obtém versão das regras de fusão.

    Args:
        conn: Conexão com banco

    Returns:
        Versão das regras ou None
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_info WHERE key='fusion_rules_version'")
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None

def validate_fusion_structure(conn: sqlite3.Connection) -> Tuple[bool, List[str]]:
    """
    Valida estrutura de fusão inteligente.

    Args:
        conn: Conexão com banco

    Returns:
        (validade, lista de problemas)
    """
    problems = []

    try:
        cursor = conn.cursor()

        # Verificar tabelas de fusão
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fusion%' OR name IN ('source_trust', 'rom_sources', 'merge_candidates', 'rom_merge_log', 'universal_catalog_stats')")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in FUSION_TABLES.keys():
            if table not in existing_tables:
                problems.append(f"Tabela de fusão ausente: {table}")

        # Verificar índices de fusão
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%fusion%' OR name LIKE '%merge%' OR name LIKE '%source%'")
        existing_indexes = {row[0] for row in cursor.fetchall()}

        for index in FUSION_INDEXES.keys():
            if index not in existing_indexes:
                problems.append(f"Índice de fusão ausente: {index}")

        # Verificar versão das regras
        version = get_fusion_rules_version(conn)
        if version != FUSION_RULES_VERSION:
            problems.append(f"Versão das regras de fusão incorreta: {version} (esperado: {FUSION_RULES_VERSION})")

        return len(problems) == 0, problems

    except Exception as e:
        return False, [f"Erro ao validar estrutura de fusão: {e}"]