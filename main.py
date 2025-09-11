#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Aplicativo principal.
"""

import re
import os
import sys
import logging
from datetime import datetime
from typing import NoReturn, Optional
from pathlib import Path
import sqlite3

from constants import *
from engine import (
    AppConfig,
    ThemeManager,
    MainWindow
)
from engine.errors import (
    DatabaseError,
    ConfigError,
    ThemeError,
    MegaEmuError,
    MigrationError
)
from engine.db import (
    DatabaseManagerV2,
    DatabaseConfig,
    MigrationManager
)
class SecureFormatter(logging.Formatter):
    """Formatter personalizado que mascara dados sensíveis em logs."""

    # Padrões para mascarar
    SENSITIVE_PATTERNS = [
        # Caminhos absolutos de arquivo/diretório
        (r'(/[a-zA-Z0-9_/-]+)', '/****'),  # Unix/Linux paths
        (r'([A-Za-z]:\\[a-zA-Z0-9_\\-]+)', '****'),  # Windows paths
        # Hashes (MD5, SHA1, SHA256, CRC32)
        (r'\b[a-fA-F0-9]{32}\b', '****'),  # MD5
        (r'\b[a-fA-F0-9]{40}\b', '****'),  # SHA1
        (r'\b[a-fA-F0-9]{64}\b', '****'),  # SHA256
        (r'\b[a-fA-F0-9]{8}\b', '****'),  # CRC32
        # Senhas (palavras-chave comuns)
        (r'(?i)(password|senha|passwd|pwd)\s*[:=]\s*\S+', r'\1: ****'),
        # Chaves API
        (r'(?i)(api_key|apikey|token|secret)\s*[:=]\s*\S+', r'\1: ****'),
    ]

    def format(self, record):
        """Formata o log record mascarando dados sensíveis."""
        message = super().format(record)

        # Aplica mascaramento
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, replacement, message)

        return message


def setup_logging() -> None:
    """Configura logging com tratamento robusto de erros."""
    try:
        # Cria diretório de logs com tratamento de permissões
        log_dir = Path("logs")
        try:
            log_dir.mkdir(exist_ok=True, parents=True)
        except PermissionError as e:
            # Tenta criar em diretório temporário se não tiver permissão
            log_dir = Path.home() / ".megaemu" / "logs"
            log_dir.mkdir(exist_ok=True, parents=True)
            print(f"Aviso: Usando diretório de logs alternativo: {log_dir}")
        
        # Nome do arquivo de log
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Cria formatter seguro
        secure_formatter = SecureFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        )

        # Configura handlers com formatter seguro
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(secure_formatter)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(secure_formatter)

        # Configura logging estruturado
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, stream_handler]
        )
        
        # Configura níveis específicos
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('PIL').setLevel(logging.WARNING)
        
        logging.info("Sistema de logging inicializado com sucesso")
        logging.info(f"Arquivo de log: {log_file}")
        
    except (OSError, PermissionError) as e:
        print(f"Erro crítico ao configurar logging: {str(e)}")
        # Fallback para logging básico com formatter seguro
        secure_formatter_fallback = SecureFormatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s"
        )

        stream_handler_fallback = logging.StreamHandler(sys.stdout)
        stream_handler_fallback.setFormatter(secure_formatter_fallback)

        logging.basicConfig(
            level=logging.WARNING,
            handlers=[stream_handler_fallback]
        )
        logging.error(f"Falha ao configurar logging completo: {e}")
    except Exception as e:
        print(f"Erro inesperado ao configurar logging: {str(e)}")
        sys.exit(1)

def main() -> NoReturn:
    """Função principal com tratamento de erros robusto."""
    try:
        # Configura logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        logger.info("Iniciando MegaEmu DataBase ROMs")
        
        # Valida ambiente
        if not validate_environment():
            sys.exit(1)
        
        # Carrega configuração do banco de dados
        db_config = DatabaseConfig.from_file("config/database.json")
        
        # Cria instância do novo DatabaseManagerV2
        try:
            db_manager: DatabaseManagerV2 = DatabaseManagerV2(db_config)
            logger.info("DatabaseManagerV2 inicializado")
        except DatabaseError as e:
            logger.error(f"Erro ao inicializar DatabaseManagerV2: {e}")
            sys.exit(1)
        
        # Conecta ao banco de dados
        try:
            if not db_manager.connect(db_config.database_path):
                logger.error("Falha ao conectar ao banco de dados. Encerrando.")
                sys.exit(1)
            logger.info(f"Conectado ao banco de dados: {db_config.database_path}")
        except DatabaseError as e:
            logger.error(f"Erro ao conectar ao banco de dados: {e}")
            sys.exit(1)
        
        # Realiza migração do banco de dados
        try:
            migration_manager = MigrationManager(db_config.database_path)
            migration_manager.create_migration_table()
            
            # Verifica se há migrações pendentes
            current_version = migration_manager.get_current_version()
            logger.info(f"Versão atual do banco: {current_version or 'nenhuma'}")
            
            # Valida integridade das migrações
            valid, problems = migration_manager.validate_integrity()
            if not valid:
                logger.warning("Problemas encontrados nas migrações:")
                for problem in problems:
                    logger.warning(f"  - {problem}")
            
            logger.info("Sistema de migrações inicializado")
        except MigrationError as e:
            logger.error(f"Erro durante migração: {e}", exc_info=True)
            sys.exit(1)
        except Exception as e:
            logger.error(f"Erro inesperado durante migração: {e}", exc_info=True)
            sys.exit(1)

        # Configuração da aplicação
        try:
            app_config: AppConfig = AppConfig()
            logger.info("AppConfig carregado")
        except ConfigError as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            sys.exit(1)
        
        try:
            theme_manager: ThemeManager = ThemeManager()
            logger.info("ThemeManager inicializado")
        except ThemeError as e:
            logger.error(f"Erro ao inicializar ThemeManager: {e}")
            theme_manager = ThemeManager()  # Fallback para tema padrão
        
        # Aplica tema
        try:
            theme: str = app_config.get("theme", "light")
            theme_manager.apply_theme(theme)
            logger.info(f"Tema aplicado: {theme}")
        except ThemeError as e:
            logger.warning(f"Erro ao aplicar tema '{theme}': {e}")
            theme_manager.apply_theme("light")  # Fallback
        
        # Cria janela principal
        try:
            window: MainWindow = MainWindow(
                db_manager=db_manager, # Passa o novo db_manager
                app_config=app_config,
                theme_manager=theme_manager
            )
            logger.info("Janela principal criada")
        except MegaEmuError as e:
            logger.error(f"Erro ao criar janela principal: {e}")
            sys.exit(1)
        
        # Configura handlers para exceções não tratadas
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                logger.info("Aplicação interrompida pelo usuário")
                return
            
            logger.error(
                "Exceção não tratada",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
            # Mostra mensagem ao usuário se possível
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "Erro Fatal",
                    f"Ocorreu um erro inesperado:\n{str(exc_value)}\n\n"
                    f"Verifique os logs para mais detalhes."
                )
                root.destroy()
            except:
                pass
        
        sys.excepthook = handle_exception
        
        # Inicia aplicativo
        logger.info("Iniciando loop principal")
        window.mainloop()
        
    except KeyboardInterrupt:
        logger.info("Aplicação interrompida pelo usuário (Ctrl+C)")
        sys.exit(0)
    except MegaEmuError as e:
        logger.error(f"Erro da aplicação: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro fatal não tratado: {e}", exc_info=True)
        sys.exit(1)

def validate_environment() -> bool:
    """Valida se o ambiente está adequado para execução."""
    try:
        # Verifica versão do Python
        if sys.version_info < PYTHON_MIN_VERSION:
            logging.error("Python 3.8 ou superior é necessário")
            return False

        # Verifica espaço em disco mínimo
        import shutil
        current_dir = Path.cwd()
        total, used, free = shutil.disk_usage(current_dir)
        free_mb = free // BYTES_TO_MB

        if free_mb < MIN_DISK_SPACE_MB:
            logging.error(f"Espaço em disco insuficiente: {free_mb}MB disponíveis (mínimo {MIN_DISK_SPACE_MB}MB)")
            return False
        
        # Verifica permissões de escrita
        test_file = Path("write_test.tmp")
        try:
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError):
            logging.error("Sem permissão de escrita no diretório atual")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"Erro ao validar ambiente: {e}")
        return False

if __name__ == "__main__":
    main()