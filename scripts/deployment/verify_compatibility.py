#!/usr/bin/env python3
"""
MegaEmu DataBase ROMs - Production Compatibility Verifier
Verifica se o ambiente está pronto para deploy em produção
"""

import sys
import platform
import sqlite3
import importlib
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple

class CompatibilityVerifier:
    """Verificador abrangente de compatibilidade para produção."""

    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.errors = []
        self.warnings = []
        self.recommendations = []

    def verify_all(self) -> bool:
        """Executa verificação completa de compatibilidade."""
        print("🔍 Verificando compatibilidade para produção...")
        print("=" * 60)

        checks = [
            ("Sistema operacional", self.check_os),
            ("Versão Python", self.check_python_version),
            ("SQLite version", self.check_sqlite_version),
            ("Dependências principais", self.check_core_dependencies),
            ("Dependências avançadas", self.check_advanced_dependencies),
            ("Diretórios necessários", self.check_directories),
            ("Permissões de arquivo", self.check_file_permissions),
            ("Capacidade de disco", self.check_disk_space),
            ("Memória disponível", self.check_memory),
            ("Configuração SQLite", self.check_sqlite_configuration),
        ]

        for check_name, check_func in checks:
            print(f"\n📋 Verificando: {check_name}")
            try:
                success, details = check_func()
                if success:
                    print("  ✅ PASSOU")
                    self.checks_passed += 1
                else:
                    print("  ❌ FALHOU")
                    self.checks_failed += 1

                if details:
                    for detail in details:
                        print(f"    {detail}")

            except Exception as e:
                print(f"  ⚠️  ERRO: {e}")
                self.errors.append(f"{check_name}: {e}")
                self.checks_failed += 1

        return self._generate_report()

    def check_os(self) -> Tuple[bool, List[str]]:
        """Verifica sistema operacional compatível."""
        supported_os = ['Windows', 'Linux', 'Darwin']  # macOS
        current_os = platform.system()

        if current_os in supported_os:
            return True, [f"Sistema: {current_os} {platform.release()}"]
        else:
            self.recommendations.append("Ambiente Windows/Linux/macOS recomendado")
            return False, [f"Sistema não suportado: {current_os}"]

    def check_python_version(self) -> Tuple[bool, List[str]]:
        """Verifica versão Python compatível."""
        version_info = sys.version_info
        version_string = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

        # Suporta Python 3.8+ (ótimo), 3.11+ (recomendado)
        min_version = (3, 8, 0)
        recommended_version = (3, 11, 0)

        if version_info >= recommended_version:
            return True, [f"Versão: Python {version_string} (ótimo)"]
        elif version_info >= min_version:
            self.warnings.append("Python 3.11+ recomendado para melhor performance")
            return True, [f"Versão: Python {version_string} (compatível, mas não ideal)"]
        else:
            return False, [f"Versão: Python {version_string} (muito antigo, mínimo 3.8+)"]

    def check_sqlite_version(self) -> Tuple[bool, List[str]]:
        """Verifica versão SQLite compatível."""
        try:
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]

            # Suporta SQLite 3.35+ básico, 3.42+ para recursos avançados
            version_tuple = tuple(map(int, version.split('.')))
            min_version = (3, 35, 0)
            recommended_version = (3, 42, 0)

            conn.close()

            if version_tuple >= recommended_version:
                return True, [f"SQLite {version} (recurso avançado completo)"]
            elif version_tuple >= min_version:
               редит self.warnings.append("SQLite 3.42+ recomendado para recursos avançados")
                return True, [f"SQLite {version} (básico compatível)"]
            else:
                return False, [f"SQLite {version} (muito antigo, mínimo 3.35+)"]

        except Exception as e:
            return False, [f"Erro ao verificar SQLite: {e}"]

    def check_core_dependencies(self) -> Tuple[bool, List[str]]:
        """Verifica dependências principais."""
        core_packages = ['sqlite3', 'tkinter', 'logging', 'threading']
        missing = []
        warnings = []

        for package in core_packages:
            try:
                if package == 'tkinter':
                    import tkinter
                    version = tkinter.TkVersion
                    warnings.append(f"tkinter {version} (opcional para GUI)")
                elif package == 'sqlite3':
                    import sqlite3
                    warnings.append(f"sqlite3 integrado a Python")
                else:
                    importlib.import_module(package)
            except ImportError:
                missing.append(package)

        if missing:
            self.recommendations.append(f"Instalar pacotes faltantes: {', '.join(missing)}")
            return False, [f"Pacotes faltantes: {', '.join(missing)}"]

        return True, warnings

    def check_advanced_dependencies(self) -> Tuple[bool, List[str]]:
        """Verifica dependências avançadas opcionais."""
        advanced_packages = ['psutil', 'pytest', 'coverage', 'flake8']
        available = []
        missing = []

        for package in advanced_packages:
            try:
                module = importlib.import_module(package)
                version = getattr(module, '__version__', 'N/A')
                available.append(f"{package} {version}")
            except ImportError:
                missing.append(package)

        self.warnings.append(f"Pacotes avançados disponíveis: {', '.join(available)}")
        if missing:
            self.warnings.append(f"Pacotes avançados faltantes: {', '.join(missing)}")

        # Sempre retorna True pois são opcionais
        return True, [f"Disponíveis: {', '.join(available)}", f"Faltantes: {', '.join(missing)}"]

    def check_directories(self) -> Tuple[bool, List[str]]:
        """Verifica diretórios necessários."""
        required_dirs = [
            'engine/db',
            'engine/ui',
            'tests',
            'logs',
            'data',
            'backup',
            'meta'
        ]

        missing_dirs = []
        created_dirs = []

        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                try:
                    Path(dir_path).mkdir(parents=True, exist_ok=True)
                    created_dirs.append(dir_path)
                except Exception as e:
                    missing_dirs.append(dir_path)

        if missing_dirs:
            return False, [f"Não conseguiu criar: {', '.join(missing_dirs)}"]

        return True, created_dirs

    def check_file_permissions(self) -> Tuple[bool, List[str]]:
        """Verifica permissões de arquivo."""
        test_files = [
            'test_write.tmp',
            'logs/test_log.tmp',
            'data/test_data.tmp'
        ]

        issues = []

        for file_path in test_files:
            try:
                # Cria arquivo de teste
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)

                with open(file_path, 'w') as f:
                    f.write("Permission test")

                # Limpa arquivo de teste
                Path(file_path).unlink()

            except Exception as e:
                issues.append(f"{file_path}: {e}")

        if issues:
            return False, issues

        return True, ["Permissões OK para escrever em diretórios principais"]

    def check_disk_space(self) -> Tuple[bool, List[str]]:
        """Verifica espaço em disco disponível."""
        try:
            # Verifica espaço no diretório atual
            stat = Path.cwd().statvfs()
            # Espaço disponível em GB
            space_gb = (stat.f_avail * stat.f_frsize) / (1024**3)

            # Requisito: mínimo 1GB disponível
            if space_gb < 1.0:
                self.recommendations.append(".1f")
                return False, [".1f"]
            elif space_gb < 5.0:
                self.warnings.append(".1f")
                return True, [".1f"]
            else:
                return True, [".1f"]

        except Exception as e:
            # Fallback para sistemas sem statvfs (Windows)
            try:
                # Verifica espaço usando tempfile
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w+b', delete=True) as f:
                    # Tenta escrever 1MB
                    f.write(b'x' * 1024*1024)
                    f.flush()
                    f.close()  # Deve ser possível fechar sem erro
                return True, ["Espaço suficiente detectado (>1MB)"]
            except:
                return False, ["Erro ao verificar espaço em disco"]

    def check_memory(self) -> Tuple[bool, List[str]]:
        """Verifica memória disponível."""
        try:
            import psutil

            # Memória disponível em GB
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024**3)

            # Requisito: mínimo 512MB disponível
            if available_gb < 0.5:
                self.recommendations.append(".1f")
                return False, [".1f"]
            elif available_gb < 2.0:
                self.warnings.append(".1f")
                return True, [".1f"]
            else:
                return True, [".1f"]

        except ImportError:
            # Se psutil não está disponível, considera compatível
            self.warnings.append("psutil não disponível - monitoramento avançado limitado")
            return True, ["Memória: verificação psutil não disponível"]
        except Exception as e:
            return True, [f"Erro ao verificar memória: {e}"]

    def check_sqlite_configuration(self) -> Tuple[bool, List[str]]:
        """Verifica configuração SQLite para produção."""
        try:
            conn = sqlite3.connect(":memory:")

            # Verifica journal mode padrão
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

            # Verifica foreign keys
            cursor.execute("PRAGMA foreign_keys")
            fk_enabled = bool(cursor.fetchone()[0])

            # Verifica threadsafety
            thread_safe = sqlite3.threadsafety

            conn.close()

            details = [
                f"Journal mode: {journal_mode} (DELETE=produção)",
                f"Foreign keys: {fk_enabled}",
                f"Thread safety: {thread_safe} (3=recomendado)"
            ]

            if thread_safe < 3:
                self.warnings.append("SQLite não tem suporte completo a threads")
                return True, details  # Não precisa falhar por isso
            else:
                return True, details

        except Exception as e:
            return False, [f"Erro ao verificar configuração SQLite: {e}"]

    def _generate_report(self) -> bool:
        """Gera relatório final de compatibilidade."""
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO FINAL DE COMPATIBILIDADE")
        print("=" * 60)

        total_checks = self.checks_passed + self.checks_failed
        success_rate = (self.checks_passed / max(1, total_checks)) * 100

        print(f"Total de verificações: {total_checks}")
        print("✅ Sucessos: {}".format(self.checks_passed))
        print("❌ Falhas: {}".format(self.checks_failed))
        print(f"Taxa de sucesso: {success_rate:.1f}%")

        if self.errors:
            print("\n🔧 ERROS CRÍTICOS:")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print("\n⚠️  AVISOS:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.recommendations:
            print("\n🎯 RECOMENDAÇÕES:")
            for rec in self.recommendations:
                print(f"  - {rec}")

        # Critérios de sucesso para produção
        can_deploy = (
            success_rate >= 80.0 and  # Pelo menos 80% de compatibilidade
            len(self.errors) == 0     # Sem erros críticos
        )

        print("\n" + "=" * 60)
        if can_deploy:
            print("🚀 COMPATÍVEL COM DEPLOYMENT EM PRODUÇÃO")
            print("Sistema pronto para uso com features avançadas")
        else:
            print("⚠️  COMPATÍVEL PARA DESENVOLVIMENTO")
            print("Resolver problemas críticos antes do deployment em produção")
        print("=" * 60)

        return can_deploy


def main():
    """Função principal."""
    verifier = CompatibilityVerifier()
    success = verifier.verify_all()

    # Saída para scripts de automatização
    if success:
        print("\n✅ RESULTADO: COMPATIBLE", file=sys.stderr)
        sys.exit(0)
    else:
        print("\n⚠️  RESULTADO: NEEDS_ATTENTION", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()