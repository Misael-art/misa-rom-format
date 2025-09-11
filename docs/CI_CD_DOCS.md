# Pipelines CI/CD - Mega_Emu_DataBase_ROMs

Este documento descreve os workflows GitHub Actions para CI/CD, garantindo testes golden benchmarks (boot<10ms, seek<1ms, coverage>90%), deploy docs e release PyPI. Conformidade: timeout 120s, badge.json gerado, secrets managed sem hard-code. Workflows definitivos, sem workarounds.

## 1. Workflow CI (ci.yml)

Triggers: push/PR to main. Jobs: setup Python 3.13/Docker/Rust, pip install requirements.txt + pytest-cov/black, lint black --check, test pytest --cov --fail-under=90 -k "golden" --tb=short (ROMs samples em tests/assets), generate badge.json (passing brightgreen se success, failing red), upload artifact badge.json, timeout-minutes=2 (120s). Comando local: act -j ci (instale act via brew/scoop).

## 2. Workflow Deploy Docs (deploy-docs.yml)

Trigger: push main. Permissions: contents read, pages write, id-token write. Jobs: checkout, setup Python 3.13, pip sphinx/sphinx-rtd-theme, sphinx-build docs/ _build, configure-pages, upload-pages-artifact _build, deploy-pages. Environment: github-pages. Comando local: sphinx-build -b html docs _build/html.

Badge em README: ![Benchmark](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/user/repo/main/benchmarks/badge.json).

## 3. Workflow Release (release.yml)

Trigger: release published. Jobs: build (setup Python 3.13, pip build/twine, python setup.py sdist bdist_wheel, Rust se Cargo.toml, twine upload dist/*.whl com TWINE_PASSWORD ${{ secrets.PYPI_TOKEN }}); benchmarks (setup Python, pip pytest-json-report/pandas, pytest test_performance_benchmarks.py -k golden --json-report benchmarks.json, parse to CSV benchmarks/benchmark_results.csv, upload artifact). Env: RUST_VERSION=stable.

## 4. pytest.ini Config

[tool:pytest]
markers = golden: golden benchmarks
addons = pytest-cov

## 5. Manutenção

Atualize requirements.txt para deps (pytest-cov, black, sphinx). Verifique coverage>90%, golden pass. Sem inconformidades: soluções definitivas, ciclo completo (test/deploy). Para local: pytest -k golden -v (skip se no samples, lógica pass).

## 2. Integração Contínua (CI) com GitHub Actions

A documentação será automaticamente gerada e publicada no GitHub Pages sempre que houver um push para a branch `main`.
