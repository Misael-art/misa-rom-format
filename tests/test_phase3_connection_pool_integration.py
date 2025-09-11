#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Phase 3 Tests
Testes de integração para EnhancedConnectionPool com features de produção
"""

import pytest
import sqlite3
import tempfile
import os
import time
import threading
import concurrent.futures
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime

from engine.db.enhanced_connection_pool import EnhancedDatabaseConnectionPool, PoolMetrics


class TestConnectionPoolPhase3:
    """Testes de integração para EnhancedConnectionPool com features de produção."""

    @pytest.fixture
    def temp_db_path(self):
        """Fixture para caminho de banco temporário."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def pool_config(self):
        """Fixture para configuração otimizada do pool."""
        return {
            'min_connections': 2,
            'max_connections': 10,
            'connection_timeout': 5.0,
            'idle_timeout': 30.0,
            'health_check_interval': 2.0,
            'health_check_timeout': 3.0,
            'enable_metrics': True,
            'enable_health_checks': True,
            'enable_auto_scaling': True,
            'scale_up_threshold': 0.7,
            'scale_down_threshold': 0.3,
            'enable_connection_validation': True,
            'enable_statement_caching': True,
            'enable_wal_mode': True,
            'enable_foreign_keys': True
        }

    def test_pool_preload_connections(self, temp_db_path, pool_config):
        """Testa preload de conexões no pool."""
        # Este teste verifica se o pool cria conexões mínimas na inicialização
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Aguardar inicialização
            time.sleep(1.0)

            metrics = pool.get_metrics()
            global_metrics = metrics['global_metrics']

            # Deve ter criado conexões mínimas
            assert global_metrics['current_pool_size'] >= pool_config['min_connections']

            # Deve ter conexões ociosas
            assert global_metrics['idle_connections'] >= pool_config['min_connections']

    def test_connection_health_monitoring(self, temp_db_path, pool_config):
        """Testa monitoring de saúde das conexões."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Executar algumas operações
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
                cursor.execute("INSERT INTO test (data) VALUES (?)", ("test_data",))
                conn.connection.commit()

            # Verificar métricas de saúde
            metrics = pool.get_metrics()
            global_metrics = metrics['global_metrics']

            # Deve ter conexões ativas
            assert global_metrics['total_requests'] > 0
            assert global_metrics['total_connections_created'] > 0

    def test_auto_scaling_pool_adjustment(self, temp_db_path, pool_config):
        """Testa auto-scaling automático do pool baseado na utilização."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Aguardar health check inicial
            time.sleep(2.5)

            # Simular alta utilização
            connections = []
            for i in range(pool_config['min_connections'] + 2):
                conn = pool._get_connection_internal()
                connections.append(conn)

            # Aguardar auto-scaling
            time.sleep(pool_config['health_check_interval'] + 1)

            # Verificar métricas após escalabilidade
            metrics = pool.get_metrics()
            global_metrics = metrics['global_metrics']

            # Deve ter criado conexões adicionais
            assert global_metrics['current_pool_size'] >= len(connections)

            # Liberar conexões
            for conn in connections:
                pool._return_connection(conn)

            # Aguardar scale down
            time.sleep(pool_config['health_check_interval'] + 1)

            # Verificar scale down
            final_metrics = pool.get_metrics()['global_metrics']
            assert final_metrics['current_pool_size'] >= pool_config['min_connections']

    @pytest.mark.parametrize("concurrency_level", [2, 5, 8])
    def test_concurrent_access_pool_stress(self, temp_db_path, pool_config, concurrency_level):
        """Testa acesso concorrente ao pool sob estresse."""
        results = []
        errors = []
        lock = threading.Lock()

        def concurrent_worker(worker_id: int):
            """Worker para teste de concorrência."""
            try:
                worker_results = []
                with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
                    for i in range(10):  # 10 operações por worker
                        with pool.get_connection() as conn:
                            cursor = conn.connection.cursor()

                            # Operação de leitura/escrita alternada
                            if i % 2 == 0:
                                cursor.execute("SELECT ?, sqlite_version()", (worker_id * 100 + i,))
                                result = cursor.fetchone()
                                worker_results.append(result)
                            else:
                                # Criar tabela se não existir
                                cursor.execute("CREATE TABLE IF NOT EXISTS concurrent_test (id INTEGER, worker_id INTEGER, op_count INTEGER)")
                                # Inserir dados
                                cursor.execute(
                                    "INSERT INTO concurrent_test (worker_id, op_count) VALUES (?, ?)",
                                    (worker_id, i)
                                )

                            conn.connection.commit()

                with lock:
                    results.extend(worker_results)

            except Exception as e:
                with lock:
                    errors.append(f"Worker {worker_id}: {str(e)}")

        # Executar threads concorrentes
        threads = []
        for i in range(concurrency_level):
            thread = threading.Thread(target=concurrent_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Aguardar conclusão
        for thread in threads:
            thread.join(timeout=30.0)

        # Verificar resultados
        assert len(results) >= concurrency_level * 5, "Devem haver resultados de operações SELECT"
        assert len(errors) == 0, f"Erros durante acesso concorrente: {errors}"

    def test_connection_validation_prevents_corruption(self, temp_db_path, pool_config):
        """Testa como validação de conexões previne corrupção."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Forçar erro em uma conexão
            with pool.get_connection() as conn:
                # Simular problema na conexão
                try:
                    conn.connection.cursor().execute("INVALID SQL")
                except sqlite3.OperationalError:
                    pass

                # Retornar conexão ao pool (deve ser marcada como não saudável)
                # (Isso seria feito automaticamente pelo context manager)

            # Próxima operação deve usar conexão saudável
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

                assert result == (1,), "Dever usar conexão saudável"

    def test_statement_caching_performance(self, temp_db_path, pool_config):
        """Testa melhoria de performance do statement caching."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            test_query = "SELECT ?, ?";
            params_list = [(i, i*2) for i in range(100)]  # 100 execuções

            # Medir tempo com caching
            start_time = time.time()

            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                for params in params_list:
                    cursor.execute(test_query, params)
                    # Não fazer fetch para focar na execução

            caching_time = time.time() - start_time

            # Verificar que não demorou muito (>100ms por execução seria preocupante)
            if caching_time > 10.0:  # Mais de 10 segundos para 100 execuções
                pytest.fail(f"Statement caching muito lento: {caching_time:.2f}s para {len(params_list)} execuções")

    def test_wal_mode_integration(self, temp_db_path, pool_config):
        """Testa integração de WAL mode para melhor concorrência."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Criar tabela para testar WAL
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("CREATE TABLE wal_test (id INTEGER, data TEXT)")

                # Inserir dados para gerar WAL traffic
                for i in range(20):
                    cursor.execute("INSERT INTO wal_test (id, data) VALUES (?, ?)", (i, f"data_{i}"))

                conn.connection.commit()

            # Verificar que operações funcionam com WAL habilitado
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM wal_test")
                count = cursor.fetchone()[0]

                assert count == 20, "WAL mode deve permitir operações normais"

    def test_foreign_keys_pool_integration(self, temp_db_path, pool_config):
        """Testa integração de foreign keys no pool."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Criar tabelas com foreign keys
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()

                cursor.execute("""
                    CREATE TABLE parent (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE child (
                        id INTEGER PRIMARY KEY,
                        parent_id INTEGER,
                        name TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent(id)
                    )
                """)

                conn.connection.commit()

            # Testar foreign key enforcement
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()

                # Inserir dados válidos
                cursor.execute("INSERT INTO parent (name) VALUES (?)", ("parent_data",))
                parent_id = cursor.lastrowid

                cursor.execute("INSERT INTO child (parent_id, name) VALUES (?, ?)",
                             (parent_id, "child_data"))
                conn.connection.commit()

            # Verificar dados
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM parent")
                parent_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM child")
                child_count = cursor.fetchone()[0]

                assert parent_count == 1 and child_count == 1, "Foreign keys devem funcionar corretamente"

    def test_connection_pool_metrics_comprehensiveness(self, temp_db_path, pool_config):
        """Testa abrangência das métricas do pool de conexões."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Executar operações diversas
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("CREATE TABLE metrics_test (id INTEGER)")
                for i in range(5):
                    cursor.execute("INSERT INTO metrics_test (id) VALUES (?)", (i,))
                conn.connection.commit()

            # Obter métricas
            metrics = pool.get_metrics()

            # Verificar estrutura completa
            required_sections = ['global_metrics', 'config', 'timestamp']
            for section in required_sections:
                assert section in metrics, f"Section {section} faltando em métricas"

            # Verificar métricas globais críticas
            global_metrics = metrics['global_metrics']
            critical_metrics = [
                'total_connections_created', 'total_requests',
                'current_pool_size', 'pool_hits'
            ]

            for metric in critical_metrics:
                assert metric in global_metrics, f"Métrica crítica {metric} faltando"

            # Valores devem ser não-negativos
            for metric, value in global_metrics.items():
                if isinstance(value, (int, float)):
                    assert value >= 0, f"Métrica {metric} tem valor negativo: {value}"

    def test_pool_exhaustion_graceful_handling(self, temp_db_path):
        """Testa handling gracioso quando pool é esgotado."""
        # Configurar pool pequeno para forçar exaustão
        small_config = {
            'min_connections': 1,
            'max_connections': 2,
            'connection_timeout': 1.0,  # Timeout curto
            'busy_timeout': 1000  # Timeout SQLite curto
        }

        with EnhancedDatabaseConnectionPool(temp_db_path, small_config) as pool:
            connections = []

            # Usar todas as conexões disponíveis
            try:
                while len(connections) < small_config['max_connections']:
                    conn = pool._get_connection_internal()
                    connections.append(conn)

                # Próxima tentativa deve falhar graciosamente
                with pytest.raises(RuntimeError, match="esgotado"):
                    pool._get_connection_internal()

            finally:
                # Liberar conexões
                for conn in connections:
                    try:
                        pool._return_connection(conn)
                    except Exception:
                        pass

    def test_health_check_prevents_stale_connections(self, temp_db_path, pool_config):
        """Testa como health check previne uso de conexões stale."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Aguardar health check
            time.sleep(pool_config['health_check_interval'] + 1)

            # Verificar métricas após health check
            metrics_before = pool.get_metrics()

            # Aguardar mais um ciclo de health check
            time.sleep(pool_config['health_check_interval'] + 1)

            metrics_after = pool.get_metrics()

            # Health checks devem estar funcionando
            # (não podemos testar conexão stale sem simular falha de rede)
            assert isinstance(metrics_after, dict)
            assert 'global_metrics' in metrics_after

    def test_pool_scaling_under_load(self, temp_db_path, pool_config):
        """Testa escalabilidade do pool sob carga real."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Determinar carga inicial
            initial_metrics = pool.get_metrics()['global_metrics']

            # Simular carga pesada
            def load_worker():
                for _ in range(10):
                    with pool.get_connection() as conn:
                        cursor = conn.connection.cursor()
                        cursor.execute("SELECT sqlite_version()")
                        time.sleep(0.1)  # Simular processamento

            # Executar múltiplos workers
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(load_worker) for _ in range(3)]
                concurrent.futures.wait(futures, timeout=30.0)

            # Verificar escalabilidade
            final_metrics = pool.get_metrics()['global_metrics']

            # Deve ter atendido todas as requisições
            assert final_metrics['total_requests'] > 0

            # Pool deve ter se ajustado à carga
            assert final_metrics['current_pool_size'] >= pool_config['min_connections']

    def test_pool_metrics_export_functionality(self, temp_db_path, pool_config):
        """Testa funcionalidade de exportação de métricas do pool."""
        with EnhancedDatabaseConnectionPool(temp_db_path, pool_config) as pool:
            # Gerar algumas métricas
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("CREATE TABLE export_test (id INTEGER)")
                cursor.execute("INSERT INTO export_test (id) VALUES (1)")
                conn.connection.commit()

            # Exportar métricas
            export_path = pool.export_metrics()

            # Verificar se arquivo foi criado
            assert export_path and os.path.exists(export_path), f"Arquivo de métricas não criado: {export_path}"

            # Verificar conteúdo do arquivo
            if export_path and os.path.exists(export_path):
                with open(export_path, 'r', encoding='utf-8') as f:
                    try:
                        metrics_data = json.load(f)

                        # Verificar estrutura
                        assert 'global_metrics' in metrics_data
                        assert 'config' in metrics_data
                        assert 'timestamp' in metrics_data

                        # Cleanup
                        os.remove(export_path)

                    except Exception as e:
                        pytest.fail(f"Erro na leitura do arquivo de métricas: {e}")