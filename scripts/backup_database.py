import os
import sqlite3
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def backup_database(db_path: str, backup_dir: str = None) -> str:
    """
    Cria backup incremental de banco SQLite.

    Args:
        db_path: Caminho do banco de dados
        backup_dir: Diretório para salvar backup (default: mesmo dir)

    Returns:
        Caminho do backup criado
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco de dados não encontrado: {db_path}")

    # Gera nome backup com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = Path(db_path).stem
    backup_filename = f"{name}_backup_{timestamp}.bak"
    
    if backup_dir:
        backup_path = Path(backup_dir) / backup_filename
        os.makedirs(backup_dir, exist_ok=True)
    else:
        backup_path = Path(db_path).parent / backup_filename

    # Cópia segura
    import shutil
    shutil.copy2(db_path, str(backup_path))

    logger.info(f"Backup criado: {backup_path}")
    return str(backup_path)

def restore_backup(backup_path: str, target_path: str = None) -> str:
    """
    Restaura banco de dados de backup.

    Args:
        backup_path: Caminho do backup
        target_path: Caminho alvo (default: sobrescreve original)

    Returns:
        Caminho do banco restaurado
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup não encontrado: {backup_path}")

    if target_path:
        restored_path = target_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
    else:
        restored_path = backup_path.replace('.bak', '')

    import shutil
    shutil.copy2(backup_path, restored_path)

    logger.info(f"Backup restaurado: {restored_path}")
    return restored_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python backup_database.py <db_path>")
    else:
        backup = backup_database(sys.argv[1])
        print(f"Backup criado: {backup}")
