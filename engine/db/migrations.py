# engine/db/migrations.py

import sqlite3
import logging
from typing import Optional, Dict, Any
from engine.db.database_schema import SCHEMA_VERSION, get_database_version, TABLES, INDEXES
from engine.errors import MigrationError, DatabaseError, handle_database_error

logger = logging.getLogger(__name__)

def migrate_database(conn: sqlite3.Connection) -> bool:
    """
    Gerencia as migrações do banco de dados para garantir que o schema esteja atualizado.
    
    Args:
        conn: Conexão SQLite ativa
        
    Returns:
        bool: True se a migração foi bem-sucedida, False caso contrário
        
    Raises:
        MigrationError: Se houver erro crítico durante a migração
    """
    try:
        current_version = get_database_version(conn)
        
        if current_version is None:
            logger.info("Banco de dados novo ou sem versão. Criando estrutura inicial.")
            try:
                with conn:
                    # Cria tabela app_info se não existir
                    conn.execute(TABLES["app_info"])
                    
                    # Insere versão do schema
                    conn.execute("""
                        INSERT OR REPLACE INTO app_info
                        (key, value, created_at, updated_at)
                        VALUES (?, ?, datetime('now'), datetime('now'))
                    """, ('schema_version', SCHEMA_VERSION))
                    
                    # Cria todas as tabelas
                    for table_name, table_sql in TABLES.items():
                        if table_name != "app_info":  # Já criada acima
                            conn.execute(table_sql)
                    
                    # Cria todos os índices
                    for index_name, index_sql in INDEXES.items():
                        conn.execute(index_sql)
                    
                    logger.info(f"Estrutura inicial criada com schema v{SCHEMA_VERSION}")
                    return True
                    
            except sqlite3.Error as e:
                raise MigrationError(
                    f"Erro ao criar estrutura inicial do banco de dados",
                    migration_version=SCHEMA_VERSION
                ) from e
        
        if current_version < SCHEMA_VERSION:
            logger.info(f"Migrando banco de dados de v{current_version} para v{SCHEMA_VERSION}")
            
            try:
                with conn:
                    cursor = conn.cursor()
                    
                    # Migrações específicas por versão
                    if current_version < "1.0.0":
                        _migrate_to_1_0_0(conn, cursor)
                    
                    # Atualiza versão do schema
                    conn.execute("""
                        UPDATE app_info
                        SET value = ?, updated_at = datetime('now')
                        WHERE key = 'schema_version'
                    """, (SCHEMA_VERSION,))
                    
                    logger.info(f"Migração concluída: v{current_version} -> v{SCHEMA_VERSION}")
                    return True
                    
            except sqlite3.Error as e:
                raise MigrationError(
                    f"Erro durante migração de v{current_version} para v{SCHEMA_VERSION}",
                    migration_version=SCHEMA_VERSION
                ) from e
        
        if current_version == SCHEMA_VERSION:
            logger.debug(f"Banco de dados já está na versão mais recente: v{SCHEMA_VERSION}")
            return True
            
        # Versão futura - log warning mas não falha
        logger.warning(
            f"Banco de dados v{current_version} é mais recente que o schema v{SCHEMA_VERSION}. "
            f"Isso pode indicar downgrade ou versão desatualizada da aplicação."
        )
        return True

    except MigrationError:
        # Re-raise MigrationError
        raise
    except sqlite3.Error as e:
        # Converte para DatabaseError com contexto
        raise handle_database_error(e, "Migration query")
    except Exception as e:
        # Qualquer outro erro
        raise MigrationError(
            f"Erro inesperado durante migração: {str(e)}",
            migration_version=SCHEMA_VERSION
        ) from e


def _migrate_to_1_0_0(conn: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
    """
    Migração específica para versão 1.0.0.
    
    Args:
        conn: Conexão SQLite
        cursor: Cursor SQLite
    """
    logger.info("Aplicando migrações para v1.0.0")
    
    # Verifica e adiciona colunas ausentes
    cursor.execute("PRAGMA table_info(roms)")
    columns = {row[1] for row in cursor.fetchall()}
    
    # Adiciona coluna 'name' se não existir
    if "name" not in columns:
        conn.execute("ALTER TABLE roms ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        logger.info("Coluna 'name' adicionada à tabela 'roms'")
    
    # Adiciona coluna 'rom_filename' se não existir (para compatibilidade)
    if "rom_filename" not in columns and "filename" in columns:
        conn.execute("ALTER TABLE roms ADD COLUMN rom_filename TEXT")
        conn.execute("UPDATE roms SET rom_filename = filename")
        logger.info("Coluna 'rom_filename' adicionada e populada com dados de 'filename'")
    
    # Re-cria índices para garantir consistência
    _recreate_indexes(conn, "roms")


def _recreate_indexes(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Re-cria índices para uma tabela específica.
    
    Args:
        conn: Conexão SQLite
        table_name: Nome da tabela
    """
    logger.info(f"Recriando índices para tabela '{table_name}'")
    
    # Remove índices antigos
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table_name,))
    old_indexes = [row[0] for row in cursor.fetchall()]
    
    for index_name in old_indexes:
        if index_name.startswith("idx_"):
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
    
    # Cria índices novos
    for index_name, index_sql in INDEXES.items():
        if index_name.startswith(f"idx_{table_name}_"):
            conn.execute(index_sql)
    
    logger.info(f"Índices da tabela '{table_name}' atualizados")


def validate_database_integrity(conn: sqlite3.Connection) -> bool:
    """
    Valida a integridade do banco de dados.
    
    Args:
        conn: Conexão SQLite
        
    Returns:
        bool: True se o banco está íntegro, False caso contrário
    """
    try:
        cursor = conn.cursor()
        
        # Verifica integridade com PRAGMA
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        if result and result[0] == "ok":
            logger.debug("Integridade do banco de dados verificada")
            return True
        else:
            logger.error(f"Problema de integridade detectado: {result}")
            return False
            
    except sqlite3.Error as e:
        logger.error(f"Erro ao verificar integridade: {e}")
        return False


def get_migration_status(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Retorna status detalhado das migrações.
    
    Args:
        conn: Conexão SQLite
        
    Returns:
        Dict com informações sobre versões e status
    """
    try:
        current_version = get_database_version(conn)
        
        return {
            "current_version": current_version or "N/A",
            "target_version": SCHEMA_VERSION,
            "needs_migration": current_version != SCHEMA_VERSION if current_version else True,
            "is_compatible": current_version <= SCHEMA_VERSION if current_version else True
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter status de migração: {e}")
        return {
            "current_version": "ERROR",
            "target_version": SCHEMA_VERSION,
            "needs_migration": True,
            "is_compatible": False,
            "error": str(e)
        }