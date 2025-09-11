#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Cleanup Obsolete Files
Script para remover arquivos obsoletos identificados na auditoria suprema.

Este script remove com segurança:
- Pasta backup/ completa (40+ arquivos antigos)
- Arquivos de log antigos
- Arquivos de teste temporários
- Arquivos de backup de banco de dados antigos
- Outros arquivos não utilizados
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Set
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent

# Arquivos e diretórios para remoção
OBSOLETE_DIRECTORIES = [
    'backup',           # Pasta backup completa (40+ arquivos antigos)
    'obsolete_backup',  # Pasta de backup obsoleto
    'htmlcov',          # Coverage HTML reports antigos
    '.pytest_cache',    # Cache do pytest
    'test_compression', # Testes de compressão temporários
    'test_integration', # Testes de integração temporários
]

OBSOLETE_FILES = [
    # Arquivos de log antigos
    'app_debug.log.1',
    'app_debug.log.2', 
    'app_debug.log.3',
    'debug_ps1_log.txt',
    'batch_import_log.txt',
    'import_log.txt',
    'test_output.txt',
    'test_results.txt',
    
    # Arquivos de teste temporários
    'test_phase2.db-shm',
    'test_phase2.db-wal',
    'test_phase2.db.backup_20250602_102338',
    
    # Arquivos de backup antigos
    'data/default.db.backup_20250909_111918',
    
    # Scripts temporários e de teste
    'fix.py',  # Arquivo vazio identificado
    'fix_line.txt',
    'according_file.py',
    'reorganize_project.py',
    'check_dependencies.py',
    'check_schema.py',
    'test_migration.py',
    'test_performance.py',
    'test_regex.py',
    'test_tkinter.py',
    'test_schema_validation.py',
    'test_phase2_integration.py',
    'test_phase3_integration.py',
    'schema_migration.py',
    'setup_directories.py',
    'monitor.py',
    'monitor_app.py',
    'run.py',
    'run_app.py',
    'run_tests.py',
    'fix_exception_handling.py',
    
    # Arquivos de configuração duplicados
    'config.json',  # Duplicado com config/app_config.json
    
    # Documentos temporários
    'plano.md',
    'Prompt - Infor.txt',
]

# Padrões de arquivos para remoção
OBSOLETE_PATTERNS = [
    '*.log',
    '*.tmp',
    '*.temp',
    '*.bak',
    '*.old',
    '*~',
    '.DS_Store',
    'Thumbs.db',
    '*.pyc',
    '__pycache__',
]

# Arquivos críticos que NUNCA devem ser removidos
CRITICAL_FILES = {
    'main.py',
    'app.py', 
    'requirements.txt',
    'requirements-test.txt',
    'pyproject.toml',
    'pytest.ini',
    'mypy.ini',
    'setup.py',
    'README.md',
    'LICENSE',
    '.gitignore',
    'constants.py',
}

# Diretórios críticos que NUNCA devem ser removidos
CRITICAL_DIRECTORIES = {
    'engine',
    'ui',
    'tests',
    'docs',
    'config',
    'data',
    'meta',
    'scripts',
    'assets',
    'examples',
    'MISAROM',
    '.github',
    '.trae',
}


class ObsoleteFileCleaner:
    """Limpador de arquivos obsoletos."""
    
    def __init__(self, project_root: Path, dry_run: bool = True):
        """
        Inicializa o limpador.
        
        Args:
            project_root: Diretório raiz do projeto
            dry_run: Se True, apenas simula a remoção
        """
        self.project_root = project_root
        self.dry_run = dry_run
        self.removed_files: List[str] = []
        self.removed_dirs: List[str] = []
        self.errors: List[str] = []
        
        logger.info(f"Inicializando limpeza {'(DRY RUN)' if dry_run else '(REAL)'}")
        logger.info(f"Diretório do projeto: {project_root}")
    
    def is_safe_to_remove(self, path: Path) -> bool:
        """
        Verifica se é seguro remover um arquivo/diretório.
        
        Args:
            path: Caminho a verificar
            
        Returns:
            True se for seguro remover
        """
        # Verifica se é arquivo/diretório crítico
        if path.name in CRITICAL_FILES or path.name in CRITICAL_DIRECTORIES:
            return False
        
        # Verifica se está dentro de diretório crítico
        for critical_dir in CRITICAL_DIRECTORIES:
            if critical_dir in path.parts:
                # Permite remoção apenas de arquivos específicos dentro de diretórios críticos
                if path.is_file() and path.name in OBSOLETE_FILES:
                    return True
                return False
        
        return True
    
    def remove_obsolete_directories(self):
        """Remove diretórios obsoletos."""
        logger.info("Removendo diretórios obsoletos...")
        
        for dir_name in OBSOLETE_DIRECTORIES:
            dir_path = self.project_root / dir_name
            
            if not dir_path.exists():
                logger.debug(f"Diretório não existe: {dir_path}")
                continue
            
            if not self.is_safe_to_remove(dir_path):
                logger.warning(f"Diretório crítico, pulando: {dir_path}")
                continue
            
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Removeria diretório: {dir_path}")
                    # Conta arquivos que seriam removidos
                    file_count = sum(1 for _ in dir_path.rglob('*') if _.is_file())
                    logger.info(f"[DRY RUN] Contém {file_count} arquivos")
                else:
                    logger.info(f"Removendo diretório: {dir_path}")
                    shutil.rmtree(dir_path)
                    logger.info(f"Diretório removido: {dir_path}")
                
                self.removed_dirs.append(str(dir_path))
                
            except Exception as e:
                error_msg = f"Erro ao remover diretório {dir_path}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def remove_obsolete_files(self):
        """Remove arquivos obsoletos específicos."""
        logger.info("Removendo arquivos obsoletos...")
        
        for file_name in OBSOLETE_FILES:
            file_path = self.project_root / file_name
            
            if not file_path.exists():
                logger.debug(f"Arquivo não existe: {file_path}")
                continue
            
            if not self.is_safe_to_remove(file_path):
                logger.warning(f"Arquivo crítico, pulando: {file_path}")
                continue
            
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Removeria arquivo: {file_path}")
                    # Mostra tamanho do arquivo
                    size = file_path.stat().st_size
                    logger.info(f"[DRY RUN] Tamanho: {size} bytes")
                else:
                    logger.info(f"Removendo arquivo: {file_path}")
                    file_path.unlink()
                    logger.info(f"Arquivo removido: {file_path}")
                
                self.removed_files.append(str(file_path))
                
            except Exception as e:
                error_msg = f"Erro ao remover arquivo {file_path}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def remove_files_by_pattern(self):
        """Remove arquivos por padrão."""
        logger.info("Removendo arquivos por padrão...")
        
        for pattern in OBSOLETE_PATTERNS:
            logger.debug(f"Procurando arquivos com padrão: {pattern}")
            
            for file_path in self.project_root.rglob(pattern):
                # Pula diretórios
                if file_path.is_dir():
                    continue
                
                # Verifica se é seguro remover
                if not self.is_safe_to_remove(file_path):
                    logger.debug(f"Arquivo crítico, pulando: {file_path}")
                    continue
                
                # Pula arquivos já listados especificamente
                if file_path.name in OBSOLETE_FILES:
                    continue
                
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Removeria arquivo (padrão {pattern}): {file_path}")
                    else:
                        logger.info(f"Removendo arquivo (padrão {pattern}): {file_path}")
                        file_path.unlink()
                        logger.info(f"Arquivo removido: {file_path}")
                    
                    self.removed_files.append(str(file_path))
                    
                except Exception as e:
                    error_msg = f"Erro ao remover arquivo {file_path}: {e}"
                    logger.error(error_msg)
                    self.errors.append(error_msg)
    
    def clean_empty_directories(self):
        """Remove diretórios vazios."""
        logger.info("Removendo diretórios vazios...")
        
        # Procura diretórios vazios (bottom-up)
        for dir_path in sorted(self.project_root.rglob('*'), reverse=True):
            if not dir_path.is_dir():
                continue
            
            # Verifica se é diretório crítico
            if not self.is_safe_to_remove(dir_path):
                continue
            
            try:
                # Verifica se está vazio
                if not any(dir_path.iterdir()):
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Removeria diretório vazio: {dir_path}")
                    else:
                        logger.info(f"Removendo diretório vazio: {dir_path}")
                        dir_path.rmdir()
                        logger.info(f"Diretório vazio removido: {dir_path}")
                    
                    self.removed_dirs.append(str(dir_path))
                    
            except Exception as e:
                error_msg = f"Erro ao remover diretório vazio {dir_path}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def generate_report(self) -> str:
        """Gera relatório da limpeza."""
        report = []
        report.append("=" * 60)
        report.append(f"RELATÓRIO DE LIMPEZA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Modo: {'DRY RUN (Simulação)' if self.dry_run else 'EXECUÇÃO REAL'}")
        report.append("=" * 60)
        report.append("")
        
        report.append(f"📁 Diretórios removidos: {len(self.removed_dirs)}")
        for dir_path in self.removed_dirs:
            report.append(f"  - {dir_path}")
        report.append("")
        
        report.append(f"📄 Arquivos removidos: {len(self.removed_files)}")
        for file_path in self.removed_files:
            report.append(f"  - {file_path}")
        report.append("")
        
        if self.errors:
            report.append(f"❌ Erros encontrados: {len(self.errors)}")
            for error in self.errors:
                report.append(f"  - {error}")
            report.append("")
        
        report.append("=" * 60)
        report.append(f"TOTAL: {len(self.removed_dirs)} diretórios + {len(self.removed_files)} arquivos")
        
        if self.dry_run:
            report.append("")
            report.append("⚠️  ATENÇÃO: Esta foi uma simulação!")
            report.append("   Para executar a limpeza real, execute:")
            report.append("   python cleanup_obsolete_files.py --real")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def run_cleanup(self):
        """Executa limpeza completa."""
        logger.info("Iniciando limpeza de arquivos obsoletos...")
        
        # Remove diretórios obsoletos
        self.remove_obsolete_directories()
        
        # Remove arquivos específicos
        self.remove_obsolete_files()
        
        # Remove arquivos por padrão
        self.remove_files_by_pattern()
        
        # Remove diretórios vazios
        self.clean_empty_directories()
        
        # Gera e exibe relatório
        report = self.generate_report()
        print("\n" + report)
        
        # Salva relatório
        report_file = self.project_root / f"cleanup_report_{'dry_run' if self.dry_run else 'real'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Relatório salvo em: {report_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar relatório: {e}")
        
        logger.info("Limpeza concluída!")


def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Remove arquivos obsoletos do projeto MegaEmu"
    )
    parser.add_argument(
        '--real', 
        action='store_true',
        help='Executa remoção real (padrão é dry-run)'
    )
    parser.add_argument(
        '--project-root',
        type=Path,
        default=PROJECT_ROOT,
        help='Diretório raiz do projeto'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Força execução sem confirmação manual'
    )
    
    args = parser.parse_args()
    
    # Confirma execução real
    if args.real:
        print("⚠️  ATENÇÃO: Você está prestes a REMOVER PERMANENTEMENTE arquivos obsoletos!")
        print("   Esta operação NÃO PODE SER DESFEITA!")
        print("")
        print("   Arquivos que serão removidos:")
        print(f"   - {len(OBSOLETE_DIRECTORIES)} diretórios obsoletos")
        print(f"   - {len(OBSOLETE_FILES)} arquivos específicos")
        print(f"   - Arquivos com padrões: {', '.join(OBSOLETE_PATTERNS)}")
        print("")
        
        if not args.force:
            confirm = input("Tem certeza que deseja continuar? (digite 'CONFIRMO' para prosseguir): ")
            if confirm != 'CONFIRMO':
                print("Operação cancelada pelo usuário.")
                return
        else:
            print("Modo --force ativado, prosseguindo automaticamente...")
    
    # Executa limpeza
    cleaner = ObsoleteFileCleaner(args.project_root, dry_run=not args.real)
    cleaner.run_cleanup()


if __name__ == '__main__':
    main()