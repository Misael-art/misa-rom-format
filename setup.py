#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de instalação e configuração do MegaEmu DataBase ROMs v2
"""

import os
import sys
import shutil
import logging
from pathlib import Path
import json
import subprocess

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MegaEmuSetup:
    """Classe responsável pela instalação e configuração do sistema."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.backup_dir = self.base_dir / "backup"
        
    def create_directories(self):
        """Cria estrutura de diretórios necessária."""
        directories = [
            self.data_dir,
            self.data_dir / "databases",
            self.data_dir / "exports",
            self.data_dir / "imports",
            self.data_dir / "extracted",
            self.config_dir,
            self.backup_dir,
            self.backup_dir / "databases",
            self.backup_dir / "media",
            self.backup_dir / "debug"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Diretório criado: {directory}")
            
    def check_dependencies(self):
        """Verifica dependências do sistema."""
        dependencies = {
            "sqlite3": "sqlite3",
            "python": sys.version
        }
        
        logger.info("Verificando dependências...")
        
        # Verifica SQLite
        try:
            import sqlite3
            logger.info(f"SQLite: {sqlite3.sqlite_version}")
        except ImportError:
            logger.error("SQLite não está disponível")
            return False
            
        # Verifica versão do Python
        if sys.version_info < (3, 8):
            logger.error("Python 3.8 ou superior é necessário")
            return False
            
        logger.info(f"Python: {sys.version}")
        return True
        
    def create_default_config(self):
        """Cria arquivo de configuração padrão."""
        config_path = self.config_dir / "database.json"
        
        if config_path.exists():
            logger.info("Configuração já existe, pulando...")
            return
            
        default_config = {
            "database_path": "data/megaemu.db",
            "backup_enabled": True,
            "backup_interval_hours": 24,
            "max_backups": 10,
            "pool": {
                "max_connections": 20,
                "timeout": 30.0,
                "health_check_interval": 300,
                "max_idle_time": 3600
            },
            "retry": {
                "max_attempts": 5,
                "base_delay": 0.5,
                "max_delay": 10.0,
                "jitter": True,
                "backoff_multiplier": 2.0
            },
            "cache_size": 20000,
            "synchronous": "normal",
            "journal_mode": "wal",
            "temp_store": "memory",
            "mmap_size": 268435456,
            "log_queries": False,
            "log_slow_queries": True,
            "slow_query_threshold": 1.0,
            "log_level": "INFO",
            "metrics_enabled": True,
            "metrics_retention_days": 30
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
            
        logger.info(f"Configuração criada: {config_path}")
        
    def run_tests(self):
        """Executa testes de integração."""
        logger.info("Executando testes...")
        
        test_dir = self.base_dir / "tests"
        if not test_dir.exists():
            logger.warning("Diretório de testes não encontrado")
            return
            
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_dir), "-v"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Todos os testes passaram!")
            else:
                logger.warning("Alguns testes falharam")
                logger.warning(result.stdout)
                
        except FileNotFoundError:
            # Executa com unittest se pytest não estiver disponível
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", str(test_dir), "-v"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Todos os testes passaram!")
            else:
                logger.warning("Alguns testes falharam")
                
    def create_startup_script(self):
        """Cria script de inicialização."""
        script_content = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de inicialização do MegaEmu DataBase ROMs
"""


# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from engine.db import UnifiedDatabaseManager as DatabaseManagerV2, DatabaseConfig

def main():
    """Função principal de inicialização."""
    print("Inicializando MegaEmu DataBase ROMs v2...")
    
    # Carrega configuração
    config_path = Path("config/database.json")
    if config_path.exists():
        with open(config_path) as f:
            config_data = json.load(f)
        config = DatabaseConfig(**config_data)
    else:
        config = DatabaseConfig()
    
    # Inicializa banco de dados
    db = DatabaseManagerV2(config)
    
    # Testa conexão
    if db.connect("data/megaemu.db"):
        print("✓ Banco de dados conectado com sucesso")
        
        # Verifica saúde
        health = db.health_check()
        if health['pool_healthy']:
            print("✓ Pool de conexões saudável")
        else:
            print("⚠ Pool de conexões com problemas")
            
        db.close_all()
    else:
        print("✗ Falha ao conectar ao banco de dados")
        return 1
    
    print("Sistema pronto para uso!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        script_path = self.base_dir / "start.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
            
        # Torna executável no Unix
        if os.name != 'nt':
            os.chmod(script_path, 0o755)
            
        logger.info(f"Script de inicialização criado: {script_path}")
        
    def install(self):
        """Executa instalação completa."""
        logger.info("Iniciando instalação do MegaEmu DataBase ROMs v2...")
        
        try:
            # Verifica dependências
            if not self.check_dependencies():
                return False
                
            # Cria estrutura
            self.create_directories()
            
            # Configuração padrão
            self.create_default_config()
            
            # Script de inicialização
            self.create_startup_script()
            
            # Executa testes
            self.run_tests()
            
            logger.info("Instalação concluída com sucesso!")
            logger.info("Use 'python start.py' para iniciar o sistema")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro durante instalação: {e}")
            return False


def main():
    """Função principal."""
    setup = MegaEmuSetup()
    success = setup.install()
    
    if success:
        print("\n" + "="*50)
        print("MegaEmu DataBase ROMs v2 - Instalação Concluída")
        print("="*50)
        print("\nPróximos passos:")
        print("1. Execute 'python start.py' para testar o sistema")
        print("2. Configure 'config/database.json' conforme necessário")
        print("3. Importe seus arquivos de ROM")
        print("\nPara migração de dados antigos:")
        print("python scripts/migrate_to_v2.py data/megaemu.db data/megaemu_v2.db")
    else:
        print("\nInstalação falhou. Verifique os logs acima.")
        sys.exit(1)


if __name__ == "__main__":
    main()