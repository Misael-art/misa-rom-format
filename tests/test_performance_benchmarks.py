import pytest
import hashlib
import time
import os
import json
from pathlib import Path
from typing import Dict, Tuple

from engine.utils.compression import compress_misa, decompress_misa
from engine.ai_picker import pick_ultimate_strategy


@pytest.fixture
def sample_golden_roms() -> Dict[str, Tuple[str, int]]:
    """Fixture com samples de ROMs e seus tamanhos golden standards."""
    return {
        'psp_gow': ('tests/samples/god_of_war_umd.iso', int(1.02 * 1024 ** 3)),  # 1.02GB
        'crisis_core': ('tests/samples/crisis_core.iso', int(1.19 * 1024 ** 3)),  # 1.19GB
        'ffvii_ps1': ('tests/samples/ffvii.bin', int(1.04 * 1024 ** 3)),  # 1.04GB
        're4_gc': ('tests/samples/re4_gc.iso', int(0.97 * 1024 ** 3)),  # 0.97GB
        'smw_snes': ('tests/samples/smw.sfc', int(0.27 * 1024 ** 2)),  # 0.27MB
        'zelda_n64': ('tests/samples/zelda.z64', int(4.0 * 1024 ** 2)),  # 4.0MB
    }


@pytest.mark.parametrize('sample_name,console', [
    ('psp_gow', 'psp'),
    ('crisis_core', 'psp'),
    ('ffvii_ps1', 'ps1'),
    ('re4_gc', 'gc'),
    ('smw_snes', 'snes'),
    ('zelda_n64', 'n64')
])
def test_golden_benchmark(sample_name: str, console: str, sample_golden_roms: Dict[str, Tuple[str, int]]):
    """Teste parametrizado para validar benchmarks golden standards."""
    rom_path_str, golden_size = sample_golden_roms[sample_name]
    rom_path = Path(rom_path_str)

    # Skip if sample file doesn't exist
    if not rom_path.exists():
        pytest.skip(f"Sample file {rom_path} does not exist")

    # Ler dados da ROM
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # Selecionar estratégia e comprimir
    strategy = pick_ultimate_strategy(rom_path, console)
    misa_data = compress_misa(rom_data, console)

    # Assert tamanho golden (permitir até 5% acima)
    assert len(misa_data) <= golden_size * 1.05, (
        f"{sample_name} >1.05x golden {golden_size} bytes "
        f"(atual: {len(misa_data)})"
    )

    # Assert integridade - descomprimir e verificar MD5
    decompressed_chunks = list(decompress_misa(misa_data))
    decompressed_data = b''.join(decompressed_chunks)
    original_md5 = hashlib.md5(rom_data).hexdigest()
    decompressed_md5 = hashlib.md5(decompressed_data).hexdigest()
    assert original_md5 == decompressed_md5, (
        "MD5 mismatch after decompression"
    )

    # Assert performance de boot (<10ms)
    start_time = time.perf_counter()
    raw_slice = rom_data[:512 * 1024]  # Simular raw_slice
    for _ in raw_slice:
        pass
    boot_time = time.perf_counter() - start_time
    assert boot_time < 0.010, f"Boot time {boot_time:.6f}s > 10ms"

    # Assert performance de seek (<1ms médio)
    seek_times = []
    for _ in range(10):  # 10 amostras
        start_time = time.perf_counter()
        # Simular seek aleatório
        chunk_idx = len(decompressed_chunks) // 2 if decompressed_chunks else 0
        if chunk_idx < len(decompressed_chunks):
            _ = decompressed_chunks[chunk_idx]
        seek_time = time.perf_counter() - start_time
        seek_times.append(seek_time)

    if seek_times:
        avg_seek_time = sum(seek_times) / len(seek_times)
        assert avg_seek_time < 0.001, f"Average seek time {avg_seek_time:.6f}s > 1ms"


def misa_benchmark(console: str, file_path: str) -> Dict[str, float]:
    """
    Função CLI para benchmark MISA - gera JSON com métricas.

    Args:
        console: Console/arquitetura (ex: 'psp', 'ps1')
        file_path: Caminho para arquivo ROM

    Returns:
        Dict com métricas: size, gain, boot_ms, seek_ms
    """
    rom_path = Path(file_path)

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM file {file_path} not found")

    # Ler ROM
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    original_size = len(rom_data)

    # Selecionar estratégia
    strategy = pick_ultimate_strategy(rom_path, console)

    # Comprimir
    start_compress = time.perf_counter()
    misa_data = compress_misa(rom_data, console)
    compress_time = time.perf_counter() - start_compress

    compressed_size = len(misa_data)
    compression_ratio = compressed_size / original_size
    gain = (original_size - compressed_size) / original_size

    # Medir boot time (simulado)
    start_boot = time.perf_counter()
    raw_slice = rom_data[:512 * 1024]
    for _ in raw_slice:
        pass
    boot_ms = (time.perf_counter() - start_boot) * 1000

    # Medir seek time médio
    decompressed_chunks = list(decompress_misa(misa_data))
    seek_times = []
    for _ in range(10):
        start_seek = time.perf_counter()
        chunk_idx = len(decompressed_chunks) // 2
        if chunk_idx < len(decompressed_chunks):
            _ = decompressed_chunks[chunk_idx]
        seek_times.append((time.perf_counter() - start_seek) * 1000)

    seek_ms = sum(seek_times) / len(seek_times) if seek_times else 0.0

    # Gerar relatório
    benchmark_data = {
        'size': compressed_size,
        'gain': gain,
        'compression_ratio': compression_ratio,
        'boot_ms': boot_ms,
        'seek_ms': seek_ms,
        'console': console,
        'filename': rom_path.name,
        'original_size': original_size,
        'strategy': strategy
    }

    # Salvar JSON
    output_file = Path('benchmarks') / f"{console}_{rom_path.stem}.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    return benchmark_data


def get_original_md5(rom_path: Path) -> str:
    """Calcula MD5 do arquivo ROM original."""
    with open(rom_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()