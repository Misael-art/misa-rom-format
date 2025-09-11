# MegaEmu DataBase ROMs - Sistema de Banco de Dados v2

## Visão Geral

O sistema de banco de dados foi completamente reescrito para oferecer melhor performance, confiabilidade e monitoramento. As principais melhorias incluem:

- **Pool de Conexões**: Gerenciamento eficiente de conexões SQLite
- **Retry Automático**: Recuperação automática de falhas transitórias
- **Métricas em Tempo Real**: Monitoramento detalhado de performance
- **Configuração Flexível**: Parâmetros ajustáveis para diferentes ambientes
- **Migração Segura**: Script automatizado para atualização de bancos existentes

## Arquitetura

### Componentes Principais

1. **DatabaseManagerV2**: Gerenciador principal com pool de conexões
2. **ConnectionPool**: Pool de conexões SQLite thread-safe
3. **RetryManager**: Sistema de retry com backoff exponencial
4. **MetricsCollector**: Coleta de métricas de performance
5. **DatabaseConfig**: Configuração centralizada
6. **MigrationManager**: Gerenciamento de migrações

## Instalação e Configuração

### Configuração Básica

```python
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2, DatabaseConfig

# Configuração padrão
config = DatabaseConfig.production()
db = DatabaseManagerV2(config)
db.connect("data/megaemu.db")
```

### Configuração por Ambiente

```python
# Desenvolvimento
dev_config = DatabaseConfig.development()
db = DatabaseManagerV2(dev_config)

# Produção
prod_config = DatabaseConfig.production()
db = DatabaseManagerV2(prod_config)

# Testes
test_config = DatabaseConfig.testing()
db = DatabaseManagerV2(test_config)
```

### Configuração Personalizada

```python
config = DatabaseConfig(
    database_path="data/custom.db",
    pool=PoolConfig(
        max_connections=20,
        timeout=30.0,
        health_check_interval=60
    ),
    retry=RetryConfig(
        max_attempts=5,
        base_delay=0.5,
        max_delay=10.0
    ),
    cache_size=50000,
    log_slow_queries=True,
    slow_query_threshold=1.0
)
```

## Uso

### Operações Básicas

```python
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2

# Conectar ao banco
db = DatabaseManagerV2()
db.connect("data/megaemu.db")

# Executar query
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM roms WHERE id = ?", (1,))
    result = cursor.fetchone()

# Inserir dados
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO roms (name, filename, system_id) VALUES (?, ?, ?)",
        ("Super Mario", "mario.smc", 1)
    )
    conn.commit()
```

### Operações com Retry

```python
# Operações com retry automático são aplicadas automaticamente
# O sistema tentará novamente em caso de falhas transitórias
```

### Monitoramento

```python
from engine.db import default_metrics_collector

# Obter estatísticas
stats = default_metrics_collector.get_performance_summary()
print(f"Total queries: {stats['stats']['total_queries']}")
print(f"Success rate: {stats['stats']['success_rate']}%")
print(f"Average time: {stats['stats']['average_query_time']}s")

# Resetar métricas
default_metrics_collector.reset()
```

## Migração de Bancos Existentes

### Usando o Script de Migração

```bash
# Migração básica
python scripts/migrate_to_v2.py data/megaemu.db

# Migração com saída personalizada
python scripts/migrate_to_v2.py data/megaemu.db --output data/megaemu_v2.db

# Migração forçada (sem confirmação)
python scripts/migrate_to_v2.py data/megaemu.db --force
```

### Processo de Migração

1. **Verificação de compatibilidade**: Verifica se o banco pode ser migrado
2. **Criação de backup**: Cria backup automático do banco original
3. **Migração de dados**: Transfere todos os dados para o novo formato
4. **Verificação de integridade**: Valida a migração

## Configuração de Performance

### Ajustes para Produção

```json
{
  "database_path": "data/megaemu.db",
  "pool": {
    "max_connections": 20,
    "timeout": 30.0,
    "health_check_interval": 300
  },
  "retry": {
    "max_attempts": 5,
    "base_delay": 0.5,
    "max_delay": 10.0,
    "jitter": true
  },
  "cache_size": 20000,
  "synchronous": "normal",
  "log_slow_queries": true,
  "slow_query_threshold": 2.0,
  "backup_enabled": true,
  "backup_interval_hours": 6
}
```

### Ajustes para Desenvolvimento

```json
{
  "database_path": "data/dev_megaemu.db",
  "pool": {
    "max_connections": 5,
    "timeout": 10.0
  },
  "retry": {
    "max_attempts": 2,
    "base_delay": 0.1
  },
  "log_queries": true,
  "log_slow_queries": true,
  "slow_query_threshold": 0.5
}
```

## Troubleshooting

### Problemas Comuns

#### Erro de Timeout
```python
# Aumentar timeout
config = DatabaseConfig()
config.pool.timeout = 60.0  # 60 segundos
```

#### Muitas Falhas de Retry
```python
# Ajustar configuração de retry
config = DatabaseConfig()
config.retry.max_attempts = 10
config.retry.base_delay = 1.0
```

#### Performance Lenta
```python
# Aumentar cache
config = DatabaseConfig()
config.cache_size = 50000
config.synchronous = "normal"
```

### Logs e Debugging

```python
import logging

# Ativar logs detalhados
logging.basicConfig(level=logging.DEBUG)

# Verificar health check
db = DatabaseManagerV2()
health = db.health_check()
print(f"Pool health: {health}")
```

## API Reference

### DatabaseManagerV2

#### Métodos Principais

- `connect(database_path: str) -> bool`: Conecta ao banco de dados
- `close_all() -> None`: Fecha todas as conexões
- `get_connection() -> ContextManager`: Obtém conexão do pool
- `health_check() -> Dict`: Verifica saúde do sistema
- `get_metrics() -> Dict`: Obtém métricas de performance

### DatabaseConfig

#### Configurações Disponíveis

- `database_path`: Caminho do arquivo do banco
- `pool`: Configurações do pool de conexões
- `retry`: Configurações de retry
- `cache_size`: Tamanho do cache SQLite
- `synchronous`: Modo de sincronização
- `log_queries`: Log de todas as queries
- `log_slow_queries`: Log de queries lentas
- `slow_query_threshold`: Limite para queries lentas

## Exemplos de Uso Avançado

### Transações

```python

db = DatabaseManagerV2()
db.connect("data/megaemu.db")

# Transação manual
with db.get_connection() as conn:
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # Múltiplas operações
        cursor.execute("INSERT INTO ...")
        cursor.execute("UPDATE ...")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
```

### Batch Operations

```python
# Operações em lote
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Preparar dados
    data = [(f"ROM {i}", f"file{i}.rom") for i in range(1000)]
    
    # Inserir em lote
    cursor.executemany(
        "INSERT INTO roms (name, filename) VALUES (?, ?)",
        data
    )
    conn.commit()
```

### Queries Complexas com Monitoramento

```python

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Query complexa
    cursor.execute("""
        SELECT r.*, s.name as system_name
        FROM roms r
        JOIN systems s ON r.system_id = s.id
        WHERE r.name LIKE ? AND s.active = 1
        ORDER BY r.name
        LIMIT 100
    """, ("mario%",))
    
    results = cursor.fetchall()

# Verificar performance
metrics = default_metrics_collector.get_query_metrics("SELECT")
print(f"Tempo médio SELECT: {metrics['average_time']}s")
```

## Segurança

### Práticas Recomendadas

1. **Sempre use parâmetros em queries**:
   ```python
   # Correto
   cursor.execute("SELECT * FROM roms WHERE id = ?", (rom_id,))
   
   # Incorreto
   cursor.execute(f"SELECT * FROM roms WHERE id = {rom_id}")
   ```

2. **Valide entrada de dados**:
   ```python
   def validate_rom_data(data):
       if not data.get('name'):
           raise ValueError("Nome é obrigatório")
       if not data.get('filename'):
           raise ValueError("Filename é obrigatório")
       return data
   ```

3. **Use transações para operações atômicas**:
   ```python
   with db.get_connection() as conn:
       cursor = conn.cursor()
       cursor.execute("BEGIN TRANSACTION")
       # ... operações ...
       conn.commit()
   ```

## Suporte

Para problemas ou dúvidas, consulte:
- [Issues no GitHub](https://github.com/seu-repo/megaemu-issues)
- [Documentação completa](https://docs.megaemu.com)
- [Fórum da comunidade](https://forum.megaemu.com)