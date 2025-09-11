#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Database Schema
Define a estrutura do banco de dados e funções de validação
"""

import sqlite3
import logging
import json
from typing import Dict, List, Tuple, Optional, Set
from engine.errors import DatabaseError, ValidationError, handle_database_error

logger = logging.getLogger(__name__)

# Versão atual do esquema
SCHEMA_VERSION = "2.2.0"

# Definição das tabelas
TABLES = {
    "app_info": """
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "games": """
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "roms": """
        CREATE TABLE IF NOT EXISTS roms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            filename TEXT,
            size INTEGER NOT NULL,
            crc TEXT,
            md5 TEXT,
            sha1 TEXT,
            system TEXT,
            region TEXT,
            language TEXT,
            rom_type TEXT,
            status TEXT DEFAULT 'active',
            release_year INTEGER,
            genre TEXT,
            publisher TEXT,
            developer TEXT,
            metadata_json TEXT,  -- Campos flexíveis para metadados variáveis
            region_json TEXT,    -- Dados regionais específicos
            compression_type TEXT DEFAULT NULL, -- Tipo de compressão ('lz4', 'none', 'hybrid')
            compression_offset INTEGER DEFAULT NULL, -- Offset para compressão híbrida (bytes)
            hybrid_ratio REAL DEFAULT NULL, -- Ratio para compressão híbrida (0.0-1.0)
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games (id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        )
    """,
    
    "systems": """
        CREATE TABLE IF NOT EXISTS systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            manufacturer TEXT,
            release_date TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "regions": """
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "languages": """
        CREATE TABLE IF NOT EXISTS languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "rom_types": """
        CREATE TABLE IF NOT EXISTS rom_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
}

# Índices para otimização - Compostos para melhor performance
INDEXES = {
    # Índices individuais
    "idx_roms_name": "CREATE INDEX IF NOT EXISTS idx_roms_name ON roms(name)",
    "idx_roms_crc": "CREATE INDEX IF NOT EXISTS idx_roms_crc ON roms(crc)",
    "idx_roms_md5": "CREATE INDEX IF NOT EXISTS idx_roms_md5 ON roms(md5)",
    "idx_roms_sha1": "CREATE INDEX IF NOT EXISTS idx_roms_sha1 ON roms(sha1)",
    "idx_roms_system": "CREATE INDEX IF NOT EXISTS idx_roms_system ON roms(system)",
    "idx_roms_status": "CREATE INDEX IF NOT EXISTS idx_roms_status ON roms(status)",
    "idx_roms_filename": "CREATE INDEX IF NOT EXISTS idx_roms_filename ON roms(filename)",
    "idx_roms_release_year": "CREATE INDEX IF NOT EXISTS idx_roms_release_year ON roms(release_year)",
    "idx_roms_genre": "CREATE INDEX IF NOT EXISTS idx_roms_genre ON roms(genre)",
    "idx_roms_publisher": "CREATE INDEX IF NOT EXISTS idx_roms_publisher ON roms(publisher)",
    "idx_roms_developer": "CREATE INDEX IF NOT EXISTS idx_roms_developer ON roms(developer)",

    # Índices compostos para queries combinadas
    "idx_roms_system_sha1": "CREATE INDEX IF NOT EXISTS idx_roms_system_sha1 ON roms(system, sha1)",
    "idx_roms_name_system": "CREATE INDEX IF NOT EXISTS idx_roms_name_system ON roms(name, system)",
    "idx_roms_release_year_system": "CREATE INDEX IF NOT EXISTS idx_roms_release_year_system ON roms(release_year, system)",
    "idx_roms_genre_release_year": "CREATE INDEX IF NOT EXISTS idx_roms_genre_release_year ON roms(genre, release_year)",
    "idx_roms_publisher_status": "CREATE INDEX IF NOT EXISTS idx_roms_publisher_status ON roms(publisher, status) WHERE status='active'",
    "idx_roms_developer_status": "CREATE INDEX IF NOT EXISTS idx_roms_developer_status ON roms(developer, status) WHERE status='active'",

    # Índices para compressão
    "idx_roms_compression_type": "CREATE INDEX IF NOT EXISTS idx_roms_compression_type ON roms(compression_type)",

    # Índices para outras tabelas
    "idx_systems_name": "CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name)",
    "idx_regions_code": "CREATE INDEX IF NOT EXISTS idx_regions_code ON regions(code)",
    "idx_languages_code": "CREATE INDEX IF NOT EXISTS idx_languages_code ON languages(code)",
    "idx_rom_types_code": "CREATE INDEX IF NOT EXISTS idx_rom_types_code ON rom_types(code)",

    # Índices compostos para games
    "idx_games_name": "CREATE INDEX IF NOT EXISTS idx_games_name ON games(name COLLATE NOCASE)",
    "idx_games_created_at_desc": "CREATE INDEX IF NOT EXISTS idx_games_created_at_desc ON games(created_at DESC)"
}

# Triggers e Constraints para automatização e validação
TRIGGERS = {
    # Trigger para atualização automática de updated_at
    "trig_update_roms_timestamp": """
        CREATE TRIGGER IF NOT EXISTS trig_update_roms_timestamp
            AFTER UPDATE ON roms
            FOR EACH ROW
            BEGIN
                UPDATE roms SET updated_at = datetime('now') WHERE id = NEW.id;
            END;
    """,
    "trig_update_games_timestamp": """
        CREATE TRIGGER IF NOT EXISTS trig_update_games_timestamp
            AFTER UPDATE ON games
            FOR EACH ROW
            BEGIN
                UPDATE games SET updated_at = datetime('now') WHERE id = NEW.id;
            END;
    """,
    "trig_validate_json_metadata": """
        CREATE TRIGGER IF NOT EXISTS trig_validate_json_metadata
            BEFORE INSERT ON roms
            FOR EACH ROW
            WHEN NEW.metadata_json IS NOT NULL AND NEW.metadata_json != ''
            BEGIN
                SELECT CASE
                    WHEN json_valid(NEW.metadata_json) == 0
                    THEN RAISE(ABORT, 'Campo metadata_json deve conter JSON válido')
                END;
            END;
    """,
    "trig_validate_json_region": """
        CREATE TRIGGER IF NOT EXISTS trig_validate_json_region
            BEFORE INSERT ON roms
            FOR EACH ROW
            WHEN NEW.region_json IS NOT NULL AND NEW.region_json != ''
            BEGIN
                SELECT CASE
                    WHEN json_valid(NEW.region_json) == 0
                    THEN RAISE(ABORT, 'Campo region_json deve conter JSON válido')
                END;
            END;
    """
}

# Validações adicionais para campos JSON
def validate_json_field(json_str: str) -> bool:
    """
    Valida se uma string contém JSON válido.

    Args:
        json_str: String a ser validada

    Returns:
        bool: True se for JSON válido
    """
    if not json_str or json_str.strip() == '':
        return True  # Campo vazio é válido

    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

# Particionamento Lógico
PARTITION_CONFIG = {
    "strategy": "hybrid",  # "hybrid" (por platform + year) ou "table_based"
    "platforms_per_db": 50,
    "years_per_db": 10,
    "auto_expand": True
}

def setup_partitioning(conn: sqlite3.Connection) -> None:
    """
    Configura particionamento lógico do banco por plataforma e ano.

    Args:
        conn: Conexão com o banco
    """
    try:
        # Cria função para determinar banco particionado
        conn.execute("""
            CREATE TEMP TRIGGER IF NOT EXISTS trig_partition_on_insert
                AFTER INSERT ON roms
                WHEN NEW.release_year IS NOT NULL
                BEGIN
                    SELECT CASE
                        WHEN NEW.release_year < 1990 THEN INSERT OR REPLACE INTO roms_pre_1990 SELECT NEW.*
                        WHEN NEW.release_year BETWEEN 1990 AND 1999 THEN INSERT OR REPLACE INTO roms_1990s SELECT NEW.*
                        WHEN NEW.release_year BETWEEN 2000 AND 2009 THEN INSERT OR REPLACE INTO roms_2000s SELECT NEW.*
                        WHEN NEW.release_year BETWEEN 2010 AND 2019 THEN INSERT OR REPLACE INTO roms_2010s SELECT NEW.*
                        ELSE INSERT OR REPLACE INTO roms_2020_plus SELECT NEW.*
                    END;
                END;
        """)

        # Cria tabelas de partição
        partition_tables = {
            "roms_pre_1990": """
                CREATE TABLE IF NOT EXISTS roms_pre_1990 AS
                SELECT * FROM roms WHERE release_year < 1990
            """,
            "roms_1990s": """
                CREATE TABLE IF NOT EXISTS roms_1990s AS
                SELECT * FROM roms WHERE release_year BETWEEN 1990 AND 1999
            """,
            "roms_2000s": """
                CREATE TABLE IF NOT EXISTS roms_2000s AS
                SELECT * FROM roms WHERE release_year BETWEEN 2000 AND 2009
            """,
            "roms_2010s": """
                CREATE TABLE IF NOT EXISTS roms_2010s AS
                SELECT * FROM roms WHERE release_year BETWEEN 2010 AND 2019
            """,
            "roms_2020_plus": """
                CREATE TABLE IF NOT EXISTS roms_2020_plus AS
                SELECT * FROM roms WHERE release_year >= 2020
            """
        }

        for table_name, sql in partition_tables.items():
            try:
                conn.execute(sql)
                logger.debug(f"Partição {table_name} criada/verificada")
            except sqlite3.Error as e:
                logger.warning(f"Erro ao criar partição {table_name}: {e}")

        # Cria vistas unificadoras
        partition_views = {
            "roms_stats_per_partition": """
                CREATE VIEW IF NOT EXISTS roms_stats_per_partition AS
                SELECT
                    'roms_pre_1990' as partition_name,
                    COUNT(*) as count,
                    MIN(release_year) as min_year,
                    MAX(release_year) as max_year
                FROM roms WHERE release_year < 1990
                UNION ALL
                SELECT 'roms_1990s', COUNT(*), MIN(release_year), MAX(release_year)
                FROM roms WHERE release_year BETWEEN 1990 AND 1999
                UNION ALL
                SELECT 'roms_2000s', COUNT(*), MIN(release_year), MAX(release_year)
                FROM roms WHERE release_year BETWEEN 2000 AND 2009
                UNION ALL
                SELECT 'roms_2010s', COUNT(*), MIN(release_year), MAX(release_year)
                FROM roms WHERE release_year BETWEEN 2010 AND 2019
                UNION ALL
                SELECT 'roms_2020_plus', COUNT(*), MIN(release_year), MAX(release_year)
                FROM roms WHERE release_year >= 2020;
            """
        }

        for view_name, view_sql in partition_views.items():
            if view_sql:
                try:
                    conn.execute(view_sql)
                    logger.debug(f"Vista {view_name} criada/verificada")
                except sqlite3.Error as e:
                    logger.warning(f"Erro ao criar vista {view_name}: {e}")

        logger.info("Particionamento lógico configurado")

    except sqlite3.Error as e:
        raise DatabaseError("Erro ao configurar particionamento", original_error=e)
    except Exception as e:
        raise DatabaseError("Erro inesperado no particionamento", original_error=e)

# Dados iniciais
INITIAL_DATA = {
    "regions": [
        ("JPN", "Japan"),
        ("USA", "United States"),
        ("EUR", "Europe"),
        ("BRA", "Brazil"),
        ("ASI", "Asia"),
        ("KOR", "Korea"),
        ("CHN", "China"),
        ("TWN", "Taiwan"),
        ("WOR", "World"),
        ("UNK", "Unknown")
    ],
    
    "languages": [
        ("en", "English"),
        ("ja", "Japanese"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ko", "Korean"),
        ("zh", "Chinese"),
        ("nl", "Dutch"),
        ("ru", "Russian"),
        ("multi", "Multi-Language")
    ],
    
    "rom_types": [
        ("retail", "Retail", "Official retail release"),
        ("proto", "Prototype", "Pre-release version"),
        ("beta", "Beta", "Beta version"),
        ("demo", "Demo", "Demonstration version"),
        ("sample", "Sample", "Sample version"),
        ("test", "Test", "Test program"),
        ("hack", "Hack", "Modified version"),
        ("trans", "Translation", "Translated version"),
        ("unl", "Unlicensed", "Unofficial release"),
        ("bios", "BIOS", "System BIOS")
    ]
}

def create_database_structure(conn: sqlite3.Connection) -> bool:
    """
    Cria estrutura do banco de dados.
    
    Args:
        conn: Conexão com o banco
        
    Returns:
        True se criado com sucesso
        
    Raises:
        DatabaseError: Se houver erro ao criar estrutura
    """
    try:
        with conn:
            # Habilita chaves estrangeiras
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Cria tabelas
            for table_name, table_sql in TABLES.items():
                try:
                    conn.execute(table_sql)
                    logger.debug(f"Tabela '{table_name}' criada/verificada com sucesso")
                except sqlite3.Error as e:
                    raise DatabaseError(
                        f"Erro ao criar tabela '{table_name}'",
                        details={"table": table_name, "sql": table_sql},
                        original_error=e
                    )
            
            # Cria índices
            for index_name, index_sql in INDEXES.items():
                try:
                    conn.execute(index_sql)
                    logger.debug(f"Índice '{index_name}' criado/verificado com sucesso")
                except sqlite3.Error as e:
                    logger.warning(f"Erro ao criar índice '{index_name}': {e}")

            # Cria triggers e constraints
            for trigger_name, trigger_sql in TRIGGERS.items():
                try:
                    conn.execute(trigger_sql)
                    logger.debug(f"Trigger '{trigger_name}' criado/verificado com sucesso")
                except sqlite3.Error as e:
                    logger.warning(f"Erro ao criar trigger '{trigger_name}': {e}")
            
            # Insere versão do esquema
            conn.execute("""
                INSERT OR REPLACE INTO app_info (key, value, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """, ("schema_version", SCHEMA_VERSION))
            
            # Insere dados iniciais
            _insert_initial_data(conn)
            
            logger.info("Estrutura do banco de dados criada com sucesso")
            return True
            
    except sqlite3.Error as e:
        raise DatabaseError(
            "Erro ao criar estrutura do banco de dados",
            details={"schema_version": SCHEMA_VERSION},
            original_error=e
        )
    except Exception as e:
        raise DatabaseError(
            "Erro inesperado ao criar estrutura do banco de dados",
            details={"schema_version": SCHEMA_VERSION},
            original_error=e
        )

def _insert_initial_data(conn: sqlite3.Connection) -> None:
    """
    Insere dados iniciais no banco de dados.
    
    Args:
        conn: Conexão com o banco
        
    Raises:
        DatabaseError: Se houver erro ao inserir dados
    """
    try:
        # Insere regiões
        for code, name in INITIAL_DATA["regions"]:
            conn.execute("""
                INSERT OR IGNORE INTO regions (code, name, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """, (code, name))
        
        # Insere idiomas
        for code, name in INITIAL_DATA["languages"]:
            conn.execute("""
                INSERT OR IGNORE INTO languages (code, name, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """, (code, name))
        
        # Insere tipos de ROM
        for code, name, description in INITIAL_DATA["rom_types"]:
            conn.execute("""
                INSERT OR IGNORE INTO rom_types (code, name, description, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
            """, (code, name, description))
            
        logger.debug("Dados iniciais inseridos com sucesso")
        
    except sqlite3.Error as e:
        raise DatabaseError(
            "Erro ao inserir dados iniciais",
            details={"data_types": list(INITIAL_DATA.keys())},
            original_error=e
        )

def validate_database_structure(conn: sqlite3.Connection) -> Tuple[bool, List[str]]:
    """
    Valida a estrutura do banco de dados.
    
    Args:
        conn: Conexão com o banco de dados
    
    Returns:
        Tuple[bool, List[str]]: (sucesso, lista de problemas encontrados)
        
    Raises:
        ValidationError: Se houver erro na validação
    """
    try:
        cursor = conn.cursor()
        problems = []
        
        # Verifica tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table_name in TABLES.keys():
            if table_name not in existing_tables:
                problems.append(f"Tabela ausente: {table_name}")
                logger.warning(f"Tabela '{table_name}' não encontrada")
            else:
                logger.debug(f"Tabela '{table_name}' encontrada")
        
        # Verifica colunas de cada tabela
        for table_name in TABLES.keys():
            if table_name in existing_tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # Analisa colunas esperadas do SQL
                expected_columns = _extract_columns_from_sql(TABLES[table_name])
                
                for col in expected_columns:
                    if col not in existing_columns:
                        problems.append(f"Coluna ausente em {table_name}: {col}")
                        logger.warning(f"Coluna '{col}' ausente na tabela '{table_name}'")
        
        # Verifica índices
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes = {row[0] for row in cursor.fetchall()}

        for index_name in INDEXES.keys():
            if index_name not in existing_indexes:
                problems.append(f"Índice ausente: {index_name}")
                logger.warning(f"Índice '{index_name}' não encontrado")
            else:
                logger.debug(f"Índice '{index_name}' encontrado")

        # Verifica triggers
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        existing_triggers = {row[0] for row in cursor.fetchall()}

        for trigger_name in TRIGGERS.keys():
            if trigger_name not in existing_triggers:
                problems.append(f"Trigger ausente: {trigger_name}")
                logger.warning(f"Trigger '{trigger_name}' não encontrado")
            else:
                logger.debug(f"Trigger '{trigger_name}' encontrado")
        
        # Verifica versão do esquema
        cursor.execute("SELECT value FROM app_info WHERE key='schema_version'")
        row = cursor.fetchone()
        
        if not row:
            problems.append("Versão do esquema não encontrada na tabela app_info")
            logger.warning("Versão do esquema não encontrada")
        elif row[0] != SCHEMA_VERSION:
            problems.append(f"Versão do esquema incorreta: {row[0]} (esperado: {SCHEMA_VERSION})")
            logger.warning(f"Versão incorreta: {row[0]} (esperado: {SCHEMA_VERSION})")
        else:
            logger.info(f"Versão do esquema correta: {SCHEMA_VERSION}")
        
        if problems:
            logger.warning(f"Validação encontrou {len(problems)} problema(s)")
            return (False, problems)
        
        logger.info("Validação concluída sem problemas")
        return (True, [])
        
    except sqlite3.Error as e:
        raise ValidationError(
            "Erro ao validar estrutura do banco de dados",
            details={"operation": "database_validation"},
            original_error=e
        )
    except Exception as e:
        raise ValidationError(
            "Erro inesperado ao validar estrutura do banco de dados",
            details={"operation": "database_validation"},
            original_error=e
        )

def _extract_columns_from_sql(sql: str) -> Set[str]:
    """
    Extrai nomes de colunas de uma instrução SQL CREATE TABLE.
    
    Args:
        sql: Instrução SQL
        
    Returns:
        Set[str]: Conjunto de nomes de colunas
    """
    columns = set()
    lines = sql.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith(('CREATE', ')', ',')):
            parts = line.split()
            if parts and parts[0].upper() not in ['PRIMARY', 'FOREIGN', 'UNIQUE']:
                col_name = parts[0]
                if col_name != 'id':  # Ignora ID que é sempre criado
                    columns.add(col_name)
    
    return columns

def get_database_version(conn: sqlite3.Connection) -> Optional[str]:
    """
    Obtém a versão do esquema do banco de dados.
    
    Args:
        conn: Conexão com o banco de dados
    
    Returns:
        Optional[str]: Versão do esquema ou None se não encontrada
        
    Raises:
        DatabaseError: Se houver erro ao obter versão
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_info WHERE key='schema_version'")
        row = cursor.fetchone()
        
        if row:
            logger.debug(f"Versão do banco encontrada: {row[0]}")
            return row[0]
        
        logger.debug("Versão do banco não encontrada")
        return None
        
    except sqlite3.Error as e:
        raise DatabaseError(
            "Erro ao obter versão do banco de dados",
            details={"key": "schema_version"},
            original_error=e
        )
    except Exception as e:
        raise DatabaseError(
            "Erro inesperado ao obter versão do banco de dados",
            details={"key": "schema_version"},
            original_error=e
        )

def check_database_integrity(conn: sqlite3.Connection) -> Tuple[bool, List[str]]:
    """
    Verifica integridade do banco de dados usando PRAGMA integrity_check.
    
    Args:
        conn: Conexão com o banco
        
    Returns:
        Tuple[bool, List[str]]: (integridade_ok, lista de problemas)
        
    Raises:
        DatabaseError: Se houver erro na verificação
    """
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        if result and result[0] == 'ok':
            logger.info("Integridade do banco de dados verificada com sucesso")
            return (True, [])
        
        problems = [result[0]] if result else ["Erro desconhecido na verificação"]
        logger.warning(f"Problemas de integridade encontrados: {problems}")
        return (False, problems)
        
    except sqlite3.Error as e:
        raise DatabaseError(
            "Erro ao verificar integridade do banco de dados",
            details={"operation": "integrity_check"},
            original_error=e
        )
    except Exception as e:
        raise DatabaseError(
            "Erro inesperado ao verificar integridade",
            details={"operation": "integrity_check"},
            original_error=e
        )

def get_database_stats(conn: sqlite3.Connection) -> Dict[str, any]:
    """
    Obtém estatísticas do banco de dados.
    
    Args:
        conn: Conexão com o banco
        
    Returns:
        Dict[str, any]: Estatísticas do banco
        
    Raises:
        DatabaseError: Se houver erro ao obter estatísticas
    """
    try:
        cursor = conn.cursor()
        stats = {}
        
        # Conta registros por tabela
        for table in ['games', 'roms', 'systems', 'regions', 'languages', 'rom_types']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats[f"{table}_count"] = 0
        
        # Tamanho do banco
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        stats["database_size_bytes"] = page_count * page_size
        
        # Versão do SQLite
        cursor.execute("SELECT sqlite_version()")
        stats["sqlite_version"] = cursor.fetchone()[0]
        
        logger.debug(f"Estatísticas do banco: {stats}")
        return stats
        
    except sqlite3.Error as e:
        raise DatabaseError(
            "Erro ao obter estatísticas do banco de dados",
            details={"operation": "get_stats"},
            original_error=e
        )
    except Exception as e:
        raise DatabaseError(
            "Erro inesperado ao obter estatísticas",
            details={"operation": "get_stats"},
            original_error=e
        )