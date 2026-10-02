# MegaEmu DataBase ROMs — MISA ROM Format

Ferramentas e documentação em desenvolvimento para organizar coleções locais de jogos retrô e explorar o formato `.misa`.

> **Status:** em desenvolvimento. Ainda não há release estável nem benchmarks reproduzíveis publicados.

## O que há neste repositório

- `MegaEmu_Launcher.pyw` e `MegaEmu_Launcher.bat`: launchers para abrir a aplicação no Windows.
- `setup.py`: prepara diretórios e configuração local e gera `start.py`.
- `LAUNCHER_README.md`: descreve os launchers, seus requisitos e o diagnóstico básico.
- `docs/`: documentação técnica do projeto.

## Requisitos

- Python 3.8 ou superior.
- SQLite disponível com a instalação de Python.

## Quick start

No terminal, na pasta do repositório:

```bash
python setup.py
python start.py
```

No Windows, `MegaEmu_Launcher.pyw` inicia sem console; `MegaEmu_Launcher.bat` mantém o console visível para diagnóstico. Veja [LAUNCHER_README.md](LAUNCHER_README.md) para detalhes.

## Estado e compatibilidade

A compatibilidade do formato `.misa`, o suporte a emuladores e os números de desempenho precisam de resultados reproduzíveis antes de serem anunciados como prontos para produção.

## Licença

MIT — veja [LICENSE](LICENSE).
