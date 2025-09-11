#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - System Health Monitor
Monitora saúde do sistema em tempo real com alertas e métricas
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import argparse

# Adiciona diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.db import UnifiedDatabaseManager as DatabaseManagerV2

class SystemHealthMonitor:
    """Monitor avançado da saúde do sistema."""

    def __init__(self):
        self.db_manager: Optional[DatabaseManagerV2] = None
        self.monitoring_active = False
        self.check_interval = 60  # 1 minuto por padrão
        self.alert_history = []
        self.metrics_history = []
        self.max_history_size = 1000

    def start_monitoring(self, continuous: bool = True, interval_seconds: int = 60):
        """Inicia monitoramento do sistema."""
        print("🏥 Iniciando monitoramento da saúde do sistema...")
        print(f"⏱️ Intervalo: {interval_seconds} segundos")
        print(f"🔄 Modo: {'contínuo' if continuous else 'único'}")

        self.check_interval = interval_seconds

        # Carrega configuração
        config_path = "config/production.json"
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            # Configuração padrão
            config = {
                'pool': {'max_connections': 10},
                'enable_system_monitoring': True
            }

        # Inicializa DbManager
        self.db_manager = DatabaseManagerV2(config)

        if self.db_manager.connect("data/megaemu_production.db"):
            self.monitoring_active = True
            print("✅ Monitorização iniciada")

            if continuous:
                self._continuous_monitoring()
            else:
                return self.check_system_health()
        else:
            print("❌ Falha ao conectar ao banco de dados")
            return None

    def _continuous_monitoring(self):
        """Executa monitoramento contínuo."""
        print("🔄 Iniciando monitoramento contínuo (Ctrl+C para parar)...")
        print("=" * 60)

        try:
            while True:
                start_time = time.time()

                # Executa verificação
                health_report = self.check_system_health()

                # Log da verificação
                self._log_health_check(health_report)

                # Cálculo do tempo restante até próximo check
                elapsed = time.time() - start_time
                remaining = max(0, self.check_interval - elapsed)

                if remaining > 0:
                    time.sleep(remaining)

        except KeyboardInterrupt:
            print("\n👋 Monitoramento interrompido pelo usuário")
        except Exception as e:
            print(f"❌ Erro no monitoramento: {e}")
        finally:
            self.stop_monitoring()

    def check_system_health(self) -> Dict[str, Any]:
        """Verifica saúde completa do sistema."""
        if not self.db_manager or not self.monitoring_active:
            return {
                'status': 'error',
                'message': 'Monitorado não ativo',
                'timestamp': datetime.now().isoformat()
            }

        health_report = {
            'timestamp': datetime.now().isoformat(),
            'system_status': 'healthy',
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'metrics': {},
            'components': {}
        }

        try:
            # 1. Verificar saúde do sistema operacional
            health_report['metrics']['system'] = self.db_manager.system_monitor.get_system_metrics()

            # 2. Verificar pool de conexões
            pool_metrics = self.db_manager.get_performance_metrics()
            health_report['components']['database_pool'] = pool_metrics

            # 3. Verificar banco de dados
            db_health = self._check_database_health()
            health_report['components']['database'] = db_health

            # 4. Verificar Query performance
            query_health = self._check_query_performance()
            health_report['components']['query_performance'] = query_health

            # 5. Verificar Recovery stats
            recovery_health = self._check_recovery_stats()
            health_report['components']['recovery'] = recovery_health

            # 6. Análise geral
            overall_status = self._analyze_overall_health(health_report)
            health_report.update(overall_status)

            # 7. Adiciona ao histórico
            self._add_to_history(health_report)

            # 8. Executa alertas se necessário
            self._process_alerts(health_report)

        except Exception as e:
            health_report['status'] = 'error'
            health_report['message'] = str(e)
            health_report['system_status'] = 'critical'
            health_report['issues'].append(f"Erro crítico no monitoring: {e}")

        finally:
            # Fecha conexão se aberta
            if self.db_manager:
                try:
                    self.db_manager.close_all()
                except:
                    pass

        return health_report

    def _check_database_health(self) -> Dict[str, Any]:
        """Verifica saúde específica do banco de dados."""
        db_health = {
            'status': 'healthy',
            'issues': [],
            'metrics': {}
        }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.connection.cursor()

                # Verifica integridade
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()

                if integrity_result and integrity_result[0] == 'ok':
                    db_health['metrics']['integrity'] = 'good'
                else:
                    db_health['status'] = 'critical'
                    db_health['issues'].append("Problemas de integridade no banco")
                    db_health['metrics']['integrity'] = 'bad'

                # Verifica foreign keys
                cursor.execute("PRAGMA foreign_keys")
                fk_enabled = bool(cursor.fetchone()[0])

                if not fk_enabled:
                    db_health['issues'].append("Foreign keys desabilitadas")
                    db_health['status'] = 'warning'

                # Conta registros
                table_counts = {}
                for table in ['roms', 'games', 'systems', 'categories']:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        table_counts[table] = count
                    except:
                        table_counts[table] = 0

                db_health['metrics']['table_counts'] = table_counts

                # Verifica espaço usado
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]

                db_health['metrics']['size_mb'] = (page_count * page_size) / (1024 * 1024)

        except Exception as e:
            db_health['status'] = 'critical'
            db_health['issues'].append(f"Erro na verificação do banco: {e}")

        return db_health

    def _check_query_performance(self) -> Dict[str, Any]:
        """Verifica performance de queries."""
        perf_health = {
            'status': 'healthy',
            'issues': [],
            'metrics': {}
        }

        try:
            perf_metrics = self.db_manager.get_performance_metrics()
            performance_metrics = perf_metrics.get('performance_metrics', {})

            # Analisa tempo médio de queries
            avg_query_time = performance_metrics.get('average_query_time', 0)
            if avg_query_time > 2.0:  # Mais de 2 segundos
                perf_health['status'] = 'warning'
                perf_health['issues'].append(".2f")

            # Analisa queries lentas
            slow_queries = performance_metrics.get('slow_queries_count', 0)
            if slow_queries > 10:
                perf_health['status'] = 'warning'
                perf_health['issues'].append(f"Alto número de queries lentas: {slow_queries}")

            # Total de queries executadas
            total_queries = performance_metrics.get('total_queries', 0)
            perf_health['metrics'] = {
                'average_query_time': avg_query_time,
                'slow_queries_count': slow_queries,
                'total_queries': total_queries,
                'queries_per_minute': total_queries / (performance_metrics.get('last_performance_check', {}).get('age', 1) / 60) if total_queries > 0 else 0
            }

        except Exception as e:
            perf_health['status'] = 'warning'
            perf_health['issues'].append(f"Erro na análise de performance: {e}")

        return perf_health

    def _check_recovery_stats(self) -> Dict[str, Any]:
        """Verifica estatísticas de recovery."""
        recovery_health = {
            'status': 'healthy',
            'issues': [],
            'metrics': {}
        }

        try:
            performance_metrics = self.db_manager.get_performance_metrics()
            recovery_stats = performance_metrics.get('recovery_stats', {})

            connection_recoveries = recovery_stats.get('recovered_connections', 0)
            failed_recoveries = recovery_stats.get('failed_recoveries', 0)
            total_recovery_attempts = recovery_stats.get('total_recovery_attempts', 0)

            success_rate = (connection_recoveries / max(1, total_recovery_attempts)) * 100 if total_recovery_attempts > 0 else 100

            if failed_recoveries > 5:
                recovery_health['status'] = 'warning'
                recovery_health['issues'].append(f"Muitos falhas de recovery: {failed_recoveries}")

            if success_rate < 80:
                recovery_health['status'] = 'warning'
                recovery_health['issues'].append(".1f")

            recovery_health['metrics'] = {
                'recovered_connections': connection_recoveries,
                'failed_recoveries': failed_recoveries,
                'total_recovery_attempts': total_recovery_attempts,
                'success_rate': success_rate
            }

        except Exception as e:
            recovery_health['status'] = 'warning'
            recovery_health['issues'].append(f"Erro na análise de recovery: {e}")

        return recovery_health

    def _analyze_overall_health(self, health_report: Dict[str, Any]) -> Dict[str, Any]:
        """Análise geral da saúde do sistema."""
        overall_issues = []
        overall_warnings = []
        overall_recommendations = []

        # Analisa alertas de sistema
        system_metrics = health_report['metrics'].get('system', {})
        if system_metrics.get('cpu_alert'):
            overall_issues.append("Uso alto de CPU detectado")
            overall_recommendations.append("Otimize queries ou considere recursos adicionais")

        if system_metrics.get('memory_alert'):
            overall_issues.append("Uso alto de memória detectado")
            overall_recommendations.append("Monitore vazamentos de memória ou aumente RAM")

        # Analisa pool de conexões
        active_conns = health_report['components']['database']['metrics'].get('table_counts', {}).get('active_connections', 0)
        max_conns = self.db_manager.pool.config.max_connections if hasattr(self.db_manager, 'pool') else 10

        if active_conns > max_conns * 0.9:
            overall_warnings.append("Pool de conexões próximo ao limite")
            overall_recommendations.append("Aumente max_connections ou implemente connection pooling melhorado")

        # Status geral
        component_statuses = []
        for component_name, component_info in health_report['components'].items():
            if component_info.get('status'):
                component_statuses.append(component_info['status'])

        if 'critical' in component_statuses:
            overall_status = 'critical'
        elif 'warning' in component_statuses:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'

        # Coleta todos os issues
        for component_info in health_report['components'].values():
            overall_issues.extend(component_info.get('issues', []))

        return {
            'system_status': overall_status,
            'issues': set(overall_issues),  # Remove duplicatas
            'warnings': overall_warnings,
            'recommendations': overall_recommendations
        }

    def _add_to_history(self, health_report: Dict[str, Any]):
        """Adiciona relatório ao histórico."""
        self.metrics_history.append(health_report)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)

    def _process_alerts(self, health_report: Dict[str, Any]):
        """Processa alertas baseados no health report."""
        if health_report['system_status'] == 'critical':
            self.alert_history.append({
                'level': 'CRITICAL',
                'timestamp': health_report['timestamp'],
                'issues': health_report.get('issues', []),
                'message': "ALERTA CRÍTICO: Problemas mínimos detectados"
            })
            print("🚨 ALERTA CRÍTICO! Verifique logs imediatos")

        elif len(health_report.get('issues', [])) > 0:
            self.alert_history.append({
                'level': 'WARNING',
                'timestamp': health_report['timestamp'],
                'issues': health_report['issues'],
                'message': "Problemas detectados"
            })

        # Limita histórico de alertas
        if len(self.alert_history) > 100:
            self.alert_history.pop(0)

    def _log_health_check(self, health_report: Dict[str, Any]):
        """Log da verificação de saúde."""
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🚨',
            'error': '❌'
        }

        emoji = status_emoji.get(health_report['system_status'], '❓')
        issues_count = len(health_report.get('issues', []))

        print(f"{emoji} [{health_report['timestamp']}] Status: {health_report['system_status'].upper()}")

        if issues_count > 0:
            print(f"   Problemas: {issues_count}")

        # Log detalhado se houver problemas
        if health_report['system_status'] != 'healthy':
            for issue in health_report.get('issues', []):
                print(f"   • {issue}")

    def stop_monitoring(self):
        """Para monitoramento."""
        if self.db_manager:
            self.db_manager.close_all()
        self.monitoring_active = False

    def get_alert_history(self) -> list:
        """Retorna histórico de alertas."""
        return self.alert_history.copy()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas coletadas."""
        if not self.metrics_history:
            return {'error': 'Nenhuma métrica coletada'}

        recent = self.metrics_history[-10:] if len(self.metrics_history) >= 10 else self.metrics_history

        # Calcula estatísticas básicas
        statuses = [m['system_status'] for m in recent]
        status_counts = {
            'healthy': statuses.count('healthy'),
            'warning': statuses.count('warning'),
            'critical': statuses.count('critical'),
            'error': statuses.count('error')
        }

        return {
            'total_checks': len(self.metrics_history),
            'recent_checks': len(recent),
            'status_summary': status_counts,
            'last_check': recent[-1] if recent else None,
            'timestamp': datetime.now().isoformat()
        }


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description='Monitor de saúde do sistema MegaEmu')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Intervalo de verificação em segundos (padrão: 60)')
    parser.add_argument('--continuous', '-c', action='store_true',
                       help='Executa monitoramento contínuo')
    parser.add_argument('--single', '-s', action='store_true',
                       help='Executa uma única verificação')

    args = parser.parse_args()

    monitor = SystemHealthMonitor()

    try:
        if args.single:
            result = monitor.start_monitoring(continuous=False)
            if result:
                print("\\n📊 RESULTADO DA VERIFICAÇÃO:")
                print(json.dumps(result, indent=2, default=str))
        else:
            monitor.start_monitoring(continuous=args.continuous or True, interval_seconds=args.interval)

    except KeyboardInterrupt:
        print("\\n👋 Finalizado pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sys.exit(1)
    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()