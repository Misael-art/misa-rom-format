#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Script de Migração para v2
Script para migrar bancos de dados existentes para o novo sistema
"""

import os
import sys
import shutil
import logging
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import (
    DatabaseManager,
    DatabaseManagerV2,
    DatabaseConfig,
    RetryManager,
    RetryConfig
)
from engine.db.config import ConfigLoader
from engine.db.connection_pool import ConnectionPool
from engine.db.pool_config import PoolConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationTool:
    """Ferramenta de migração para o novo sistema com gerenciamento robusto."""

    def __init__(self, old_db_path: str, new_db_path: str = None):
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path or f"{old_db_path}.v2"
        self.backup_path = f"{old_db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Configurações de pool e retry para migração robusta
        self.retry_manager = RetryManager(RetryConfig(max_attempts=3, base_delay=0.5))
        self.pool_config = PoolConfig(max_connections=3, timeout=30.0)

        # Controle de estado para gerenciamento seguro de FK
        self._fk_original_state = None
        self._migration_pool = None
        
    def check_compatibility(self) -> bool:
        """Verifica se o banco pode ser migrado."""
        if not os.path.exists(self.old_db_path):
            logger.error(f"Banco não encontrado: {self.old_db_path}")
            return False
        
        # Verifica integridade do banco antigo
        old_db = DatabaseManager()
        try:
            if old_db.connect(self.old_db_path):
                tables = old_db.get_tables()
                required_tables = ['roms', 'systems', 'categories']
                
                for table in required_tables:
                    if table not in tables:
                        logger.error(f"Tabela obrigatória ausente: {table}")
                        return False
                
                logger.info("✓ Banco compatível para migração")
                return True
                
        finally:
            old_db.close_all()
        
        return False
    
    def create_backup(self) -> bool:
        """Cria backup do banco original."""
        try:
            shutil.copy2(self.old_db_path, self.backup_path)
            logger.info(f"✓ Backup criado: {self.backup_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            return False
    
    def migrate_data(self) -> bool:
        """Migra dados para o novo sistema com manejo robusto de PRAGMAs e pool."""
        logger.info("Iniciando migração de dados com configurações otimizadas...")

        old_db = DatabaseManager()
        new_db = DatabaseManagerV2()

        try:
            # Preparar PRAGMAs para migração segura
            if not self.safe_pragmas_management(self.old_db_path, 'prepare'):
                logger.error("Falha ao preparar PRAGMAs do banco antigo")
                return False

            if not self.safe_pragmas_management(self.new_db_path, 'prepare'):
                logger.error("Falha ao preparar PRAGMAs do banco novo")
                return False

            # Conecta aos bancos
            if not old_db.connect(self.old_db_path):
                logger.error("Falha ao conectar banco antigo")
                return False

            # Criar pool de conexão otimizado para o novo banco
            if not self.create_migration_pool(self.new_db_path):
                logger.error("Falha ao criar pool de migração")
                return False

            # Configurar DatabaseManagerV2 com pool customizado
            new_db.pool = self._migration_pool
            new_db.current_db = self.new_db_path

            # Migra tabelas críticas primeiro (dependências)
            critical_tables = ['systems', 'categories']
            for table in critical_tables:
                if not self._migrate_table_robust(old_db, new_db, table):
                    logger.error(f"Falha crítica ao migrar tabela: {table}")
                    return False

            # Migra tabela principal de ROMs
            if not self._migrate_table_robust(old_db, new_db, 'roms'):
                logger.error("Falha ao migrar tabela ROMs")
                return False

            # Migra dados adicionais com tratamento de erro
            try:
                self._migrate_additional_tables_safe(old_db, new_db)
            except Exception as e:
                logger.warning(f"Tabelas adicionais não migradas completamente: {e}")
                # Não falhar completamente por causa de tabelas adicionais

            # Restaurar PRAGMAs para estado operacional
            self.safe_pragmas_management(self.old_db_path, 'restore')
            self.safe_pragmas_management(self.new_db_path, 'restore')

            logger.info("✓ Migração de dados concluída com sucesso")
            return True

        except Exception as e:
            logger.error(f"Erro crítico durante migração: {e}")
            return False

        finally:
            # Cleanup seguro
            old_db.close_all()
            new_db.close_all()
            self.cleanup_migration_pool()
    
    def _migrate_table_robust(self, old_db: DatabaseManager, new_db: DatabaseManagerV2,
                             table_name: str, max_retries: int = 3) -> bool:
        """Migra uma tabela específica com retry automático e validações."""
        logger.info(f"Migrando tabela: {table_name} com retry robusto")

        try:
            return self.retry_manager.execute_with_retry(
                self._migrate_table_impl,
                old_db=old_db,
                new_db=new_db,
                table_name=table_name
            )
        except Exception as e:
            logger.error(f"Falha definitiva ao migrar {table_name}: {e}")
            return False

    def _migrate_table_impl(self, old_db: DatabaseManager, new_db: DatabaseManagerV2,
                           table_name: str) -> bool:
        """Implementação interna robusta da migração de tabela."""
        try:
            # Verificar se tabela existe no banco antigo
            if not old_db.table_exists(table_name):
                logger.warning(f"Tabela {table_name} não existe no banco antigo, pulando")
                return True

            # Obtém estrutura da tabela
            with old_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                schema_info = cursor.fetchall()

                if not schema_info:
                    logger.warning(f"Tabela {table_name} vazia ou sem estrutura")
                    return True

                columns = [col[1] for col in schema_info]  # nome das colunas

            # Contar registros totais
            total_rows = old_db.get_row_count(table_name)
            if total_rows == 0:
                logger.info(f"  Tabela {table_name} vazia")
                return True

            logger.info(f"  Migrando {total_rows} registros de {table_name}")

            # Migrar dados em lotes com progresso
            batch_size = min(1000, max(100, total_rows // 20))  # Ajuste dinâmico
            migrated = 0
            errors = 0

            # Migrar em lotes para evitar memory issues
            with old_db.get_connection() as source_conn:
                source_cursor = source_conn.cursor()

                for offset in range(0, total_rows, batch_size):
                    try:
                        # Buscar lote do banco antigo
                        source_cursor.execute(
                            f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
                            (batch_size, offset)
                        )
                        batch = source_cursor.fetchall()

                        if not batch:
                            break

                        # Inserir lote no novo banco com pool
                        success = new_db.execute_many(
                            f"INSERT OR IGNORE INTO {table_name} ({','.join(columns)}) VALUES ({','.join(['?' for _ in columns])})",
                            [tuple(row) for row in batch]
                        )

                        if success:
                            migrated += len(batch)
                            logger.info(f"  ✓ {table_name}: {migrated}/{total_rows} registros migrados")
                        else:
                            errors += len(batch)
                            logger.warning(f"  ✗ Lote falhou: {len(batch)} registros")

                    except Exception as e:
                        errors += batch_size
                        logger.error(f"Erro no lote offset {offset}: {e}")
                        continue

            # Relatório final da migração
            success_rate = (migrated / total_rows * 100) if total_rows > 0 else 0
            logger.info(".1f")

            if errors > 0:
                logger.warning(f"  {errors} registros com erro em {table_name}")
                # Não falhar se sucesso > 90%
                return success_rate > 90.0

            return True

        except Exception as e:
            logger.error(f"Erro crítico na migração de {table_name}: {e}")
            return False
    
    def _migrate_additional_tables_safe(self, old_db: DatabaseManager, new_db: DatabaseManagerV2):
        """Migra tabelas adicionais com tratamento seguro de erros."""
        additional_tables = [
            ('rom_tags', 'Tags associadas às ROMs'),
            ('rom_metadata', 'Metadados adicionais das ROMs'),
            ('favorites', 'ROMs favoritadas pelo usuário'),
            ('game_metadata', 'Metadados de jogos'),
            ('system_aliases', 'Aliases de sistemas alternativos')
        ]

        migrated = 0
        failed = 0

        logger.info("Migrando tabelas adicionais...")

        for table_name, description in additional_tables:
            try:
                if not old_db.table_exists(table_name):
                    logger.debug(f"Tabela opcional {table_name} não existe, pulando")
                    continue

                logger.info(f"Migrando tabela opcional: {table_name} ({description})")

                if self._migrate_table_robust(old_db, new_db, table_name):
                    migrated += 1
                    logger.info(f"✓ Tabela {table_name} migrada com sucesso")
                else:
                    failed += 1
                    logger.warning(f"✗ Falha ao migrar {table_name}")

            except Exception as e:
                failed += 1
                logger.error(f"Erro inesperado migrando {table_name}: {e}")
                continue  # Continuar com próximas tabelas

        logger.info(f"Tabelas adicionais - Sucesso: {migrated}, Falhas: {failed}")

        if failed > 0:
            logger.warning("Algumas tabelas adicionais não foram migradas completamente")
    
    def verify_migration(self) -> bool:
        """Verifica se a migração foi bem-sucedida."""
        logger.info("Verificando migração...")
        
        new_db = DatabaseManagerV2()
        
        try:
            new_db.connect(self.new_db_path)
            
            # Verifica contagem de registros
            expected_counts = {
                'systems': new_db.get_row_count('systems'),
                'categories': new_db.get_row_count('categories'),
                'roms': new_db.get_row_count('roms')
            }
            
            old_db = DatabaseManager()
            old_db.connect(self.old_db_path)
            
            for table, new_count in expected_counts.items():
                old_count = old_db.get_row_count(table)
                if new_count != old_count:
                    logger.error(
                        f"Contagem incorreta para {table}: "
                        f"esperado {old_count}, obtido {new_count}"
                    )
                    return False
                logger.info(f"✓ {table}: {new_count} registros migrados")
            
            # Verifica integridade
            if not new_db.validate_database_structure():
                logger.error("Integridade do banco comprometida")
                return False
            
            logger.info("✓ Verificação concluída com sucesso")
            return True
            
        finally:
            new_db.close_all()
            old_db.close_all()
    
    def safe_pragmas_management(self, db_path: str, operation: str) -> bool:
        """Método auxiliar seguro para gerenciar PRAGMAs críticas durante migração."""
        if operation not in ['prepare', 'restore']:
            logger.error(f"Operação inválida: {operation}")
            return False

        try:
            return self.retry_manager.execute_with_retry(
                self._manage_pragmas_impl,
                db_path=db_path,
                operation=operation
            )
        except Exception as e:
            logger.error(f"Falha ao gerenciar PRAGMAs ({operation}): {e}")
            return False

    def _manage_pragmas_impl(self, db_path: str, operation: str) -> bool:
        """Implementação interna do gerenciamento de PRAGMAs."""
        import sqlite3

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            if operation == 'prepare':
                # Salvar estado original
                cursor.execute("PRAGMA foreign_keys")
                self._fk_original_state = bool(cursor.fetchone()[0])

                # Preparar para migração
                cursor.execute("PRAGMA foreign_keys = OFF")  # Desabilitar durante migração
                cursor.execute("PRAGMA synchronous = NORMAL")  # Balanced speed/safety
                cursor.execute("PRAGMA journal_mode = WAL")  # Better concurrent access

                logger.info("PRAGMAs preparados para migração")

            elif operation == 'restore':
                # Restaurar estado original
                if self._fk_original_state is not None:
                    fk_state = "ON" if self._fk_original_state else "OFF"
                    cursor.execute(f"PRAGMA foreign_keys = {fk_state}")
                    logger.info(f"Foreign keys restaurado para: {fk_state}")
                else:
                    # Safely enable FK if state unknown
                    cursor.execute("PRAGMA foreign_keys = ON")
                    logger.warning("Estado original de FK desconhecido, habilitando por segurança")

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"Erro SQL no gerenciamento de PRAGMAs: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Erro ao fechar conexão: {e}")

    def create_migration_pool(self, db_path: str) -> bool:
        """Cria pool de conexões dedicado para migração."""
        try:
            if self._migration_pool:
                self._migration_pool.close_all()

            self._migration_pool = ConnectionPool(
                db_path=db_path,
                max_connections=self.pool_config.max_connections,
                timeout=self.pool_config.timeout,
                health_check_interval=5.0  # Mais frequente durante migração
            )

            logger.info("Pool de conexões criado para migração")
            return True

        except Exception as e:
            logger.error(f"Falha ao criar pool de migração: {e}")
            return False

    def cleanup_migration_pool(self):
        """Limpa pool de conexões de migração."""
        if self._migration_pool:
            try:
                self._migration_pool.close_all()
                self._migration_pool = None
                logger.info("Pool de migração limpo")
            except Exception as e:
                logger.warning(f"Erro ao limpar pool de migração: {e}")

    def optimize_migration_settings(self, db_path: str) -> bool:
        """Otimiza configurações do banco para migração rápida e segura."""
        try:
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Configurações otimizadas para migração
                optimizations = [
                    "PRAGMA synchronous = NORMAL",  # Melhor equilíbrio performance/segurança
                    "PRAGMA journal_mode = WAL",    # Melhor acesso concorrente
                    "PRAGMA wal_autocheckpoint = 1000",  # Checkpoint automático
                    "PRAGMA cache_size = 10000",    # Mais cache para performance
                    "PRAGMA temp_store = MEMORY"     # Temp em memória
                ]

                for pragma in optimizations:
                    cursor.execute(pragma)

                # Verificar otimizações aplicadas
                cursor.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()[0]

                cursor.execute("PRAGMA synchronous")
                sync_mode = cursor.fetchone()[0]

                conn.commit()

                logger.info(f"Banco otimizado - Journal: {journal_mode}, Sync: {sync_mode}")
                return True

            except sqlite3.Error as e:
                logger.error(f"Erro ao otimizar configurações: {e}")
                return False
            finally:
                if conn:
                    conn.close()

        except Exception as e:
            logger.error(f"Falha geral na otimização: {e}")
            return False

    def run_migration(self) -> bool:
        """Executa migração completa com melhor gerenciamento."""
        logger.info("=" * 50)
        logger.info("Iniciando migração para v2 (versão aprimorada)")
        logger.info("=" * 50)
        
        steps = [
            ("Verificando compatibilidade", self.check_compatibility),
            ("Criando backup", self.create_backup),
            ("Migrando dados", self.migrate_data),
            ("Verificando migração", self.verify_migration)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n{step_name}...")
            if not step_func():
                logger.error(f"Falha em: {step_name}")
                return False
        
        logger.info("\n" + "=" * 50)
        logger.info("✓ Migração concluída com sucesso!")
        logger.info(f"  Novo banco: {self.new_db_path}")
        logger.info(f"  Backup: {self.backup_path}")
        logger.info("=" * 50)
        
        return True

def main():
    """Função principal do script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migra banco de dados para v2")
    parser.add_argument("database", help="Caminho do banco de dados antigo")
    parser.add_argument("--output", "-o", help="Caminho do novo banco de dados")
    parser.add_argument("--force", "-f", action="store_true", 
                       help="Força migração sem confirmação")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.database):
        print(f"Erro: Banco não encontrado: {args.database}")
        sys.exit(1)
    
    if not args.force:
        print("Atenção: Esta migração irá:")
        print(f"  1. Criar backup de {args.database}")
        print(f"  2. Criar novo banco em {args.output or args.database + '.v2'}")
        print(f"  3. Migrar todos os dados")
        
        response = input("\nContinuar? (s/N): ")
        if response.lower() != 's':
            print("Migração cancelada")
            sys.exit(0)
    
    # Executa migração
    migrator = MigrationTool(args.database, args.output)
    
    if migrator.run_migration():
        print("\nPróximos passos:")
        print("1. Teste o novo banco com sua aplicação")
        print("2. Se tudo funcionar, renomeie o novo banco:")
        print(f"   mv {migrator.new_db_path} {args.database}")
        print("3. O backup está disponível em:", migrator.backup_path)
    else:
        print("\nMigração falhou. Verifique os logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()