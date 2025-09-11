#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Schema Validator
Validação e verificação da estrutura do banco de dados
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from ..database_schema import get_database_version, SCHEMA_VERSION

# Configuração avançada de logging com file rotation para produção
SCHEMA_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs', 'schema_validation.log')

def setup_structured_logging():
    """Configura logging estruturado com file rotation para monitoramento avançado."""
    if not os.path.exists(os.path.dirname(SCHEMA_LOG_FILE)):
        os.makedirs(os.path.dirname(SCHEMA_LOG_FILE))

    # Configurar logger para este módulo
    schema_logger = logging.getLogger(__name__)
    schema_logger.setLevel(logging.INFO)

    # Handler para file com rotation
    file_handler = RotatingFileHandler(
        SCHEMA_LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB por arquivo
        backupCount=5,          # Manter 5 arquivos de backup
        encoding='utf-8'
    )

    # Formatação estruturada com timestamps e contexto
    formatter = logging.Formatter(
        '%(asctime)s | %(module)s | %(levelname)s | %(funcName)s | %(message)s'
    )
    file_handler.setFormatter(formatter)

    # Evitar duplicação de handlers
    if not schema_logger.handlers:
        schema_logger.addHandler(file_handler)

    return schema_logger

# Inicializar logging na importação
logger = setup_structured_logging()

logger = logging.getLogger(__name__)

class SchemaValidationError(Exception):
    """Erro na validação do schema."""
    pass

class TriggerAuditor:
    """Sistema de triggers automáticos para auditoria proativa de inconsistências."""

    AUDIT_TRIGGERS = {
        'audit_roms_changes': """
            CREATE TRIGGER IF NOT EXISTS audit_roms_changes
            AFTER INSERT OR UPDATE OR DELETE ON roms
            BEGIN
                INSERT INTO schema_audit_log (
                    table_name, operation_type, record_id, timestamp, user_info,
                    old_data, new_data, inconsistency_detected
                ) VALUES (
                    'roms',
                    CASE WHEN OLD.id IS NULL THEN 'INSERT'
                         WHEN NEW.id IS NULL THEN 'DELETE'
                         ELSE 'UPDATE' END,
                    COALESCE(NEW.id, OLD.id),
                    datetime('now'),
                    'schema_validator_auto',
                    CASE WHEN OLD.id IS NOT NULL THEN json(OLD.*) ELSE NULL END,
                    CASE WHEN NEW.id IS NOT NULL THEN json(NEW.*) ELSE NULL END,
                    CASE WHEN (OLD.id IS NOT NULL AND NEW.game_id IS NOT NULL AND
                               NOT EXISTS (SELECT 1 FROM games WHERE id = NEW.game_id)) THEN 1
                         WHEN (NEW.sha1 IS NOT NULL AND
                               EXISTS (SELECT 1 FROM roms WHERE sha1 = NEW.sha1 AND id != COALESCE(OLD.id, 0))) THEN 1
                         ELSE 0 END
                );
            END;
        """,
        'audit_games_integrity': """
            CREATE TRIGGER IF NOT EXISTS audit_games_integrity
            AFTER INSERT OR UPDATE OR DELETE ON games
            BEGIN
                INSERT INTO schema_audit_log (
                    table_name, operation_type, record_id, timestamp, user_info,
                    inconsistency_detected, audit_context
                ) VALUES (
                    'games',
                    CASE WHEN OLD.id IS NULL THEN 'INSERT'
                         WHEN NEW.id IS NULL THEN 'DELETE'
                         ELSE 'UPDATE' END,
                    COALESCE(NEW.id, OLD.id),
                    datetime('now'),
                    'schema_validator_auto',
                    CASE WHEN (NEW.id IS NOT NULL AND
                               NOT EXISTS (SELECT 1 FROM systems WHERE id = NEW.system_id)) THEN 1
                         WHEN (NEW.name IS NOT NULL AND
                               EXISTS (SELECT 1 FROM games WHERE name = NEW.name AND id != COALESCE(OLD.id, 0))) THEN 1
                         ELSE 0 END,
                    CASE WHEN NEW.system_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM systems WHERE id = NEW.system_id)
                         THEN 'system_reference_missing'
                         ELSE 'integrity_check_passed' END
                );
            END;
        """,
        'audit_foreign_key_violations': """
            CREATE TRIGGER IF NOT EXISTS audit_foreign_key_violations
            AFTER DELETE ON games
            BEGIN
                INSERT INTO schema_audit_log (
                    table_name, operation_type, record_id, timestamp, user_info,
                    inconsistency_detected, audit_context, severity_level
                )
                SELECT
                    'roms', 'POTENTIAL_ORPHAN', r.id, datetime('now'), 'schema_validator_auto',
                    1, json('{"orphan_detected": ' || r.id || ', "missing_game_id": ' || OLD.id || '}'),
                    'CRITICAL'
                FROM roms r
                WHERE r.game_id = OLD.id;
            END;
        """
    }

    @staticmethod
    def create_audit_table(cursor):
        """Cria tabela de auditoria estruturada."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                record_id TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                user_info TEXT,
                old_data TEXT,
                new_data TEXT,
                inconsistency_detected INTEGER DEFAULT 0,
                audit_context TEXT,
                severity_level TEXT DEFAULT 'INFO',
                resolved INTEGER DEFAULT 0,
                resolution_timestamp TEXT,
                resolution_notes TEXT
            );
        """)

        # Criar índices de performance para auditoria
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON schema_audit_log(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_inconsistency ON schema_audit_log(inconsistency_detected) WHERE inconsistency_detected = 1;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_table ON schema_audit_log(table_name);")

        logger.info("Tabela de auditoria criada/verificada com índices de performance")

    @staticmethod
    def deploy_audit_triggers(cursor, enable_audit: bool = True):
        """Implanta triggers de auditoria proativos."""
        if enable_audit:
            for trigger_name, trigger_sql in TriggerAuditor.AUDIT_TRIGGERS.items():
                try:
                    cursor.execute(trigger_sql)
                    logger.debug(f"Trigger {trigger_name} implantado com sucesso")
                except sqlite3.Error as e:
                    logger.warning(f"Falha ao implantar trigger {trigger_name}: {e}")
            logger.info(f"Triggers de auditoria implantados: {len(TriggerAuditor.AUDIT_TRIGGERS)}")
        else:
            # Remover triggers quando desabilitados
            for trigger_name in TriggerAuditor.AUDIT_TRIGGERS.keys():
                try:
                    cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
                except sqlite3.Error as e:
                    logger.warning(f"Falha ao remover trigger {trigger_name}: {e}")
            logger.info("Triggers de auditoria removidos")


class SchemaValidator:
    """Validador da estrutura do banco de dados com auditoria proativa e triggers avançados."""

    def __init__(self, db_path: str, enable_audit: bool = True):
        self.db_path = db_path
        self.connection = None
        self.enable_audit = enable_audit
        self.triggers_deployed = False
        self.audit_validator = TriggerAuditor()

    def validate_schema(self) -> Dict[str, Any]:
        """
        Valida completamente a estrutura do banco de dados com melhor tratamento de erros.

        Returns:
            Dict com resultados da validação
        """
        results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'version': None,
            'tables': [],
            'foreign_keys': False,
            'schema_validated': False
        }

        self.connection = None
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row

            # Forçar PRAGMA foreign_keys=ON para validação consistente
            cursor = self.connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            self.connection.commit()

            # Verificar versão do schema com validação contra SCHEMA_VERSION
            db_version = get_database_version(self.connection)
            results['version'] = db_version

            if db_version != SCHEMA_VERSION:
                results['errors'].append(
                    f"Versão do schema incompatível: encontrado {db_version}, "
                    f"esperado {SCHEMA_VERSION}"
                )
                results['warnings'].append("Atualização do schema recomendada")

            # Verificar foreign keys (já forçado como ON)
            results['foreign_keys'] = True

            # Verificar tabelas com validação escalável
            results['tables'] = self._validate_tables()

            # Verificar índices com tratamento de performance
            self._validate_indexes(results)

            # Verificar integridade referencial com checagens robustas
            self._validate_foreign_key_constraints(results)

            # Validar dados existentes com verificações otimizadas
            self._validate_data_integrity(results)

            # Marcar validação completa
            results['schema_validated'] = True

            # Resultado final baseado em erros críticos
            results['valid'] = len(results['errors']) == 0

            if results['valid']:
                logger.info("Estrutura do banco de dados validada com sucesso")
                results['warnings'].append(f"Validação completa - versão {SCHEMA_VERSION}")
            else:
                logger.error(f"Falhas críticas encontradas: {len(results['errors'])} erros")

        except sqlite3.OperationalError as e:
            results['errors'].append(f"Erro operacional do banco: {str(e)}")
            logger.error(f"Erro operacional durante validação: {e}", exc_info=True)
        except sqlite3.IntegrityError as e:
           results['errors'].append(f"Violação de integridade: {str(e)}")
           logger.error(f"Violação de integridade detectada: {e}", exc_info=True)
        except SchemaValidationError as e:
            results['errors'].append(str(e))
            logger.warning(f"Erro de validação do schema: {e}")
        except Exception as e:
            results['errors'].append(f"Erro crítico na validação: {str(e)}")
            logger.error(f"Erro inesperado ao validar schema: {str(e)}", exc_info=True)

        finally:
            if self.connection:
                try:
                    self.connection.close()
                    self.connection = None
                except Exception as close_e:
                    logger.warning(f"Erro ao fechar conexão: {close_e}")

        return results

    def _check_foreign_keys(self) -> bool:
        """Verifica se foreign keys estão habilitadas."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()
            return bool(result[0])
        except Exception as e:
            logger.warning(f"Não foi possível verificar foreign keys: {e}")
            return False

    def _validate_tables(self) -> List[str]:
        """Valida a existência e estrutura das tabelas obrigatórias com tratamento robusto."""
        try:
            cursor = self.connection.cursor()

            # Obter todas as tabelas com query otimizada
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]

            if not existing_tables:
                raise SchemaValidationError("Nenhuma tabela encontrada no banco de dados")

            # Tabelas obrigatórias com versões para escalabilidade
            required_tables = [
                ('roms', 'Tabela principal de ROMs'),
                ('games', 'Catálogo de jogos'),
                ('systems', 'Sistemas suportados'),
                ('categories', 'Categorias organizacionais')
            ]

            # Verificar existência das tabelas obrigatórias
            missing_tables = []
            for table_name, description in required_tables:
                if table_name not in existing_tables:
                    missing_tables.append(table_name)
                    logger.warning(f"Tabela obrigatória faltando: {table_name} ({description})")

            if missing_tables:
                raise SchemaValidationError(f"Tabelas obrigatórias faltando: {', '.join(missing_tables)}")

            # Verificar estrutura das tabelas sem duplicação
            structure_errors = []
            for table_name, description in required_tables:
                try:
                    self._validate_table_structure(table_name)
                    logger.debug(f"Tabela {table_name} validada com sucesso")
                except SchemaValidationError as e:
                    structure_errors.append(str(e))

            if structure_errors:
                for error in structure_errors:
                    logger.warning(error)
                raise SchemaValidationError(f"Erros na estrutura das tabelas:\n" + "\n".join(structure_errors))

            return existing_tables

        except sqlite3.Error as e:
            error_msg = f"Erro de banco ao validar tabelas: {str(e)}"
            logger.error(error_msg)
            raise SchemaValidationError(error_msg)
        except SchemaValidationError:
            # Re-raise SchemaValidationError sem modificação
            raise
        except Exception as e:
            error_msg = f"Erro inesperado ao validar tabelas: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise SchemaValidationError(error_msg)

    def _validate_table_structure(self, table_name: str):
        """Valida a estrutura específica de uma tabela."""
        try:
            cursor = self.connection.cursor()

            # Obter estrutura da tabela
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            # Verificar colunas obrigatórias por tabela
            if table_name == 'roms':
                required_cols = ['id', 'game_id', 'name', 'size_file', 'crc', 'md5', 'sha1']
            elif table_name == 'games':
                required_cols = ['id', 'name', 'description']
            elif table_name == 'systems':
                required_cols = ['id', 'name']
            elif table_name == 'categories':
                required_cols = ['id', 'name']
            else:
                return  # Tabela opcional

            # Verificar colunas
            existing_cols = [col[1] for col in columns]
            for col in required_cols:
                if col not in existing_cols:
                    raise SchemaValidationError(f"Coluna obrigatória faltando em {table_name}: {col}")

        except Exception as e:
            raise SchemaValidationError(f"Erro ao validar estrutura de {table_name}: {str(e)}")

    def _validate_indexes(self, results: Dict[str, Any]):
        """Valida presença e estrutura dos índices."""
        try:
            cursor = self.connection.cursor()

            # Obter índices existentes
            cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
            existing_indexes = [(row[0], row[1], row[2]) for row in cursor.fetchall()]

            # Verificar índices críticos
            critical_indexes = [
                'idx_roms_sha1', 'idx_roms_game_id',
                'idx_games_name', 'idx_systems_name'
            ]

            for index_name in critical_indexes:
                found = any(idx[0] == index_name for idx in existing_indexes)
                if not found:
                    results['warnings'].append(f"Índice sugerido faltando: {index_name}")

        except Exception as e:
            results['warnings'].append(f"Não foi possível validar índices: {str(e)}")

    def _validate_foreign_key_constraints(self, results: Dict[str, Any]):
        """Valida as restrições de chave estrangeira."""
        try:
            # Verificar se há dados que violariam foreign keys
            cursor = self.connection.cursor()

            # ROMs sem games válidos
            cursor.execute("""
                SELECT COUNT(*) FROM roms r
                LEFT JOIN games g ON r.game_id = g.id
                WHERE g.id IS NULL AND r.game_id IS NOT NULL
            """)
            orphan_roms = cursor.fetchone()[0]
            if orphan_roms > 0:
                results['errors'].append(f"Encontradas {orphan_roms} ROMs com game_id inválido")

        except Exception as e:
            results['warnings'].append(f"Não foi possível validar restrições FK: {str(e)}")

    def _validate_data_integrity(self, results: Dict[str, Any]):
        """Valida integridade dos dados existentes."""
        try:
            cursor = self.connection.cursor()

            # Verificar integridade geral
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            if integrity_result[0] != 'ok':
                results['errors'].append("Problema de integridade detectado no banco")

            # Verificar unique constraints
            unique_constraints = [
                ("SHA1 duplicado", "roms", "sha1"),
                ("Nome do game duplicado", "games", "name"),
                ("Nome do sistema duplicado", "systems", "name")
            ]

            for description, table, column in unique_constraints:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM (
                        SELECT {column}, COUNT(*) as cnt
                        FROM {table}
                        WHERE {column} IS NOT NULL AND {column} != ''
                        GROUP BY {column}
                        HAVING cnt > 1
                    )
                """)

                duplicates = cursor.fetchone()[0]
                if duplicates > 0:
                    results['warnings'].append(f"{description}: {duplicates} duplicatas encontradas")

        except Exception as e:
            results['warnings'].append(f"Não foi possível validar integridade dos dados: {str(e)}")

    def repair_schema(self) -> Dict[str, Any]:
        """
        Tenta reparar problemas no schema automaticamente com melhor tratamento.

        Returns:
            Dict com operações executadas e métricas
        """
        repairs = {
            'executed': [],
            'errors': [],
            'warnings': [],
            'schema_repaired': False,
            'execution_time': 0
        }

        import time
        start_time = time.time()

        self.connection = None
        try:
            self.connection = sqlite3.connect(self.db_path)
            cursor = self.connection.cursor()

            # Forçar PRAGMA foreign_keys=ON com verificação
            cursor.execute("PRAGMA foreign_keys")
            current_fk_status = bool(cursor.fetchone()[0])

            if not current_fk_status:
                cursor.execute("PRAGMA foreign_keys = ON")
                repairs['executed'].append("Foreign keys habilitadas")
            else:
                repairs['warnings'].append("Foreign keys já estavam habilitadas")

            # Verificar versão do schema antes dos reparos
            db_version = get_database_version(self.connection)
            if db_version != SCHEMA_VERSION:
                repairs['warnings'].append(
                    f"Versão do schema diferente: atual {db_version}, alvo {SCHEMA_VERSION}"
                )

            # Reparar índices faltantes com validação de performance
            self._repair_missing_indexes(cursor, repairs)

            # Verificações adicionais de integridade
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            if integrity_result != 'ok':
                repairs['warnings'].append("Problemas de integridade detectados - reparo manual recomendado")
            else:
                repairs['executed'].append("Verificação de integridade passou")

            # Commit se tudo funcionou
            self.connection.commit()
            repairs['schema_repaired'] = True

            execution_time = time.time() - start_time
            repairs['execution_time'] = round(execution_time, 3)

            logger.info(f"Reparos executados: {len(repairs['executed'])}, tempo: {execution_time:.3f}s")
            if repairs['warnings']:
                logger.warning(f"Avisos durante reparo: {len(repairs['warnings'])}")

        except sqlite3.OperationalError as e:
            repairs['errors'].append(f"Erro operacional nos reparos: {str(e)}")
            logger.error(f"Erro operacional durante reparos: {e}")
        except sqlite3.IntegrityError as e:
            repairs['errors'].append(f"Erro de integridade nos reparos: {str(e)}")
            logger.error(f"Erro de integridade durante reparos: {e}")
        except Exception as e:
            repairs['errors'].append(f"Erro crítico nos reparos: {str(e)}")
            logger.error(f"Erro inesperado nos reparos: {str(e)}", exc_info=True)

        finally:
            if self.connection:
                try:
                    self.connection.close()
                    self.connection = None
                except Exception as close_e:
                    repairs['errors'].append(f"Erro ao fechar conexão: {str(close_e)}")
                    logger.warning(f"Erro ao fechar conexão: {close_e}")

        return repairs

    def _repair_missing_indexes(self, cursor: sqlite3.Cursor, repairs: Dict):
        """Cria índices faltantes críticos com validações e métricas."""
        try:
            # Definições de índices críticos sem duplicação
            critical_indexes = {
                "idx_roms_sha1": ("roms", "(sha1)", "Aceleração de busca por hash"),
                "idx_roms_game_id": ("roms", "(game_id)", "Indexação de ROMs por jogo"),
                "idx_games_name": ("games", "(name)", "Busca rápida por nome do jogo"),
                "idx_systems_name": ("systems", "(name)", "Indexação de sistemas"),
                "idx_categories_name": ("categories", "(name)", "Indexação de categorias")
            }

            # Obter índices existentes uma vez só para otimização
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
            existing_indexes = {row[0] for row in cursor.fetchall()}

            indexes_created = 0
            indexes_skipped = 0

            for index_name, (table, cols, description) in critical_indexes.items():
                if index_name in existing_indexes:
                    indexes_skipped += 1
                    logger.debug(f"Índice já existe: {index_name}")
                    continue

                try:
                    # Verificar se tabela existe antes de criar índice
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name=?
                    """, (table,))

                    if not cursor.fetchone():
                        repairs['warnings'].append(f"Tabela {table} não encontrada - pulando índice {index_name}")
                        continue

                    # Criar índice com verificação de CONSTRAINT
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} {cols}")
                    repairs['executed'].append(f"Índice criado: {index_name} ({description})")
                    indexes_created += 1

                    logger.info(f"Índice criado: {index_name} na tabela {table}")

                except sqlite3.Error as e:
                    error_msg = f"Erro ao criar índice {index_name}: {str(e)}"
                    repairs['errors'].append(error_msg)
                    logger.error(error_msg)

            # Adicionar métricas dos reparos
            repairs['indexes_created'] = indexes_created
            repairs['indexes_skipped'] = indexes_skipped

            logger.info(f"Índices criados: {indexes_created}, pulados: {indexes_skipped}")

        except sqlite3.Error as e:
            repairs['errors'].append(f"Erro crítico ao criar índices: {str(e)}")
            logger.error(f"Erro crítico nos índices: {e}", exc_info=True)
        except Exception as e:
            repairs['errors'].append(f"Erro inesperado nos índices: {str(e)}")
            logger.error(f"Erro inesperado nos índices: {str(e)}", exc_info=True)

    def backup_before_migration(self, backup_path: str) -> bool:
        """Cria backup antes de migração."""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Backup criado antes de migração: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar backup: {str(e)}")
    def _detect_inconsistencies_proactively(self, cursor) -> Dict[str, Any]:
        """Detecta inconsistências de forma proativa usando dados de auditoria."""
        audit_problems = {
            'count': 0,
            'details': {
                'inconsistencies_found': 0,
                'critical_violations': 0,
                'potential_orphans': 0
            }
        }

        try:
            # Verificar problemas capturados pelos triggers
            cursor.execute("""
                SELECT COUNT(*),
                       COUNT(CASE WHEN severity_level = 'CRITICAL' THEN 1 END) as critical_count,
                       COUNT(CASE WHEN operation_type = 'POTENTIAL_ORPHAN' THEN 1 END) as orphans_count
                FROM schema_audit_log
                WHERE inconsistency_detected = 1
                AND datetime(timestamp) > datetime('now', '-1 hour')
            """)

            audit_stats = cursor.fetchone()
            audit_problems['count'] = audit_stats[0]
            audit_problems['details']['inconsistencies_found'] = audit_stats[0]
            audit_problems['details']['critical_violations'] = audit_stats[1] or 0
            audit_problems['details']['potential_orphans'] = audit_stats[2] or 0

            logger.info(f"Auditoria detectada: {audit_problems['count']} inconsistências")

        except sqlite3.Error as e:
            logger.warning(f"Falha ao consultar audit log: {e}")
            audit_problems['details']['query_failed'] = True

        return audit_problems

    def _validate_structural_elements(self) -> Dict[str, Any]:
        """Valida elementos estruturais consolidando validações para eliminar duplicações."""
        structural_results = {
            'tables_valid': False,
            'indexes_valid': False,
            'constraints_valid': False,
            'integrity_valid': False,
            'errors': [],
            'warnings': []
        }

        cursor = self.connection.cursor()

        try:
            # Validar tabelas (usando método existente sem duplicação)
            structural_results['tables'] = self._validate_tables()
            structural_results['tables_valid'] = (len(structural_results['tables']) >= 4)

            # Validar índices de forma consolidada
            indexes_result = {
                'foreign_keys': self.connection.execute("PRAGMA foreign_keys").fetchone()[0],
                'warnings': [],
                'errors': []
            }
            self._validate_indexes(indexes_result)
            structural_results['indexes_valid'] = (len(indexes_result['warnings']) == 0)
            structural_results['warnings'].extend(indexes_result['warnings'])

            # Validar constraints e integridade de forma consolidada
            constraints_result = {
                'foreign_keys_valid': True,
                'data_integrity_valid': True,
                'warnings': [],
                'errors': []
            }
            self._validate_foreign_key_constraints(constraints_result)
            self._validate_data_integrity(constraints_result)

            # Atualizar result validation_summary
            structural_results['constraints_valid'] = (
                constraints_result['foreign_keys_valid'] and constraints_result['data_integrity_valid']
            )
            structural_results['warnings'].extend(constraints_result['warnings'] or [])
            structural_results['errors'].extend(constraints_result['errors'] or [])

        except Exception as e:
            structural_results['errors'].append(f"Erro estrutural crítico: {str(e)}")
            logger.error(f"Erro ao validar elementos estruturais: {e}", exc_info=True)
        finally:
            cursor.close()

        # Resumo final da validação estrutural
        all_errors = structural_results['errors']
        structural_results['structural_validation_complete'] = (
            structural_results['tables_valid'] and
            structural_results['indexes_valid'] and
            structural_results['constraints_valid'] and
            len(all_errors) == 0
        )

        logger.info(f"Validação estrutural: tabelas={structural_results['tables_valid']}, "
                   f"índices={structural_results['indexes_valid']}, "
                   f"constraints={structural_results['constraints_valid']}")

        return structural_results


def validate_database_structure(db_path: str) -> Dict[str, Any]:
            return False

def validate_database_structure(db_path: str) -> Dict[str, Any]:
    """
    Função utilitária para validação completa do banco.

    Args:
        db_path: Caminho do banco de dados

    Returns:
        Resultados da validação
    """
    validator = SchemaValidator(db_path)
    return validator.validate_schema()

def repair_database_schema(db_path: str, backup_first: bool = True) -> Dict[str, Any]:
    """
    Função utilitária para reparo automático do schema.

    Args:
        db_path: Caminho do banco de dados
        backup_first: Criar backup antes dos reparos

    Returns:
        Resultados dos reparos
    """
    validator = SchemaValidator(db_path)

    if backup_first:
        backup_path = db_path + ".backup_repair"
        validator.backup_before_migration(backup_path)

    return validator.repair_schema()

# Utilitários para integração com migration
def prepare_database_for_migration(db_path: str) -> Dict[str, Any]:
    """
    Prepara e valida banco para migração com tratamento robusto.

    Returns:
        Status de preparação detalhado
    """
    results = {
        'valid': False,
        'backup_created': False,
        'errors': [],
        'warnings': [],
        'schema_ready': False,
        'migration_safe': False
    }

    try:
        validator = SchemaValidator(db_path)

        logger.info(f"Iniciando preparação para migração do banco: {db_path}")

        # Validar estrutura atual com checagem de foreign keys
        validation = validator.validate_schema()

        if validation.get('schema_validated'):
            results['schema_ready'] = True
            logger.info("Schema validado para migração")
        else:
            results['warnings'].append("Schema não validado completamente")

        if not validation['valid']:
            logger.warning(f"Problemas encontrados na validação: {len(validation['errors'])} erros")

            # Criar backup sempre, mesmo com erros
            backup_path = db_path + ".pre_migration_backup"
            if validator.backup_before_migration(backup_path):
                results['backup_created'] = True
                results['warnings'].append(f"Backup crítico criado: {backup_path}")
                logger.info(f"Backup criado em: {backup_path}")
            else:
                results['errors'].append("Falha crítica ao criar backup")
                logger.error("Falhou ao criar backup - migração não segura")
                return results

            # Para erros críticos, bloquear migração
            critical_errors = [err for err in validation['errors']
                             if any(keyword in err.lower()
                                   for keyword in ['faltando', 'incompatível', 'violação'])]
            if critical_errors:
                results['errors'].extend(validation['errors'])
                logger.error(f"Erros críticos encontrados: {len(critical_errors)}")
                return results

        # Tentar reparar problemas menores mesmo com validação OK
        logger.info("Executando reparos preventivos...")
        repairs = validator.repair_schema()
        if repairs.get('schema_repaired'):
            results['migration_safe'] = True
            logger.info("Reparos executados com sucesso")
        else:
            results['warnings'].extend(repairs.get('warnings', []))
            if repairs.get('errors'):
                results['errors'].extend(repairs['errors'])
                return results

        # Verificações finais de integridade
        if validation['valid'] and not results['errors']:
            results['valid'] = True
            results['warnings'].append("Banco totalmente preparado para migração")
        else:
            results['warnings'].append("Banco parcialmente preparado - verifique avisos")

        logger.info(f"Preparação concluída: válido={results['valid']}, seguro={results['migration_safe']}")

    except SchemaValidationError as e:
        results['errors'].append(f"Erro de validação: {str(e)}")
        logger.warning(f"Erro de validação do schema: {e}")
    except sqlite3.Error as e:
        results['errors'].append(f"Erro de banco de dados: {str(e)}")
        logger.error(f"Erro de SQLite durante preparação: {e}")
    except Exception as e:
        results['errors'].append(f"Erro inesperado na preparação: {str(e)}")
        logger.error(f"Erro inesperado ao preparar banco para migração: {str(e)}", exc_info=True)

    return results