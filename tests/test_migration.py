#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testes para o sistema de migração de banco de dados v2
"""

import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import UnifiedDatabaseManager as DatabaseManagerV2, DatabaseConfig
from scripts.migrate_to_v2 import MigrationTool as MigrationManager # Renomeado para compatibilidade com o teste
import sqlite3


class TestMigration(unittest.TestCase):
    """Testes para o sistema de migração."""
    
    def setUp(self):
        """Configuração inicial para cada teste."""
        self.temp_dir = tempfile.mkdtemp()
        self.old_db_path = os.path.join(self.temp_dir, "old_megaemu.db")
        self.new_db_path = os.path.join(self.temp_dir, "new_megaemu.db")
        
    def tearDown(self):
        """Limpeza após cada teste."""
        shutil.rmtree(self.temp_dir)
        
    def create_old_database(self):
        """Cria um banco de dados no formato antigo."""
        conn = sqlite3.connect(self.old_db_path)
        cursor = conn.cursor()
        
        # Cria tabelas no formato antigo
        cursor.execute("""
            CREATE TABLE roms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rom_filename TEXT NOT NULL,
                system TEXT,
                size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)
        
        # Insere dados de teste
        cursor.executemany(
            "INSERT INTO roms (name, rom_filename, system, size) VALUES (?, ?, ?, ?)",
            [
                ("Super Mario World", "smw.smc", "SNES", 2048),
                ("Sonic the Hedgehog", "sonic.md", "Genesis", 1024),
                ("Tetris", "tetris.gb", "Game Boy", 512)
            ]
        )
        
        cursor.executemany(
            "INSERT INTO systems (name, description) VALUES (?, ?)",
            [
                ("SNES", "Super Nintendo Entertainment System"),
                ("Genesis", "Sega Genesis"),
                ("Game Boy", "Nintendo Game Boy")
            ]
        )
        
        conn.commit()
        conn.close()
        
    def test_migration_success(self):
        """Testa migração bem-sucedida."""
        self.create_old_database()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        success = migration.migrate()
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.new_db_path))
        
        # Verifica se os dados foram migrados
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM roms")
        rom_count = cursor.fetchone()[0]
        self.assertEqual(rom_count, 3)
        
        cursor.execute("SELECT COUNT(*) FROM systems")
        system_count = cursor.fetchone()[0]
        self.assertEqual(system_count, 3)
        
        # Verifica se a coluna foi renomeada corretamente
        cursor.execute("PRAGMA table_info(roms)")
        columns = [col[1] for col in cursor.fetchall()]
        self.assertIn("filename", columns)
        self.assertNotIn("rom_filename", columns)
        
        conn.close()
        
    def test_migration_with_existing_v2(self):
        """Testa migração quando já existe um banco v2."""
        self.create_old_database()
        
        # Cria um banco v2 existente
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE roms (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        success = migration.migrate(force=False)
        
        # Deve falhar sem --force
        self.assertFalse(success)
        
    def test_migration_force(self):
        """Testa migração com flag --force."""
        self.create_old_database()
        
        # Cria um banco v2 existente
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE roms (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        success = migration.migrate(force=True)
        
        # Deve suceder com --force
        self.assertTrue(success)
        
    def test_migration_data_integrity(self):
        """Testa integridade dos dados após migração."""
        self.create_old_database()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        migration.migrate()
        
        # Verifica integridade dos dados
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.name, r.filename, s.name
            FROM roms r
            JOIN systems s ON r.system_id = s.id
            ORDER BY r.id
        """)
        
        results = cursor.fetchall()
        expected = [
            ("Super Mario World", "smw.smc", "SNES"),
            ("Sonic the Hedgehog", "sonic.md", "Genesis"),
            ("Tetris", "tetris.gb", "Game Boy")
        ]
        
        self.assertEqual(results, expected)
        conn.close()
        
    def test_migration_backup(self):
        """Testa criação de backup durante migração."""
        self.create_old_database()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        migration.migrate()
        
        # Verifica se o backup foi criado
        backup_path = self.old_db_path + ".backup"
        self.assertTrue(os.path.exists(backup_path))
        
    def test_migration_empty_database(self):
        """Testa migração de banco vazio."""
        # Cria banco vazio
        conn = sqlite3.connect(self.old_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE roms (id INTEGER PRIMARY KEY)")
        cursor.execute("CREATE TABLE systems (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        migration = MigrationManager(self.old_db_path, self.new_db_path)
        success = migration.migrate()
        
        self.assertTrue(success)
        
        # Verifica estrutura
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM roms")
        self.assertEqual(cursor.fetchone()[0], 0)
        
        cursor.execute("SELECT COUNT(*) FROM systems")
        self.assertEqual(cursor.fetchone()[0], 0)
        
        conn.close()


class TestDatabaseV2(unittest.TestCase):
    """Testes para o novo sistema de banco de dados."""
    
    def setUp(self):
        """Configuração inicial."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
    def tearDown(self):
        """Limpeza."""
        shutil.rmtree(self.temp_dir)
        
    def test_database_connection(self):
        """Testa conexão com o banco v2."""
        config = DatabaseConfig.testing()
        db = DatabaseManagerV2(config)
        
        success = db.connect(self.db_path)
        self.assertTrue(success)
        
        # Verifica health check
        health = db.health_check()
        self.assertTrue(health['pool_healthy'])
        
        db.close_all()
        
    def test_pool_management(self):
        """Testa gerenciamento do pool de conexões."""
        config = DatabaseConfig.testing()
        config.pool.max_connections = 3
        
        db = DatabaseManagerV2(config)
        db.connect(self.db_path)
        
        # Obtém múltiplas conexões
        connections = []
        for i in range(3):
            conn = db.get_connection()
            connections.append(conn)
            
        # Verifica limite
        with self.assertRaises(Exception):
            db.get_connection()
            
        # Libera conexões
        for conn in connections:
            conn.close()
            
        db.close_all()
        
    def test_retry_mechanism(self):
        """Testa mecanismo de retry."""
        config = DatabaseConfig.testing()
        config.retry.max_attempts = 3
        
        db = DatabaseManagerV2(config)
        db.connect(self.db_path)
        
        # Testa operação bem-sucedida
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.commit()
            
        db.close_all()


if __name__ == "__main__":
    unittest.main()
