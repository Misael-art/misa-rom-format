#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Database Metrics
Sistema de monitoramento e métricas de performance do banco de dados
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)

@dataclass
class QueryMetrics:
    """Métricas de uma query específica."""
    query: str
    execution_time: float
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    rows_affected: int = 0
    
@dataclass
class DatabaseStats:
    """Estatísticas gerais do banco de dados."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_query_time: float = 0.0
    total_execution_time: float = 0.0
    peak_connections: int = 0
    current_connections: int = 0
    
    def success_rate(self) -> float:
        """Taxa de sucesso das queries."""
        if self.total_queries == 0:
            return 0.0
        return (self.successful_queries / self.total_queries) * 100
    
    def error_rate(self) -> float:
        """Taxa de erro das queries."""
        return 100 - self.success_rate()

class MetricsCollector:
    """Coletor de métricas de performance do banco."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._lock = threading.RLock()
        
        # Métricas atuais
        self.stats = DatabaseStats()
        
        # Histórico de queries
        self.query_history: deque = deque(maxlen=max_history)
        
        # Métricas por tipo de query
        self.query_types: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'count': 0,
                'total_time': 0.0,
                'errors': 0,
                'last_execution': None
            }
        )
        
        # Métricas por tabela
        self.table_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'selects': 0,
                'inserts': 0,
                'updates': 0,
                'deletes': 0,
                'total_time': 0.0
            }
        )
        
        # Métricas de conexão
        self.connection_history: deque = deque(maxlen=100)
        
        # Alertas
        self.alerts: List[Dict[str, Any]] = []
        
        logger.info("Coletor de métricas inicializado")
    
    def record_query(self, query: str, execution_time: float, 
                    success: bool = True, error_message: Optional[str] = None,
                    rows_affected: int = 0):
        """Registra uma query executada."""
        with self._lock:
            # Cria métrica da query
            metric = QueryMetrics(
                query=query,
                execution_time=execution_time,
                timestamp=datetime.now(),
                success=success,
                error_message=error_message,
                rows_affected=rows_affected
            )
            
            # Adiciona ao histórico
            self.query_history.append(metric)
            
            # Atualiza estatísticas gerais
            self.stats.total_queries += 1
            self.stats.total_execution_time += execution_time
            
            if success:
                self.stats.successful_queries += 1
            else:
                self.stats.failed_queries += 1
            
            # Calcula média ponderada
            if self.stats.total_queries > 0:
                self.stats.average_query_time = (
                    self.stats.total_execution_time / self.stats.total_queries
                )
            
            # Analisa tipo de query
            query_type = self._get_query_type(query)
            self._update_query_type_metrics(query_type, execution_time, success)
            
            # Analisa tabelas afetadas
            tables = self._extract_tables(query)
            for table in tables:
                self._update_table_metrics(table, query_type, execution_time)
            
            # Verifica alertas
            self._check_alerts(metric)
    
    def record_connection_event(self, event_type: str, count: int):
        """Registra evento de conexão."""
        with self._lock:
            self.connection_history.append({
                'type': event_type,
                'count': count,
                'timestamp': datetime.now()
            })
            
            if event_type == 'peak':
                self.stats.peak_connections = max(
                    self.stats.peak_connections, count
                )
            elif event_type == 'current':
                self.stats.current_connections = count
    
    def get_recent_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Obtém queries recentes."""
        with self._lock:
            return list(self.query_history)[-limit:]
    
    def get_slow_queries(self, threshold: float = 1.0) -> List[QueryMetrics]:
        """Obtém queries lentas."""
        with self._lock:
            return [q for q in self.query_history if q.execution_time > threshold]
    
    def get_error_queries(self) -> List[QueryMetrics]:
        """Obtém queries com erro."""
        with self._lock:
            return [q for q in self.query_history if not q.success]
    
    def get_query_type_stats(self) -> Dict[str, Dict[str, Any]]:
        """Obtém estatísticas por tipo de query."""
        with self._lock:
            return dict(self.query_types)
    
    def get_table_stats(self) -> Dict[str, Dict[str, Any]]:
        """Obtém estatísticas por tabela."""
        with self._lock:
            return dict(self.table_metrics)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtém resumo de performance."""
        with self._lock:
            return {
                'stats': asdict(self.stats),
                'query_types': self.get_query_type_stats(),
                'table_stats': self.get_table_stats(),
                'recent_queries': len(self.query_history),
                'alerts': len(self.alerts)
            }
    
    def reset_metrics(self):
        """Reseta todas as métricas."""
        with self._lock:
            self.stats = DatabaseStats()
            self.query_history.clear()
            self.query_types.clear()
            self.table_metrics.clear()
            self.connection_history.clear()
            self.alerts.clear()
            logger.info("Métricas resetadas")
    
    def _get_query_type(self, query: str) -> str:
        """Identifica o tipo de query."""
        query = query.strip().upper()
        
        if query.startswith('SELECT'):
            return 'SELECT'
        elif query.startswith('INSERT'):
            return 'INSERT'
        elif query.startswith('UPDATE'):
            return 'UPDATE'
        elif query.startswith('DELETE'):
            return 'DELETE'
        elif query.startswith('CREATE'):
            return 'CREATE'
        elif query.startswith('DROP'):
            return 'DROP'
        elif query.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'OTHER'
    
    def _extract_tables(self, query: str) -> List[str]:
        """Extrai nomes de tabelas da query."""
        query = query.upper()
        tables = []
        
        # Padrões simples para extrair tabelas
        patterns = [
            'FROM\\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            'JOIN\\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            'INTO\\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            'UPDATE\\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            'TABLE\\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            tables.extend(matches)
        
        return list(set(tables))  # Remove duplicatas
    
    def _update_query_type_metrics(self, query_type: str, 
                                 execution_time: float, success: bool):
        """Atualiza métricas por tipo de query."""
        metrics = self.query_types[query_type]
        metrics['count'] += 1
        metrics['total_time'] += execution_time
        metrics['last_execution'] = datetime.now()
        
        if not success:
            metrics['errors'] += 1
    
    def _update_table_metrics(self, table: str, query_type: str, 
                            execution_time: float):
        """Atualiza métricas por tabela."""
        metrics = self.table_metrics[table]
        metrics['total_time'] += execution_time
        
        if query_type == 'SELECT':
            metrics['selects'] += 1
        elif query_type == 'INSERT':
            metrics['inserts'] += 1
        elif query_type == 'UPDATE':
            metrics['updates'] += 1
        elif query_type == 'DELETE':
            metrics['deletes'] += 1
    
    def _check_alerts(self, metric: QueryMetrics):
        """Verifica e gera alertas baseados em thresholds."""
        alerts = []
        
        # Alerta para queries lentas
        if metric.execution_time > 5.0:
            alerts.append({
                'type': 'slow_query',
                'message': f"Query lenta detectada: {metric.execution_time:.2f}s",
                'query': metric.query[:100] + '...' if len(metric.query) > 100 else metric.query,
                'timestamp': metric.timestamp
            })
        
        # Alerta para taxa de erro alta
        if not metric.success:
            error_rate = self.stats.error_rate()
            if error_rate > 10.0:  # 10% de erro
                alerts.append({
                    'type': 'high_error_rate',
                    'message': f"Taxa de erro alta: {error_rate:.1f}%",
                    'timestamp': metric.timestamp
                })
        
        # Adiciona alertas
        self.alerts.extend(alerts)
        
        # Limita número de alertas
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-50:]
        
        # Log alertas
        for alert in alerts:
            logger.warning(f"Alerta: {alert['message']}")

class MetricsReporter:
    """Relatório de métricas do banco de dados."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def generate_report(self) -> Dict[str, Any]:
        """Gera relatório completo de métricas."""
        summary = self.collector.get_performance_summary()
        
        # Análise de tendências
        recent_queries = self.collector.get_recent_queries(100)
        
        if recent_queries:
            avg_recent_time = sum(q.execution_time for q in recent_queries) / len(recent_queries)
            recent_errors = sum(1 for q in recent_queries if not q.success)
        else:
            avg_recent_time = 0.0
            recent_errors = 0
        
        return {
            'summary': summary,
            'trends': {
                'recent_average_time': avg_recent_time,
                'recent_errors': recent_errors,
                'error_trend': 'increasing' if recent_errors > 5 else 'stable'
            },
            'recommendations': self._generate_recommendations(summary),
            'generated_at': datetime.now().isoformat()
        }
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Gera recomendações baseadas nas métricas."""
        recommendations = []
        
        stats = summary['stats']
        
        # Recomendações baseadas em taxa de erro
        if stats['error_rate'] > 5.0:
            recommendations.append(
                "Taxa de erro alta. Verifique logs para identificar problemas."
            )
        
        # Recomendações baseadas em queries lentas
        slow_queries = self.collector.get_slow_queries(2.0)
        if len(slow_queries) > 10:
            recommendations.append(
                f"Muitas queries lentas ({len(slow_queries)}). "
                "Considere otimizar índices ou queries."
            )
        
        # Recomendações baseadas em uso de conexões
        if stats['peak_connections'] > 50:
            recommendations.append(
                "Pico de conexões alto. Considere aumentar o pool ou otimizar uso."
            )
        
        return recommendations

# Instância global do coletor de métricas
metrics_collector = MetricsCollector()