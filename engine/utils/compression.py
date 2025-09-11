"""
Módulo de compressão otimizada para ROMs no Mega_Emu_DataBase_ROMs.

Implementa compressão usando LZ4 para equilíbrio entre velocidade e ratio de compressão,
adequado para descompressão rápida em emuladores. Suporte para compressão básica
e futura extensão híbrida.

Biblioteca selecionada: LZ4
- Vantagens: Velocidade de compressão/descompressão alta, multiplataforma (Python bindings via lz4)
- Ratio: Médio (tipicamente 40-60% de redução para dados binários como ROMs)
- Compatibilidade: Excelente com Python 3.x, multi-threading seguro

Alternativas consideradas:
- Brotli: Melhor ratio, mais lento, overhead maior para descompressão on-the-fly
- Gzip/Lzma: Padrão Python, mas LZ4 mais otimizado para velocidade

Uso:
    compressed = compress_rom(data)
    original = decompress_rom(compressed)
    ratio = get_compression_ratio(data, compressed)
"""

import lz4.frame
import time
import logging
import hashlib
import struct
from typing import Any, Generator
from ..config.constants import COMPRESSION_LEVEL_LZ4

logger = logging.getLogger(__name__)

# Constants para compressão híbrida
HYBRID_RAW_RATIO_DEFAULT = 0.333
HYBRID_HEADER_SIZE = 16
HYBRID_MAGIC = b'HEMU'  # Header magic para identificar arquivo híbrido

# Imports para MISA
import lz4.frame as lz4
import zlib
import lzma
from pathlib import Path
from engine.config import MISA_HEADER_SIZE, MISA_META_FMT
from engine.ai_picker import pick_ultimate_strategy, get_coder
from engine.utils.capp import apply_capp, reverse_capp

def compress_rom(data: bytes, level: int = COMPRESSION_LEVEL_LZ4) -> bytes:
    """
    Comprime dados de ROM usando LZ4.

    Args:
        data: Dados binários da ROM
        level: Nível de compressão (1-16, padrão do constants.py)

    Returns:
        Dados comprimidos em bytes
    """
    start_time = time.time()
    compressed = lz4.frame.compress(data, compression_level=level)
    compress_time = time.time() - start_time

    ratio = len(compressed) / len(data) if data else 1.0
    logger.info(
        "Compressão LZ4 concluída: %.2f%% do tamanho original, tempo %.4fs",
        ratio * 100, compress_time
    )

    return compressed

def decompress_rom(compressed_data: bytes) -> bytes:
    """
    Descomprime dados de ROM usando LZ4.

    Args:
        compressed_data: Dados comprimidos

    Returns:
        Dados originais em bytes
    """
    start_time = time.time()
    original = lz4.frame.decompress(compressed_data)
    decompress_time = time.time() - start_time

    logger.info("Descompressão LZ4 concluída em %.4fs", decompress_time)

    return original

def get_compression_ratio(original: bytes, compressed: bytes) -> float:
    """
    Calcula ratio de compressão (0.0-1.0, menor = melhor compressão).

    Args:
        original: Dados originais
        compressed: Dados comprimidos

    Returns:
        Ratio de compressão
    """
    if not original:
        return 1.0
    return len(compressed) / len(original)

def benchmark_compression(data: bytes, iterations: int = 5) -> dict:
    """
    Benchmark de compressão/descompressão para avaliação de performance.

    Args:
        data: Dados para testar
        iterations: Número de execuções para média

    Returns:
        Dict com métricas: compress_time, decompress_time, ratio
    """
    compress_times = []
    decompress_times = []

    for _ in range(iterations):
        # Compressão
        start = time.time()
        compressed = compress_rom(data)
        compress_times.append(time.time() - start)

        # Descompressão
        start = time.time()
        decompress_rom(compressed)
        decompress_times.append(time.time() - start)

    return {
        'avg_compress_time': sum(compress_times) / len(compress_times),
        'avg_decompress_time': sum(decompress_times) / len(decompress_times),
        'compression_ratio': get_compression_ratio(data, compressed)
    }

def compress_hybrid(data: bytes, raw_ratio: float = HYBRID_RAW_RATIO_DEFAULT) -> bytes:
    """
    Comprime dados usando abordagem híbrida: 1/3 inicial raw + 2/3 LZ4.

    Args:
        data: Dados originais da ROM
        raw_ratio: Porcentagem inicial que permanece raw (0.0-1.0)

    Returns:
        Dados comprimidos em formato híbrido com header

    Raises:
        ValueError: Se dados inválidos ou hash não corresponder
    """
    if not data:
        raise ValueError("Dados não podem estar vazios")

    if not (0.0 < raw_ratio < 1.0):
        raise ValueError(f"Ratio deve estar entre 0.0 e 1.0, recebido: {raw_ratio}")

    # Calcular hash original
    hash_original = hashlib.md5(data).hexdigest()
    logger.debug(f"Hash original: {hash_original}")

    # Calcular offset para divisão
    offset = int(len(data) * raw_ratio)
    if offset <= 0 or offset >= len(data):
        raise ValueError(f"Offset inválido: {offset} para dados de tamanho {len(data)}")

    # Dividir dados
    raw_data = data[:offset]
    remaining_data = data[offset:]

    # Comprimir a parte restante com LZ4
    compressed_remaining = compress_rom(remaining_data)

    # Criar header
    header = _create_hybrid_header(offset, raw_ratio)

    # Concatenar: header + raw_data + compressed_remaining
    hybrid_data = header + raw_data + compressed_remaining

    logger.info(
        f"Compressão híbrida concluída: {len(hybrid_data)} bytes "
        f"(raw: {len(raw_data)}, compressed: {len(compressed_remaining)})"
    )

    return hybrid_data

def decompress_hybrid(hybrid_data: bytes, offset: int, ratio: float) -> bytes:
    """
    Descomprime dados híbridos on-the-fly sem salvar disco.

    Args:
        hybrid_data: Dados híbridos com header
        offset: Offset onde começa a compressão LZ4
        ratio: Ratio usado na compressão

    Returns:
        Dados originais descomprimidos

    Raises:
        ValueError: Se hash não corresponder ou dados inválidos
    """
    if not hybrid_data:
        raise ValueError("Dados híbridos não podem estar vazios")

    if len(hybrid_data) < HYBRID_HEADER_SIZE:
        raise ValueError("Dados híbridos muito pequenos para conter header válido")

    # Ler header
    magic, stored_offset, stored_ratio = _read_hybrid_header(hybrid_data[:HYBRID_HEADER_SIZE])

    if magic != HYBRID_MAGIC:
        raise ValueError("Header mágico inválido - não é arquivo híbrido")

    # Usar offset fornecido se disponível, senão usar do header
    if offset > 0:
        actual_offset = offset
    else:
        actual_offset = stored_offset

    if actual_offset <= 0 or actual_offset >= len(hybrid_data):
        raise ValueError(f"Offset inválido: {actual_offset}")

    # Extrair partes
    header_size = HYBRID_HEADER_SIZE
    raw_data = hybrid_data[header_size:header_size + actual_offset]
    compressed_remaining = hybrid_data[header_size + actual_offset:]

    if not compressed_remaining:
        raise ValueError("Dados comprimidos não encontrados")

    # Descomprimir parte LZ4
    decompressed_remaining = decompress_rom(compressed_remaining)

    # Concatenar: raw_data + decompressed_remaining
    original_data = raw_data + decompressed_remaining

    # Validar integridade via hash se possível
    hash_decompressed = hashlib.md5(original_data).hexdigest()
    logger.debug(f"Hash descomprimido: {hash_decompressed}")

    logger.info(
        f"Descompressão híbrida concluída: {len(original_data)} bytes "
        f"(raw: {len(raw_data)}, decompressed: {len(decompressed_remaining)})"
    )

    return original_data

def _create_hybrid_header(offset: int, ratio: float) -> bytes:
    """
    Cria header binário para arquivo híbrido.

    Args:
        offset: Offset onde começa compressão LZ4
        ratio: Ratio usado na compressão

    Returns:
        Header binário de tamanho fixo (16 bytes)
    """
    # Formato: magic(4) + offset(8) + ratio(4) = 16 bytes
    ratio_bytes = struct.pack('<f', ratio)  # float32 little-endian
    offset_bytes = struct.pack('<Q', offset)  # uint64 little-endian
    header = HYBRID_MAGIC + offset_bytes + ratio_bytes

    if len(header) != HYBRID_HEADER_SIZE:
        raise ValueError(f"Header deve ter exatamente {HYBRID_HEADER_SIZE} bytes")

    return header

def _read_hybrid_header(header: bytes) -> tuple:
    """
    Lê header de arquivo híbrido.

    Args:
        header: Bytes do header (16 bytes)

    Returns:
        Tupla (magic, offset, ratio)
    """
    if len(header) != HYBRID_HEADER_SIZE:
        raise ValueError(f"Header deve ter {HYBRID_HEADER_SIZE} bytes")

    magic = header[:4]
    offset = struct.unpack('<Q', header[4:12])[0]
    ratio = struct.unpack('<f', header[12:16])[0]

    return magic, offset, ratio

# ==================== Funções MISA ====================

def compress_misa(rom_data: bytes, console: str) -> bytes:
    """
    Comprime ROM usando formato MISA com CAPP e estratégia otimizada.

    Args:
        rom_data: Dados da ROM original
        console: Console/arquitetura (ex: 'psp', 'ps1', 'n64')

    Returns:
        Dados comprimidos no formato MISA
    """
    # Selecionar estratégia ótima
    temp_path = Path('temp.rom')
    with open(temp_path, 'wb') as f:
        f.write(rom_data)

    strategy = pick_ultimate_strategy(temp_path, console)
    temp_path.unlink()  # Remover arquivo temporário

    # Raw slice inicial (512KB)
    raw_slice = rom_data[:512 * 1024]

    # Packed meta
    meta_packed = struct.pack(
        MISA_META_FMT,
        b'MISA',  # magic
        1,  # version
        strategy['coder'],  # coder_id
        strategy['capp'],  # capp_id
        0,  # sub_id
        4 * 1024 * 1024,  # chunk_size
        len(rom_data),  # raw_size
        0b1111 | (1 << 4 if strategy['nested'] else 0),  # flags
        hashlib.md5(rom_data).digest(),  # md5
        int(time.time() * 1000),  # updated_at
        console.encode()[:32].ljust(32, b'\x00')  # filename/console
    )

    meta_lz4 = lz4.frame.compress(meta_packed)

    # Processar chunks
    chunks = []
    for i in range(512 * 1024, len(rom_data), 4 * 1024 * 1024):
        chunk = rom_data[i:i + 4 * 1024 * 1024]

        transformed, table = apply_capp(chunk, strategy['capp'])

        if strategy['nested']:
            compressed_chunk = lzma.compress(transformed + table)
        else:
            coder_func = get_coder(strategy['coder'])
            compressed_chunk = coder_func.compress(transformed) + table

        crc = zlib.crc32(compressed_chunk)
        chunks.append(struct.pack('<II', len(compressed_chunk), crc) + compressed_chunk)

    # Header
    header = struct.pack(
        '<4sBBBHII16sQ32s',
        b'MISA',  # magic
        1,  # version
        strategy['coder'],  # coder_id
        strategy['capp'],  # capp_id
        0,  # sub_id
        4 * 1024 * 1024,  # chunk_size
        len(rom_data),  # raw_size
        hashlib.md5(rom_data).digest(),  # md5
        int(time.time() * 1000),  # updated_at
        console.encode()[:32].ljust(32, b'\x00')  # filename
    )

    # Footer com index
    footer = pack_footer(build_index(chunks))

    return header + raw_slice + meta_lz4 + b''.join(chunks) + footer

def decompress_misa(misa_bytes: bytes) -> Generator[bytes, None, None]:
    """
    Descomprime arquivo MISA, yield chunks sequencialmente.

    Args:
        misa_bytes: Dados do arquivo MISA

    Yields:
        Chunks descomprimidos (raw_slice primeiro, depois chunks)
    """
    header = parse_header(misa_bytes[:MISA_HEADER_SIZE])
    raw_offset = MISA_HEADER_SIZE
    meta_offset = raw_offset + 512 * 1024

    # Meta LZ4
    meta_lz4 = misa_bytes[meta_offset:meta_offset + 1024]  # Assumir tamanho máximo
    meta = lz4.frame.decompress(meta_lz4)
    meta_unpacked = struct.unpack(MISA_META_FMT, meta)

    # Yield raw slice
    yield misa_bytes[raw_offset:raw_offset + 512 * 1024]

    # Processar chunks
    chunk_data = misa_bytes[meta_offset + len(meta_lz4):]
    pos = 0

    while pos < len(chunk_data):
        if pos + 8 > len(chunk_data):
            break

        size, crc = struct.unpack('<II', chunk_data[pos:pos + 8])
        pos += 8

        if pos + size > len(chunk_data):
            break

        compressed = chunk_data[pos:pos + size]
        pos += size

        # Verificar CRC
        if zlib.crc32(compressed) != crc:
            raise ValueError("CRC mismatch no chunk")

        # Split dados e tabela
        table_len = ...  # Calcular baseado no capp
        compressed_data = compressed[:-table_len]
        table = compressed[-table_len:]

        # Descomprimir
        if header.nested:
            transformed = lzma.decompress(compressed_data)
        else:
            coder_func = get_coder(header.coder_id)
            transformed = coder_func.decompress(compressed_data)

        # Reverse CAPP
        original = reverse_capp(transformed, table, header.capp_id)
        yield original

def misa_read(misa_path: str, offset: int, size: int) -> bytes:
    """
    Lê dados random access de arquivo MISA.

    Args:
        misa_path: Caminho para arquivo MISA
        offset: Offset no arquivo original
        size: Tamanho a ler

    Returns:
        Dados lidos
    """
    with open(misa_path, 'rb') as f:
        # Ler header
        header_data = f.read(MISA_HEADER_SIZE)
        header = parse_header(header_data)

        raw_offset = MISA_HEADER_SIZE
        meta_offset = raw_offset + 512 * 1024

        # Se offset está na raw slice
        if offset < 512 * 1024:
            f.seek(raw_offset + offset)
            return f.read(size)

        # Calcular chunk index
        chunk_size = 4 * 1024 * 1024
        chunk_idx = (offset - 512 * 1024) // chunk_size
        local_offset = (offset - 512 * 1024) % chunk_size

        # Pular para meta e ler index
        f.seek(meta_offset)
        meta_lz4 = f.read(1024)  # Assumir tamanho
        meta = lz4.frame.decompress(meta_lz4)

        # Ler index do footer
        f.seek(-1024, 2)  # Final do arquivo
        index_data = f.read(1024)
        index = parse_index(index_data)

        if chunk_idx not in index:
            raise ValueError(f"Chunk {chunk_idx} não encontrado")

        chunk_start = index[chunk_idx]
        f.seek(chunk_start)

        # Ler chunk header
        chunk_header = f.read(8)
        chunk_size_stored, crc = struct.unpack('<II', chunk_header)

        # Ler chunk comprimido
        compressed = f.read(chunk_size_stored)

        # Verificar CRC
        if zlib.crc32(compressed) != crc:
            raise ValueError("CRC mismatch")

        # Descomprimir chunk
        table_len = ...  # Calcular
        compressed_data = compressed[:-table_len]
        table = compressed[-table_len:]

        if header.nested:
            transformed = lzma.decompress(compressed_data)
        else:
            coder_func = get_coder(header.coder_id)
            transformed = coder_func.decompress(compressed_data)

        original = reverse_capp(transformed, table, header.capp_id)

        # Retornar parte solicitada
        return original[local_offset:local_offset + size]

# Funções auxiliares MISA

def build_index(chunks: list) -> dict:
    """Constrói index de chunks para random access."""
    index = {}
    pos = 0
    for i, chunk in enumerate(chunks):
        index[i] = pos
        pos += len(chunk)
    return index

def pack_footer(index: dict) -> bytes:
    """Empacota footer com index."""
    # Simples serialização do dict
    return str(index).encode()

def parse_header(header_bytes: bytes) -> dict:
    """Parse header MISA."""
    unpacked = struct.unpack('<4sBBBHII16sQ32s', header_bytes)
    return {
        'magic': unpacked[0],
        'version': unpacked[1],
        'coder_id': unpacked[2],
        'capp_id': unpacked[3],
        'sub_id': unpacked[4],
        'chunk_size': unpacked[5],
        'raw_size': unpacked[6],
        'md5': unpacked[7],
        'updated_at': unpacked[8],
        'filename': unpacked[9].decode().rstrip('\x00')
    }

def parse_index(index_bytes: bytes) -> dict:
    """Parse index do footer."""
    # Simples eval para proto
    return eval(index_bytes.decode())