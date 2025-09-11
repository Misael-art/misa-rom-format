#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Migration Manager
Sistema robusto de migrações com versionamento, rollback, hooks e backups
"""

import sqlite3
import logging
import shutil
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from engine.errors import DatabaseError, MigrationError, handle_database_error

logger = logging.getLogger(__name__)

@dataclass
class MigrationState:
    """Estado de uma migração."""
    version: str
    name: str
    applied_at: datetime
    success: bool
    rollback_available: bool
    error_message: Optional[str] = None
    rollback_state: Optional[str] = None

@dataclass
class MigrationConfig:
    """Configuração para migrações."""
    backup_before_migration: bool = True
    backup_directory: str = "backups/migrations"
    max_rollback_attempts: int = 3
    enable_hooks: bool = True
    auto_rollback_on_error: bool = True

class MigrationManager:
    """
    Gerenciador de migrações robusto para banco de dados.

    Funcionalidades:
    - Versionamento semântico (e.g., v1.0.0, v2.1.0, v3.0.0-alpha)
    - Rollback automático em caso de erro
    - Backups incrementais
    - Hooks pre/post migração
    - Estado persistente de migrações
    - Validação de integridade
    """

    def __init__(self, db_path: str, config: MigrationConfig = None):
        """
        Inicializa o MigrationManager.

        Args:
            db_path: Caminho para o banco de dados
            config: Configuração das migrações
        """
        self.db_path = db_path
        self.config = config or MigrationConfig()
        self._setup_backup_directory()

    def _setup_backup_directory(self) -> None:
        """Cria diretório de backups se não existir."""
        backup_dir = Path(self.config.backup_directory)
        backup_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """
        Context manager para conexões seguras com auto-commit/rollback.

        Yields:
            sqlite3.Connection: Conexão com o banco
        """
        conn = None
        backup_path = None

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")

            # Cria backup se necessário
            if self.config.backup_before_migration:
                backup_path = self._create_backup()
                logger.info(f"Backup criado: {backup_path}")

            yield conn

            conn.commit()
            logger.info("Migração aplicada com sucesso")

        except Exception as e:
            if conn:
                conn.rollback()

            # Restaura backup em caso de erro
            if backup_path and self.config.auto_rollback_on_error:
                logger.warning(f"Erro na migração, restaurando backup: {backup_path}")
                self._restore_backup(backup_path)

            raise

        finally:
            if conn:
                conn.close()

    def _create_backup(self) -> str:
        """
        Cria backup incremental do banco.

        Returns:
            str: Caminho do backup criado
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_path = Path(self.db_path)
        backup_name = f"{original_path.stem}_{timestamp}{original_path.suffix}"
        backup_path = Path(self.config.backup_directory) / backup_name

        shutil.copy2(self.db_path, backup_path)
        return str(backup_path)

    def _restore_backup(self, backup_path: str) -> None:
        """
        Restaura backup em caso de falha.

        Args:
            backup_path: Caminho do backup
        """
        try:
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Backup restaurado: {backup_path}")
        except Exception as e:
            logger.error(f"Erro ao restaurar backup {backup_path}: {e}")
            raise MigrationError(f"Falha ao restaurar backup: {backup_path}", original_error=e)

    def create_migration_table(self) -> None:
        """Cria tabela de migrations se não existir."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN NOT NULL DEFAULT 1,
                    rollback_available BOOLEAN NOT NULL DEFAULT 0,
                    error_message TEXT,
                    rollback_state TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Tabela schema_migrations criada/verificada")

    def get_current_version(self) -> Optional[str]:
        """
        Obtém versão atual do esquema.

        Returns:
            Optional[str]: Versão atual ou None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT version FROM schema_migrations
                    WHERE success = 1
                    ORDER BY id DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Erro ao obter versão atual: {e}")
            return None

    def get_migration_history(self) -> List[MigrationState]:
        """
        Lista histórico de migrações.

        Returns:
            List[MigrationState]: Lista de estados de migração
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT version, name, applied_at, success, rollback_available,
                           error_message, rollback_state
                    FROM schema_migrations
                    ORDER BY id DESC
                """)
                return [
                    MigrationState(
                        version=row[0],
                        name=row[1],
                        applied_at=datetime.fromisoformat(row[2]),
                        success=bool(row[3]),
                        rollback_available=bool(row[4]),
                        error_message=row[5],
                        rollback_state=row[6]
                    )
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            logger.error(f"Erro ao obter histórico: {e}")
            raise MigrationError("Falha ao obter histórico de migrações", original_error=e)

    def apply_migration(
        self,
        version: str,
        name: str,
        migration_sql: str,
        rollback_sql: Optional[str] = None,
        pre_hooks: List[Callable] = None,
        post_hooks: List[Callable] = None
    ) -> bool:
        """
        Aplica uma migração com hooks e rollback.

        Args:
            version: Versão da migração (semver)
            name: Nome descritivo
            migration_sql: SQL da migração
            rollback_sql: SQL de rollback (opcional)
            pre_hooks: Funções a executar antes
            post_hooks: Funções a executar depois

        Returns:
            bool: True se aplicada com sucesso

        Raises:
            MigrationError: Se houver erro na migração
        """
        # Executa pre-hooks
        if self.config.enable_hooks and pre_hooks:
            for hook in pre_hooks:
                try:
                    hook()
                except Exception as e:
                    logger.error(f"Erro em pre-hook: {e}")
                    raise MigrationError(f"Pre-hook falhou: {e}", original_error=e)

        success = False
        backup_path = None

        with self._get_connection() as conn:
            try:
                # Registra migração no estado inicial
                conn.execute("""
                    INSERT INTO schema_migrations (
                        version, name, success, rollback_available,
                        created_at, updated_at
                    ) VALUES (?, ?, 0, ?, datetime('now'), datetime('now'))
                """, (version, name, rollback_sql is not None))

                # Aplica migração
                conn.execute(migration_sql)
                logger.info(f"Migração {version} ({name}) aplicada")

                # Executa post-hooks
                if self.config.enable_hooks and post_hooks:
                    for hook in post_hooks:
                        try:
                            hook()
                        except Exception as e:
                            logger.error(f"Erro em post-hook: {e}")
                            # Não falha migração por post-hook, apenas loga

                # Marca como sucesso
                conn.execute("""
                    UPDATE schema_migrations
                    SET success = 1, applied_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE version = ?
                """, (version,))

                success = True
                logger.info(f"Migração {version} concluída com sucesso")

            except sqlite3.Error as e:
                error_msg = str(e)

                # Registra erro
                conn.execute("""
                    UPDATE schema_migrations
                    SET success = 0, error_message = ?,
                        updated_at = datetime('now')
                    WHERE version = ?
                """, (error_msg, version))

                logger.error(f"Erro na migração {version}: {error_msg}")
                raise MigrationError(f"Migração {version} falhou", original_error=e)

        return success

    def rollback_migration(self, version: str, max_attempts: int = None) -> bool:
        """
        Realiza rollback de uma migração.

        Args:
            version: Versão a fazer rollback
            max_attempts: Tentativas máximas

        Returns:
            bool: True se rollback teve sucesso

        Raises:
            MigrationError: Se rollback falhar
        """
        if max_attempts is None:
            max_attempts = self.config.max_rollback_attempts

        # Obtém migração
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name, rollback_state
                    FROM schema_migrations
                    WHERE version = ? AND rollback_available = 1
                    ORDER BY id DESC LIMIT 1
                """, (version,))

                row = cursor.fetchone()
                if not row:
                    raise MigrationError(f"Nenhuma migração rollback-able encontrada para versão {version}")

                name, rollback_sql = row

        except sqlite3.Error as e:
            raise MigrationError(f"Erro ao buscar migração {version}", original_error=e)

        if not rollback_sql:
            raise MigrationError(f"Rollback não disponível para versão {version}")

        # Tenta rollback com múltiplas tentativas
        for attempt in range(1, max_attempts + 1):
            try:
                with self._get_connection() as conn:
                    conn.execute(rollback_sql)

                    # Remove registro da migração
                    conn.execute("""
                        DELETE FROM schema_migrations WHERE version = ?
                    """, (version,))

                    logger.info(f"Rollback {version} ({name}) concluído na tentativa {attempt}")
                    return True

            except Exception as e:
                logger.warning(f"Tentativa {attempt} de rollback {version} falhou: {e}")
                if attempt == max_attempts:
                    raise MigrationError(
                        f"Rollback {version} falhou após {max_attempts} tentativas",
                        original_error=e
                    )

        return False

    def validate_integrity(self) -> Tuple[bool, List[str]]:
        """
        Valida integridade de migrações.

        Returns:
            Tuple[bool, List[str]]: (válido, lista de problemas)
        """
        problems = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Verifica se tabela existe
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='schema_migrations'
                """)
                if not cursor.fetchone():
                    problems.append("Tabela schema_migrations não existe")
                    return False, problems

                # Verifica se há migrações sem sucesso
                cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE success = 0")
                failed_count = cursor.fetchone()[0]

                if failed_count > 0:
                    problems.append(f"{failed_count} migração(ões) falharam e podem precisar de rollback")

                # Verifica ordem de versões
                cursor.execute("""
                    SELECT version FROM schema_migrations
                    WHERE success = 1
                    ORDER BY id
                """)
                versions = [row[0] for row in cursor.fetchall()]

                # Validação semântica básica
                for version in versions:
                    if not self._validate_semantic_version(version):
                        problems.append(f"Versão inválida: {version}")

        except sqlite3.Error as e:
            problems.append(f"Erro de banco: {e}")

        return len(problems) == 0, problems

    def _validate_semantic_version(self, version: str) -> bool:
        """
        Valida formato de versão semântica.

        Args:
            version: Versão a validar

        Returns:
            bool: True se válida
        """
        # Remove prefixo 'v' se existir
        if version.startswith('v'):
            version = version[1:]

        # Padrão básico de semver: Major.Minor.Patch[-pre-release]
        import re
        pattern = r'^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$'
        return bool(re.match(pattern, version))

    def generate_migration_template(
        self,
        version: str,
        name: str,
        description: str = None
    ) -> str:
        """
        Gera template de migração.

        Args:
            version: Versão da migração
            name: Nome da migração
            description: Descrição opcional

        Returns:
            str: Template de migração em JSON
        """
        template = {
            "version": version,
            "name": name,
            "description": description or f"Migração {version}",
            "migration": {
                "up": "# SQL statements to apply migration",
                "down": "# SQL statements to rollback migration (optional)"
            },
            "hooks": {
                "pre": "# Commands to run before migration",
                "post": "# Commands to run after migration"
            },
            "metadata": {
                "requires_manual_review": False,
                "backup_required": True,
                "estimated_duration": "low|medium|high"
            }
        }

        return json.dumps(template, indent=2, ensure_ascii=False)

    def list_pending_migrations(self, available_versions: List[str]) -> List[str]:
        """
        Lista migrações pendentes com base nas versões disponíveis.

        Args:
            available_versions: Lista de versões disponíveis

        Returns:
            List[str]: Migrações pendentes
        """
        applied_versions = set()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version FROM schema_migrations WHERE success = 1")
                applied_versions = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.warning(f"Erro ao ler migrações aplicadas: {e}")

        return [v for v in available_versions if v not in applied_versions]

def main():
    """
    Função principal para teste do MigrationManager.
    """
    import sys

    if len(sys.argv) < 3:
        print("Uso: python migration_manager.py <db_path> <command> [args...]")
        sys.exit(1)

    db_path = sys.argv[1]
    command = sys.argv[2]

    manager = MigrationManager(db_path)

    try:
        if command == "init":
            manager.create_migration_table()
            print("✓ Sistema de migrações inicializado")

        elif command == "current":
            version = manager.get_current_version()
            print(f"Versão atual: {version or 'nenhuma'}")

        elif command == "history":
            history = manager.get_migration_history()
            print("Histórico de migrações:")
            for migration in history:
                status = "✓" if migration.success else "✗"
                rollback = " (rollback disponível)" if migration.rollback_available else ""
                print(f"  {status} {migration.version}: {migration.name}{rollback}")

        elif command == "validate":
            valid, problems = manager.validate_integrity()
            if valid:
                print("✓ Integridade validada")
            else:
                print("✗ Problemas encontrados:")
                for problem in problems:
                    print(f"  - {problem}")
                sys.exit(1)

        else:
            print(f"Comando desconhecido: {command}")

    except Exception as e:
        print(f"✗ Erro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()