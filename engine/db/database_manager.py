#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Database Manager
Gerencia conexões e operações no banco de dados SQLite
"""

import os
import sqlite3
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple
from queue import Queue
from datetime import datetime

from .database_schema import (
    validate_database_structure,
    create_database_structure,
    get_database_version,
    SCHEMA_VERSION
)

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gerenciador do banco de dados."""
    
    def __init__(self, config=None):
        """Inicializa o gerenciador.
        
        Args:
            config: Gerenciador de configuração
        """
        self.current_db = None
        self._connections = {}
        self.config = config
        
    def connection(self) -> Optional[sqlite3.Connection]:
        """Obtém conexão da thread atual.
        
        Returns:
            Conexão SQLite da thread atual ou None se não estiver conectado
        """
        thread_id = self._get_thread_id()
        conn = self._connections.get(thread_id)
        
        # Verifica se a conexão está válida
        if conn:
            try:
                # Tenta executar uma query simples para verificar se a conexão está ativa
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error as e:
                logging.warning(f"Conexão inválida para thread {thread_id}: {str(e)}")
                # Remove a conexão inválida
                self._connections.pop(thread_id, None)
                return None
        return None
        
    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Obtém conexão da thread atual.
        
        Returns:
            Conexão SQLite da thread atual ou None se não estiver conectado
        """
        conn = self.connection()
        if not conn and self.current_db and os.path.exists(self.current_db):
            # Tenta reconectar automaticamente se tiver um banco definido
            try:
                logging.info(f"Tentando reconectar automaticamente ao banco: {self.current_db}")
                self.connect(self.current_db)
                return self.connection()
            except Exception as e:
                logging.error(f"Falha ao reconectar automaticamente: {str(e)}")
        return conn
        
    def connect(self, db_path: str) -> bool:
        """
        Conecta ao banco de dados.
        
        Args:
            db_path: Caminho do banco de dados
            
        Returns:
            True se conectou com sucesso
        """
        try:
            # Verifica se já está conectado
            if self.current_db == db_path:
                return True
            
            # Fecha conexões anteriores
            self.close_all()
            
            # Verifica se o arquivo existe
            file_exists = os.path.exists(db_path)
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
            # Conecta ao banco
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # Se o arquivo não existia, cria a estrutura
            if not file_exists:
                logging.info(f"Criando nova estrutura de banco em: {db_path}")
                if not create_database_structure(conn):
                    logging.warning("Erro ao criar estrutura do banco, mas tentando continuar")
            else:
                # Se o arquivo já existia, tenta verificar a estrutura, mas não falha se houver problemas
                logging.info(f"Conectando a banco existente: {db_path}")
                try:
                    # Habilita chaves estrangeiras
                    conn.execute("PRAGMA foreign_keys = ON")
                    
                    # Verifica se há tabelas no banco
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    
                    if not tables:
                        logging.warning("Banco de dados vazio, criando estrutura")
                        if not create_database_structure(conn):
                            logging.warning("Erro ao criar estrutura do banco, mas tentando continuar")
                except Exception as e:
                    logging.warning(f"Erro ao verificar estrutura do banco: {str(e)}, mas tentando continuar")
            
            # Salva caminho e conexão
            self.current_db = db_path
            thread_id = self._get_thread_id()
            self._connections[thread_id] = conn
            
            # Valida a integridade do schema após conexão
            try:
                from ..database.schema_validator import validate_database_schema, ValidationLevel
                result = validate_database_schema(db_path, ValidationLevel.BASIC)
                
                if not result.is_valid:
                    logging.warning(f"Schema do banco de dados possui problemas:")
                    for issue in result.issues:
                        logging.warning(f"  - {issue}")
                    
                    # Tenta correção automática se disponível
                    try:
                        from ..database.migration_script import DatabaseMigrator
                        migrator = DatabaseMigrator()
                        if migrator.migrate_database(db_path, backup=True):
                            logging.info("Schema corrigido automaticamente.")
                        else:
                            logging.warning("Falha na correção automática do schema.")
                    except ImportError:
                        logging.warning("Script de migração não disponível para correção automática.")
                else:
                    logging.info("Schema do banco de dados validado com sucesso.")
                    
            except ImportError:
                logging.debug("Validador de schema não disponível - continuando sem validação.")
            except Exception as e:
                logging.warning(f"Erro durante validação do schema: {e}")
            
            logging.info(f"Conectado ao banco: {db_path}")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao conectar ao banco: {str(e)}", exc_info=True)
            self.close_all()
            return False
            
    def close_all(self):
        """Fecha todas as conexões."""
        try:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
            self.current_db = None
        except Exception as e:
            logging.error(f"Erro ao fechar conexões: {str(e)}", exc_info=True)
            
    def close(self):
        """Fecha a conexão da thread atual e todas as outras conexões.
        
        Este método é um alias para close_all() para compatibilidade com o código existente.
        """
        self.close_all()
            
    def _get_thread_id(self) -> int:
        """Obtém ID da thread atual."""
        return threading.get_ident()
        
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[sqlite3.Row]]:
        """
        Executa uma query.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Resultados da query ou None se falhar
        """
        try:
            conn = self.connection()
            if not conn:
                raise ValueError("Banco não conectado")
                
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            results = cursor.fetchall()
            conn.commit()
            return results
            
        except Exception as e:
            logging.error(f"Erro ao executar query: {str(e)}", exc_info=True)
            return None
    
    def create_new_database(self, db_path: str, app_info: Dict[str, str]) -> bool:
        """
        Cria um novo banco de dados.
        
        Args:
            db_path: Caminho do banco
            app_info: Informações do aplicativo
            
        Returns:
            True se criado com sucesso
        """
        try:
            # Verifica se já existe
            if os.path.exists(db_path):
                os.remove(db_path)
            
            # Cria diretório se necessário
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Conecta ao banco
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # Cria tabelas
            with conn:
                # Tabela de informações
                conn.execute("""
                    CREATE TABLE app_info (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
                
                # Insere informações
                for key, value in app_info.items():
                    conn.execute(
                        "INSERT INTO app_info VALUES (?, ?)",
                        (key, value)
                    )
                
                # Tabela de jogos
                conn.execute("""
                    CREATE TABLE games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        platform TEXT,
                        year TEXT,
                        manufacturer TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Tabela de ROMs
                conn.execute("""
                    CREATE TABLE roms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        crc32 TEXT NOT NULL,
                        md5 TEXT NOT NULL,
                        sha1 TEXT NOT NULL,
                        status TEXT DEFAULT 'unknown',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (game_id) REFERENCES games (id)
                            ON DELETE CASCADE
                    )
                """)
                
                # Índices
                conn.execute(
                    "CREATE INDEX idx_games_name ON games (name)"
                )
                conn.execute(
                    "CREATE INDEX idx_roms_game_id ON roms (game_id)"
                )
                conn.execute(
                    "CREATE INDEX idx_roms_name ON roms (name)"
                )
                conn.execute(
                    "CREATE INDEX idx_roms_status ON roms (status)"
                )
            
            # Fecha conexão
            conn.close()
            
            # Conecta ao novo banco
            return self.connect(db_path)
            
        except Exception as e:
            logging.error(f"Erro ao criar banco: {str(e)}", exc_info=True)
            return False
    
    def _check_structure(self):
        """Verifica e atualiza estrutura do banco."""
        try:
            # Obtém conexão
            conn = self.connection()
            if not conn:
                raise Exception("Nenhuma conexão ativa")
            
            cursor = conn.cursor()
            
            # Verifica tabelas - lista de tabelas mínimas necessárias
            required_tables = ["app_info", "games", "roms"]
            
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
            """)
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # Verifica se pelo menos uma das tabelas principais existe
            # Em vez de exigir todas as tabelas, verificamos se pelo menos uma existe
            found_tables = [table for table in required_tables if table in existing_tables]
            if not found_tables:
                logging.warning(f"Nenhuma tabela principal encontrada. Tabelas existentes: {existing_tables}")
                # Não levanta exceção, apenas registra o aviso
            else:
                logging.info(f"Tabelas encontradas: {found_tables}")
            
            # Verifica versão de forma mais flexível
            version_found = False
            schema_version = None
            
            # Tenta obter versão da tabela app_info
            if "app_info" in existing_tables:
                try:
                    cursor.execute("""
                        SELECT value FROM app_info
                        WHERE key = 'schema_version' OR key = 'version'
                    """)
                    row = cursor.fetchone()
                    if row:
                        schema_version = row[0]
                        version_found = True
                        logging.info(f"Versão do esquema encontrada em app_info: {schema_version}")
                except Exception as e:
                    logging.warning(f"Erro ao verificar versão em app_info: {str(e)}")
            
            # Se não encontrou na app_info, tenta na tabela info
            if not version_found and "info" in existing_tables:
                try:
                    cursor.execute("""
                        SELECT value FROM info
                        WHERE key = 'version' OR key = 'schema_version'
                    """)
                    row = cursor.fetchone()
                    if row:
                        schema_version = row[0]
                        version_found = True
                        logging.info(f"Versão do esquema encontrada em info: {schema_version}")
                except Exception as e:
                    logging.warning(f"Erro ao verificar versão em info: {str(e)}")
            
            # Se ainda não encontrou, tenta outras abordagens comuns
            if not version_found and "version" in existing_tables:
                try:
                    cursor.execute("SELECT version FROM version LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        schema_version = row[0]
                        version_found = True
                        logging.info(f"Versão do esquema encontrada em tabela version: {schema_version}")
                except Exception as e:
                    logging.warning(f"Erro ao verificar tabela version: {str(e)}")
            
            # Registra se não encontrou versão, mas não levanta exceção
            if not version_found:
                logging.warning("Versão do banco não encontrada em nenhuma tabela conhecida")
            
            # TODO: Implementar atualizações de estrutura se necessário
            
            return True
            
        except Exception as e:
            logging.error(f"Erro ao verificar estrutura: {str(e)}", exc_info=True)
            # Não propaga a exceção, apenas registra o erro
            return False
    
    def get_tables(self) -> List[str]:
        """
        Obtém lista de tabelas.
        
        Returns:
            List[str]: Lista de tabelas
        """
        try:
            if not self.connection():
                return []
            
            query = """
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """
            
            results = self.execute_query(query)
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Erro ao obter tabelas: {str(e)}")
            return []
    
    def get_table_info(self, table: str) -> List[tuple]:
        """
        Obtém informações de uma tabela.
        
        Args:
            table: Nome da tabela
        
        Returns:
            List[tuple]: Lista de colunas
        """
        try:
            if not self.connection():
                return []
            
            query = f"PRAGMA table_info({table})"
            return self.execute_query(query)
            
        except Exception as e:
            logger.error(f"Erro ao obter informações da tabela: {str(e)}")
            return []
    
    def table_exists(self, table: str) -> bool:
        """
        Verifica se uma tabela existe.
        
        Args:
            table: Nome da tabela
        
        Returns:
            bool: True se existe
        """
        try:
            if not self.connection():
                return False
            
            query = """
                SELECT COUNT(*) FROM sqlite_master
                WHERE type='table' AND name=?
            """
            
            result = self.execute_query(query, (table,))
            return result[0][0] > 0
            
        except Exception as e:
            logger.error(f"Erro ao verificar tabela: {str(e)}")
            return False
    
    def get_row_count(self, table: str) -> int:
        """
        Obtém número de registros em uma tabela.
        
        Args:
            table: Nome da tabela
        
        Returns:
            int: Número de registros
        """
        try:
            if not self.connection():
                return 0
            
            query = f"SELECT COUNT(*) FROM {table}"
            result = self.execute_query(query)
            return result[0][0]
            
        except Exception as e:
            logger.error(f"Erro ao contar registros: {str(e)}")
            return 0
    
    def execute_many(
        self,
        query: str,
        params: List[Tuple]
    ) -> bool:
        """
        Executa várias consultas.
        
        Args:
            query: Consulta SQL
            params: Lista de parâmetros
            
        Returns:
            True se executado com sucesso
        """
        try:
            if not self.connection():
                return False
            
            conn = self.connection()
            with conn:
                conn.executemany(query, params)
                return True
            
        except Exception as e:
            logging.error(
                f"Erro ao executar consultas: {str(e)}",
                exc_info=True
            )
            return False
    
    def __enter__(self):
        """Suporte a context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fecha conexões ao sair do contexto."""
        self.close_all()