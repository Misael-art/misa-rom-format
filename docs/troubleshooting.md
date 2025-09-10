# Troubleshooting

Esta seção fornece guias para problemas comuns no MISAROM e como resolvê-los.

## Erros de Dependências

**Problema:** Erro ao instalar dependências com `pip install -r requirements.txt`, como "No module named 'flask'".

**Soluções:**
1. Verifique se o Python é 3.8 ou superior: `python --version`.
2. Atualize pip: `python -m pip install --upgrade pip`.
3. Tente instalar em um ambiente virtual: `python -m venv venv` e ative-o (`venv\Scripts\activate` no Windows).
4. Instale manualmente: `pip install Flask requests`.

## Falhas no Banco de Dados SQLite

**Problema:** Erro de permissão ao criar ou acessar o DB, como "sqlite3.OperationalError: unable to open database file".

**Soluções:**
1. Verifique permissões no diretório db/: Execute como administrador