# Troubleshooting - MegaEmu Database ROMs

## Problemas Comuns e Soluções

### 1. Erros de Import (ModuleNotFoundError)

**Sintoma:**
```
ImportError: No module named 'pydantic'
ImportError: No module named 'dependency_injector'
ModuleNotFoundError: No module named 'bs4'
ModuleNotFoundError: No module named 'selenium'
```

**Causa:** Dependências não instaladas.

**Solução:**
Instale as dependências principais:
```bash
pip install -r requirements.txt
```

Para testes (backup/):
```bash
pip install beautifulsoup4 selenium
```

### 2. Erros de Sintaxe (SyntaxError)

**Sintoma:**
```
SyntaxError: invalid syntax
IndentationError: expected an indented block
```

**Causa:** Blocos de código incompletos ou indentação errada (ex: def sem body).

**Solução:**
- Verifique funções vazias - adicione `pass` ou implemente.
- Execute `black .` para formatar indentação.
- Cheque linhas específicas (ex: linha 691 directory_scanner.py - indent else).

### 3. Erros de Test Collection (pytest)

**Sintoma:**
```
ERROR collecting backup/test_xml_import.py - SyntaxError
ERROR collecting test_output.txt - UnicodeDecodeError
```

**Causa:** Arquivos não-Python como tests, sintaxe em backup/.

**Solução:**
- Remova txt de tests/ (mova para data/).
- Fixe sintaxe em backup/ ou ignore com pytest.ini: add `python_files = *.py` se necessário.
- Rode `pytest --collect-only` para listar erros.

### 4. Erros de Banco de Dados (SQLite)

**Sintoma:**
```
sqlite3.OperationalError: table roms has no column named rom_filename
```

**Causa:** Schema desatualizado.

**Solução:**
Execute scripts/migrate_to_v2.py para atualizar schema.

### 5. Erros de Threading/UI

**Sintoma:**
```
AttributeError: 'NoneType' object has no attribute 'show_message'
```

**Causa:** Componentes UI não inicializados.

**Solução:**
- Verifique __init__ ordem (setup_managers antes setup_ui).
- Adicione checks: if self.status_bar: self.status_bar.show_message(...)

### 6. Deps Frágeis (Scraping/IA)

**Sintoma:**
```
QuotaExceededError or RateLimitError
```

**Solução:**
- Configure chaves API em config.json.
- Aumente rate_limit em web_scraper config.
- Use fallback engine em AIEnricher.

### 7. Performance (Parsing XML Grandes)

**Sintoma:**
```
MemoryError or timeout in import_xml
```

**Solução:**
- Use parsing incremental em lxml.
- Limite max_file_size em DirectoryScanner.
- Execute em background com progress.

Para mais, consulte logs/ e pytest --cov-report=html para coverage.
