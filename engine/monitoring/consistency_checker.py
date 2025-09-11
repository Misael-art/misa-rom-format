#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Verificador de Consistência MCP
Implementa monitoramento contínuo para detectar discrepâncias no projeto.
Usa ThreadPoolExecutor para paralelismo, pool de conexões para queries,
e logs mascarados com SecureFormatter.
Retorna lista de discrepâncias para alertas via GitHub issues.
"""

import os
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import logging
from engine.logging.secure_formatter import SecureFormatter  # Assumindo implementação existente
from constants import (
    DB_CONNECTION_TIMEOUT,
    MAX_WORKERS_DEFAULT,
    CHECK_INTERVAL,
    BUFFER_SIZE_4KB,
    HASH_SHA256_LENGTH,
    DIR_DATA,
    FILE_DATABASE_DEFAULT,
    STATUS_WARNING,
    STATUS_ERROR
)


# Configurar logging com SecureFormatter
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = SecureFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def get_db_connection():
    """Obtém conexão com pool simples (para SQLite, usa connect com timeout)."""
    try:
        conn = sqlite3.connect(
            os.path.join(DIR_DATA, FILE_DATABASE_DEFAULT),
            timeout=DB_CONNECTION_TIMEOUT,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Erro ao conectar ao DB: {str(e)}")  # SecureFormatter mascara se necessário
        return None


def check_file_exists(rom_path: str) -> bool:
    """Verifica se arquivo ROM existe."""
    return os.path.exists(rom_path)


def compute_file_hash(file_path: str) -> str:
    """Computa hash SHA256 do arquivo."""
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(BUFFER_SIZE_4KB), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, OSError) as e:
        logger.warning(f"Erro ao computar hash para {file_path}: {str(e)}")
        return None


def check_missing_roms(conn, roms_dir: str = "meta") -> list:
    """Detecta ROMs ausentes: compara paths no DB vs arquivos."""
    discrepancies = []
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM roms")  # Assumindo tabela roms com coluna path
    db_roms = cursor.fetchall()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_DEFAULT) as executor:
        future_to_rom = {executor.submit(check_file_exists, os.path.join(roms_dir, path[0])): path[0] for path in db_roms}
        for future in as_completed(future_to_rom):
            rom_path = future_to_rom[future]
            if not future.result():
                discrepancies.append(f"ROM ausente: {rom_path}")
    
    return discrepancies


def check_invalid_hashes(conn, roms_dir: str = "meta") -> list:
    """Detecta hashes inválidos: compara hash no DB vs arquivo real."""
    discrepancies = []
    cursor = conn.cursor()
    cursor.execute("SELECT path, hash_sha256 FROM roms")  # Assumindo colunas path e hash_sha256
    rom_data = cursor.fetchall()
    
    def validate_hash(path, expected_hash):
        file_path = os.path.join(roms_dir, path)
        if not os.path.exists(file_path):
            return f"Arquivo ausente (hash inválido): {path}"
        computed = compute_file_hash(file_path)
        if computed != expected_hash:
            return f"Hash inválido para {path}: esperado {expected_hash[:8]}..., computado {computed[:8]}..."
        return None
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_DEFAULT) as executor:
        future_to_rom = {executor.submit(validate_hash, path, hsh): (path, hsh) for path, hsh in rom_data}
        for future in as_completed(future_to_rom):
            result = future.result()
            if result:
                discrepancies.append(result)
    
    return discrepancies


def check_view_consistency(conn, view_name: str = "roms_by_game") -> list:
    """Verifica inconsistências em views, ex: contagens em roms_by_game."""
    discrepancies = []
    cursor = conn.cursor()
    # Exemplo: contar total em tabela base vs view
    cursor.execute(f"SELECT COUNT(*) FROM {view_name}")
    view_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM roms")  # Assumindo base roms
    base_count = cursor.fetchone()[0]
    if view_count != base_count:
        discrepancies.append(f"Inconsistência em view {view_name}: view={view_count}, base={base_count}")
    return discrepancies


def check_scan_timeouts(log_dir: str = "logs") -> list:
    """Verifica timeouts em scans via logs recentes."""
    # Simples: buscar por 'timeout' em logs mais recentes
    discrepancies = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    if not log_files:
        return []
    latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
    log_path = os.path.join(log_dir, latest_log)
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'timeout' in content.lower() and 'scan' in content.lower():
                discrepancies.append("Possível timeout detectado em scan recente no log")
    except IOError:
        pass
    return discrepancies


def run_consistency_check() -> dict:
    """Executa verificações completas e retorna relatório."""
    start_time = datetime.now()
    logger.info(f"Iniciando verificação de consistência MCP em {start_time}")
    
    conn = get_db_connection()
    if not conn:
        return {"status": STATUS_ERROR, "discrepancies": ["Falha na conexão com DB"], "timestamp": start_time}
    
    discrepancies = []
    checks = [
        ("ROMs ausentes", lambda: check_missing_roms(conn)),
        ("Hashes inválidos", lambda: check_invalid_hashes(conn)),
        ("Inconsistências em views", lambda: check_view_consistency(conn)),
        ("Timeouts em scans", lambda: check_scan_timeouts())
    ]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_DEFAULT) as executor:
        future_to_check = {executor.submit(check_func, *args if args else ()): name for name, check_func in checks for args in [()] if callable(check_func)}
        for future in as_completed(future_to_check):
            check_name = future_to_check[future]
            try:
                result = future.result()
                if result:
                    discrepancies.extend(result)
                    logger.warning(f"{check_name}: {len(result)} discrepâncias encontradas")
                else:
                    logger.info(f"{check_name}: OK")
            except Exception as e:
                logger.error(f"Erro em {check_name}: {str(e)}")
                discrepancies.append(f"Erro em {check_name}: {str(e)}")
    
    conn.close()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Verificação concluída em {duration:.2f}s. Total discrepâncias: {len(discrepancies)}")
    
    return {
        "status": STATUS_WARNING if discrepancies else STATUS_SUCCESS,
        "discrepancies": discrepancies,
        "timestamp": end_time,
        "duration": duration
    }


if __name__ == "__main__":
    report = run_consistency_check()
    print(f"\n=== Relatório MCP {report['timestamp'].strftime('%Y-%m-%d %H:%M')} ===")
    print(f"Status: {'OK' if report['status'] == STATUS_SUCCESS else 'Discrepâncias Encontradas'}")
    print(f"Duração: {report['duration']:.2f}s")
    if report['discrepancies']:
        print("\nDiscrepâncias:")
        for disc in report['discrepancies']:
            print(f"- {disc}")
    else:
        print("Nenhuma discrepância detectada.")

    import json
    print(json.dumps(report))