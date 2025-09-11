# Constants para o sistema MISA com CAPP

# Tamanho do header MISA em bytes
MISA_HEADER_SIZE = 128

# Tabela de transformações CAPP (Content Aware Pre-Processing)
# Formato: {id: (nome, ganho, uso)}
CAPP_TABLE = {
    0x00: ('Passthrough', '0%', 'Sem transformação'),
    0x10: ('UMD-ZERO', '+12%', 'PSP zeros RLE'),
    0x12: ('PMF-TRANS', '+8%', 'PS1 PMF magic'),
    0x20: ('STR-AUDIO', '+15%', 'PS1 STR audio'),
    0x21: ('XA-AUDIO', '+10%', 'PS1 XA audio'),
    0x30: ('N64-SWIZZLE', '+5%', 'Nintendo 64 swizzle'),
    0x50: ('ZERO-RLE', '+20%', 'RLE zeros genérico'),
}

# Tabela de codificadores
# Formato: {id: (nome, nível, módulo)}
CODER_TABLE = {
    0x01: ('LZ4 HC', 12, 'lz4.frame'),
    0x03: ('ZLIB', 6, 'zlib'),
    0x05: ('LZMA', 6, 'lzma'),
    0xF0: ('7Z', 0, 'py7zr'),  # Para nested 7z
}

# Melhores taxas de compressão conhecidas por console
KNOWN_BEST_RATIOS = {
    'psp': 0.25,
    'ps1': 0.30,
    'n64': 0.35,
    'gba': 0.20,
    'nes': 0.15,
    'snes': 0.18,
}

# Tamanho limite para arquivos pequenos (32MB)
SMALL_FILE_SIZE = 32 * 1024 * 1024

# Ganho mínimo para usar 7z nested (2%)
MIN_GAIN_7Z = 0.02

# Formato do struct meta MISA
# <4sB B B H I I 16s Q 32s
# magic(4)/version(1)/coder_id(1)/capp_id(1)/sub_id(2)/chunk_size(4)/raw_size(4)/flags(4)/md5(16)/updated_at(8)/filename(32)
MISA_META_FMT = '<4sB B B H I I 16s Q 32s'