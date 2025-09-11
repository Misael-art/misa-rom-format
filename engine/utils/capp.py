import struct
import zlib
import lzma
from typing import List, Tuple

def fingerprint_header(header: bytes) -> List[int]:
    """
    Analisa o header de 64KB para sugerir transformações CAPP aplicáveis.
    Retorna lista de capp_ids recomendados, ordenados por prioridade.
    """
    candidates = []

    # Verificar ratio de zeros
    zero_ratio = header.count(b'\x00') / len(header) if header else 0
    if zero_ratio > 0.3:
        candidates.append(0x10)  # UMD-ZERO

    # Verificar magic específico
    if header.startswith(b'PMF'):
        candidates.append(0x12)  # PMF-TRANS

    # Verificar headers de áudio PS1
    if b'STR' in header[:16]:
        candidates.append(0x20)  # STR-AUDIO
    if b'XA' in header[:16]:
        candidates.append(0x21)  # XA-AUDIO

    # Verificar header específico PS1 STR transcode
    if header.startswith(b'\x00\xFF\xFF\xFF\xCD\x00') or b'XA' in header:
        candidates.append(0x21)  # CAPP_PS1_STR_TRANSCODE

    # Verificar padrões N64 (simples check)
    if len(header) >= 16 and header[0] == 0x80 and header[1] == 0x37:
        candidates.append(0x30)  # N64-SWIZZLE

    # Fallback para RLE zeros se ratio alto
    if zero_ratio > 0.1:
        candidates.append(0x50)  # ZERO-RLE

    # Sempre incluir passthrough como última opção
    if not candidates:
        candidates.append(0x00)

    return candidates

def apply_capp(data: bytes, capp_id: int, sub_id: int = 0) -> Tuple[bytes, bytes]:
    """
    Aplica transformação CAPP baseada no capp_id.
    Retorna (dados_transformados, tabela_auxiliar)
    """
    if capp_id == 0x00:
        # Passthrough - sem transformação
        return data, b''

    elif capp_id == 0x10:
        # UMD-ZERO: RLE de zeros PSP
        transformed, table = _umd_zero_encode(data)
        return transformed, table

    elif capp_id == 0x12:
        # PMF-TRANS: Transformação PMF PS1
        transformed, table = _pmf_transcode(data)
        return transformed, table

    elif capp_id == 0x20:
        # STR-AUDIO: Transcode STR PS1
        transformed, table = _str_audio_transcode(data)
        return transformed, table

    elif capp_id == 0x21:
        # XA-AUDIO: Transcode XA PS1
        transformed, table = _xa_audio_transcode(data)
        return transformed, table

    elif capp_id == 0x30:
        # N64-SWIZZLE: Swizzle N64
        transformed, table = _n64_swizzle_encode(data)
        return transformed, table

    elif capp_id == 0x50:
        # ZERO-RLE: RLE genérico de zeros
        transformed, table = _zero_rle_encode(data)
        return transformed, table

    else:
        # Fallback para passthrough
        return data, b''

def reverse_capp(transformed: bytes, table: bytes, capp_id: int, sub_id: int = 0) -> bytes:
    """
    Reverte transformação CAPP baseada no capp_id.
    """
    if capp_id == 0x00:
        # Passthrough
        return transformed

    elif capp_id == 0x10:
        # Reverse UMD-ZERO
        return _umd_zero_decode(transformed, table)

    elif capp_id == 0x12:
        # Reverse PMF-TRANS
        return _pmf_transcode_reverse(transformed, table)

    elif capp_id == 0x20:
        # Reverse STR-AUDIO
        return _str_audio_transcode_reverse(transformed, table)

    elif capp_id == 0x21:
        # Reverse XA-AUDIO
        return _xa_audio_transcode_reverse(transformed, table)

    elif capp_id == 0x30:
        # Reverse N64-SWIZZLE
        return _n64_swizzle_decode(transformed, table)

    elif capp_id == 0x50:
        # Reverse ZERO-RLE
        return _zero_rle_decode(transformed, table)

    else:
        # Fallback
        return transformed

# Funções auxiliares para cada transformação

def _umd_zero_encode(data: bytes) -> Tuple[bytes, bytes]:
    """
    Codifica dados usando RLE de offsets de zeros para o formato UMD-ZERO (PSP).

    Args:
        data (bytes): Os dados de entrada a serem codificados.

    Returns:
        Tuple[bytes, bytes]: Uma tupla contendo os dados transformados e a tabela auxiliar comprimida.
    """
    # Simulação: coletar offsets de sequências de zeros
    offsets = []
    i = 0
    while i < len(data) - 4:
        if data[i:i+4] == b'\x00\x00\x00\x00':
            start = i
            while i < len(data) and data[i] == 0:
                i += 1
            offsets.append((start, i - start))
        else:
            i += 1

    # Criar dados transformados (remover zeros) e tabela
    transformed = bytearray()
    table_data = bytearray()
    last_end = 0

    for start, length in offsets:
        # Adicionar dados não-zero
        transformed.extend(data[last_end:start])
        # Adicionar offset/length na tabela
        table_data.extend(struct.pack('<II', start, length))
        last_end = start + length

    # Adicionar resto
    transformed.extend(data[last_end:])

    return bytes(transformed), zlib.compress(table_data)

def _umd_zero_decode(transformed: bytes, table_compressed: bytes) -> bytes:
    """
    Decodifica dados que foram transformados usando UMD-ZERO.

    Args:
        transformed (bytes): Os dados transformados.
        table_compressed (bytes): A tabela auxiliar comprimida.

    Returns:
        bytes: Os dados originais decodificados.
    """
    table = zlib.decompress(table_compressed)
    data = bytearray(transformed)

    # Inserir zeros nos offsets
    pos = 0
    while pos < len(table):
        offset, length = struct.unpack('<II', table[pos:pos+8])
        # Inserir zeros na posição
        data[offset:offset] = b'\x00' * length
        pos += 8

    return bytes(data)

def _pmf_transcode(data: bytes) -> Tuple[bytes, bytes]:
    """
    Aplica uma transformação mock PMF (PlayMotion File) aos dados.

    Args:
        data (bytes): Os dados de entrada a serem transformados.

    Returns:
        Tuple[bytes, bytes]: Uma tupla contendo os dados transformados e uma tabela auxiliar mock.
    """
    # Simulação: swap bytes para proto
    transformed = bytes((b ^ 0xAA) for b in data)  # Simples XOR mock
    return transformed, b'pmf_meta'

def _pmf_transcode_reverse(transformed: bytes, table: bytes) -> bytes:
    """
    Reverte a transformação mock PMF aplicada aos dados.

    Args:
        transformed (bytes): Os dados transformados.
        table (bytes): A tabela auxiliar (não utilizada nesta mock).

    Returns:
        bytes: Os dados originais decodificados.
    """
    return bytes((b ^ 0xAA) for b in transformed)

def _str_audio_transcode(data: bytes) -> Tuple[bytes, bytes]:
    """
    Aplica uma transformação mock de transcodificação de áudio STR (PS1) aos dados.

    Args:
        data (bytes): Os dados de áudio de entrada a serem transformados.

    Returns:
        Tuple[bytes, bytes]: Uma tupla contendo os dados transformados e uma tabela auxiliar mock.
    """
    # Simulação: swap even/odd bytes
    transformed = bytearray(data)
    for i in range(0, len(transformed) - 1, 2):
        transformed[i], transformed[i+1] = transformed[i+1], transformed[i]
    return bytes(transformed), b'flac_meta'

def _str_audio_transcode_reverse(transformed: bytes, table: bytes) -> bytes:
    """
    Reverte a transformação mock de transcodificação de áudio STR.

    Args:
        transformed (bytes): Os dados de áudio transformados.
        table (bytes): A tabela auxiliar (não utilizada nesta mock).

    Returns:
        bytes: Os dados de áudio originais decodificados.
    """
    # Mesmo que encode, é simétrico
    return _str_audio_transcode(transformed)[0]

def _xa_audio_transcode(data: bytes) -> Tuple[bytes, bytes]:
    """
    Aplica uma transformação mock de transcodificação de áudio XA (PS1) aos dados.

    Args:
        data (bytes): Os dados de áudio de entrada a serem transformados.

    Returns:
        Tuple[bytes, bytes]: Uma tupla contendo os dados transformados e uma tabela auxiliar mock.
    """
    # Similar ao STR mas com pattern diferente
    transformed = bytearray(data)
    for i in range(0, len(transformed), 4):
        if i + 3 < len(transformed):
            # Swap pattern para XA
            transformed[i], transformed[i+2] = transformed[i+2], transformed[i]
    return bytes(transformed), b'flac_meta'

def _xa_audio_transcode_reverse(transformed: bytes, table: bytes) -> bytes:
    """Reverse XA audio"""
    return _xa_audio_transcode(transformed)[0]

def _n64_swizzle_encode(data: bytes) -> Tuple[bytes, bytes]:
    """Mock N64 swizzle Δ-LUT"""
    # Simulação: reverse bytes em blocos
    transformed = data[::-1]  # Simples reverse para proto
    return transformed, b'n64_lut'

def _n64_swizzle_decode(transformed: bytes, table: bytes) -> bytes:
    """Reverse N64 swizzle"""
    return transformed[::-1]

def _zero_rle_encode(data: bytes) -> Tuple[bytes, bytes]:
    """RLE genérico de zeros"""
    # Similar ao UMD-ZERO mas mais simples
    transformed = bytearray()
    table_data = bytearray()
    i = 0

    while i < len(data):
        if data[i] == 0:
            # Contar zeros consecutivos
            start = i
            while i < len(data) and data[i] == 0:
                i += 1
            length = i - start
            table_data.extend(struct.pack('<II', start, length))
        else:
            transformed.append(data[i])
            i += 1

    return bytes(transformed), table_data

def _zero_rle_decode(transformed: bytes, table: bytes) -> bytes:
    """Reverse ZERO-RLE"""
    data = bytearray(transformed)
    pos = 0
    table_pos = 0

    while table_pos < len(table):
        offset, length = struct.unpack('<II', table[table_pos:table_pos+8])
        # Inserir zeros
        data[offset:offset] = b'\x00' * length
        table_pos += 8

    return bytes(data)
