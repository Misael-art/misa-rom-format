# Instalação do MISAROM

Esta seção fornece um guia detalhado para configurar e instalar o MISAROM em seu ambiente local ou de produção.

## Requisitos do Sistema

- **Python**: Versão 3.8 ou superior. Verifique com `python --version`.
- **Sistema Operacional**: Compatível com Windows, Linux ou macOS.
- **Dependências**: Listadas em `requirements.txt` (Flask, Requests, sqlite3).
- **Git**: Para clonar o repositório (opcional, se baixar manualmente).
- **Espaço em Disco**: Mínimo 100 MB para o banco de dados SQLite e arquivos de configuração.

Recomenda-se o uso de um ambiente virtual para isolar as dependências.

## Passos de Instalação

### 1. Clonar o Repositório

Clone o projeto do GitHub:

```
git clone https://github.com/Misael-art/MISAROM.git
cd MISAROM
```

Se não tiver Git, baixe o ZIP do repositório e extraia para um diretório local.

### 2. Configurar Ambiente Virtual (Recomendado)

Crie e ative um ambiente virtual:

- No Windows:
  ```
  python -m venv venv
  venv\Scripts\activate
  ```

- No Linux/macOS:
  ```
  python -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar Dependências

Instale as bibliotecas necessárias:

```
pip install --upgrade pip
pip install -r requirements.txt
```

Isso instalará Flask para o servidor web, Requests para integrações de IA e sqlite3 para o banco de dados.

Se houver erros de permissão, use `pip install --user -r requirements.txt` ou execute como administrador.

### 4. Configuração Inicial

- Crie o diretório `.misa/` se não existir (deve conter `config.json`).
- Edite `.misa/config.json` com as configurações específicas do seu ambiente.

Exemplo de conteúdo para `config.json`:

```json
{
  "db_path": "db/misarom.db",
  "ia_endpoint": "https://api.exemplo.com/v1/enrich",
  "api_key": "sua_chave_de_api_aqui",
  "debug_mode": true,
  "log_level": "INFO"
}
```

- **db_path**: Caminho para o arquivo SQLite.
- **ia_endpoint**: URL da API de IA (use mock se não tiver chave real).
- **api_key**: Chave de autenticação para serviços de IA (deixe vazio para modo mock).
- **debug_mode**: Ative para logs detalhados em desenvolvimento.
- **log_level**: Nível de logging (DEBUG, INFO, WARNING, ERROR).

### 5. Inicializar o Banco de Dados

O banco de dados SQLite é configurado automaticamente no primeiro run, mas verifique a pasta `db/` para scripts de setup.

Execute manualmente se necessário (assumindo script `setup_db.py` em db/):

```
python db/setup_db.py
```

Isso criará as tabelas necessárias para ROMs, metadados e logs.

### 6. Executar o Aplicativo

Inicie o servidor principal:

```
python main.py
```

O Flask deve iniciar em `http://localhost:5000`. Você verá logs indicando que o app está rodando.

Para execução em produção, use um servidor WSGI como Gunicorn:

```
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

## Verificação da Instalação

1. Acesse `http://localhost:5000` no navegador ou via curl:

   ```
   curl http://localhost:5000/
   ```

   Deve retornar uma resposta de status ou página inicial.

2. Teste um endpoint de exemplo (ex: enriquecimento de ROM):

   ```
   curl -X POST http://localhost:5000/enrich -F "rom=@sample.rom"
   ```

3. Verifique os logs no terminal para erros.

4. Confirme que o arquivo `db/misarom.db` foi criado e contém dados de teste.

## Problemas Comuns na Instalação

- **Erro de porta ocupada**: Mude a porta no config.json ou mate o processo: `netstat -ano | findstr :5000` (Windows).
- **SQLite sem permissões**: Execute o terminal como administrador ou mude o db_path para um diretório acessível.
- **Dependências falhando**: Use `pip list` para verificar instalações e reinstale se necessário.

Para mais suporte, consulte [Troubleshooting](../troubleshooting.md).

## Notas para Produção

- Use variáveis de ambiente para chaves sensíveis (ex: `export API_KEY=sua_chave`).
- Configure um proxy reverso (Nginx) para HTTPS.
- Monitore com ferramentas como Prometheus para logs e performance.

A instalação deve levar menos de 5 minutos em um ambiente padrão.