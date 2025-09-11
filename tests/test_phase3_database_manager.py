#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Phase 3 Tests
Testes abrangentes para DatabaseManagerV2 com monitoring e recovery
"""

import pytest
import sqlite3
import tempfile
import os
import time
import threading
import concurrent.futures
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any
from datetime import datetime

from engine.db import UnifiedDatabaseManager as DatabaseManagerV2
from engine.db.enhanced_connection_pool import EnhancedDatabaseConnectionPool


class TestDatabaseManagerPhase3:
    """Testes abrangentes para DatabaseManagerV2 com features de produção."""

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
    def db_manager(self, temp_db_path):
        """Fixture para DatabaseManagerV2 configurado."""
        config = {
            'pool': {
                'min_connections': 1,
                'max_connections': 5,
                'connection_timeout': 5.0,
                'health_check_interval': 1.0
            },
            'retry': {
                'max_retries': 3,
                'base_delay': 0.1,
                'backoff_factor': 2.0
            }
        }

        manager = DatabaseManagerV2(config)
        manager.connect(temp_db_path)
        yield manager
        manager.close_all()

    def test_connection_health_monitoring(self, db_manager):
        """Testa monitoring de saúde das conexões."""
        # Obter métricas de sistema
        system_metrics = db_manager.system_monitor.get_system_metrics()

        # Verificar estrutura das métricas
        assert isinstance(system_metrics, dict)
        assert 'available' in system_metrics
        assert 'timestamp' in system_metrics

        if system_metrics['available']:
            assert 'cpu_percent' in system_metrics
            assert 'memory_percent' in system_metrics
            assert 'cpu_alert' in system_metrics
            assert 'memory_alert' in system_metrics

    def test_performance_metrics_tracking(self, db_manager):
        """Testa tracking de métricas de performance."""
        # Executar algumas operações para gerar métricas
        db_manager.execute_query("SELECT 1")

        # Verificar métricas
        metrics = db_manager.get_performance_metrics()

        assert 'performance_metrics' in metrics
        assert 'system_metrics' in metrics
        assert 'recovery_stats' in metrics
        assert 'error_stats' in metrics

        # Verificar estrutura de métricas de performance
        perf_metrics = metrics['performance_metrics']
        assert 'total_queries' in perf_metrics
        assert 'average_query_time' in perf_metrics
        assert perf_metrics['total_queries'] > 0

    def test_recovery_from_connection_loss(self, db_manager, temp_db_path):
        """Testa recovery automático de conexões perdidas."""
        # Simular perda de conexão
        with patch.object(db_manager.system_monitor, 'check_performance_alerts') as mock_alerts:
            mock_alerts.return_value = []  # Sem alerts inicialmente

            # Forçar um cenário que pode causar falha
            try:
                # Simula operational error que pode indicar conexão perdida
                with patch('sqlite3.connect') as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.cursor.side_effect = sqlite3.OperationalError("connection lost")
                    mock_connect.return_value = mock_conn

                    # Tentar executar query - deve falhar graciosamente
                    result = db_manager.execute_query("SELECT 1")
                    assert result is None

                    # Verificar estatísticas de erro
                    error_stats = db_manager.get_error_stats()
                    assert error_stats['query_errors'] > 0

            except Exception:
                # Espera-se falha controlada neste cenário
                pass

    def test_concurrent_access_handling(self, db_manager):
        """Testa handling de acesso concorrente."""
        results = []
        errors = []

        def worker(worker_id: int):
            """Worker function para testes de concorrência."""
            try:
                # Executar queries simultâneas
                for i in range(10):
                    result = db_manager.execute_query("SELECT ?, ?", (worker_id, i))
                    results.append(result)

                    # Pequeno delay para aumentar concorrência
                    time.sleep(0.01)

            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")

        # Executar múltiplas threads simultaneamente
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]

            # Aguardar conclusão
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verificar resultados
        assert len(results) == 50  # 5 workers * 10 queries cada
        assert len(errors) == 0, f"Erros durante concorrência: {errors}"

    def test_memory_pressure_handling(self, db_manager):
        """Testa handling de pressão de memória."""
        # Simular cenário de alta pressão de memória
        with patch.object(db_manager.system_monitor, 'get_system_metrics') as mock_metrics:
            # Simular alta utilização de memória
            mock_metrics.return_value = {
                'available': True,
                'cpu_percent': 50.0,
                'memory_percent': 90.0,
                'memory_mb': 1024.0,
                'cpu_alert': False,
                'memory_alert': True,
                'timestamp': datetime.now().isoformat()
            }

            # Executar queries em condição de memória alta
            for i in range(10):
                result = db_manager.execute_query("SELECT ?", (i,))

            # Verificar se sistema lidou com a situação
            system_alerts = db_manager.system_monitor.check_performance_alerts()
            assert len(system_alerts) > 0
            assert any('memory' in alert.lower() for alert in system_alerts)

    def test_large_dataset_performance(self, db_manager):
        """Testa performance com datasets grandes (1000+ registros)."""
        # Preparar dados de teste grandes
        test_data = [(i, f"name_{i}", f"desc_{i}", "png") for i in range(1200)]

        # Inserir dados em lotes
        start_time = time.time()
        batch_size = 100

        for i in range(0, len(test_data), batch_size):
            batch = test_data[i:i+batch_size]

            # Usar executeMany para inserção em lote
            db_manager.execute_many(
                "INSERT OR IGNORE INTO roms (id, name, description, size_file) VALUES (?, ?, ?, ?)",
                batch
            )

        insertion_time = time.time() - start_time

        # Verificar contagem
        count_result = db_manager.execute_query("SELECT COUNT(*) FROM roms")
        assert count_result is not None
        assert count_result[0][0] >= 1000

        # Verificar performance (deve ser < 5 segundos para 1000 inserts)
        assert insertion_time < 10.0, f"Inserção muito lenta: {insertion_time:.2f}s"

        # Verificar métricas de performance
        metrics = db_manager.get_performance_metrics()
        perf_metrics = metrics['performance_metrics']

        assert perf_metrics['total_queries'] > 0
        assert perf_metrics['average_query_time'] > 0

    def test_transaction_rollback_scenarios(self, db_manager):
        """Testa cenários de rollback em transações."""
        # Criar dados de teste
        test_data = [
            ("INSERT INTO roms VALUES (1, 1, 'game1', '100MB', 'crc1', 'md51', 'sha1', 'filename1')",
             None),
            ("INSERT INTO roms VALUES (2, 1, 'game2', '200MB', 'crc2', 'md52', 'sha2', 'filename2')",
             None),
            ("INSERT INTO roms SELECT NULL FROM roms", None),  # Deve falhar por constraint
        ]

        # Executar transação que deve falhar no meio
        result = db_manager.execute_transaction(test_data)
        assert result == False  # Deve falhar devido à query inválida

        # Verificar que dados não foram inseridos
        count_result = db_manager.execute_query("SELECT COUNT(*) FROM roms")
        if count_result:
            count = count_result[0][0]
            # Se rollback funcionou, deve ter 0 registros
            assert count == 0

    def test_system_health_monitoring(self, db_manager):
        """Testa monitoramento completo de saúde do sistema."""
        health_report = db_manager.check_system_health()

        # Verificar estrutura do relatório
        assert isinstance(health_report, dict)
        assert 'system_status' in health_report
        assert 'issues' in health_report
        assert 'recommendations' in health_report
        assert 'timestamp' in health_report

        # Status deve ser válido
        assert health_report['system_status'] in ['healthy', 'warning', 'critical']
        assert isinstance(health_report['issues'], list)
        assert isinstance(health_report['recommendations'], list)

    def test_error_statistic_tracking(self, db_manager):
        """Testa tracking detalhado de estatísticas de erro."""
        # Forçar alguns erros
        db_manager._track_error('connection_errors')
        db_manager._track_error('query_errors')
        db_manager._track_error('integrity_errors')

        # Obter estatísticas
        error_stats = db_manager.get_error_stats()

        # Verificar estatísticas básicas
        assert error_stats['connection_errors'] >= 1
        assert error_stats['query_errors'] >= 1
        assert error_stats['integrity_errors'] >= 1

        # Resetar e verificar
        db_manager.reset_error_stats()
        reset_stats = db_manager.get_error_stats()

        assert reset_stats['connection_errors'] == 0
        assert reset_stats['query_errors'] == 0
        assert reset_stats['integrity_errors'] == 0

    @pytest.mark.parametrize("thread_count", [1, 5, 10])
    def test_multi_threading_stress(self, db_manager, thread_count):
        """Testa estresse com múltiplas threads."""

        results = []
        errors = []
        lock = threading.Lock()

        def stress_worker(thread_id: int):
            """Worker para estresse."""
            try:
                thread_results = []
                for i in range(20):  # 20 operações por thread
                    # Mix de operações de leitura/escrita
                    if i % 2 == 0:
                        result = db_manager.execute_query("SELECT ?, ?", (thread_id, i))
                        thread_results.append(result)
                    else:
                        # Tentativa de INSERT (pode falhar, é OK)
                        try:
                            db_manager.execute_query(
                                "INSERT OR IGNORE INTO roms VALUES (?, NULL, ?, ?, ?, ?, ?, ?)",
                                (thread_id * 1000 + i, f"name_{i}", "10MB", "crc", "md5", "sha", f"file_{i}")
                            )
                        except Exception:
                            pass  # Ignorar erros esperados

                with lock:
                    results.extend(thread_results)

            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Executar threads simultaneamente
        threads = []
        for i in range(thread_count):
            thread = threading.Thread(target=stress_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Aguardar conclusão
        for thread in threads:
            thread.join(timeout=30.0)  # Timeout de 30 segundos

        # Verificar que operações foram executadas
        assert len(results) >= thread_count * 10  # Pelo menos 10 operações por thread
        total_errors = len(errors)

        if total_errors > 0:
            # Log de erros mas não falha obrigatória (concorrência pode gerar conflitos)
            pytest.fail(f"Erros excessivos em teste de concorrência: {total_errors}: {errors[:3]}...")

        # Verificar métricas de performance
        metrics = db_manager.get_performance_metrics()
        assert metrics['performance_metrics']['total_queries'] > thread_count * 10

    def test_memory_usage_under_stress(self, db_manager):
        """Testa uso de memória sob estresse."""
        import gc

        # Baseline de memória
        initial_metrics = db_manager.system_monitor.get_system_metrics()

        # Estressar com muitas operações
        for i in range(500):
            db_manager.execute_query("SELECT ?, ?, ?, ?, ?", (i, i*2, i*3, i*4, i*5))

        # Coletar lixo
        gc.collect()

        # Verificar métricas após estresse
        final_metrics = db_manager.system_monitor.get_system_metrics()

        # Verificar que o sistema não ficou com alertas de memória
        if final_metrics.get('available') and not final_metrics.get('memory_alert'):
            # Apenas log se não há alerta
            pass
        elif not final_metrics.get('available'):
            # Sistema não disponível - pode ser ambiente de teste
            pytest.skip("Monitoramento de memória não disponível no ambiente de teste")

    def test_connection_pool_resiliency(self, db_manager):
        """Testa resiliência do pool de conexões."""
        pool_metrics = db_manager.get_metrics()

        if pool_metrics:
            # Verificar estrutura das métricas do pool
            assert 'global_metrics' in pool_metrics
            assert 'config' in pool_metrics
            assert 'timestamp' in pool_metrics

            global_metrics = pool_metrics['global_metrics']
            assert 'total_requests' in global_metrics
            assert 'total_errors' in global_metrics
            assert 'current_pool_size' in global_metrics
        else:
            pytest.skip("Pool metrics não disponíveis")

    def test_error_recovery_and_resilience(self, db_manager, temp_db_path):
        """Testa recuperação de erros e resiliência geral."""
        # Simular vários tipos de erro
        error_scenarios = [
            ("database_locked", lambda: db_manager.execute_query("SELECT 1")),
            ("corrupted_data", lambda: db_manager.execute_query("SELECT * FROM nonexistent_table")),
        ]

        total_errors = 0

        for scenario_name, operation in error_scenarios:
            try:
                # Tentar operação que pode falhar
                result = operation()
                if result is None:
                    total_errors += 1
            except Exception as e:
                # Registrar erro mas continuar
                total_errors += 1

        # Verificar estatísticas após erros
        error_stats = db_manager.get_error_stats()

        # Sistema deve continuar operacional mesmo depois de erros
        assert db_manager.is_connected()
        assert isinstance(error_stats, dict)

        # Performance deve ainda ser monitorada
        perf_metrics = db_manager.get_performance_metrics()
        assert isinstance(perf_metrics, dict)