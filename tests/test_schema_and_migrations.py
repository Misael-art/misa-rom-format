"""
Testes abrangentes para Schema e Migrações
Cobertura: Validações JSON, schema setup, partitioning, migrations, rollback
Cenários críticos: JSON inválido, migração falha, rollback errors, schema inconsistente
"""

import pytest
import sqlite3
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, 'engine/db')

from database_schema import (
    SCHEMA_VERSION,
    TABLES,
    INDEXES,
    TRIGGERS,
    validate_json_field,
    setup_partitioning,
    create_database_structure,
    validate_database_structure,
    get_database_version,
    check_database_integrity,
    get_database_stats
)
from migration_manager import (
    MigrationManager,
    MigrationConfig,
    MigrationState
)


@pytest.fixture
def temp_db():
    """Fixture para banco de dados temporário."""
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_file.close()

    yield db_file.name

    # Cleanup
    try:
        Path(db_file.name).unlink(missing_ok=True)
    except:
        pass


@pytest.fixture
def temp_backup_dir():
    """Fixture para diretório de backup temporário."""
    backup_dir = tempfile.mkdtemp()

    yield backup_dir

    # Cleanup
    try:
        shutil.rmtree(backup_dir)
    except:
        pass


@pytest.fixture
def mock_migration_manager(temp_db, temp_backup_dir):
    """Fixture para MigrationManager."""
    config = MigrationConfig(
        backup_before_migration=True,
        backup_directory=temp_backup_dir,
        max_rollback_attempts=2
    )
    manager = MigrationManager(temp_db, config)
    manager.create_migration_table()
    return manager


class TestJsonValidation:
    """Testes para validação de campos JSON."""

    def test_valid_json_string(self):
        """Testa JSON válido."""
        valid_json = '{"test": "value", "number": 42}'
        assert validate_json_field(valid_json)

    def test_invalid_json_string(self):
        """Testa JSON inválido."""
        invalid_json = '{"test": "value", invalid}'
        assert not validate_json_field(invalid_json)

    def test_empty_string(self):
        """Testa string vazia."""
        assert validate_json_field("")

    def test_none_value(self):
        """Testa valor None."""
        assert validate_json_field(None)

    def test_complex_json(self):
        """Testa JSON complexo."""
        complex_json = '''
        {
            "game": {
                "title": "Super Mario",
                "genres": ["Platform", "Adventure"],
                "metadata": {
                    "publisher": "Nintendo",
                    "year": 1990
                }
            },
            "roms": [
                {"crc": "ABC123", "size": 1024},
                {"crc": "DEF456", "size": 2048}
            ]
        }
        '''
        assert validate_json_field(complex_json)


class TestDatabaseStructure:
    """Testes para estrutura do banco de dados."""

    def test_schema_constants(self):
        """Testa constantes de schema."""
        assert SCHEMA_VERSION == "2.1.0"
        assert isinstance(TABLES, dict)
        assert isinstance(INDEXES, dict)
        assert isinstance(TRIGGERS, dict)

    def test_create_database_structure(self, temp_db):
        """Testa criação da estrutura do banco."""
        success = create_database_structure(sqlite3.connect(temp_db))
        assert success

        # Verifica tabelas criadas
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = set(TABLES.keys())
        assert expected_tables.issubset(tables)

        # Verifica versão
        cursor.execute("SELECT value FROM app_info WHERE key='schema_version'")
        version_row = cursor.fetchone()
        assert version_row and version_row[0] == SCHEMA_VERSION

        conn.close()

    def test_validate_database_structure_success(self, temp_db):
        """Testa validação de estrutura bem-sucedida."""
        create_database_structure(sqlite3.connect(temp_db))

        valid, problems = validate_database_structure(sqlite3.connect(temp_db))
        assert valid
        assert len(problems) == 0

    def test_validate_database_structure_missing_table(self, temp_db):
        """Testa validação com tabela faltante."""
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE placeholder (id INTEGER)")

        valid, problems = validate_database_structure(conn)
        assert not valid
        assert len(problems) > 0
        assert any("ausente" in problem for problem in problems)

        conn.close()

    def test_get_database_version(self, temp_db):
        """Testa obtenção de versão do banco."""
        create_database_structure(sqlite3.connect(temp_db))
        version = get_database_version(sqlite3.connect(temp_db))
        assert version == SCHEMA_VERSION

    def test_get_database_version_none(self):
        """Testa versão None quando não há banco."""
        version = get_database_version(":memory:")
        assert version is None

    def test_check_database_integrity_valid(self):
        """Testa integridade de banco válido."""
        conn = sqlite3.connect(":memory:")
        create_database_structure(conn)

        valid, problems = check_database_integrity(conn)
        assert valid
        assert len(problems) == 0

        conn.close()

    def test_get_database_stats(self, temp_db):
        """Testa obtenção de estatísticas do banco."""
        conn = sqlite3.connect(temp_db)
        create_database_structure(conn)

        # Insere alguns dados de teste
        conn.execute("""
            INSERT INTO games (name) VALUES ('Test Game 1'), ('Test Game 2')
        """)
        conn.execute("""
            INSERT INTO roms (game_id, name, size, crc)
            VALUES (1, 'rom1.zip', 1024, 'ABC123'), (2, 'rom2.zip', 2048, 'DEF456')
        """)
        conn.commit()

        stats = get_database_stats(conn)

        assert stats['games_count'] == 2
        assert stats['roms_count'] == 2
        assert stats['database_size_bytes'] > 0
        assert 'sqlite_version' in stats

        conn.close()


class TestPartitioning:
    """Testes para particionamento."""

    def test_setup_partitioning(self, temp_db):
        """Testa configuração de particionamento."""
        conn = sqlite3.connect(temp_db)
        create_database_structure(conn)

        # Insere dados de teste
        conn.execute("""
            INSERT INTO roms (game_id, name, size, release_year)
            VALUES (1, 'old_game.zip', 1024, 1985),
                   (2, 'modern_game.zip', 2048, 2005)
        """)
        conn.commit()

        # Setup partitioning
        setup_partitioning(conn)

        # Verifica tabelas de partição criadas
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'roms%'")
        partition_tables = [row[0] for row in cursor.fetchall()]

        # Deve ter criado tabelas de partição
        assert len(partition_tables) > 1

        conn.close()


class TestMigrationManager:
    """Testes para MigrationManager."""

    def test_initialization(self, temp_db):
        """Testa inicialização."""
        manager = MigrationManager(temp_db)
        assert manager.db_path == temp_db
        assert manager.config.backup_before_migration

    def test_create_migration_table(self, temp_db):
        """Testa criação da tabela de migrações."""
        manager = MigrationManager(temp_db)
        manager.create_migration_table()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_get_current_version_empty(self, temp_db):
        """Testa versão atual quando vazio."""
        manager = MigrationManager(temp_db)
        manager.create_migration_table()
        version = manager.get_current_version()
        assert version is None

    def test_apply_migration_success(self, temp_db, mock_migration_manager):
        """Testa aplicação de migração bem-sucedida."""
        manager = mock_migration_manager

        # Migração simples
        sql = "ALTER TABLE schema_migrations ADD COLUMN test_col TEXT DEFAULT ''"
        rollback_sql = "ALTER TABLE schema_migrations DROP COLUMN test_col"

        success = manager.apply_migration(
            version="v1.0.0",
            name="Add Test Column",
            migration_sql=sql,
            rollback_sql=rollback_sql
        )

        assert success
        current_version = manager.get_current_version()
        assert current_version == "v1.0.0"

    def test_apply_migration_with_hooks(self, temp_db, mock_migration_manager):
        """Testa migração com hooks."""
        manager = mock_migration_manager

        hook_called = []

        def pre_hook():
            hook_called.append("pre")

        def post_hook():
            hook_called.append("post")

        sql = "SELECT 1"  # Migração neutra

        manager.apply_migration(
            version="v1.0.1",
            name="Test Hooks",
            migration_sql=sql,
            pre_hooks=[pre_hook],
            post_hooks=[post_hook]
        )

        assert "pre" in hook_called
        assert "post" in hook_called

    def test_apply_migration_failure(self, temp_db, mock_migration_manager):
        """Testa falha em migração."""
        manager = mock_migration_manager

        # SQL inválido
        invalid_sql = "INVALID SQL STATEMENT"

        with pytest.raises(Exception):
            manager.apply_migration(
                version="v1.0.0-fail",
                name="Failing Migration",
                migration_sql=invalid_sql
            )

        # Verifica que migração falhou
        conn = sqlite3.connect(man.component.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT success FROM schema_migrations WHERE version=?",
                      ("v1.0.0-fail",))
        row = cursor.fetchone()
        assert row and row[0] == 0  # success = False
        conn.close()

    def test_get_migration_history(self, temp_db, mock_migration_manager):
        """Testa histórico de migrações."""
        manager = mock_migration_manager

        # Aplica algumas migrações
        manager.apply_migration("v1.0.0", "Init", "SELECT 1")
        manager.apply_migration("v2.0.0", "Major Update", "SELECT 1")

        history = manager.get_migration_history()
        assert len(history) >= 2

        versions = [state.version for state in history]
        assert "v2.0.0" in versions
        assert "v1.0.0" in versions

        # Última migração deve ser a mais recente
        assert history[0].version == "v2.0.0"

    def test_rollback_migration(self, temp_db, mock_migration_manager):
        """Testa rollback de migração."""
        manager = mock_migration_manager

        # Migração com rollback
        create_sql = "ALTER TABLE schema_migrations ADD COLUMN rollback_test TEXT DEFAULT 'test'"
        drop_sql = "ALTER TABLE schema_migrations DROP COLUMN rollback_test"

        # Aplica
        manager.apply_migration("v1.1.0", "Add Column for Rollback", create_sql, drop_sql)

        # Verifica coluna existe
        conn = sqlite3.connect(manager.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schema_migrations)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "rollback_test" in columns
        conn.close()

        # Rollback
        success = manager.rollback_migration("v1.1.0")
        assert success

        # Verifica coluna não existe mais
        conn = sqlite3.connect(manager.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schema_migrations)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "rollback_test" not in columns
        conn.close()

    def test_rollback_migration_no_rollback_sql(self, temp_db, mock_migration_manager):
        """Testa rollback sem SQL de rollback."""
        manager = mock_migration_manager

        # Migração sem rollback
        manager.apply_migration("v1.2.0", "No Rollback", "SELECT 1")

        with pytest.raises(Exception):
            manager.rollback_migration("v1.2.0")

    def test_validate_integrity_empty(self, temp_db, mock_migration_manager):
        """Testa validação de integridade vazia."""
        manager = mock_migration_manager
        valid, problems = manager.validate_integrity()
        assert valid
        assert len(problems) == 0

    def test_validate_semantic_version(self):
        """Testa validação de versão semântica."""
        manager = MigrationManager(":memory")

        valid_versions = ["1.0.0", "1.0.0-alpha", "v2.3.4", "10.5.0-rc.1"]
        invalid_versions = ["1.0", "1.0.0.1", "1.0.0+", "not-a-version"]

        for version in valid_versions:
            assert manager._validate_semantic_version(version)

        for version in invalid_versions:
            assert not manager._validate_semantic_version(version)

    def test_generate_migration_template(self, temp_db):
        """Testa geração de template de migração."""
        manager = MigrationManager(temp_db)

        template_json = manager.generate_migration_template(
            "v3.0.0",
            "Major Refactor",
            "Refatoração completa do sistema"
        )

        template = json.loads(template_json)
        assert template["version"] == "v3.0.0"
        assert template["name"] == "Major Refactor"
        assert "migration" in template
        assert "hooks" in template
        assert "metadata" in template

    @patch('shutil.copy2')
    def test_backup_creation(self, mock_copy, temp_db, temp_backup_dir):
        """Testa criação de backup."""
        config = MigrationConfig(backup_directory=temp_backup_dir)
        manager = MigrationManager(temp_db, config)

        with manager._get_connection() as conn:
            # Backup deve ser chamado
            mock_copy.assert_called()

    def test_list_pending_migrations(self, temp_db, mock_migration_manager):
        """Testa listagem de migrações pendentes."""
        manager = mock_migration_manager

        # Aplica uma migração
        manager.apply_migration("v1.0.0", "Applied", "SELECT 1")

        # Lista pendentes
        available = ["v1.0.0", "v2.0.0", "v3.0.0"]
        pending = manager.list_pending_migrations(available)

        assert "v1.0.0" not in pending
        assert "v2.0.0" in pending
        assert "v3.0.0" in pending


class TestMigrationConfig:
    """Testes para MigrationConfig."""

    def test_default_config(self):
        """Testa configuração padrão."""
        config = MigrationConfig()
        assert config.backup_before_migration
        assert config.max_rollback_attempts == 3
        assert config.enable_hooks

    def test_custom_config(self, temp_backup_dir):
        """Testa configuração customizada."""
        config = MigrationConfig(
            backup_before_migration=False,
            backup_directory=temp_backup_dir,
            max_rollback_attempts=5,
            enable_hooks=False
        )

        assert not config.backup_before_migration
        assert config.backup_directory == temp_backup_dir
        assert config.max_rollback_attempts == 5
        assert not config.enable_hooks


class TestMigrationState:
    """Testes para MigrationState dataclass."""

    def test_creation(self):
        """Testa criação de MigrationState."""
        applied_at = datetime.now()

        state = MigrationState(
            version="v1.0.0",
            name="Test Migration",
            applied_at=applied_at,
            success=True,
            rollback_available=False,
            error_message="Test error",
            rollback_state="Test rollback"
        )

        assert state.version == "v1.0.0"
        assert state.name == "Test Migration"
        assert state.success
        assert not state.rollback_available


if __name__ == "__main__":
    pytest.main([__file__])