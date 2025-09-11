"""
Testes abrangentes para Expansões do DB: Prometheus, Retry Manager, Monitoring
Cobertura: Métricas Prometheus, retry logic, alert thresholds, monitoring
Cenários críticos: falhas de conexão, métricas corrompidas, timeouts de retry
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer
import socket

import sys
sys.path.insert(0, 'engine/db')

from prometheus_exports import (
    MetricsCollector,
    PrometheusExporter,
    PrometheusHandler,
    get_global_exporter
)
from retry_manager import (
    RetryManager,
    RetryConfig,
    retryable,
    retry_operation
)


@pytest.fixture
def metrics_collector():
    """Fixture para MetricsCollector."""
    return MetricsCollector()


@pytest.fixture
def prometheus_exporter():
    """Fixture para PrometheusExporter."""
    # Usar porta alta para evitar conflitos
    exporter = PrometheusExporter(port=0, host='localhost')
    yield exporter
    exporter.stop()


class TestMetricsCollector:
    """Testes para MetricsCollector."""

    def test_gauge_metric(self, metrics_collector):
        """Testa métrica gauge."""
        metrics_collector.set_gauge("test_gauge", 42.5, description="Test gauge")

        text = metrics_collector.get_metrics_text()
        assert "# HELP test_gauge Test gauge" in text
        assert "# TYPE test_gauge gauge" in text
        assert "test_gauge 42.5" in text

    def test_counter_metric(self, metrics_collector):
        """Testa métrica counter."""
        metrics_collector.increment_counter("test_counter", description="Test counter")
        metrics_collector.increment_counter("test_counter", 2.5)

        text = metrics_collector.get_metrics_text()
        assert "# HELP test_counter Test counter" in text
        assert "# TYPE test_counter counter" in text
        assert "test_counter 3.5" in text

    def test_histogram_metric(self, metrics_collector):
        """Testa métrica histogram."""
        metrics_collector.observe_histogram("test_histogram", 5.0, description="Test histogram")
        metrics_collector.observe_histogram("test_histogram", 10.0)

        text = metrics_collector.get_metrics_text()
        assert "# HELP test_histogram Test histogram" in text
        assert "# TYPE test_histogram histogram" in text
        assert "test_histogram_count 2" in text

    def test_gauge_with_labels(self, metrics_collector):
        """Testa métrica com labels."""
        labels = {"method": "GET", "status": "200"}
        metrics_collector.set_gauge("http_requests", 5.0, labels=labels)

        text = metrics_collector.get_metrics_text()
        assert 'http_requests{method="GET",status="200"} 5.0' in text

    def test_thread_safety(self, metrics_collector):
        """Testa segurança de threads."""
        results = []

        def update_metrics():
            for i in range(100):
                metrics_collector.set_gauge("thread_test", i)
                results.append(metrics_collector.metrics.get('thread_test', {}).get('value', 0))

        threads = [threading.Thread(target=update_metrics) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Deve ter criado métricas para thread_test
        assert 'thread_test' in metrics_collector.metrics


class TestPrometheusExporter:
    """Testes para PrometheusExporter."""

    def test_initialization(self):
        """Testa inicialização do exportador."""
        exporter = PrometheusExporter(port=8080, host='127.0.0.1')
        assert exporter.port == 8080
        assert exporter.host == '127.0.0.1'
        assert not exporter._running
        assert exporter.server is None

    def test_start_and_stop(self):
        """Testa início e parada do servidor."""
        # Usar porta dinâmica para evitar conflitos
        exporter = PrometheusExporter(port=0, host='localhost')
        exporter.start()

        assert exporter._running
        assert exporter.server is not None

        exporter.stop()
        assert not exporter._running

    @patch('time.sleep')  # Evitar delay real
    def test_start_stop_multiple_times(self, mock_sleep):
        """Testa iniciar/parar múltiplas vezes."""
        exporter = PrometheusExporter(port=0, host='localhost')

        # Primeiro ciclo
        exporter.start()
        assert exporter._running
        exporter.stop()
        assert not exporter._running

        # Segundo ciclo
        exporter.start()
        assert exporter._running
        exporter.stop()
        assert not exporter._running

    def test_global_exporter_instance(self):
        """Testa instância global."""
        global_exp1 = get_global_exporter()
        global_exp2 = get_global_exporter()

        assert global_exp1 is global_exp2  # Mesma instância

    def test_collect_db_metrics_with_mock_db(self):
        """Testa coleta de métricas do banco mockado."""
        exporter = PrometheusExporter(port=0, host='localhost')

        # Mock DB manager
        db_manager = Mock()
        db_manager.get_metrics.return_value = Mock(
            active_connections=5,
            idle_connections=10,
            total_connections_created=15
        )
        db_manager.get_performance_metrics.return_value = {
            'performance_metrics': {
                'total_queries': 100,
                'total_transactions': 20,
                'average_query_time': 0.5,
                'slow_queries_count': 2
            },
            'system_metrics': {
                'available': True,
                'cpu_percent': 45.2,
                'memory_mb': 2048
            }
        }

        db_manager.get_error_stats.return_value = {
            'connection_errors': 3,
            'timeout_errors': 1,
            'last_error': 'Simulated error',
            'last_error_time': time.time()
        }

        exporter.collect_db_metrics(db_manager)

        # Verifica métricas coletadas
        text = exporter.metrics_collector.get_metrics_text()
        assert "db_pool_connections_active 5" in text
        assert "db_pool_connections_idle 10" in text
        assert "db_queries_total 100" in text
        assert "db_errors_total{type=\"connection_errors\"} 3" in text
        assert "system_cpu_percent 45.2" in text


class TestPrometheusHandler:
    """Testes para PrometheusHandler."""

    def test_handler_creation(self):
        """Testa criação do handler."""
        collector = MetricsCollector()
        handler_class = PrometheusHandler

        # Simular criação de handler com request mock
        class MockRequest:
            def makefile(self, *args, **kwargs):
                return Mock()

        request = MockRequest()
        handler = handler_class(collector, request, ('127.0.0.1', 0), Mock())

        assert handler.metrics_collector is collector

    @patch('http.server.BaseHTTPRequestHandler.send_response')
    @patch('http.server.BaseHTTPRequestHandler.send_header')
    @patch('http.server.BaseHTTPRequestHandler.end_headers')
    def test_metrics_endpoint(self, mock_end_headers, mock_send_header, mock_send_response, metrics_collector):
        """Testa endpoint /metrics."""
        # Adicionar uma métrica de teste
        metrics_collector.set_gauge("test_metric", 42)

        collector = metrics_collector
        handler_class = PrometheusHandler

        # Simular criação de handler
        class MockRequest:
            def makefile(self, *args, **kwargs):
                return Mock()

        request = MockRequest()
        handler = handler_class(collector, request, ('127.0.0.1', 0), Mock())

        # Simular request GET para /metrics
        with patch.object(handler, 'path', '/metrics'):
            with patch.object(handler, 'send_response') as mock_resp, \
                 patch.object(handler, 'send_header') as mock_header, \
                 patch.object(handler, 'end_headers') as mock_end, \
                 patch.object(handler, 'wfile') as mock_wfile:

                handler.do_GET()

                mock_resp.assert_called_with(200)
                mock_header.assert_called_with('Content-Type', 'text/plain; charset=utf-8')
                mock_end.assert_called()

                # Verifica que dados foram escritos
                written_data = b''.join(call[0][0] for call in mock_wfile.write.call_args_list)
                assert b'test_metric 42' in written_data

    @patch('http.server.BaseHTTPRequestHandler.send_response')
    @patch('http.server.BaseHTTPRequestHandler.end_headers')
    def test_not_found_endpoint(self, mock_end_headers, mock_send_response):
        """Testa endpoint não encontrado."""
        collector = MetricsCollector()
        handler_class = PrometheusHandler

        # Simular criação de handler
        class MockRequest:
            def makefile(self, *args, **kwargs):
                return Mock()

        request = MockRequest()
        handler = handler_class(collector, request, ('127.0.0.1', 0), Mock())

        # Simular request GET para endpoint inválido
        with patch.object(handler, 'path', '/invalid'):
            with patch.object(handler, 'send_response') as mock_resp:
                handler.do_GET()
                mock_resp.assert_called_with(404)


class TestRetryManager:
    """Testes para RetryManager."""

    def test_initialization_default_config(self):
        """Testa inicialização com config padrão."""
        manager = RetryManager()
        assert manager.config.max_attempts == 3
        assert manager.config.base_delay == 0.1
        assert manager.stats['total_retries'] == 0

    def test_initialization_custom_config(self):
        """Testa inicialização com config customizada."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        manager = RetryManager(config)
        assert manager.config.max_attempts == 5
        assert manager.config.base_delay == 1.0

    def test_successful_execution_no_retry(self):
        """Testa execução bem-sucedida sem retry."""
        manager = RetryManager()

        def success_func():
            return "success"

        result = manager.execute_with_retry(success_func)
        assert result == "success"
        assert manager.stats['total_retries'] == 0
        assert manager.stats['successful_retries'] == 0

    @patch('time.sleep')
    def test_retry_on_failure_then_success(self, mock_sleep):
        """Testa retry falhando primeiro, depois succeeding."""
        manager = RetryManager()
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Simulated failure")
            return "success"

        result = manager.execute_with_retry(flaky_func)
        assert result == "success"
        assert call_count == 2  # Chamada inicial + 1 retry
        assert manager.stats['total_retries'] == 1
        assert manager.stats['successful_retries'] == 1

    @patch('time.sleep')
    def test_exhausted_retries(self, mock_sleep):
        """Testa quando retriers são esgotados."""
        manager = RetryManager(RetryConfig(max_attempts=2))

        def always_fail():
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            manager.execute_with_retry(always_fail)

        assert manager.stats['total_retries'] == 1
        assert manager.stats['successful_retries'] == 0
        assert manager.stats['failed_retries'] == 1

    def test_no_retry_on_non_retryable_exception(self):
        """Testa que exceções não retryable não são retried."""
        manager = RetryManager()

        def non_retryable_error():
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            manager.execute_with_retry(non_retryable_error)

        assert manager.stats['total_retries'] == 0

    @patch('time.sleep')
    @patch('random.uniform')
    def test_exponential_backoff_with_jitter(self, mock_random, mock_sleep):
        """Testa backoff exponencial com jitter."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            exponential_base=2.0,
            jitter=True
        )
        manager = RetryManager(config)

        def fail_twice():
            return "will fail"

        # Mock para controlar tempo e delay
        mock_random.return_value = 0.5

        try:
            manager.execute_with_retry(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except:
            pass

        # Verifica se jitter foi aplicado
        assert mock_random.called

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        manager = RetryManager()

        # Reseta stats antes de começar
        manager.reset_stats()

        success_func = lambda: "success"
        manager.execute_with_retry(success_func)

        stats = manager.get_stats()
        assert 'total_retries' in stats
        assert 'successful_retries' in stats


class TestRetryConfig:
    """Testes para RetryConfig."""

    def test_aggressive_config(self):
        """Testa configuração agressiva."""
        config = RetryConfig.aggressive()
        assert config.max_attempts == 5
        assert config.base_delay == 0.05
        assert config.exponential_base == 1.5

    def test_conservative_config(self):
        """Testa configuração conservadora."""
        config = RetryConfig.conservative()
        assert config.max_attempts == 2
        assert config.base_delay == 0.5
        assert config.exponential_base == 2.0

    def test_custom_exception_types(self):
        """Testa tipos de exceção customizados."""
        from sqlite3 import OperationalError
        config = RetryConfig(retryable_exceptions=[ValueError, OperationalError])
        assert ValueError in config.retryable_exceptions
        assert OperationalError in config.retryable_exceptions


@retryable()
def retryable_test_function():
    """Função de teste para decorator @retryable."""
    return "success"


@retryable(RetryConfig(max_attempts=5))
def retryable_custom_config():
    """Função de teste com config customizada."""
    return "success"


class TestRetryDecorators:
    """Testes para decorators de retry."""

    def test_retryable_decorator_default(self):
        """Testa decorator @retryable padrão."""
        result = retryable_test_function()
        assert result == "success"

    def test_retryable_decorator_custom_config(self):
        """Testa decorator @retryable com config customizada."""
        result = retryable_custom_config()
        assert result == "success"

    @patch('time.sleep')
    def test_retry_operation_utility(self, mock_sleep):
        """Testa função utilitária retry_operation."""
        call_count = [0]

        def operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Retry me")
            return "success"

        result = retry_operation(operation, max_attempts=3, base_delay=0.01)
        assert result == "success"
        assert call_count[0] == 2


class TestIntegration:
    """Testes de integração dos componentes de monitoramento."""

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_end_to_end_monitoring(self, mock_virtual_memory, mock_cpu_percent):
        """Testa monitoramento end-to-end com mocks."""
        # Mock system metrics
        mock_cpu_percent.return_value = 65.5
        mock_virtual_memory.return_value = Mock()
        mock_virtual_memory.return_value.available = 1024 * 1024 * 1024  # 1GB

        exporter = PrometheusExporter(port=0, host='localhost')
        exporter.start()

        try:
            # Adicionar métricas manuais
            exporter.metrics_collector.set_gauge("system_cpu_percent", 65.5)
            exporter.metrics_collector.set_gauge("system_memory_mb", 2048)

            # Simular coleta de dados de DB
            mock_db_manager = Mock()
            mock_db_manager.get_metrics.return_value = Mock(
                active_connections=8,
                idle_connections=12,
                total_connections_created=25
            )

            exporter.collect_db_metrics(mock_db_manager)

            # Verificar métricas no output
            metrics_output = exporter.metrics_collector.get_metrics_text()

            assert "system_cpu_percent 65.5" in metrics_output
            assert "db_pool_connections_active 8" in metrics_output
            assert "db_pool_connections_idle 12" in metrics_output

        finally:
            exporter.stop()

    def test_concurrent_access_to_exporter(self):
        """Testa acesso concorrente ao exportador."""
        exporter = PrometheusExporter(port=0, host='localhost')
        exporter.start()

        results = []
        errors = []

        def concurrent_worker(worker_id):
            try:
                for i in range(10):
                    exporter.metrics_collector.set_gauge(f"test_{worker_id}", i)
                    # Pequeno delay para simular concorrência
                    time.sleep(0.001)
                results.append(f"worker_{worker_id}_done")
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")

        threads = [threading.Thread(target=concurrent_worker, args=(i,)) for i in range(5)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert len(errors) == 0

        # Verificar que métricas foram criadas
        assert len(exporter.metrics_collector.metrics) > 0

        exporter.stop()


if __name__ == "__main__":
    pytest.main([__file__])