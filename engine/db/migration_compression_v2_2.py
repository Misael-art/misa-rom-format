#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Migration to Schema v2.2.0
Adiciona campos de compressão à tabela roms

Este script adiciona os novos campos de compressão:
- compression_type: Tipo de compressão usada ('lz4', 'none', 'hybrid')
- compression_offset: Offset para compressão híbrida (bytes)
- hybrid_ratio: Ratio para compressão híbrida (0.0-1.0)

Compatível com bancos de dados existentes (não quebra dados)
"""

import sqlite3
import logging
from typing import Set, List

# Constantes hardcoded para evitar problemas de importação circular
CONFIG_LARGE_ROM_THRESHOLD_MB = 10
CONFIG_HYBRID_RAW_RATIO = 0.333

logger = logging.getLogger(__name__)

def get_existing_columns(conn: sqlite3.Connection, table_name: str) -> Set[str]:
    """
    Obtém nomes de colunas existentes em uma tabela.

    Args:
        conn: Conexão com o banco
        table_name: Nome da tabela

    Returns:
        Set[str]: Conjunto de nomes de colunas
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    return columns

def add_column_if_not_exists(conn: sqlite3.Connection, table_name: str,
                           column_name: str, column_definition: str) -> bool:
    """
    Adiciona uma coluna se ela não existir.

    Args:
        conn: Conexão com o banco
        table_name: Nome da tabela
        column_name: Nome da coluna
        column_definition: Definição completa da coluna

    Returns:
        bool: True se adicionada, False se já existia
    """
    try:
        cursor = conn.cursor()
        existing_columns = get_existing_columns(conn, table_name)

        if column_name not in existing_columns:
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"
            cursor.execute(alter_sql)
            logger.info(f"Coluna '{column_name}' adicionada à tabela '{table_name}'")
            return True
        else:
            logger.debug(f"Coluna '{column_name}' já existe em '{table_name}'")
            return False

    except sqlite3.Error as e:
        logger.error(f"Erro ao adicionar coluna '{column_name}': {e}")
        raise

def migrate_compression_fields(conn: sqlite3.Connection) -> bool:
    """
    Executa migração para adicionar campos de compressão.

    Args:
        conn: Conexão com o banco de dados

    Returns:
        bool: True se migração bem-sucedida

    Raises:
        sqlite3.Error: Se houver erro na migração
    """
    try:
        with conn:
            logger.info("Iniciando migração de campos de compressão (v2.2.0)")

            # Verificar tabela roms existe
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roms'")
            if not cursor.fetchone():
                logger.error("Tabela 'roms' não encontrada - migração abortada")
                return False

            # Adicionar colunas de compressão
            columns_added = []

            # compression_type
            if add_column_if_not_exists(conn, "roms",
                "compression_type", "compression_type TEXT DEFAULT NULL"):
                columns_added.append("compression_type")

            # compression_offset
            if add_column_if_not_exists(conn, "roms",
                "compression_offset", "compression_offset INTEGER DEFAULT NULL"):
                columns_added.append("compression_offset")

            # hybrid_ratio
            if add_column_if_not_exists(conn, "roms",
                "hybrid_ratio", "hybrid_ratio REAL DEFAULT NULL"):
                columns_added.append("hybrid_ratio")

            # Criar índice para compression_type
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_roms_compression_type
                    ON roms(compression_type)
                """)
                logger.debug("Índice 'idx_roms_compression_type' criado/verificado")
            except sqlite3.Error as e:
                logger.warning(f"Erro ao criar índice: {e}")

            # Atualizar versão do schema
            cursor.execute("""
                INSERT OR REPLACE INTO app_info (key, value, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """, ("schema_version", "2.2.0"))

            logger.info("Migração v2.2.0 concluída com sucesso")
            if columns_added:
                logger.info(f"Colunas adicionadas: {', '.join(columns_added)}")

            return True

    except sqlite3.Error as e:
        logger.error(f"Erro na migração v2.2.0: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Erro inesperado na migração: {e}")
        conn.rollback()
        raise

def validate_hybrid_integrity(conn: sqlite3.Connection, cursor=None) -> bool:
    """
    Valida e atualiza ROMs existentes para compressão híbrida baseada no tamanho.

    Args:
        conn: Conexão com o banco de dados
        cursor: Cursor opcional para reutilização

    Returns:
        bool: True se validação bem-sucedida
    """
    import hashlib
    from pathlib import Path

    try:
        if cursor is None:
            cursor = conn.cursor()

        # Buscar ROMs sem tipo de compressão definido e com tamanho grande
        cursor.execute("""
            SELECT id, rom_filename, size, md5
            FROM roms
            WHERE compression_type IS NULL
              AND size > ?
        """, (CONFIG_LARGE_ROM_THRESHOLD_MB * 1024 * 1024,))

        roms_to_update = cursor.fetchall()
        logger.info(f"Encontradas {len(roms_to_update)} ROMs para validação híbrida")

        for rom_id, rom_filename, size, stored_md5 in roms_to_update:
            try:
                if not rom_filename or not Path(rom_filename).exists():
                    logger.warning(f"Arquivo não encontrado: {rom_filename}")
                    continue

                # Ler conteúdo do arquivo
                with open(rom_filename, 'rb') as f:
                    data = f.read()

                if not data:
                    logger.warning(f"Arquivo vazio: {rom_filename}")
                    continue

                # Verificar hash se disponível
                if stored_md5:
                    calculated_md5 = hashlib.md5(data).hexdigest()
                    if calculated_md5 != stored_md5:
                        logger.error(f"Hash MD5 não corresponde para {rom_filename}")
                        continue

                # Calcular parâmetros híbridos
                offset = int(len(data) * CONFIG_HYBRID_RAW_RATIO)
                hybrid_ratio = CONFIG_HYBRID_RAW_RATIO

                # Atualizar registro no banco
                cursor.execute("""
                    UPDATE roms
                    SET compression_type = 'hybrid',
                        compression_offset = ?,
                        hybrid_ratio = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                """, (offset, hybrid_ratio, rom_id))

                logger.info(f"ROM {rom_id} atualizada para compressão híbrida")

            except Exception as e:
                logger.error(f"Erro ao processar ROM {rom_id}: {e}")
                continue

        logger.info("Validação de integridade híbrida concluída")
        return True

    except Exception as e:
        logger.error(f"Erro na validação híbrida: {e}")
        return False

def main():
    """Função principal para execução standalone."""
    import argparse

    parser = argparse.ArgumentParser(description="Migração de campos de compressão v2.2.0")
    parser.add_argument("db_path", help="Caminho para o arquivo de banco de dados")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        conn = sqlite3.connect(args.db_path)
        success = migrate_compression_fields(conn)
        conn.close()

        if success:
            print("Migração v2.2.0 concluída com sucesso!")
            return 0
        else:
            print("Migração falhou!")
            return 1

    except Exception as e:
        print(f"Erro: {e}")
        return 1

if __name__ == "__main__":
    exit(main())