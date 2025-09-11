#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Migração de Banco de Dados

Este script verifica e migra bancos de dados existentes para garantir
compatibilidade com a estrutura atual do schema.

Autor: Sistema de Migração Automática
Data: 2024
"""

import sqlite3
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """
    Classe responsável por migrar bancos de dados para a estrutura atual.
    """
    
    def __init__(self):
        self.current_schema_version = "1.1"
        self.required_columns = {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'title': 'TEXT',
            'description': 'TEXT',
            'name_nointro': 'TEXT',
            'name_goodtools': 'TEXT',
            'name_TOSEC': 'TEXT',
            'name_redump': 'TEXT',
            'name_ROM_Header': 'TEXT',
            'name_progetto_EMU': 'TEXT',
            'name_custom': 'TEXT',
            'name_unofficial_dumps': 'TEXT',
            'flag': 'TEXT',
            'language': 'TEXT',
            'distribution': 'TEXT',
            'versions': 'TEXT',
            'region': 'TEXT',
            'platform': 'TEXT',

            'path_file': 'TEXT',
            'path_image': 'TEXT',
            'size_file': 'TEXT',
            'crc': 'TEXT',
            'md5': 'TEXT',
            'sha1': 'TEXT UNIQUE',
            'sha256': 'TEXT',
            'serial': 'TEXT',
            'BIOS': 'BOOLEAN DEFAULT 0',
            'source_file': 'TEXT',
            'date_added': 'TEXT DEFAULT CURRENT_TIMESTAMP'
        }
        
        self.required_indexes = [
            'CREATE INDEX IF NOT EXISTS idx_title ON roms (title)',
            'CREATE INDEX IF NOT EXISTS idx_platform ON roms (platform)',
            'CREATE INDEX IF NOT EXISTS idx_region ON roms (region)',
            'CREATE INDEX IF NOT EXISTS idx_serial ON roms (serial)',
            'CREATE INDEX IF NOT EXISTS idx_sha1 ON roms (sha1)'
        ]
    
    def verify_database_integrity(self, db_path: str) -> Dict[str, any]:
        """
        Verifica a integridade do banco de dados.
        
        Args:
            db_path: Caminho para o arquivo do banco de dados
            
        Returns:
            Dicionário com informações sobre a integridade
        """
        result = {
            'valid': True,
            'issues': [],
            'missing_columns': [],
            'missing_indexes': [],
            'schema_version': None,
            'needs_migration': False
        }
        
        try:
            if not os.path.exists(db_path):
                result['valid'] = False
                result['issues'].append(f"Arquivo de banco de dados não encontrado: {db_path}")
                return result
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verifica se a tabela roms existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roms'")
            if not cursor.fetchone():
                result['valid'] = False
                result['issues'].append("Tabela 'roms' não encontrada")
                result['needs_migration'] = True
                conn.close()
                return result
            
            # Verifica colunas existentes
            cursor.execute("PRAGMA table_info(roms)")
            existing_columns = {col[1]: col[2] for col in cursor.fetchall()}
            
            # Identifica colunas faltantes
            for col_name, col_type in self.required_columns.items():
                if col_name not in existing_columns:
                    result['missing_columns'].append(col_name)
                    result['needs_migration'] = True
            
            # Verifica índices
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = {row[0] for row in cursor.fetchall()}
            
            required_index_names = {
                'idx_title', 'idx_platform', 'idx_region', 'idx_serial', 'idx_sha1'
            }
            
            for idx_name in required_index_names:
                if idx_name not in existing_indexes:
                    result['missing_indexes'].append(idx_name)
                    result['needs_migration'] = True
            
            # Verifica versão do schema
            try:
                cursor.execute("SELECT value FROM database_info WHERE key='database_version'")
                version_row = cursor.fetchone()
                if version_row:
                    result['schema_version'] = version_row[0]
                    if version_row[0] != self.current_schema_version:
                        result['needs_migration'] = True
                else:
                    result['needs_migration'] = True
            except sqlite3.OperationalError:
                # Tabela database_info não existe
                result['needs_migration'] = True
            
            conn.close()
            
            if result['missing_columns'] or result['missing_indexes']:
                result['valid'] = False
                result['issues'].append("Schema incompleto detectado")
            
            logger.info(f"Verificação de integridade concluída para {db_path}")
            logger.info(f"Colunas faltantes: {result['missing_columns']}")
            logger.info(f"Índices faltantes: {result['missing_indexes']}")
            
        except Exception as e:
            result['valid'] = False
            result['issues'].append(f"Erro durante verificação: {str(e)}")
            logger.error(f"Erro ao verificar integridade do banco: {e}")
        
        return result
    
    def create_backup(self, db_path: str) -> str:
        """
        Cria um backup do banco de dados antes da migração.
        
        Args:
            db_path: Caminho para o arquivo do banco de dados
            
        Returns:
            Caminho para o arquivo de backup
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_{timestamp}"
        
        try:
            shutil.copy2(db_path, backup_path)
            logger.info(f"Backup criado: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            raise
    
    def migrate_database(self, db_path: str, create_backup: bool = True) -> bool:
        """
        Migra o banco de dados para a estrutura atual.
        
        Args:
            db_path: Caminho para o arquivo do banco de dados
            create_backup: Se deve criar backup antes da migração
            
        Returns:
            True se a migração foi bem-sucedida
        """
        try:
            # Verifica integridade atual
            integrity = self.verify_database_integrity(db_path)
            
            if not integrity['needs_migration']:
                logger.info("Banco de dados já está atualizado")
                return True
            
            # Cria backup se solicitado
            if create_backup:
                self.create_backup(db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Adiciona colunas faltantes
            for col_name in integrity['missing_columns']:
                col_definition = self.required_columns[col_name]
                try:
                    cursor.execute(f"ALTER TABLE roms ADD COLUMN {col_name} {col_definition}")
                    logger.info(f"Coluna adicionada: {col_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.error(f"Erro ao adicionar coluna {col_name}: {e}")
                        raise
            
            # Cria índices faltantes
            for index_sql in self.required_indexes:
                try:
                    cursor.execute(index_sql)
                    logger.info(f"Índice criado: {index_sql}")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Aviso ao criar índice: {e}")
            
            # Cria ou atualiza tabela de metadados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Atualiza metadados
            metadata = [
                ('database_version', self.current_schema_version),
                ('last_migration', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('migration_script_version', '1.0')
            ]
            
            cursor.executemany(
                'INSERT OR REPLACE INTO database_info (key, value) VALUES (?, ?)',
                metadata
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Migração concluída com sucesso para {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro durante migração: {e}")
            return False
    
    def batch_migrate(self, db_directory: str) -> Dict[str, bool]:
        """
        Migra todos os bancos de dados em um diretório.
        
        Args:
            db_directory: Diretório contendo arquivos .db
            
        Returns:
            Dicionário com resultados da migração para cada arquivo
        """
        results = {}
        db_files = list(Path(db_directory).glob('*.db'))
        
        logger.info(f"Iniciando migração em lote para {len(db_files)} arquivos")
        
        for db_file in db_files:
            db_path = str(db_file)
            logger.info(f"Migrando: {db_path}")
            
            try:
                results[db_path] = self.migrate_database(db_path)
            except Exception as e:
                logger.error(f"Falha na migração de {db_path}: {e}")
                results[db_path] = False
        
        return results

def main():
    """
    Função principal para execução do script de migração.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Script de Migração de Banco de Dados')
    parser.add_argument('--db-path', help='Caminho para o arquivo de banco de dados')
    parser.add_argument('--db-directory', help='Diretório contendo arquivos .db para migração em lote')
    parser.add_argument('--verify-only', action='store_true', help='Apenas verificar integridade sem migrar')
    parser.add_argument('--no-backup', action='store_true', help='Não criar backup antes da migração')
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator()
    
    if args.db_path:
        # Migração de arquivo único
        if args.verify_only:
            integrity = migrator.verify_database_integrity(args.db_path)
            print(f"Integridade: {integrity}")
        else:
            success = migrator.migrate_database(args.db_path, not args.no_backup)
            print(f"Migração {'bem-sucedida' if success else 'falhou'}")
    
    elif args.db_directory:
        # Migração em lote
        if args.verify_only:
            db_files = list(Path(args.db_directory).glob('*.db'))
            for db_file in db_files:
                integrity = migrator.verify_database_integrity(str(db_file))
                print(f"{db_file}: {integrity}")
        else:
            results = migrator.batch_migrate(args.db_directory)
            for db_path, success in results.items():
                print(f"{db_path}: {'✓' if success else '✗'}")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()