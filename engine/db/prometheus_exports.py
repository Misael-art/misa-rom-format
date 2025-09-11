#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Prometheus Exports
Sistema de exposição de métricas para monitoramento com Prometheus
"""

import os
import time
import threading
from typing import Dict, Any, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
from datetime import datetime

class MetricsCollector:
    """Coletor de métricas customizado para banco de dados."""

    def __init__(self):
        self.metrics = {}
        self._lock = threading.Lock()

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, description: str = ""):
        """Define métrica gauge."""
        with self._lock:
            key = name
            if labels:
                key += "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"

            self.metrics[name] = {
                'type': 'gauge',
                'key': key,
                'value': value,
                'labels': labels or {},
                'description': description
            }

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None, description: str = ""):
        """Incrementa métrica counter."""
        with self._lock:
            key = name
            if labels:
                key += "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"

            if name not in self.metrics:
                self.metrics[name] = {
                    'type': 'counter',
                    'key': key,
                    'value': value,
                    'labels': labels or {},
                    'description': description
                }
            else:
                self.metrics[name]['value'] += value

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, description: str = ""):
        """Observa valor para histograma."""
        with self._lock:
            key = f"{name}_bucket"
            if labels:
                base_labels = labels.copy()
                base_labels['le'] = str(value)
                key += "{" + ",".join(f'{k}="{v}"' for k, v in base_labels.items()) + "}"

            if name not in self.metrics:
                self.metrics[name] = {
                    'type': 'histogram',
                    'key': key,
                    'observations': [value],
                    'labels': labels or {},
                    'description': description,
                    'count': 1,
                    'sum': value
                }
            else:
                self.metrics[name]['observations'].append(value)
                self.metrics[name]['count'] += 1
                self.metrics[name]['sum'] += value

    def get_metrics_text(self) -> str:
        """Retorna métricas no formato Prometheus."""
        lines = []
        with self._lock:
            for name, metric in self.metrics.items():
                if metric['description']:
                    lines.append(f"# HELP {name} {metric['description']}")
                lines.append(f"# TYPE {name} {metric['type']}")

                if metric['type'] == 'histogram':
                    # Adicionar buckets
                    for obs in metric['observations'][-100:]:  # Últimas 100 observações
                        lines.append(f"{metric['key']} {obs}")

                    # _count e _sum
                    labels = metric['labels'].copy()
                    count_key = name + "_count"
                    if labels:
                        count_key += "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                    lines.append(f"{count_key} {metric['count']}")

                    sum_key = name + "_sum"
                    if labels:
                        sum_key += "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                    lines.append(f"{sum_key} {metric['sum']}")
                else:
                    lines.append(f"{metric['key']} {metric['value']}")

                lines.append("")
        return "\n".join(lines)


class PrometheusHandler(BaseHTTPRequestHandler):
    """Handler HTTP para exposição de métricas Prometheus."""

    def __init__(self, metrics_collector, *args, **kwargs):
        self.metrics_collector = metrics_collector
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Processa requisições GET."""
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()

            # Adicionar métricas customizadas
            response = self.metrics_collector.get_metrics_text()

            # Adicionar métricas padrão do Python
            response += "\n# HELP python_gc_collections_total Number of GC collections\n"
            response += "# TYPE python_gc_collections_total counter\n"
            import gc
            for gen, count in enumerate(gc.get_count()):
                response += f'python_gc_collections_total{{generation="{gen}"}} {count}\n'

            response += "\n# HELP python_thread_count Current thread count\n"
            response += "# TYPE python_thread_count gauge\n"
            response += f"python_thread_count {threading.active_count()}\n"

            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def log_message(self, format, *args):
        """Suprime logs do servidor HTTP."""
        return


class PrometheusExporter:
    """Exportador de métricas para Prometheus."""

    def __init__(self, port: int = 8000, host: str = 'localhost'):
        self.port = port
        self.host = host
        self.server = None
        self.metrics_collector = MetricsCollector()
        self._running = False
        self._thread = None

    def start(self):
        """Inicia o servidor Prometheus."""
        if self._running:
            return

        try:
            def run_server():
                server_address = (self.host, self.port)
                # Criar handler personalizado com metrics_collector
                def handler(*args, **kwargs):
                    PrometheusHandler(self.metrics_collector, *args, **kwargs)

                self.server = HTTPServer(server_address, handler)
                print(f"Prometheus metrics server started on http://{self.host}:{self.port}/metrics")
                self.server.serve_forever()

            self._thread = threading.Thread(target=run_server, daemon=True)
            self._thread.start()
            self._running = True
            print(f"Prometheus exporter started successfully")

        except Exception as e:
            print(f"Erro ao iniciar exportador Prometheus: {e}")
            self._running = False

    def stop(self):
        """Para o servidor Prometheus."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self._running = False
            print("Prometheus exporter stopped")

    def collect_db_metrics(self, db_manager):
        """Coleta métricas do gerenciador de banco."""
        try:
            # Métricas do pool
            pool_metrics = db_manager.get_metrics()
            if pool_metrics:
                self.metrics_collector.set_gauge(
                    "db_pool_connections_active",
                    pool_metrics.active_connections,
                    description="Número de conexões ativas no pool"
                )
                self.metrics_collector.set_gauge(
                    "db_pool_connections_idle",
                    pool_metrics.idle_connections,
                    description="Número de conexões ociosas no pool"
                )
                self.metrics_collector.set_gauge(
                    "db_pool_connections_created",
                    pool_metrics.total_connections_created,
                    description="Total de conexões criadas"
                )

            # Métricas de performance
            perf_metrics = db_manager.get_performance_metrics()
            if perf_metrics:
                pm = perf_metrics.get('performance_metrics', {})

                self.metrics_collector.set_gauge(
                    "db_queries_total",
                    pm.get('total_queries', 0),
                    description="Total de queries executadas"
                )
                self.metrics_collector.set_gauge(
                    "db_transactions_total",
                    pm.get('total_transactions', 0),
                    description="Total de transações executadas"
                )
                self.metrics_collector.set_gauge(
                    "db_slow_queries",
                    pm.get('slow_queries_count', 0),
                    description="Número de queries lentas (>5s)"
                )

                # Métricas de sistema
                sys_metrics = perf_metrics.get('system_metrics', {})
                if sys_metrics.get('available', False):
                    self.metrics_collector.observe_histogram(
                        "db_query_execution_time",
                        pm.get('average_query_time', 0),
                        description="Tempo médio de execução de queries"
                    )

                    self.metrics_collector.set_gauge(
                        "system_cpu_percent",
                        sys_metrics.get('cpu_percent', 0),
                        description="Percentual de CPU usado"
                    )
                    self.metrics_collector.set_gauge(
                        "system_memory_mb",
                        sys_metrics.get('memory_mb', 0),
                        description="Memória usada em MB"
                    )

            # Métricas de erro
            error_stats = db_manager.get_error_stats()
            for error_type, count in error_stats.items():
                if isinstance(count, int) and error_type not in ['last_error', 'last_error_time']:
                    self.metrics_collector.set_gauge(
                        f"db_errors_total{{type=\"{error_type}\"}}",
                        count,
                        description=f"Número total de erros do tipo {error_type}"
                    )

        except Exception as e:
            print(f"Erro ao coletar métricas do banco: {e}")

    def is_running(self) -> bool:
        """Verifica se o servidor está rodando."""
        return self._running


# Instância global para uso fácil
global_exporter = PrometheusExporter()

def get_global_exporter():
    """Retorna o exportador global."""
    return global_exporter

if __name__ == "__main__":
    # Teste do exportador
    exporter = PrometheusExporter(port=8080)
    exporter.start()

    try:
        while True:
            time.sleep(5)
            print("Exporter running... visit http://localhost:8080/metrics")
    except KeyboardInterrupt:
        exporter.stop()
        print("Exporter stopped")