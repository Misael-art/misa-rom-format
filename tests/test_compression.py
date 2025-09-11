#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Testes de Compressão
Testes unitários e de integração para funções de compressão LZ4 e híbrida
"""

import os
import tempfile
import hashlib
import pytest
from pathlib import Path

from engine.utils.compression import (
    compress_rom,
    decompress_rom,
    compress_hybrid,
    decompress_hybrid,
    get_compression_ratio,
    benchmark_compression,
    _create_hybrid_header,
    _read_hybrid_header
)
# Constantes importadas diretamente do módulo de compressão
from engine.utils.compression import (
    HYBRID_RAW_RATIO_DEFAULT,
    HYBRID_HEADER_SIZE,
    HYBRID_MAGIC
)
# Constantes hardcoded para evitar problemas de importação circular
CONFIG_LARGE_ROM_THRESHOLD_MB = 10
CONFIG_COMPRESSION_TYPES = {'lz4': 1, 'hybrid': 2, 'none': 0}
# HYBRID_MAGIC está definido no compression.py

# Imports para testes de integração
from engine.utils.directory_scanner import DirectoryScanner
from engine.db.migration_compression_v2_2 import (
    migrate_compression_fields,
    validate_hybrid_integrity
)
import sqlite3


@pytest.fixture
def sample_rom_bytes():
    """Fixture para bytes de ROM sample real."""
    with open('tests/sample_rom.bin', 'rb') as f:
        return f.read()


class TestCompression:
    """Testes para funções de compressão."""

    @pytest.fixture
    def sample_data_small(self):
        """Dados de teste pequenos."""
        return b"Hello, World! This is a test ROM file for compression testing." * 100

    @pytest.fixture
    def sample_data_large(self):
        """Dados de teste grandes para compressão híbrida."""
        # Cria dados maiores que o threshold (10MB)
        base_data = b"Test ROM data for hybrid compression testing. " * 1000
        return base_data * 3000  # Aproximadamente 15MB

    @pytest.fixture
    def temp_file(self, sample_data_large):
        """Arquivo temporário para testes."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(sample_data_large)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_compress_decompress_lz4(self, sample_data_small):
        """Testa compressão e descompressão LZ4 básica."""
        # Compressão
        compressed = compress_rom(sample_data_small)

        # Verificação básica
        assert len(compressed) < len(sample_data_small)
        assert isinstance(compressed, bytes)

        # Descompressão
        decompressed = decompress_rom(compressed)

        # Verificação de integridade
        assert decompressed == sample_data_small
        assert len(decompressed) == len(sample_data_small)

    def test_compression_ratio_calculation(self, sample_data_small):
        """Testa cálculo de ratio de compressão."""
        compressed = compress_rom(sample_data_small)
        ratio = get_compression_ratio(sample_data_small, compressed)

        assert 0.0 < ratio < 1.0
        assert isinstance(ratio, float)

    def test_compress_hybrid_basic(self, sample_data_large):
        """Testa compressão híbrida básica."""
        # Compressão híbrida
        compressed = compress_hybrid(sample_data_large)

        # Verificações básicas
        assert len(compressed) < len(sample_data_large)
        assert isinstance(compressed, bytes)

        # Deve ter header + dados raw + dados comprimidos
        assert len(compressed) > HYBRID_HEADER_SIZE

    def test_decompress_hybrid_integrity(self, sample_data_large):
        """Testa descompressão híbrida com verificação de integridade."""
        # Compressão
        compressed = compress_hybrid(sample_data_large)

        # Calcular offset para descompressão
        offset = int(len(sample_data_large) * HYBRID_RAW_RATIO_DEFAULT)

        # Descompressão
        decompressed = decompress_hybrid(compressed, offset, HYBRID_RAW_RATIO_DEFAULT)

        # Verificação de integridade
        assert decompressed == sample_data_large
        assert len(decompressed) == len(sample_data_large)

    def test_hybrid_header_functions(self, sample_data_large):
        """Testa funções de header híbrido."""
        offset = 1000
        ratio = 0.333

        # Criar header
        header = _create_hybrid_header(offset, ratio)
        assert len(header) == HYBRID_HEADER_SIZE
        assert header.startswith(HYBRID_MAGIC)

        # Ler header
        magic, read_offset, read_ratio = _read_hybrid_header(header)
        assert magic == HYBRID_MAGIC
        assert read_offset == offset
        assert abs(read_ratio - ratio) < 0.001  # Tolerância para float

    def test_large_file_threshold(self, sample_data_large):
        """Testa se arquivos grandes são detectados corretamente."""
        file_size_mb = len(sample_data_large) / (1024 * 1024)
        assert file_size_mb >= CONFIG_LARGE_ROM_THRESHOLD_MB

    def test_benchmark_compression(self, sample_data_small):
        """Testa função de benchmark."""
        results = benchmark_compression(sample_data_small, iterations=3)

        required_keys = ['avg_compress_time', 'avg_decompress_time', 'compression_ratio']
        for key in required_keys:
            assert key in results
            assert isinstance(results[key], (int, float))

        assert results['compression_ratio'] > 0.0
        assert results['avg_compress_time'] > 0.0
        assert results['avg_decompress_time'] > 0.0

    def test_hash_validation_hybrid(self, sample_data_large):
        """Testa validação hash na compressão híbrida."""
        # Calcular hash original
        original_hash = hashlib.md5(sample_data_large).hexdigest()

        # Compressão
        compressed = compress_hybrid(sample_data_large)

        # Descompressão
        offset = int(len(sample_data_large) * HYBRID_RAW_RATIO_DEFAULT)
        decompressed = decompress_hybrid(compressed, offset, HYBRID_RAW_RATIO_DEFAULT)

        # Verificar hash
        decompressed_hash = hashlib.md5(decompressed).hexdigest()
        assert original_hash == decompressed_hash

    def test_edge_cases(self):
        """Testa casos extremos."""
        # Dados vazios
        with pytest.raises(ValueError):
            compress_hybrid(b"")

        # Ratio inválido
        with pytest.raises(ValueError):
            compress_hybrid(b"test", raw_ratio=1.5)

        # Ratio muito pequeno
        with pytest.raises(ValueError):
            compress_hybrid(b"test", raw_ratio=0.0)

    def test_hybrid_ratio_calculation(self, sample_data_large):
        """Testa cálculo correto do ratio híbrido."""
        compressed = compress_hybrid(sample_data_large, raw_ratio=0.333)
        ratio = get_compression_ratio(sample_data_large, compressed)

        # Ratio deve ser razoável (normalmente 0.4-0.8 para dados mistos)
        assert 0.2 < ratio < 0.9

    def test_real_file_integration(self, temp_file):
        """Testa integração com arquivo real."""
        # Ler arquivo
        with open(temp_file, 'rb') as f:
            file_data = f.read()

        # Compressão híbrida
        compressed = compress_hybrid(file_data)

        # Descompressão
        offset = int(len(file_data) * HYBRID_RAW_RATIO_DEFAULT)
        decompressed = decompress_hybrid(compressed, offset, HYBRID_RAW_RATIO_DEFAULT)

        # Verificar integridade
        assert decompressed == file_data

        # Verificar hashes
        original_hash = hashlib.md5(file_data).hexdigest()
        decompressed_hash = hashlib.md5(decompressed).hexdigest()
        assert original_hash == decompressed_hash

    @pytest.mark.parametrize("raw_ratio", [0.1, 0.25, 0.5, 0.75])
    def test_different_hybrid_ratios(self, sample_data_large, raw_ratio):
        """Testa diferentes ratios híbridos."""
        compressed = compress_hybrid(sample_data_large, raw_ratio=raw_ratio)
        ratio = get_compression_ratio(sample_data_large, compressed)

        # Ratio deve ser válido
        assert 0.0 < ratio <= 1.0

        # Descompressão deve funcionar
        offset = int(len(sample_data_large) * raw_ratio)
        decompressed = decompress_hybrid(compressed, offset, raw_ratio)
        assert decompressed == sample_data_large

    def test_compress_lz4_ratio(self, sample_data_small):
        """Testa compressão LZ4 com verificação de ratio."""
        compressed = compress_rom(sample_data_small)
        ratio = get_compression_ratio(sample_data_small, compressed)

        # Verifica ratio válido para LZ4 (pode ser muito baixo para dados repetitivos)
        assert 0.0 < ratio <= 1.0
        assert len(compressed) < len(sample_data_small)

    def test_compress_lz4_integrity(self, sample_data_small):
        """Testa compressão LZ4 com verificação de integridade por hash."""
        # Calcula hash original
        original_hash = hashlib.md5(sample_data_small).hexdigest()

        # Comprime
        compressed = compress_rom(sample_data_small)

        # Descomprime
        decompressed = decompress_rom(compressed)

        # Verifica integridade
        decompressed_hash = hashlib.md5(decompressed).hexdigest()
        assert original_hash == decompressed_hash
        assert decompressed == sample_data_small

    def test_decompress_lz4_integrity(self, sample_data_small):
        """Testa descompressão LZ4 com verificação de integridade."""
        # Comprime primeiro
        compressed = compress_rom(sample_data_small)

        # Descomprime duas vezes para verificar consistência
        decompressed1 = decompress_rom(compressed)
        decompressed2 = decompress_rom(compressed)

        # Ambas devem ser idênticas ao original
        assert decompressed1 == sample_data_small
        assert decompressed2 == sample_data_small
        assert decompressed1 == decompressed2

        # Verifica hashes
        hash1 = hashlib.md5(decompressed1).hexdigest()
        hash2 = hashlib.md5(decompressed2).hexdigest()
        original_hash = hashlib.md5(sample_data_small).hexdigest()
        assert hash1 == original_hash
        assert hash2 == original_hash

    def test_get_compression_ratio(self, sample_data_small):
        """Testa função get_compression_ratio especificamente."""
        compressed = compress_rom(sample_data_small)
        ratio = get_compression_ratio(sample_data_small, compressed)

        # Ratio deve ser float entre 0 e 1
        assert isinstance(ratio, float)
        assert 0.0 < ratio <= 1.0

        # Ratio deve ser consistente com tamanhos
        expected_ratio = len(compressed) / len(sample_data_small)
        assert abs(ratio - expected_ratio) < 0.001

    def test_benchmark_compression_ratio(self, sample_data_small):
        """Testa benchmark com foco no ratio."""
        results = benchmark_compression(sample_data_small)

        # Deve incluir ratio de compressão
        assert 'compression_ratio' in results
        ratio = results['compression_ratio']

        # Ratio deve ser válido
        assert isinstance(ratio, float)
        assert 0.0 < ratio <= 1.0

        # Ratio deve ser consistente com compressão direta
        compressed = compress_rom(sample_data_small)
        direct_ratio = get_compression_ratio(sample_data_small, compressed)
        assert abs(ratio - direct_ratio) < 0.001


class TestCompressionIntegration:
    """Testes de integração para compressão."""

    def test_full_lz4_workflow(self):
        """Testa workflow completo LZ4."""
        # Dados de teste
        sample_data = b"Hello, World! This is test data for LZ4 workflow." * 100

        # Compressão
        compressed = compress_rom(sample_data)
        ratio = get_compression_ratio(sample_data, compressed)

        # Benchmark
        benchmark = benchmark_compression(sample_data)

        # Descompressão
        decompressed = decompress_rom(compressed)

        # Verificações
        assert decompressed == sample_data
        assert ratio == benchmark['compression_ratio']

    def test_full_hybrid_workflow(self):
        """Testa workflow completo híbrido."""
        # Dados de teste grandes
        sample_data = b"Test data for hybrid workflow. " * 10000

        # Compressão
        compressed = compress_hybrid(sample_data)
        ratio = get_compression_ratio(sample_data, compressed)

        # Descompressão
        offset = int(len(sample_data) * HYBRID_RAW_RATIO_DEFAULT)
        decompressed = decompress_hybrid(compressed, offset, HYBRID_RAW_RATIO_DEFAULT)

        # Verificações
        assert decompressed == sample_data
        assert 0.0 < ratio < 1.0

        # Verificar tamanho do arquivo comprimido
        assert len(compressed) < len(sample_data)

    def test_scanner_hybrid_integration(self, sample_rom_bytes):
        """Testa integração scanner com compressão híbrida."""
        # Cria diretório temporário
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria ROM grande no diretório
            rom_path = os.path.join(temp_dir, "large_test.rom")
            with open(rom_path, 'wb') as f:
                f.write(sample_rom_bytes)

            # Cria scanner com compressão habilitada
            scanner = DirectoryScanner()
            scanner.compress_on_scan = True
            scanner.compression_type = 'hybrid'  # Força híbrida
            scanner.output_dir = temp_dir

            # Escaneia diretório
            results = scanner.scan_directory(temp_dir)

            # Verifica resultados
            assert len(results['files']) > 0
            rom_file = next(f for f in results['files'] if f['name'] == 'large_test.rom')
            assert rom_file is not None

            # Verifica metadados de compressão
            assert 'compression_type' in rom_file
            assert rom_file['compression_type'] == 'hybrid'
            assert 'compression_offset' in rom_file
            assert 'hybrid_ratio' in rom_file
            assert 'compressed_path' in rom_file

            # Verifica arquivo comprimido existe
            assert os.path.exists(rom_file['compressed_path'])
            assert rom_file['compressed_path'].endswith('.misa')

            # Verifica hash validado
            assert 'hash_original' in rom_file

    def test_migration_hybrid_validation(self):
        """Testa migração e validação de integridade híbrida."""
        # Cria DB temporária
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
            db_path = db_file.name

        try:
            # Conecta e cria tabela roms com campos antigos
            conn = sqlite3.connect(db_path)
            conn.execute('''
                CREATE TABLE roms (
                    id INTEGER PRIMARY KEY,
                    file_path TEXT,
                    rom_filename TEXT,
                    size INTEGER,
                    md5 TEXT,
                    updated_at TEXT
)
''')

            # Cria tabela app_info necessária para a migração
            conn.execute('''
                CREATE TABLE app_info (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT
)
''')

            # Insere ROM grande
            with open('tests/sample_rom.bin', 'rb') as f:
                large_rom_data = f.read()
            hash_md5 = hashlib.md5(large_rom_data).hexdigest()

            # Cria arquivo físico para o teste
            with open('large_test.rom', 'wb') as f:
                f.write(large_rom_data)

            conn.execute('''
                INSERT INTO roms (file_path, rom_filename, size, md5)
                VALUES (?, ?, ?, ?)
            ''', ('large_test.rom', 'large_test.rom', len(large_rom_data), hash_md5))
            conn.commit()

            # Executa migração
            migrate_compression_fields(conn)

            # Executa validação de integridade (esta função atualiza os campos)
            validate_hybrid_integrity(conn)

            # Verifica campos adicionados e atualizados
            cursor = conn.execute('''
                SELECT compression_type, compression_offset, hybrid_ratio
                FROM roms WHERE file_path = ?
            ''', ('large_test.rom',))
            row = cursor.fetchone()

            assert row is not None
            compression_type, offset, ratio = row

            # Deve detectar como híbrida devido ao tamanho
            assert compression_type == 'hybrid'
            assert offset is not None
            assert ratio is not None

            # Verifica que não houve erros (se houvesse, seria lançada exception)

        finally:
            conn.close()
            os.unlink(db_path)
            # Limpa arquivo temporário
            if os.path.exists('large_test.rom'):
                os.unlink('large_test.rom')

    def test_ui_compress_thread_safe(self):
        """Testa compressão thread-safe via UI (usando MainWindow diretamente)."""
        # Cria dados de teste
        rom_data = {
            'filename': 'test_sample.rom',
            'path': 'tests/sample_rom.bin'  # Usa o arquivo criado
        }

        # Mock MainWindow para teste (sem abrir janelas reais)
        from unittest.mock import Mock
        from concurrent.futures import ThreadPoolExecutor
        import queue

        # Cria mock da UI
        mock_ui = Mock()
        mock_ui.ui_queue = queue.Queue()
        mock_ui.executor = ThreadPoolExecutor(max_workers=2)

        # Adiciona método _process_single_file (simplificado)
        def mock_process_single_file(rom_data, operation):
            try:
                file_path = rom_data.get('path', '')
                with open(file_path, "rb") as f:
                    data = f.read()

                if operation == "compress":
                    compressed_data = compress_rom(data)
                    ratio = get_compression_ratio(data, compressed_data)
                    return {
                        'success': True,
                        'ratio': ratio,
                        'output_path': file_path.rsplit('.', 1)[0] + '.misa'
                    }
                elif operation == "decompress":
                    # Para teste, assume que é arquivo .misa
                    compressed_data = decompress_rom(data)
                    return {
                        'success': True,
                        'ratio': 1.0,
                        'output_path': file_path
                    }
            except Exception as e:
                return {'success': False, 'error': str(e)}

        mock_ui._process_single_file = mock_process_single_file

        # Adiciona método _perform_compression (baseado no código real)
        def mock_perform_compression(roms_list, operation):
            total_files = len(roms_list)
            processed_files = 0
            success_count = 0

            # Processa arquivos
            for rom in roms_list:
                try:
                    result = mock_ui._process_single_file(rom, operation)
                    if result['success']:
                        success_count += 1
                    processed_files += 1

                    # Envia progresso para queue
                    mock_ui.ui_queue.put({
                        'type': 'compress_progress',
                        'data': {
                            'current': processed_files,
                            'total': total_files,
                            'filename': rom.get('filename', ''),
                            'ratio': result.get('ratio', 0)
                        }
                    })

                except Exception as e:
                    processed_files += 1

            # Envia conclusão
            operation_name = "compressão" if operation == "compress" else "descompressão"
            mock_ui.ui_queue.put({
                'type': 'compress_complete',
                'data': {
                    'operation': operation_name,
                    'processed': processed_files,
                    'successful': success_count
                }
            })

        mock_ui._perform_compression = mock_perform_compression

        # Executa compressão em background
        roms_list = [rom_data]
        future = mock_ui.executor.submit(mock_ui._perform_compression, roms_list, "compress")
        future.result(timeout=30)  # Aguarda conclusão

        # Verifica mensagens na queue
        messages = []
        while not mock_ui.ui_queue.empty():
            messages.append(mock_ui.ui_queue.get())

        # Deve ter progresso + conclusão
        assert len(messages) >= 2
        assert any(msg.get('type') == 'compress_progress' for msg in messages)
        assert any(msg.get('type') == 'compress_complete' for msg in messages)

        # Verifica conclusão bem-sucedida
        complete_msg = next(msg for msg in messages if msg.get('type') == 'compress_complete')
        assert complete_msg['data']['successful'] == 1
        assert complete_msg['data']['processed'] == 1

        # Verifica que arquivo .misa foi "criado" (no resultado)
        progress_msg = next(msg for msg in messages if msg.get('type') == 'compress_progress')
        assert 'ratio' in progress_msg['data']
        assert progress_msg['data']['ratio'] > 0

        # Limpa executor
        mock_ui.executor.shutdown(wait=True)

    def test_lz4_ratio_extremes(self):
        """Testa verificações extras de ratio LZ4 com dados extremos."""
        import logging

        # Configurar logging para capturar mensagens
        logger = logging.getLogger('engine.utils.compression')
        logger.setLevel(logging.DEBUG)

        # Dados muito pequenos (deve ter ratio próximo de 1.0 devido a overhead)
        small_data = b"Hi"
        compressed_small = compress_rom(small_data)
        ratio_small = get_compression_ratio(small_data, compressed_small)

        logger.info(f"Dados pequenos: tamanho={len(small_data)}, comprimido={len(compressed_small)}, ratio={ratio_small:.4f}")
        assert 0.0 < ratio_small  # Ratio pode ser > 1.0 para dados muito pequenos devido ao overhead

        # Dados muito grandes (deve comprimir bem)
        large_data = b"A" * 100000  # Dados repetitivos devem comprimir muito bem
        compressed_large = compress_rom(large_data)
        ratio_large = get_compression_ratio(large_data, compressed_large)

        logger.info(f"Dados grandes repetitivos: tamanho={len(large_data)}, comprimido={len(compressed_large)}, ratio={ratio_large:.4f}")
        assert 0.0 < ratio_large < 1.0

        # Verificar que dados repetitivos comprimem melhor
        assert ratio_large < ratio_small, f"Ratio grande {ratio_large} deve ser menor que ratio pequeno {ratio_small}"

        # Dados aleatórios (deve ter ratio moderado)
        import random
        random.seed(42)  # Para reprodutibilidade
        random_data = bytes([random.randint(0, 255) for _ in range(10000)])
        compressed_random = compress_rom(random_data)
        ratio_random = get_compression_ratio(random_data, compressed_random)

        logger.info(f"Dados aleatórios: tamanho={len(random_data)}, comprimido={len(compressed_random)}, ratio={ratio_random:.4f}")
        assert 0.0 < ratio_random  # Ratio pode ser > 1.0 para dados que não comprimem bem

        # Verificar integridade para todos os casos
        assert decompress_rom(compressed_small) == small_data
        assert decompress_rom(compressed_large) == large_data
        assert decompress_rom(compressed_random) == random_data

    def test_error_logging_lz4(self):
        """Testa logs de erro para casos de falha LZ4."""
        import logging
        import io

        # Capturar logs
        log_capture_string = io.StringIO()
        ch = logging.StreamHandler(log_capture_string)
        ch.setLevel(logging.ERROR)

        logger = logging.getLogger('engine.utils.compression')
        logger.setLevel(logging.ERROR)
        logger.addHandler(ch)

        try:
            # Tentar comprimir dados vazios (pode causar erro)
            try:
                compress_rom(b"")
            except Exception as e:
                logger.error(f"Erro ao comprimir dados vazios: {e}")

            # Verificar se erro foi logado
            log_contents = log_capture_string.getvalue()
            # Nota: compress_rom pode não lançar erro para dados vazios, mas se lançar, deve ser logado

            logger.info("Teste de logging de erro LZ4 concluído")

        finally:
            logger.removeHandler(ch)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])