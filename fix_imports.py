#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Fix Imports
Script para corrigir imports conflitantes e dependências circulares.

Este script:
- Atualiza imports dos DatabaseManagers antigos para UnifiedDatabaseManager
- Atualiza imports dos ThemeManagers antigos para UnifiedThemeManager
- Corrige imports relativos problemáticos
- Remove imports duplicados
- Resolve dependências circulares
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent

# Mapeamento de imports antigos para novos
IMPORT_MAPPINGS = {
    # DatabaseManagers
    'from engine.db.database_manager import DatabaseManager': 'from engine.db import UnifiedDatabaseManager as DatabaseManager',
    'from engine.db.database_manager_v2 import DatabaseManagerV2': 'from engine.db import UnifiedDatabaseManager as DatabaseManagerV2',
    'from engine.db.enhanced_database_manager import EnhancedDatabaseManager': 'from engine.db import UnifiedDatabaseManager as EnhancedDatabaseManager',
    'from engine.db import DatabaseManager': 'from engine.db import UnifiedDatabaseManager as DatabaseManager',
    'from engine.db import DatabaseManagerV2': 'from engine.db import UnifiedDatabaseManager as DatabaseManagerV2',
    
    # ThemeManagers
    'from engine.ui.theme_manager import ThemeManager': 'from engine.ui import UnifiedThemeManager as ThemeManager',
    'from engine.ui.theme_manager_enhanced import ThemeManager': 'from engine.ui import UnifiedThemeManager as ThemeManager',
    'from engine.ui import ThemeManager': 'from engine.ui import UnifiedThemeManager as ThemeManager',
    
    # Imports específicos que causam conflitos
    'from engine.config import *': '''from engine.config import (
    SUPPORTED_FORMATS, DEFAULT_DB_PATH, MISA_HEADER_SIZE, MISA_META_FMT,
    COMPRESSION_LEVELS, BATCH_SIZE, MAX_WORKERS
)''',
    'from engine.ui.theme_manager_enhanced import ThemeManager': 'from engine.ui import UnifiedThemeManager as ThemeManager',
}

# Padrões de imports problemáticos
PROBLEMATIC_PATTERNS = [
    # Imports circulares
    r'from\s+engine\.engine\s+import',
    r'from\s+ui\.ui\s+import',
    
    # Imports de módulos removidos
    r'from\s+engine\.db\.database_manager\s+import\s+DatabaseManager',
    r'from\s+engine\.db\.database_manager_v2\s+import\s+DatabaseManagerV2',
    r'from\s+engine\.db\.enhanced_database_manager\s+import',
    r'from\s+engine\.ui\.theme_manager\s+import\s+ThemeManager',
    r'from\s+engine\.ui\.theme_manager_enhanced\s+import',
    
    # Imports relativos problemáticos
    r'from\s+\.\.\.engine\s+import',
    r'from\s+\.\.\.ui\s+import',
]

# Arquivos a ignorar
IGNORE_FILES = {
    'cleanup_obsolete_files.py',
    'fix_imports.py',
    'unified_database_manager.py',
    'unified_theme_manager.py',
    '__pycache__',
    '.pyc',
    '.git',
    '.venv',
    '.venv-1',
    'node_modules',
}

# Diretórios a ignorar
IGNORE_DIRS = {
    '__pycache__',
    '.git',
    '.venv',
    '.venv-1',
    'node_modules',
    '.pytest_cache',
    'htmlcov',
}


class ImportFixer:
    """Corretor de imports problemáticos."""
    
    def __init__(self, project_root: Path, dry_run: bool = True):
        """
        Inicializa o corretor.
        
        Args:
            project_root: Diretório raiz do projeto
            dry_run: Se True, apenas simula as correções
        """
        self.project_root = project_root
        self.dry_run = dry_run
        self.fixed_files: List[str] = []
        self.errors: List[str] = []
        self.changes_made: Dict[str, List[str]] = {}
        
        logger.info(f"Inicializando correção de imports {'(DRY RUN)' if dry_run else '(REAL)'}")
        logger.info(f"Diretório do projeto: {project_root}")
    
    def should_ignore_file(self, file_path: Path) -> bool:
        """
        Verifica se um arquivo deve ser ignorado.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se deve ser ignorado
        """
        # Verifica nome do arquivo
        if file_path.name in IGNORE_FILES:
            return True
        
        # Verifica extensão
        if file_path.suffix not in ['.py', '.md']:
            return True
        
        # Verifica se está em diretório ignorado
        for part in file_path.parts:
            if part in IGNORE_DIRS:
                return True
        
        return False
    
    def find_python_files(self) -> List[Path]:
        """
        Encontra todos os arquivos Python no projeto.
        
        Returns:
            Lista de caminhos de arquivos Python
        """
        python_files = []
        
        for file_path in self.project_root.rglob('*.py'):
            if not self.should_ignore_file(file_path):
                python_files.append(file_path)
        
        # Também inclui arquivos .md para documentação
        for file_path in self.project_root.rglob('*.md'):
            if not self.should_ignore_file(file_path):
                python_files.append(file_path)
        
        logger.info(f"Encontrados {len(python_files)} arquivos para análise")
        return python_files
    
    def detect_problematic_imports(self, content: str) -> List[Tuple[str, str]]:
        """
        Detecta imports problemáticos no conteúdo.
        
        Args:
            content: Conteúdo do arquivo
            
        Returns:
            Lista de (linha_problemática, motivo)
        """
        problems = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Verifica padrões problemáticos
            for pattern in PROBLEMATIC_PATTERNS:
                if re.search(pattern, line_stripped):
                    problems.append((line_stripped, f"Linha {i}: Padrão problemático detectado"))
            
            # Verifica imports que precisam ser mapeados
            for old_import in IMPORT_MAPPINGS:
                if old_import in line_stripped:
                    problems.append((line_stripped, f"Linha {i}: Import antigo detectado"))
        
        return problems
    
    def fix_imports_in_content(self, content: str) -> Tuple[str, List[str]]:
        """
        Corrige imports no conteúdo.
        
        Args:
            content: Conteúdo original
            
        Returns:
            Tuple[str, List[str]]: (conteúdo_corrigido, lista_de_mudanças)
        """
        fixed_content = content
        changes = []
        
        # Aplica mapeamentos de imports
        for old_import, new_import in IMPORT_MAPPINGS.items():
            if old_import in fixed_content:
                fixed_content = fixed_content.replace(old_import, new_import)
                changes.append(f"Substituído: {old_import} -> {new_import}")
        
        # Remove imports duplicados
        lines = fixed_content.split('\n')
        seen_imports = set()
        filtered_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Se é uma linha de import
            if line_stripped.startswith(('import ', 'from ')):
                if line_stripped not in seen_imports:
                    seen_imports.add(line_stripped)
                    filtered_lines.append(line)
                else:
                    changes.append(f"Removido import duplicado: {line_stripped}")
            else:
                filtered_lines.append(line)
        
        fixed_content = '\n'.join(filtered_lines)
        
        # Corrige imports relativos problemáticos
        problematic_relative_imports = [
            (r'from\s+\.\.\.engine\s+import', 'from engine import'),
            (r'from\s+\.\.\.ui\s+import', 'from ui import'),
            (r'from\s+\.\.engine\s+import', 'from engine import'),
            (r'from\s+\.\.ui\s+import', 'from ui import'),
        ]
        
        for pattern, replacement in problematic_relative_imports:
            new_content = re.sub(pattern, replacement, fixed_content)
            if new_content != fixed_content:
                changes.append(f"Corrigido import relativo: {pattern} -> {replacement}")
                fixed_content = new_content
        
        return fixed_content, changes
    
    def fix_file(self, file_path: Path) -> bool:
        """
        Corrige imports em um arquivo específico.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se correções foram feitas
        """
        try:
            # Lê conteúdo original
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Detecta problemas
            problems = self.detect_problematic_imports(original_content)
            
            if not problems:
                logger.debug(f"Nenhum problema encontrado em: {file_path}")
                return False
            
            # Corrige imports
            fixed_content, changes = self.fix_imports_in_content(original_content)
            
            if fixed_content == original_content:
                logger.debug(f"Nenhuma mudança necessária em: {file_path}")
                return False
            
            # Salva arquivo corrigido
            if self.dry_run:
                logger.info(f"[DRY RUN] Corrigiria arquivo: {file_path}")
                for change in changes:
                    logger.info(f"[DRY RUN]   - {change}")
            else:
                logger.info(f"Corrigindo arquivo: {file_path}")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                
                for change in changes:
                    logger.info(f"  - {change}")
            
            self.fixed_files.append(str(file_path))
            self.changes_made[str(file_path)] = changes
            
            return True
            
        except Exception as e:
            error_msg = f"Erro ao corrigir arquivo {file_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def generate_report(self) -> str:
        """
        Gera relatório das correções.
        
        Returns:
            Relatório formatado
        """
        report = []
        report.append("=" * 60)
        report.append(f"RELATÓRIO DE CORREÇÃO DE IMPORTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Modo: {'DRY RUN (Simulação)' if self.dry_run else 'EXECUÇÃO REAL'}")
        report.append("=" * 60)
        report.append("")
        
        report.append(f"📄 Arquivos corrigidos: {len(self.fixed_files)}")
        for file_path in self.fixed_files:
            report.append(f"  - {file_path}")
            if file_path in self.changes_made:
                for change in self.changes_made[file_path]:
                    report.append(f"    * {change}")
        report.append("")
        
        if self.errors:
            report.append(f"❌ Erros encontrados: {len(self.errors)}")
            for error in self.errors:
                report.append(f"  - {error}")
            report.append("")
        
        report.append("=" * 60)
        report.append(f"TOTAL: {len(self.fixed_files)} arquivos corrigidos")
        
        if self.dry_run:
            report.append("")
            report.append("⚠️  ATENÇÃO: Esta foi uma simulação!")
            report.append("   Para executar as correções reais, execute:")
            report.append("   python fix_imports.py --real")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def run_fixes(self):
        """
        Executa correções em todos os arquivos.
        """
        logger.info("Iniciando correção de imports...")
        
        # Encontra arquivos Python
        python_files = self.find_python_files()
        
        # Corrige cada arquivo
        total_fixed = 0
        for file_path in python_files:
            if self.fix_file(file_path):
                total_fixed += 1
        
        # Gera e exibe relatório
        report = self.generate_report()
        print("\n" + report)
        
        # Salva relatório
        report_file = self.project_root / f"import_fixes_report_{'dry_run' if self.dry_run else 'real'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Relatório salvo em: {report_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar relatório: {e}")
        
        logger.info(f"Correção concluída! {total_fixed} arquivos corrigidos.")


def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Corrige imports conflitantes no projeto MegaEmu"
    )
    parser.add_argument(
        '--real', 
        action='store_true',
        help='Executa correções reais (padrão é dry-run)'
    )
    parser.add_argument(
        '--project-root',
        type=Path,
        default=PROJECT_ROOT,
        help='Diretório raiz do projeto'
    )
    
    args = parser.parse_args()
    
    # Confirma execução real
    if args.real:
        print("⚠️  ATENÇÃO: Você está prestes a MODIFICAR arquivos do projeto!")
        print("   Esta operação irá alterar imports em múltiplos arquivos.")
        print("   Certifique-se de ter um backup ou controle de versão ativo.")
        print("")
        
        confirm = input("Tem certeza que deseja continuar? (digite 'SIM' para prosseguir): ")
        if confirm != 'SIM':
            print("Operação cancelada pelo usuário.")
            return
    
    # Executa correções
    fixer = ImportFixer(args.project_root, dry_run=not args.real)
    fixer.run_fixes()


if __name__ == '__main__':
    main()