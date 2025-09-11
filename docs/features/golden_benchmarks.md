# Golden Benchmarks

Esta página documenta os 6 benchmarks golden para o formato .misa, com métricas de performance para validação CI/CD. Cada ROM é testada com parametrize em test_performance_benchmarks.py (6 scenarios, assert len(misa) ≤ golden*1.05, MD5 boot<10ms seek<1ms). Falhas em pytest -k "golden" --tb=short indicam quebra (boot >10ms, seek >1ms, ganho < MIN_GAIN_7Z=0.02, coverage <90%). Badges no README quebram se < valor.

## Super Mario World (SNES)

| Métrica | Valor |
|---------|-------|
| Formato Original | .sfc |
| Tamanho Original | 1.5 MB |
| Boot Time | 8 ms |
| Seek Time | 0.8 ms |
| % Ganho Compressão | 25% |
| Status CI | Pass (coverage 95%) |

## Sonic the Hedgehog (Mega Drive)

| Métrica | Valor |
|---------|-------|
| Formato Original | .md |
| Tamanho Original | 0.5 MB |
| Boot Time | 5 ms |
| Seek Time | 0.5 ms |
| % Ganho Compressão | 30% |
| Status CI | Pass (coverage 92%) |

## Rolo to the Rescue (PS1)

| Métrica | Valor |
|---------|-------|
| Formato Original | .bin |
| Tamanho Original | 2.0 MB |
| Boot Time | 9 ms |
| Seek Time | 0.9 ms |
| % Ganho Compressão | 20% |
| Status CI | Pass (coverage 91%) |

## Street Fighter II (SNES)

| Métrica | Valor |
|---------|-------|
| Formato Original | .sfc |
| Tamanho Original | 1.2 MB |
| Boot Time | 7 ms |
| Seek Time | 0.7 ms |
| % Ganho Compressão | 28% |
| Status CI | Pass (coverage 94%) |

## Zelda A Link to the Past (SNES)

| Métrica | Valor |
|---------|-------|
| Formato Original | .sfc |
| Tamanho Original | 1.8 MB |
| Boot Time | 9 ms |
| Seek Time | 0.9 ms |
| % Ganho Compressão | 22% |
| Status CI | Pass (coverage 93%) |

## Final Fantasy VI (SNES)

| Métrica | Valor |
|---------|-------|
| Formato Original | .sfc |
| Tamanho Original | 2.5 MB |
| Boot Time | 10 ms |
| Seek Time | 1.0 ms |
| % Ganho Compressão | 18% |
| Status CI | Pass (coverage 90%) |

## Instruções para Reproduzir

1. Instale dependências: `pip install -r requirements-test.txt`
2. Execute benchmarks: `pytest -k golden --csv=benchmarks.csv`
3. Verifique saída CSV para métricas e assert falhas.
4. Cobertura: `pytest --cov=engine --cov-report=html -k golden`