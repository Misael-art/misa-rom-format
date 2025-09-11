from concurrent.futures import ProcessPoolExecutor, as_completed
import time
from pathlib import Path
import timeit
import lzma
import tempfile
import os
from typing import Dict, List, Tuple, Optional

from engine.config import (
    CAPP_TABLE, CODER_TABLE, KNOWN_BEST_RATIOS,
    SMALL_FILE_SIZE, MIN_GAIN_7Z
)
from engine.utils.capp import fingerprint_header, apply_capp

def pick_ultimate_strategy(rom_path: Path, console: str) -> Dict:
    """
    Seleciona a melhor estratégia de compressão usando benchmark paralelo.
    Retorna dict com capp, coder, nested.
    """
    size = rom_path.stat().st_size
    header = b''
    with open(rom_path, 'rb') as f:
        header = f.read(min(64 * 1024, size))

    capp_opts = fingerprint_header(header)

    # Criar lista de candidatos: (capp, coder, fmt, dict_size)
    candidates = []
    for capp in capp_opts[:3]:  # Top 3 CAPP
        for coder in [0x01, 0x03, 0x05]:  # LZ4, ZLIB, LZMA
            candidates.append((capp, coder, 'direct', None))

    if size < SMALL_FILE_SIZE:
        # Adicionar 7z para arquivos pequenos
        candidates.append((0x00, 0xF0, '7z', None))

    if size < 4*1024*1024:
        # Adicionar lzma2_7z com dict_size=16MB para arquivos <4MB
        candidates.append((0x00, 0x05, '7z', 1<<24))

    results = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {}
        for capp, coder, fmt, dict_size in candidates:
            future = executor.submit(bench_strategy, rom_path, capp, coder, fmt, dict_size)
            futures[future] = (capp, coder, fmt, dict_size)

        for future in as_completed(futures, timeout=1.0):
            try:
                result_size, decomp_time = future.result()
                capp, coder, fmt, dict_size = futures[future]
                score = result_size * decomp_time
                results.append({
                    'capp': capp,
                    'coder': coder,
                    'fmt': fmt,
                    'score': score,
                    'size': result_size
                })
            except Exception as e:
                print(f"Benchmark failed: {e}")

    # Separar resultados não-7z e 7z
    non_7z_results = [r for r in results if r['fmt'] != '7z']
    seven_z_result = next((r for r in results if r['fmt'] == '7z'), None)

    if non_7z_results:
        best_non_7z = min(non_7z_results, key=lambda x: x['score'])
    else:
        best_non_7z = None

    # Comparar com 7z se disponível
    if seven_z_result and best_non_7z:
        expected_ratio = KNOWN_BEST_RATIOS.get(console, 0.5)
        if seven_z_result['size'] < best_non_7z['size'] * (1 - MIN_GAIN_7Z):
            return {
                'capp': seven_z_result['capp'],
                'coder': seven_z_result['coder'],
                'nested': True
            }

    if best_non_7z:
        return {
            'capp': best_non_7z['capp'],
            'coder': best_non_7z['coder'],
            'nested': False
        }

    # Fallback
    return {
        'capp': 0x00,
        'coder': 0x01,
        'nested': False
    }

def bench_strategy(rom_path: Path, capp: int, coder: int, fmt: str, dict_size: Optional[int] = None) -> Tuple[int, float]:
    """
    Benchmark de uma estratégia específica.
    Retorna (tamanho_comprimido, tempo_descompressão)
    """
    # Ler slice de 512KB para teste
    with open(rom_path, 'rb') as f:
        data = f.read(512 * 1024)

    # Aplicar CAPP
    transformed, table = apply_capp(data, capp)

    # Comprimir
    if fmt == '7z':
        if dict_size:
            compressed = lzma.compress(transformed + table, filters=[{'id': lzma.FILTER_LZMA2, 'dict_size': dict_size}])
        else:
            compressed = lzma.compress(transformed + table)
    else:
        coder_func = get_coder(coder)
        compressed = coder_func.compress(transformed) + table

    # Medir tempo de descompressão
    decomp_time = timeit.timeit(
        lambda: reverse_bench(transformed, table, capp, coder, fmt, compressed, dict_size),
        number=5
    ) / 5

    return len(compressed), decomp_time

def reverse_bench(transformed: bytes, table: bytes, capp: int, coder: int, fmt: str, compressed: bytes, dict_size: Optional[int] = None) -> bytes:
    """
    Função auxiliar para benchmark de descompressão.
    """
    if fmt == '7z':
        decompressed = lzma.decompress(compressed)
    else:
        coder_func = get_coder(coder)
        decompressed = coder_func.decompress(compressed[:-len(table)])

    from engine.utils.capp import reverse_capp
    return reverse_capp(decompressed, table, capp)

def get_coder(coder_id: int):
    """
    Retorna função de compressão/decompressão baseada no coder_id.
    Mock para proto - implementar com bibliotecas reais.
    """
    if coder_id == 0x01:
        import lz4.frame as lz4
        return lz4
    elif coder_id == 0x03:
        import zlib
        return zlib
    elif coder_id == 0x05:
        import lzma
        return lzma
    else:
        raise ValueError(f"Coder {coder_id} not supported")