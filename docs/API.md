ocs/API.md</path>
<content line_count>350><![CDATA[
# 📚 MegaEmu Database ROMs - Referência de APIs

> Documentação completa das APIs dos novos módulos implementados

## 📋 Índice

- [WebScraper](#webscraper-api-) - Sistema de raspagem ética
- [AIEnricher](#aienricher-api-) - Enriquecimento inteligente de metadados
- [PrometheusExporter](#prometheus-api-) - Monitoramento e métricas
- [Database Schema v2.1](#database-schema-api-) - Schema flexível com campos JSON
- [Casos de Uso](#exemplos-práticos) - Exemplos integrados

---

## 🌐 WebScraper API

### `WebScraper` - Orquestrador Principal

Sistema completo para raspagem ética de metadados de jogos.

#### Configuração Básica

```python
from engine.scrapers.web_scraper import WebScraper, GameMetadata

config = {
    'strategies': ['thegamesdb', 'igdb'],  # Fontes disponíveis
    'rate_limit': 1.0,                    # Requisições por segundo
    'cache_enabled': True,                # Cache local SQLite
    'cache_ttl': 86400,                   # TTL do cache (24h)
    'retry_attempts': 3,                  # Tentativas de retry
    'timeout_seconds': 10,                # Timeout por requisição
    'igdb_api_key': 'your_api_key'        # Apenas para IGDB
}

scraper = WebScraper(config)
```

#### Método Principal: `scrape_metadata()`

```python
metadata = scraper.scrape_metadata("Super Mario World")

if metadata:
    print(f"Título: {metadata.title}")
    print(f"Descrição: {metadata.description}")
    print(f"Gêneros: {metadata.genres}")
    print(f"Desenvolvedor: {metadata.developer}")
```

**Parâmetros:**
- `query` (str): Nome do jogo ou identificador
- **Retorno:** `GameMetadata | None`

#### DataClass: `GameMetadata`

```python
@dataclass
class GameMetadata:
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    release_date: Optional[str] = None  # ISO 8601
    genres: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
```

#### Configurações Avançadas

```python
# Cache personalizado
config['cache_path'] = '/custom/cache.db'
config['cache_ttl'] = 7 * 24 * 3600  # 7 dias

# Rate limiting personalizado
config['rate_limit'] = 2.0  # 2 req/s

# User agents customizados
config['user_agents'] = [
    'MegaEmu-Scraper/1.0 (contact@megaemu.com)',
    # ... outros user agents
]

# Timeout personalizado
config['timeout_seconds'] = 15
```

#### Tratamento de Erros

```python
try:
    metadata = scraper.scrape_metadata("Unknown Game")
except scraper.ExternalAPIError as e:
    print(f"Erro de API externa: {e}")
except scraper.NetworkError as e:
    print(f"Erro de rede: {e}")
except scraper.RateLimitError as e:
    print("Rate limit atingido - aguardar")
```

---

## 🤖 AIEnricher API

### `AIEnricher` - Enriquecedor Inteligente

Sistema de enriquecimento de metadados usando IA com múltiplas estratégias.

#### Configuração Básica

```python
from engine.enrichment.ai_enricher import (
    AIEnricher,
    OpenAIStrategy,
    GeminiStrategy,
    EnrichmentResult
)

# Estratégias disponíveis
strategies = [
    OpenAIStrategy(api_key='sk-openai-key'),
    GeminiStrategy(api_key='google-gemini-key')
]

# Configuração principal
config = {
    'daily_quota': 100,      # Limite diário
    'monthly_quota': 3000,   # Limite mensal
    'max_retries': 3,        # Tentativa máxima por estratégia
    'enable_fallback': True  # Fallback se APIs falharem
}

enricher = AIEnricher(config, strategies, **config)
```

#### Método Principal: `enrich()`

```python
# Metadados de entrada
game_data = {
    'title': 'Final Fantasy VI',
    'description': 'Um RPG clássico de SNES',
    'genres': ['RPG'],
    'hashes': {
        'md5': 'abc123...',
        'sha1': 'def456...'
    }
}

# Processo de enriquecimento
result = enricher.enrich(game_data)

# Resultado detalhado
print(f"Confiança: {result.confidence_score}")
print(f"Estratégia utilizada: {result.used_strategy}")
print(f"Tempo processado: {result.processing_time}s")
print(f"Fallback aplicado: {result.fallback_applied}")

# Metadados enriquecidos
enriched = result.enriched_metadata
print(f"Nova descrição: {enriched['description']}")
print(f"Gêneros expandidos: {enriched['genres']}")
print(f"Traduções: {enriched['translations']}")
```

**Retorno:** `EnrichmentResult`

#### Classe: `EnrichmentResult`

```python
class EnrichmentResult:
    def __init__(
        self,
        original_metadata: Dict[str, Any],
        enriched_metadata: Dict[str, Any],
        confidence_score: float,  # 0.0 a 1.0
        used_strategy: str,       # "OpenAI", "Gemini", etc.
        processing_time: float,
        fallback_applied: bool
    ):
        pass
```

#### Monitoramento de Quota

```python
# Verificar status de quota
quota_info = enricher.get_quota_info()

print("Uso de API:")
print(f"Diário: {quota_info['daily_usage']}/{quota_info['daily_limit']}")
print(f"Mensal: {quota_info['monthly_usage']}/{quota_info['monthly_limit']}")
print(f"Restante hoje: {quota_info['daily_remaining']}")

# Pausa automática se quota excedida
try:
    result = enricher.enrich(game_data)
except QuotaExceededError:
    print("Quota excedida - aguarde reset diário")
```

#### Estratégias Disponíveis

##### OpenAIStrategy
```python
strategy = OpenAIStrategy(
    api_key='sk-your-openai-key',
    max_retries=3
)
```

##### GeminiStrategy
```python
strategy = GeminiStrategy(
    api_key='your-gemini-key',
    max_retries=3
)
```

---

## 📊 Prometheus API

### `PrometheusExporter` - Sistema de Monitoramento

Exportação de métricas no formato padrão Prometheus.

#### Configuração Básica

```python
from engine.db.prometheus_exports import PrometheusExporter, get_global_exporter

# Instância dedicada
exporter = PrometheusExporter(port=8000, host='localhost')
exporter.start()

# Ou usar instance global (recomendado)
global_exporter = get_global_exporter()
global_exporter.start()
```

#### Coleta de Métricas do Banco

```python
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2

db_manager = DatabaseManagerV2()
exporter.collect_db_metrics(db_manager)
```

#### Métricas Disponíveis

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `db_pool_connections_active` | Gauge | Conexões ativas no pool |
| `db_pool_connections_idle` | Gauge | Conexões ociosas no pool |
| `db_pool_connections_created` | Gauge | Total de conexões criadas |
| `db_queries_total` | Gauge | Total de queries executadas |
| `db_transactions_total` | Gauge | Total de transações |
| `db_slow_queries` | Gauge | Queries lentas (>5s) |
| `db_query_execution_time` | Histogram | Tempo médio de execução |
| `system_cpu_percent` | Gauge | Percentual de CPU usado |
| `system_memory_mb` | Gauge | Memória usada em MB |
| `db_errors_total{type="..."}` | Counter | Erros por tipo |

#### Acesso às Métricas

```bash
# Via HTTP (porta configurada)
curl http://localhost:8000/metrics

# Via Prometheus (adicionar ao prometheus.yml)
scrape_configs:
  - job_name: 'megaemu'
    static_configs:
      - targets: ['localhost:8000']
```

#### Formato de Métricas

```text
# HELP db_pool_connections_active Número de conexões ativas no pool
# TYPE db_pool_connections_active gauge
db_pool_connections_active 5

# HELP db_errors_total Número total de erros do tipo connection_errors
# TYPE db_errors_total counter
db_errors_total{type="connection_errors"} 3
```

---

## 🗄️ Database Schema v2.1 API

### Campos Flexíveis e Particionamento

#### Funções de Validação JSON

```python
from engine.db.database_schema import validate_json_field, setup_partitioning

# Validação de campos JSON
json_data = '{"genres": ["action", "adventure"], "rating": 9.5}'
is_valid = validate_json_field(json_data)  # True

invalid_json = '{"genres": ["action",}'  # JSON incompleto
is_valid = validate_json_field(invalid_json)  # False

empty_field = ""
is_valid = validate_json_field(empty_field)  # True (campo vazio é válido)
```

#### Estrutura da Tabela ROMs Expandida

```sql
-- Nova estrutura com campos flexíveis
CREATE TABLE roms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    filename TEXT,
    size INTEGER NOT NULL,
    crc TEXT, md5 TEXT, sha1 TEXT,
    system TEXT, region TEXT, language TEXT,
    rom_type TEXT, status TEXT DEFAULT 'active',
    release_year INTEGER, genre TEXT,
    publisher TEXT, developer TEXT,

    -- Campos flexíveis (NOVO)
    metadata_json TEXT,      -- Metadados estruturados em JSON
    region_json TEXT,        -- Dados regionais específicos

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games (id)
);
```

#### Queries com Campos JSON

```python
import sqlite3

conn = sqlite3.connect('roms.db')

# Consulta por gênero dentro de JSON
cursor = conn.execute("""
    SELECT name, metadata_json->>'genres' AS genres
    FROM roms
    WHERE metadata_json->>'rating' > '9.0'
""")

for row in cursor:
    print(f"Jogo: {row[0]}, Gêneros: {row[1]}")

# Atualização de campos JSON
conn.execute("""
    UPDATE roms
    SET metadata_json = json_set(metadata_json, '$.tags', '["IA-Enriched"]')
    WHERE id = ?
""", (rom_id,))

conn.commit()
```

#### Particionamento Automático

```python
# Configuração de particionamento lógico
setup_partitioning(conn)

# Particionamento por décadas automaticamente:
# - roms_pre_1990
# - roms_1990s
# - roms_2000s
# - roms_2010s
# - roms_2020_plus
```

#### Triggers de Validação Automática

```sql
-- Trigger validando JSON automaticamente
CREATE TRIGGER trig_validate_json_metadata
    BEFORE INSERT ON roms
    WHEN NEW.metadata_json IS NOT NULL AND NEW.metadata_json != ''
    BEGIN
        SELECT CASE
            WHEN json_valid(NEW.metadata_json) == 0
            THEN RAISE(ABORT, 'Campo metadata_json deve conter JSON válido')
        END;
    END;

-- Trigger de auditoria automática
CREATE TRIGGER trig_update_roms_timestamp
    AFTER UPDATE ON roms
    FOR EACH ROW
    BEGIN
        UPDATE roms SET updated_at = datetime('now') WHERE id = NEW.id;
    END;
```

---

## 🎯 Exemplos Práticos

### Uso Integrado: Raspagem + IA + Banco

```python
from engine.scrapers.web_scraper import WebScraper
from engine.enrichment.ai_enricher import AIEnricher, OpenAIStrategy
from engine.db.prometheus_exports import get_global_exporter

# 1. Configuração dos sistemas
scraper_config = {'strategies': ['thegamesdb'], 'cache_enabled': True}
scraper = WebScraper(scraper_config)

ai_strategies = [OpenAIStrategy('sk-openai-key')]
enricher = AIEnricher({}, ai_strategies)

db_manager = DatabaseManagerV2({'pool': {'enable_metrics': True}})

# 2. Inicializar monitoramento
exporter = get_global_exporter()
exporter.start()

# 3. Processo integrado
game_name = "Super Mario World"

def process_game_complete(game_name):
    # Raspagem de metadados básicos
    basic_metadata = scraper.scrape_metadata(game_name)

    if not basic_metadata:
        return None

    # Conversão para dict + enriquecimento IA
    metadata_dict = basic_metadata.to_dict()
    enrichment_result = enricher.enrich(metadata_dict)

    # Salvamento no banco com campos JSON
    enriched_data = enrichment_result.enriched_metadata

    db_manager.execute_query("""
        INSERT INTO roms (
            name, metadata_json, created_at
        ) VALUES (?, ?, datetime('now'))
    """, (
        enriched_data['title'],
        json.dumps(enriched_data)
    ))

    # Atualizar métricas de monitoramento
    exporter.collect_db_metrics(db_manager)

    return enrichment_result

# Execução do processo completo
result = process_game_complete(game_name)

if result:
    print(".2f"    print(f"Módulos utilizados: WebScraper + AIEnricher + DB v2.1")
    print("Métricas disponíveis em: http://localhost:8000/metrics"
```

### Pipeline de Processamento em Lote

```python
import json
from concurrent.futures import ThreadPoolExecutor

def batch_process_games(game_list, max_workers=3):
    """Processamento em lote com controle de recursos"""

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_game_complete, game)
                  for game in game_list]

        for future in futures:
            result = future.result()
            if result:
                results.append(result)

            # Controle de quota IA
            quota = enricher.get_quota_info()
            if quota['daily_remaining'] < 10:
                print("Quota baixa - aguardando próximos usos")
                break

    return results

# Processamento de lista grande
games = ["Final Fantasy VI", "Chrono Trigger", "EarthBound", "Secret of Mana"]
batch_results = batch_process_games(games)

print(f"Processamento concluído: {len(batch_results)}/{len(games)} jogos")
```

---

## 🔧 Configurações Avançadas

### Configurações de Performance

```python
# WebScraper - Performance otimizada
scraper_config = {
    'rate_limit': 2.0,           # 2 req/s para maior velocidade
    'cache_ttl': 7*24*3600,     # Cache de 7 dias
    'timeout_seconds': 8,       # Timeout reduzido
    'retry_attempts': 2         # Menos retries para velocidade
}

# AIEnricher - Controle de recursos
ai_config = {
    'daily_quota': 500,         # Quota maior para produção
    'max_retries': 1,          # Retry reduzido
    'enable_fallback': True     # Sempre manter fallback
}

# Database - Pool otimizado
db_config = {
    'pool': {
        'max_connections': 100,       # Conexões para alto tráfego
        'enable_auto_scaling': True,
        'enable_metrics': True,
        'enable_statement_caching': True
    }
}
```

### Tratamento de Erros Robusto

```python
class GameProcessor:
    def __init__(self):
        self.failure_counts = {}

    def safe_process_game(self, game_name):
        """Processamento com tratamento completo de erros"""

        try:
            # Tentativa principal
            result = process_game_complete(game_name)

            # Reset contador em sucesso
            self.failure_counts[game_name] = 0

            return result

        except Exception as e:
            # Incrementar contador de falhas
            self.failure_counts[game_name] = self.failure_counts.get(game_name, 0) + 1

            # Log detalhado
            logger.error(f"Falha no processamento de {game_name}: {e}")

            # Backoff exponencial para novos jogos
            if self.failure_counts[game_name] > 3:
                logger.warning(f"Jogo {game_name} falhando consistentemente - pulando")
                return None

            # Retry com backoff
            import time
            backoff = 2 ** self.failure_counts[game_name]
            time.sleep(min(backoff, 60))  # Máximo 60s

            return self.safe_process_game(game_name)

processor = GameProcessor()
result = processor.safe_process_game("Zelda: A Link to the Past")
```

---

## 📈 Referências Técnicas

### Dependências das APIs

| Módulo | Dependências | Versão Recomendada |
|--------|--------------|-------------------|
| WebScraper | `requests`, `sqlite3` | requests>=2.25.0 |
| AIEnricher | `openai` (opcional) | openai>=1.0.0 |
| Prometheus | `prometheus_client` (opcional) | prometheus-client>=0.17.0 |
| Database | `sqlite3` (built-in) | - |

### Limites e Recomendações

| Recurso | Limite | Recomendação |
|---------|--------|--------------|
| Rate Limit WebScraper | 1-2 req/s | 1 req/s por padrão |
| Quota OpenAI (gratuito) | 200/dia | 100/dia para testes |
| Partições DB | 5 décadas | Ajustável conforme necessidade |
| Cache TTL | 24h-7d | 24h para metadados dinâmicos |

---

**Última atualização:** Dezembro 2024
**Versão:** MegaEmu v2.1.0