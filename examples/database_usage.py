#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Exemplos de Uso do Sistema v2
Demonstração completa das funcionalidades do novo sistema de banco de dados
"""

import os
import sys
import time
import logging
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import (
    DatabaseManagerV2,
    DatabaseConfig,
    default_metrics_collector
)

# Configura logging para demonstração
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseUsageExample:
    """Classe de exemplo demonstrando o uso do sistema v2."""
    
    def __init__(self, db_path: str = "data/example.db"):
        self.db_path = db_path
        self.db = None
        
    def setup_database(self):
        """Configura o banco de dados com exemplo."""
        logger.info("Configurando banco de dados...")
        
        # Configuração personalizada para demonstração
        config = DatabaseConfig(
            database_path=self.db_path,
            pool_max_connections=10,
            pool_timeout=5.0,
            retry_max_attempts=3,
            log_slow_queries=True,
            slow_query_threshold=0.1
        )
        
        self.db = DatabaseManagerV2(config)
        
        # Conecta ao banco
        if not self.db.connect(self.db_path):
            raise RuntimeError("Falha ao conectar ao banco de dados")
        
        # Cria tabelas de exemplo
        self._create_tables()
        
    def _create_tables(self):
        """Cria tabelas de exemplo."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela de sistemas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS systems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de ROMs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    system_id INTEGER,
                    size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (system_id) REFERENCES systems (id)
                )
            """)
            
            conn.commit()
            logger.info("Tabelas criadas com sucesso")
    
    def insert_sample_data(self):
        """Insere dados de exemplo."""
        logger.info("Inserindo dados de exemplo...")
        
        systems = [
            ("Super Nintendo", "Console 16-bit da Nintendo"),
            ("PlayStation", "Console 32-bit da Sony"),
            ("Game Boy", "Console portátil da Nintendo")
        ]
        
        roms = [
            ("Super Mario World", "smw.smc", 1, 2048),
            ("Final Fantasy VII", "ff7.iso", 2, 650000),
            ("Pokémon Red", "pokemon_red.gb", 3, 512),
            ("The Legend of Zelda", "zelda.smc", 1, 1024),
            ("Metal Gear Solid", "mgs.iso", 2, 700000)
        ]
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Inserir sistemas
            cursor.executemany(
                "INSERT INTO systems (name, description) VALUES (?, ?)",
                systems
            )
            
            # Inserir ROMs
            cursor.executemany(
                "INSERT INTO roms (name, filename, system_id, size) VALUES (?, ?, ?, ?)",
                roms
            )
            
            conn.commit()
            logger.info("Dados de exemplo inseridos")
    
    def query_examples(self):
        """Demonstra diferentes tipos de queries."""
        logger.info("Executando exemplos de queries...")
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Query simples
            cursor.execute("SELECT COUNT(*) FROM roms")
            total_roms = cursor.fetchone()[0]
            logger.info(f"Total de ROMs: {total_roms}")
            
            # Query com JOIN
            cursor.execute("""
                SELECT r.name, r.filename, s.name as system_name
                FROM roms r
                JOIN systems s ON r.system_id = s.id
                ORDER BY s.name, r.name
            """)
            
            results = cursor.fetchall()
            logger.info("ROMs por sistema:")
            for name, filename, system in results:
                logger.info(f"  {system}: {name} ({filename})")
            
            # Query com filtro
            cursor.execute("""
                SELECT name, size
                FROM roms
                WHERE size > 1000
                ORDER BY size DESC
            """)
            
            large_roms = cursor.fetchall()
            logger.info("ROMs grandes:")
            for name, size in large_roms:
                logger.info(f"  {name}: {size} KB")
    
    def performance_test(self):
        """Testa performance com operações em lote."""
        logger.info("Executando teste de performance...")
        
        start_time = time.time()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Inserir 1000 registros em lote
            batch_data = [
                (f"ROM {i}", f"file_{i}.rom", (i % 3) + 1, i * 100)
                for i in range(1000)
            ]
            
            cursor.executemany(
                "INSERT INTO roms (name, filename, system_id, size) VALUES (?, ?, ?, ?)",
                batch_data
            )
            conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"1000 registros inseridos em {elapsed:.2f} segundos")
    
    def monitor_performance(self):
        """Monitora performance do sistema."""
        logger.info("Monitorando performance...")
        
        # Executar algumas queries
        for i in range(10):
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM roms WHERE system_id = ?", (i % 3 + 1,))
                count = cursor.fetchone()[0]
        
        # Obter métricas
        metrics = default_metrics_collector.get_performance_summary()
        logger.info("Métricas de performance:")
        logger.info(f"  Total queries: {metrics['stats']['total_queries']}")
        logger.info(f"  Success rate: {metrics['stats']['success_rate']}%")
        logger.info(f"  Average time: {metrics['stats']['average_query_time']:.4f}s")
        logger.info(f"  Pool size: {metrics['pool']['active_connections']}/{metrics['pool']['max_connections']}")
    
    def health_check_demo(self):
        """Demonstra verificação de saúde."""
        logger.info("Verificando saúde do sistema...")
        
        health = self.db.health_check()
        logger.info("Status de saúde:")
        logger.info(f"  Pool healthy: {health['pool_healthy']}")
        logger.info(f"  Active connections: {health['active_connections']}")
        logger.info(f"  Available connections: {health['available_connections']}")
        logger.info(f"  Total connections: {health['total_connections']}")
    
    def error_handling_demo(self):
        """Demonstra tratamento de erros."""
        logger.info("Demonstrando tratamento de erros...")
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                # Tentar inserir duplicado
                cursor.execute(
                    "INSERT INTO systems (name, description) VALUES (?, ?)",
                    ("Super Nintendo", "Duplicado")
                )
                conn.commit()
        except Exception as e:
            logger.info(f"Erro capturado (esperado): {e}")
    
    def cleanup(self):
        """Limpa recursos."""
        if self.db:
            self.db.close_all()
            logger.info("Conexões fechadas")
    
    def run_all_examples(self):
        """Executa todos os exemplos."""
        try:
            self.setup_database()
            self.insert_sample_data()
            self.query_examples()
            self.performance_test()
            self.monitor_performance()
            self.health_check_demo()
            self.error_handling_demo()
            
            logger.info("Todos os exemplos executados com sucesso!")
            
        finally:
            self.cleanup()

def main():
    """Função principal."""
    # Criar diretório de dados se não existir
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Executar exemplos
    example = DatabaseUsageExample()
    example.run_all_examples()

if __name__ == "__main__":
    main()