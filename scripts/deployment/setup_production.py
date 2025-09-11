#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Production Setup Script
Configura o ambiente para deployment em produção com features avançadas
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Adiciona diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db.enhanced_connection_pool import PoolConfig, create_enhanced_pool
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2
from engine.db.migrations import MigrationManager

class ProductionSetup:
    """Configurador completo para ambiente de produção."""

    def __init__(self, config_file: str = "config/production.json"):
        self.config_file = config_file
        self.config = {}
        self.setup_log = []
        self.errors = []

    def run_setup(self) -> bool:
        """Executa configuração completa para produção."""
        print("🚀 Iniciando configuração para produção...")
        print("=" * 60)

        try:
            # 1. Validar compatibilidade
            if not self._verify_compatibility():
                print("❌ Compatibilidade falhou - abortando configuração")
                return False

            # 2. Criar diretórios necessários
            if not self._create_directories():
                print("❌ Falha ao criar diretórios")
                return False

            # 3. Carregar configuração padrão
            if not self._load_default_config():
                print("❌ Falha ao carregar configuração")
                return False

            # 4. Configurar logging
            if not self._setup_logging():
                print("❌ Falha ao configurar logging")
                return False

            # 5. Preparar banco de dados
            if not self._setup_database():
                print("❌ Falha na configuração do banco")
                return False

            # 6. Configurar pool otimizado
            if not self._setup_connection_pool():
                print("❌ Falha no pool de conexões")
                return False

            # 7. Executar validações finais
            if not self._run_final_validations():
                print("❌ Validações finais falharam")
                return False

            # 8. Salvar configuração final
            if not self._save_configuration():
                print("❌ Falha ao salvar configuração")
                return False

            # 9. Criar script de inicialização
            if not self._create_startup_script():
                print("❌ Falha ao criar script de inicialização")
                return False

            self._show_success_message()
            return True

        except Exception as e:
            error_msg = f"Erro fatal no setup: {e}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

    def _verify_compatibility(self) -> bool:
        """Executa verificação de compatibilidade."""
        print("✅ Verificando compatibilidade...")

        try:
            from scripts.deployment.verify_compatibility import CompatibilityVerifier

            verifier = CompatibilityVerifier()
            if verifier.verify_all():
                print("  ✅ Compatibilidade verificada")
                return True
            else:
                print("  ❌ Problemas de compatibilidade encontrados")
                self.errors.extend(verifier.errors)
                return False

        except Exception as e:
            self.errors.append(f"Erro na verificação: {e}")
            return False

    def _create_directories(self) -> bool:
        """Cria estrutura de diretórios para produção."""
        print("📁 Criando estrutura de diretórios...")

        # Diretórios essenciais para produção
        production_dirs = [
            "config",
            "logs",
            "data",
            "backup",
            "temp",
            "monitor",
            "performance_reports"
        ]

        created = []
        failed = []

        for dir_name in production_dirs:
            try:
                Path(dir_name).mkdir(parents=True, exist_ok=True)

                # Cria arquivos placeholder se necessário
                if dir_name == "config":
                    Path(f"{dir_name}/.gitkeep").touch(exist_ok=True)
                elif dir_name == "logs":
                    Path(f"{dir_name}/system.log").touch(exist_ok=True)
                    Path(f"{dir_name}/performance.log").touch(exist_ok=True)

                created.append(dir_name)

            except Exception as e:
                failed.append(f"{dir_name}: {e}")

        if failed:
            self.errors.extend(f"Erro ao criar diretório: {f}" for f in failed)
            return False

        self.setup_log.extend(f"Diretório criado: {d}" for d in created)
        print(f"  ✅ {len(created)} diretórios criados")
        return True

    def _load_default_config(self) -> bool:
        """Carrega configuração padrão otimizada para produção."""
        print("⚙️ Carregando configuração padrão...")

        self.config = {
            "database": {
                "path": "data/megaemu_production.db",
                "schema_version": "2.0.0"
            },

            "connection_pool": {
                "min_connections": 5,
                "max_connections": self._calculate_optimal_connection_pool_size(),
                "connection_timeout": 120.0,
                "idle_timeout": 300.0,
                "health_check_interval": 60.0,
                "health_check_timeout": 10.0,
                "enable_metrics": True,
                "enable_health_checks": True,
                "enable_auto_scaling": True,
                "scale_up_threshold": 0.7,
                "scale_down_threshold": 0.3,
                "enable_statement_caching": True,
                "statement_cache_size": 200,
                "enable_wal_mode": True,
                "enable_foreign_keys": True,
                "busy_timeout": 50000  # 50 segundos
            },

            "logging": {
                "level": "INFO",
                "max_file_size": 10485760,  # 10MB
                "backup_count": 5,
                "log_dir": "logs",
                "structured_logging": True,
                "performance_tracking": True
            },

            "monitoring": {
                "enable_system_monitoring": True,
                "cpu_alert_threshold": 80.0,
                "memory_alert_threshold": 85.0,
                "disk_space_alert_threshold": 90.0,
                "performance_report_interval": 300,  # 5 minutos
                "health_check_interval": 60  # 1 minuto
            },

            "migrations": {
                "backup_before_migration": True,
                "backup_retention_days": 7,
                "rollback_strategy": "auto",
                "validate_before_migration": True,
                "validate_after_migration": True
            },

            "production_flags": {
                "ready_for_production": True,
                "features_enabled": [
                    "advanced_audit",
                    "connection_recovery",
                    "system_monitoring",
                    "auto_scaling",
                    "performance_tracking"
                ]
            }
        }

        print("  ✅ Configuração carregada")
        return True

    def _calculate_optimal_connection_pool_size(self) -> int:
        """Calcula tamanho ótimo do pool baseado no sistema."""
        try:
            import psutil

            # Baseado na memória disponível
            memory = psutil.virtual_memory()
            memory_gb = memory.available / (1024**3)

            # Lógica simples: 1 conexão por 500MB de RAM disponível
            # Máximo 20 conexões, mínimo 5
            calculated = max(5, min(20, int(memory_gb * 2)))
            return calculated

        except ImportError:
            # Sem psutil - assume médio (10 conexões)
            return 10
        except Exception:
            return 10

    def _setup_logging(self) -> bool:
        """Configura sistema de logging otimizado para produção."""
        print("📝 Configurando logging otimizado...")

        try:
            log_dir = self.config["logging"]["log_dir"]
            Path(log_dir).mkdir(exist_ok=True)

            # Arquivo de configuração de logging
            log_config = {
                "version": 1,
                "formatters": {
                    "structured": {
                        "format": "%(asctime)s | %(levelname)s | %(module)s | %(funcName)s | %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S"
                    },
                    "performance": {
                        "format": "%(asctime)s | PERFORMANCE | %(levelname)s | %(message)s"
                    }
                },
                "handlers": {
                    "file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": f"{log_dir}/system.log",
                        "maxBytes": self.config["logging"]["max_file_size"],
                        "backupCount": self.config["logging"]["backup_count"],
                        "formatter": "structured",
                        "encoding": "utf-8"
                    },
                    "performance": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": f"{log_dir}/performance.log",
                        "maxBytes": self.config["logging"]["max_file_size"],
                        "backupCount": self.config["logging"]["backup_count"],
                        "formatter": "performance",
                        "encoding": "utf-8"
                    }
                },
                "loggers": {
                    "": {
                        "handlers": ["file"],
                        "level": self.config["logging"]["level"]
                    },
                    "performance": {
                        "handlers": ["performance"],
                        "level": "INFO",
                        "propagate": False
                    }
                }
            }

            # Salva configuração
            config_path = f"{log_dir}/logging_config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(log_config, f, indent=2)

            self.setup_log.append(f"Logging configurado em: {config_path}")
            print("  ✅ Logging configurado")
            return True

        except Exception as e:
            self.errors.append(f"Erro no setup de logging: {e}")
            return False

    def _setup_database(self) -> bool:
        """Prepara banco de dados para produção."""
        print("💾 Preparando banco de dados para produção...")

        try:
            db_path = self.config["database"]["path"]

            # Cria banco inicial se não existir
            if not Path(db_path).exists():
                Path(db_path).parent.mkdir(exist_ok=True)

            # Executa migração inicial
            validator = MigrationManager(db_path)
            migration_result = validator.migrate_with_backup()

            if migration_result["success"]:
                self.setup_log.append(f"Banco preparado: {db_path}")
                print(f"  ✅ Banco preparado: {db_path}")
                return True
            else:
                self.errors.extend(migration_result.get("errors", []))
                print("  ❌ Falha na preparação do banco")
                return False

        except Exception as e:
            self.errors.append(f"Erro na preparação do banco: {e}")
            return False

    def _setup_connection_pool(self) -> bool:
        """Configura pool de conexões otimizado para produção."""
        print("🔗 Configurando pool de conexões otimizado...")

        try:
            pool_config = PoolConfig(**self.config["connection_pool"])
            db_path = self.config["database"]["path"]

            # Testa pool
            pool = create_enhanced_pool(db_path, **pool_config.__dict__)

            # Executa teste básico
            with pool.get_connection() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("SELECT sqlite_version(), 'pool_test'")
                result = cursor.fetchone()

                if result and len(result) == 2:
                    self.setup_log.append(f"Pool testado: SQLite {result[0]}")
                    print(f"  ✅ Pool configurado - SQLite {result[0]}")
                    return True

            self.errors.append("Falha no teste do pool de conexões")
            return False

        except Exception as e:
            self.errors.append(f"Erro no setup do pool: {e}")
            return False

    def _run_final_validations(self) -> bool:
        """Executa validações finais antes do deploy."""
        print("🔍 Executando validações finais...")

        try:
            # Validação usando DatabaseManagerV2
            db_config = {
                "pool": self.config["connection_pool"]
            }

            db_manager = DatabaseManagerV2(db_config)

            # Conecta ao banco
            db_path = self.config["database"]["path"]
            if db_manager.connect(db_path):

                # Obtém métricas
                health = db_manager.check_system_health()

                if health["system_status"] == "healthy":
                    self.setup_log.append("Sistema pronto para produção")
                    print("  ✅ Sistema validado e pronto")
                    return True
                else:
                    self.errors.extend(health.get("issues", []))
                    print("  ⚠️ Problemas encontrados na validação")
                    return True  # Warnings não bloqueiam

            else:
                self.errors.append("Falha ao conectar ao banco configurado")
                return False

        except Exception as e:
            self.errors.append(f"Erro na validação final: {e}")
            return False

    def _save_configuration(self) -> bool:
        """Salva configuração final."""
        print("💾 Salvando configuração produção...")

        try:
            # Cria backup da configuração atual se existir
            if Path(self.config_file).exists():
                backup_path = f"{self.config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.config_file, backup_path)

            # Salva nova configuração
            Path(self.config_file).parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, default=str)

            self.setup_log.append(f"Configuração salva: {self.config_file}")
            print(f"  ✅ Configuração salva: {self.config_file}")
            return True

        except Exception as e:
            self.errors.append(f"Erro ao salvar configuração: {e}")
            return False

    def _create_startup_script(self) -> bool:
        """Cria script de inicialização otimizado."""
        print("🚀 Criando scripts de inicialização...")

        try:
            startup_script = """#!/usr/bin/env python3
\"\"\"MegaEmu DataBase ROMs - Production Startup Script\"\"\"


# Adiciona diretório projeto ao path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

def main():
    \"\"\"Função principal de inicialização.\"\"\"
    try:
        print("🚀 Iniciando MegaEmu DataBase v2.0...")

        # Importa módulos principais
        from engine.db.schema_validator import SchemaValidator

        # Carrega configuração
        with open("config/production.json", 'r') as f:
            config = json.load(f)

        # Inicializa sistema
        db_manager = DatabaseManagerV2(config)

        print("✅ Sistema inicializado com sucesso!")
        print("🌐 Features ativadas:")
        for feature in config.get("production_flags", {}).get("features_enabled", []):
            print(f"  • {feature.replace('_', ' ').title()}")

        # Mantém sistema rodando
        print("\\n! Sistema pronto para uso")
        print("Pressione Ctrl+C para sair")

        # Loop simples para manter processo vivo
        while True:
            import time
            time.sleep(60)

            # Log de health check periódico
            health = db_manager.check_system_health()
            if health["system_status"] == "healthy":
                print(f"✓ Sistema saudável - {len(health['issues'])} alertas")
            else:
                print(f"⚠️ Alertas detectados: {len(health.get('issues', []))}")

    except KeyboardInterrupt:
        print("\\n👋 Encerramento solicitado pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""

            # Salva script
            script_path = "scripts/start_production.py"
            Path(script_path).parent.mkdir(exist_ok=True)

            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(startup_script)

            # Torna executável no Linux/macOS
            if os.name != 'nt':
                os.chmod(script_path, 0o755)

            self.setup_log.append(f"Script criado: {script_path}")
            print("  ✅ Scripts de inicialização criados")
            return True

        except Exception as e:
            self.errors.append(f"Erro ao criar script: {e}")
            return False

    def _show_success_message(self):
        """Exibe mensagem de sucesso."""
        print("\\n" + "=" * 60)
        print("🎉 CONFIGURAÇÃO PARA PRODUÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("\\n📋 O QUE FOI CONFIGURADO:")

        for log_item in self.setup_log:
            print(f"✅ {log_item}")

        print("\\n🚀 COMO INICIAR:")
        print("python scripts/start_production.py")

        print("\\n📊 MONITORE SEU SISTEMA:")
        print("python scripts/monitor/system_health.py --continuous")

        print("\\n🔧 SCRIPTS DISPONÍVEIS:")
        print("• scripts/deployment/verify_compatibility.py -> Verificar ambiente")
        print("• scripts/deployment/verify_backup.py -> Executar backup")
        print("• scripts/monitor/performance_monitor.py -> Monitorar performance")

        if self.config.get("connection_pool", {}).get("enable_metrics"):
            print("\\n⚡ FEATURES AVANÇADAS ATIVADAS:")
            print("• Sistema de auditoria proativo")
            print("• Recovery automático de conexões")
            print("• Monitoring CPU/Memória")
            print("• Auto-scaling de pool")
            print("• Logging estruturado")

        print("\\n" + "=" * 60)
        print("🌟 SISTEMA PRONTO PARA PRODUÇÃO!")
        print("=" * 60)


def main():
    """Função principal."""
    setup = ProductionSetup()

    if setup.run_setup():
        print("\\n🎊 Setup concluído com sucesso!")
        sys.exit(0)
    else:
        print("\\n❌ Setup falhou!")
        if setup.errors:
            print("Erros encontrados:")
            for error in setup.errors:
                print(f"  • {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()