ocs/EXAMPLES.md</path>
<content line_count>450><![CDATA[
# 🎯 Exemplos de Uso - MegaEmu Database ROMs v2.1

> Exemplos práticos de integração completa com todas as funcionalidades

## 📋 Índice

- [Configuração Inicial](#configuração-inicial-)
- [Exemplo 1: Raspagem Básica de Metadados](#exemplo-1-raspagem-básica-de-metadados)
- [Exemplo 2: Enriquecimento com IA Completo](#exemplo-2-enriquecimento-com-ia-completo)
- [Exemplo 3: Pipeline Integrado Completo](#exemplo-3-pipeline-integrado-completo)
- [Exemplo 4: Processamento em Lote](#exemplo-4-processamento-em-lote)
- [Exemplo 5: Sistema com Monitoramento](#exemplo-5-sistema-com-monitoramento)
- [Casos Avançados](#casos-avançados)
- [Scripts Úteis](#scripts-úteis)

## 🚀 Configuração Inicial

### Imports Necessários

```python
import os
import sys
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# MegaEmu imports
from engine.scrapers.web_scraper import WebScraper, GameMetadata
from engine.enrichment.ai_enricher import AIEnricher, OpenAIStrategy, GeminiStrategy
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2
from engine.db.prometheus_exports import get_global_exporter
from engine.errors import DatabaseError, EnrichmentError, ScraperError

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### Configuração Padrão dos Sistemas

```python
# Configuração completa
CONFIG = {
    'database': {
        'path': 'roms_database.db',
        'enable_monitoring': True,
        'pool_config': {
            'max_connections': 20,
            'enable_metrics': True
        }
    },
    'web_scraper': {
        'strategies': ['thegamesdb', 'igdb'],
        'rate_limit': 1.0,
        'cache_enabled': True,
        'cache_ttl': 86400,
        'timeout_seconds': 10,
        'igdb_api_key': os.getenv('IGDB_API_KEY', '')  # Opcional
    },
    'ai_enricher': {
        'openai_key': os.getenv('OPENAI_API_KEY', ''),
        'gemini_key': os.getenv('GEMINI_API_KEY', ''),
        'daily_quota': 100,
        'monthly_quota': 2500,
        'enable_fallback': True
    },
    'monitoring': {
        'prometheus_port': 8000,
        'enable_metrics': True
    }
}

def initialize_system(config: Dict[str, Any]) -> Dict[str, Any]:
    """Inicializa todos os componentes do sistema"""

    # 1. Database Manager V2
    db_config = config['database']
    db_manager = DatabaseManagerV2(db_config)

    # 2. Web Scraper
    scraper_config = config['web_scraper']
    scraper = WebScraper(scraper_config)

    # 3. AI Enricher
    ai_config = config['ai_enricher']
    ai_strategies = []

    if ai_config['openai_key']:
        ai_strategies.append(OpenAIStrategy(ai_config['openai_key']))

    if ai_config['gemini_key']:
        ai_strategies.append(GeminiStrategy(ai_config['gemini_key']))

    if ai_strategies:
        enricher = AIEnricher({}, ai_strategies, **ai_config)
    else:
        enricher = None
        logger.warning("Nenhuma chave de API IA configurada")

    # 4. Prometheus Exporter
    if config['monitoring']['enable_metrics']:
        exporter = get_global_exporter()
        exporter.start()
        logger.info("Prometheus exporter iniciado")
    else:
        exporter = None

    return {
        'database': db_manager,
        'scraper': scraper,
        'enricher': enricher,
        'exporter': exporter
    }

# Inicialização global
system = initialize_system(CONFIG)
```

---

## 🔍 Exemplo 1: Raspagem Básica de Metadados

### Cenário Simples
> Buscar metadados básicos de um único jogo usando WebScraper

```python
def simple_metadata_scraping():
    """Exemplo de raspagem simples de metadados"""

    scraper = system['scraper']

    # Jogos para testar
    games_to_scrape = [
        "Super Mario World",
        "The Legend of Zelda: A Link to the Past",
        "Final Fantasy VI",
        "Chrono Trigger"
    ]

    results = []

    for game_name in games_to_scrape:
        logger.info(f"Buscando metadados para: {game_name}")

        try:
            metadata = scraper.scrape_metadata(game_name)

            if metadata:
                game_info = {
                    'name': game_name,
                    'title': metadata.title,
                    'description': metadata.description,
                    'genres': metadata.genres,
                    'developer': metadata.developer,
                    'publisher': metadata.publisher,
                    'release_date': metadata.release_date
                }

                results.append(game_info)

                print(f"""
🎮 {game_info['name']} → {game_info['title']}
📝 {game_info['description'][:100] if game_info['description'] else 'N/A'}...
🏷️  Gêneros: {', '.join(game_info['genres'])}
🏢 Dev: {game_info['developer'] or 'N/A'} | Pub: {game_info['publisher'] or 'N/A'}
📅 Lançamento: {game_info['release_date'] or 'N/A'}
                """)
            else:
                logger.warning(f"Nenhum metadado encontrado para: {game_name}")
                results.append({'name': game_name, 'error': 'not_found'})

        except ScraperError as e:
            logger.error(f"Erro na raspagem de {game_name}: {e}")
            results.append({'name': game_name, 'error': str(e)})

    # Relatório
    successful = len([r for r in results if 'error' not in r])
    failed = len(results) - successful

    print(f"\n📊 RESULTADO GERAL:")
    print(f"✅ Sucessos: {successful}")
    print(f"❌ Falhas: {failed}")
    print(f"📈 Taxa de sucesso: {successful / len(results) * 100:.1f}%")

# Execução
if __name__ == "__main__":
    simple_metadata_scraping()
```

### Configurações Avançadas de Cache

```python
def cached_scraping_example():
    """Demonstração de uso inteligente do cache"""

    # Configuração com cache personalizado
    enhanced_config = {
        'strategies': ['thegamesdb'],
        'rate_limit': 2.0,              # Mais rápido
        'cache_enabled': True,
        'cache_path': 'custom_cache.db', # Cache personalizado
        'cache_ttl': 7 * 24 * 3600,     # 7 dias
        'user_agents': [                 # UAs customizados
            'MegaEmu-Scraper/1.0 (myproject@megaemu.com)'
        ]
    }

    scraper = WebScraper(enhanced_config)

    # Busca inicial (vai à internet)
    start_time = time.time()
    result1 = scraper.scrape_metadata("Dota 2")
    time1 = time.time() - start_time

    # Busca repetida (cache hit)
    start_time = time.time()
    result2 = scraper.scrape_metadata("Dota 2")
    time2 = time.time() - start_time

    print("
🕐 PERFORMANCE DE CACHE:"    print(".3f"    print(".3f"    print(".1f"    print("📊 Mesmo resultado:", result1.title == result2.title if result1 and result2 else False)

# Execução
cached_scraping_example()
```

---

## 🤖 Exemplo 2: Enriquecimento com IA Completo

### Enriquecimento Básico

```python
def basic_ai_enrichment():
    """Exemplo básico de enriquecimento com IA"""

    if not system['enricher']:
        logger.error("IA Enricher não configurado - verifique chaves de API")
        return

    enricher = system['enricher']

    # Dados básicos para enriquecer
    base_game = {
        'title': 'Doom',
        'description': 'Um jogo de tiro clássico',
        'genres': ['Shooter'],
        'hashes': {
            'md5': 'abc123456789',
            'sha1': 'def987654321'
        }
    }

    print(f"\n🎯 ENRIQUECIMENTO DE: {base_game['title']}")
    print(f"📝 Descrição original: {base_game['description']}")
    print(f"🏷️  Gêneros originais: {base_game['genres']}")

    try:
        # Processo de enriquecimento
        result = enricher.enrich(base_game)

        print(f"\n🎉 RESULTADO DO ENRIQUECIMENTO:")
        print(f"⭐ Confiança: {result.confidence_score}")
        print(f"🎛️  Estratégia usada: {result.used_strategy}")
        print(f"⏱️  Tempo: {result.processing_time:.2f}s")
        print(f"🔄 Fallback aplicado: {result.fallback_applied}")

        enriched = result.enriched_metadata

        print(f"\n📝 Descrição enriquecida:")
        print(f"   {enriched.get('description', 'N/A')}")

        print(f"\n🏷️  Gêneros expandidos:")
        print(f"   Originais + IA: {base_game['genres']} → {enriched.get('genres', [])}")

        if 'tags' in enriched:
            print(f"\n🏷️  Tags IA:")
            print(f"   {enriched['tags']}")

        if 'translations' in enriched:
            print(f"\n🌐 Traduções automáticas:")
            for lang, text in enriched['translations'].items():
                print(f"   {lang}: {text[:50]}...")

        # Monitoramento de quota
        quota = enricher.get_quota_info()
        print(f"\n📊 QUOTA RESTANTE:")
        print(f"   Diário: {quota['daily_remaining']}")
        print(f"   Mensal: {quota['monthly_remaining']}")

    except EnrichmentError as e:
        logger.error(f"Erro no enriquecimento: {e}")
        print(f"❌ ERRO: {e}")

# Execução
basic_ai_enrichment()
```

### Comparação de Estratégias

```python
def compare_ai_strategies():
    """Compara OpenAI vs Gemini no mesmo jogo"""

    if not system['enricher']:
        return

    # Configurações separadas para cada estratégia
    openai_only = [OpenAIStrategy(CONFIG['ai_enricher']['openai_key'])]
    gemini_only = [GeminiStrategy(CONFIG['ai_enricher']['gemini_key'])]

    enricher_openai = AIEnricher({}, openai_only, daily_quota=2)
    enricher_gemini = AIEnricher({}, gemini_only, daily_quota=2)

    # Mesmo jogo para ambas
    game = {
        'title': 'Portal 2',
        'description': 'Um puzzle game inovador',
        'genres': ['Puzzle'],
        'hashes': {'md5': 'test123', 'sha1': 'test456'}
    }

    print(f"\n🔍 COMPARAÇÃO DE ESTRATÉGIAS - {game['title']}\n")

    # Testa OpenAI
    try:
        result_openai = enricher_openai.enrich(game)
        print(f"🤖 OPENAI RESULTS:")
        print(f"   Confiança: {result_openai.confidence_score}")
        print(f"   Tempo: {result_openai.processing_time:.2f}s")
        print(f"   Gêneros: {result_openai.enriched_metadata.get('genres', [])}")
    except Exception as e:
        print(f"   ❌ OpenAI falhou: {e}")

    # Testa Gemini
    try:
        result_gemini = enricher_gemini.enrich(game)
        print(f"\n🧠 GEMINI RESULTS:")
        print(f"   Confiança: {result_gemini.confidence_score}")
        print(f"   Tempo: {result_gemini.processing_time:.2f}s")
        print(f"   Gêneros: {result_gemini.enriched_metadata.get('genres', [])}")
    except Exception as e:
        print(f"   ❌ Gemini falhou: {e}")

# Execução
compare_ai_strategies()
```

---

## 🔗 Exemplo 3: Pipeline Integrado Completo

### Pipeline Automático: Scraper → IA → Database

```python
def complete_pipeline(game_names: List[str]) -> List[Dict[str, Any]]:
    """Pipeline completo: scraping → AI → salvamento"""

    results = []

    for i, game_name in enumerate(game_names, 1):
        logger.info(f"Processando [{i}/{len(game_names)}]: {game_name}")

        pipeline_result = {
            'game_name': game_name,
            'steps': {},
            'final_metadata': None,
            'success': False
        }

        try:
            # PASSO 1: Raspagem de metadados
            pipeline_result['steps']['scraping'] = {'started': time.time()}

            metadata = system['scraper'].scrape_metadata(game_name)

            if not metadata:
                pipeline_result['steps']['scraping']['status'] = 'no_data'
                results.append(pipeline_result)
                continue

            pipeline_result['steps']['scraping'] = {
                'status': 'success',
                'data': metadata.to_dict(),
                'duration': time.time() - pipeline_result['steps']['scraping']['started']
            }

            # PASSO 2: Enriquecimento com IA (se disponível)
            if system['enricher']:
                pipeline_result['steps']['ai'] = {'started': time.time()}

                try:
                    ai_result = system['enricher'].enrich(metadata.to_dict())
                    pipeline_result['steps']['ai'] = {
                        'status': 'success',
                        'strategy': ai_result.used_strategy,
                        'confidence': ai_result.confidence_score,
                        'duration': ai_result.processing_time
                    }
                    enriched_data = ai_result.enriched_metadata
                except Exception as e:
                    pipeline_result['steps']['ai'] = {
                        'status': 'error',
                        'error': str(e),
                        'duration': time.time() - pipeline_result['steps']['ai']['started']
                    }
                    enriched_data = metadata.to_dict()
            else:
                enriched_data = metadata.to_dict()

            # PASSO 3: Salvamento no Database
            pipeline_result['steps']['database'] = {'started': time.time()}

            try:
                # Limpa dados para armazenamento
                db_data = {
                    'name': enriched_data['title'],
                    'filename': f"{game_name.replace(' ', '_')}.rom",
                    'size': 0,  # Placeholder
                    # Adiciona campos JSON flexíveis
                    'metadata_json': json.dumps(enriched_data),
                    'status': 'scraped',
                    'created_at': datetime.now().isoformat()
                }

                # Insere no banco
                system['database'].connect(CONFIG['database']['path'])
                system['database'].execute_query("""
                    INSERT INTO roms (
                        name, filename, size, metadata_json,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    db_data['name'],
                    db_data['filename'],
                    db_data['size'],
                    db_data['metadata_json'],
                    db_data['status'],
                    db_data['created_at']
                ))

                pipeline_result['steps']['database'] = {
                    'status': 'success',
                    'data': db_data,
                    'duration': time.time() - pipeline_result['steps']['database']['started']
                }

                pipeline_result['success'] = True
                pipeline_result['final_metadata'] = enriched_data

            except Exception as e:
                pipeline_result['steps']['database'] = {
                    'status': 'error',
                    'error': str(e),
                    'duration': time.time() - pipeline_result['steps']['database']['started']
                }

        except Exception as e:
            logger.error(f"Erro geral processando {game_name}: {e}")
            pipeline_result['steps']['error'] = str(e)

        results.append(pipeline_result)

    return results

def demo_complete_pipeline():
    """Demonstração do pipeline completo"""

    games = [
        "Tetris",
        "Pac-Man",
        "Space Invaders",
        "Pong"
    ]

    print(f"""
🚀 INICIANDO PIPELINE COMPLETO
📋 Jogos para processar: {', '.join(games)}
🔧 Componentes ativos:
   • WebScraper: {'✅' if system['scraper'] else '❌'}
   • AI Enricher: {'✅' if system['enricher'] else '❌'}
   • Database: {'✅' if system['database'] else '❌'}
   • Monitoring: {'✅' if system['exporter'] else '❌'}
"""""

    start_total = time.time()
    results = complete_pipeline(games)

    # Relatório
    total_time = time.time() - start_total
    successful = len([r for r in results if r['success']])

    print(f"\n📊 RESULTADO FINAL:"    print(f"⏱️  Tempo total: {total_time:.2f}s")
    print(f"✅ Sucessos: {successful}/{len(games)}")
    print(f"📈 Taxa: {successful/len(games)*100:.1f}%")

    for result in results:
        status_emoji = '✅' if result['success'] else '❌'
        print(f"   {status_emoji} {result['game_name']}")

        # Detalhes dos steps
        if result['steps'].get('scraping'):
            scr_status = result['steps']['scraping']['status']
            scr_emoji = '✅' if scr_status == 'success' else '💥'
            print(f"      🔍 Scraping: {scr_emoji} {scr_status}")

        if result['steps'].get('ai'):
            ai_status = result['steps']['ai']['status']
            ai_emoji = '🤖' if ai_status == 'success' else '❌'
            strategy = result['steps']['ai'].get('strategy', '')
            print(f"      {ai_emoji} IA: {ai_status} {strategy}")

        if result['steps'].get('database'):
            db_status = result['steps']['database']['status']
            db_emoji = '💾' if db_status == 'success' else '💥'
            print(f"      {db_emoji} DB: {db_status}")

# Execução
demo_complete_pipeline()
```

---

## 📦 Exemplo 4: Processamento em Lote

### Processamento Paralelo com Controle

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

class BatchProcessor:
    """Processador de lotes com controle avançado"""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.results_lock = Lock()
        self.quota_lock = Lock()
        self.results = []

    def safe_scrape_metadata(self, game_name: str):
        """Scraping com proteção de quota e erro"""
        try:
            return system['scraper'].scrape_metadata(game_name)
        except ScraperError as e:
            logger.warning(f"Scraping failed for {game_name}: {e}")
            return None

    def process_game_batch(self, game_names: List[str], progress_callback=None):
        """Processamento em lote com múltiplas threads"""

        if not game_names:
            return []

        print(f"""
🎯 INICIANDO PROCESSAMENTO EM LOTE
📋 Jogos: {len(game_names)}
🔄 Workers: {self.max_workers}
💡 Modos ativos: Scraping {'✅ AI' if system['enricher'] else '❌'}
        """")

        def process_single_game(game_name: str) -> Dict[str, Any]:
            """Processa um único jogo completo"""
            start_time = time.time()

            try:
                # Scraping
                metadata = self.safe_scrape_metadata(game_name)

                if not metadata:
                    return {
                        'game_name': game_name,
                        'success': False,
                        'error': 'scraping_failed',
                        'duration': time.time() - start_time
                    }

                # AI Enrichment (se disponível)
                enriched_data = metadata.to_dict()

                if system['enricher']:
                    with self.quota_lock:
                        quota = system['enricher'].get_quota_info()
                        if quota['daily_remaining'] <= 5:  # Reserva mínima
                            logger.warning(f"Pouca quota restante - pulando IA para {game_name}")
                        else:
                            try:
                                ai_result = system['enricher'].enrich(metadata.to_dict())
                                enriched_data = ai_result.enriched_metadata
                            except (EnrichmentError, QuotaExceededError) as e:
                                logger.warning(f"Enriquecimento IA falhou para {game_name}: {e}")
                                # Continue sem IA

                # Database storage
                if system['database']:
                    try:
                        db_entry = {
                            'name': enriched_data['title'],
                            'metadata_json': json.dumps(enriched_data),
                            'status': 'batch_processed'
                        }

                        system['database'].execute_query("""
                            INSERT INTO roms (name, metadata_json, status, created_at)
                            VALUES (?, ?, ?, datetime('now'))
                        """, (
                            db_entry['name'],
                            db_entry['metadata_json'],
                            db_entry['status']
                        ))

                    except DatabaseError as e:
                        logger.error(f"Erro ao salvar {game_name} no banco: {e}")

                success_result = {
                    'game_name': game_name,
                    'success': True,
                    'original_title': metadata.title,
                    'enriched_title': enriched_data['title'],
                    'genres_final': enriched_data['genres'],
                    'duration': time.time() - start_time
                }

                return success_result

            except Exception as e:
                logger.error(f"Erro inesperado processando {game_name}: {e}")

                return {
                    'game_name': game_name,
                    'success': False,
                    'error': str(e),
                    'duration': time.time() - start_time
                }

        # Execução paralela
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(process_single_game, game_name): game_name
                for game_name in game_names
            }

            for future in as_completed(futures):
                result = future.result()

                with self.results_lock:
                    self.results.append(result)

                if progress_callback:
                    progress_callback(len(self.results), len(game_names), result)

                if result['success']:
                    status_emoji = '✅'
                    details = f"{result['original_title']} ({', '.join(result.get('genres_final', []))})"
                else:
                    status_emoji = '❌'
                    details = result.get('error', 'unknown_error')

                print(f"{status_emoji} {result['game_name']}: {status_emoji}.2f")

                # Atualiza métricas do Prometheus (se ativo)
                if system['exporter']:
                    system['exporter'].collect_db_metrics(system['database'])

        return self.results

def progress_callback(processed: int, total: int, result: Dict[str, Any]):
    """Callback de progresso"""
    percent = processed / total * 100
    status = '✅' if result.get('success') else '❌'
    print(f"\r📊 Progresso: {processed}/{total} ({percent:.1f}%) - Último: {status} {result['game_name'][:20]}", end="")

def demo_batch_processing():
    """Demonstração de processamento em lote"""

    # Jogos para processamento em lote
    classic_games = [
        "Asteroids", "Centipede", "Frogger", "Galaga", "Galaxian",
        "Ms. Pac-Man", "Q*bert", "Robotron", "Tron", "Xenon"
    ]

    rpg_games = [
        "Baldur's Gate", "Divine Divinity", "Icewind Dale",
        "Planescape: Torment", "The Elder Scrolls II"
    ]

    action_games = [
        "Doom", "Duke Nukem 3D", "Quake", "Half-Life",
        "Unreal Tournament", "Counter-Strike"
    ]

    # Processa cada categoria
    processor = BatchProcessor(max_workers=2)

    for category, games in [
        ("🕹️  Clássicos Arcade", classic_games),
        ("⚔️  RPGs", rpg_games),
        ("🔫 Action/FP", action_games)
    ]:
        print(f"\n{category}")
        print("=" * len(category))

        start_time = time.time()
        results = processor.process_game_batch(games, progress_callback)

        # Estatísticas
        successful = len([r for r in results if r['success']])
        total_time = time.time() - start_time
        rate = successful / total_time if total_time > 0 else 0

        print(f"\n📊 ESTATÍSTICAS {category}:")
        print(".2f"        print(".2f"        print(f"📈 Taxa de processamento: {rate:.2f} jogos/minuto")
        print(f"📝 Processados: {len(results)}")
        print(f"✅ Sucessos: {successful}")
        print(f"❌ Falhas: {len(results) - successful}")

        # Limpa results para próxima categoria
        processor.results.clear()

# Execução
demo_batch_processing()
```

---

## 📊 Exemplo 5: Sistema com Monitoramento

### Dashboard Completo com Métricas

```python
def setup_monitoring_dashboard():
    """Configura dashboard de monitoramento completo"""

    if not system['exporter']:
        logger.warning("Monitoring não configurado")
        return

    # Inicializa métricas customizadas
    exporter = system['exporter']

    def create_custom_metrics(db_manager):
        """Cria métricas customizadas específicas"""

        try:
            # Estatísticas gerais
            with db_manager.connection_pool.get_connection() as conn:
                cursor = conn.connection.cursor()

                # Total de ROMs
                cursor.execute("SELECT COUNT(*) FROM roms")
                roms_count = cursor.fetchone()[0]

                # ROMs por status
                cursor.execute("""
                    SELECT status, COUNT(*) FROM roms
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())

                # Estatísticas de gêneros
                cursor.execute("SELECT COUNT(*) FROM roms WHERE genre IS NOT NULL")
                genre_count = cursor.fetchone()[0]

            # Registra métricas
            exporter.metrics_collector.set_gauge(
                "roms_total_count",
                roms_count,
                description="Total de ROMs no sistema"
            )

            for status, count in status_counts.items():
                exporter.metrics_collector.set_gauge(
                    f"roms_status_{status}",
                    count,
                    description=f"ROMs com status {status}"
                )

            exporter.metrics_collector.set_gauge(
                "roms_with_genre_count",
                genre_count,
                description="ROMs com gênero catalogado"
            )

            logger.info("Métricas customizadas atualizadas")

        except Exception as e:
            logger.error(f"Erro ao criar métricas customizadas: {e}")

    def continuous_monitoring():
        """Monitoramento contínuo"""

        logger.info("Iniciando monitoramento contínuo...")

        while True:
            try:
                # Atualiza métricas do banco
                db_manager = system['database']
                exporter.collect_db_metrics(db_manager)

                # Métricas customizadas
                create_custom_metrics(db_manager)

                # IA Quota (se disponível)
                if system['enricher']:
                    quota = system['enricher'].get_quota_info()
                    exporter.metrics_collector.set_gauge(
                        "ai_daily_quota_remaining",
                        quota['daily_remaining'],
                        description="Quota diária restante - IA"
                    )

                # Log status
                logger.info(".1f"                logger.info(f"Portal de métricas: http://localhost:{CONFIG['monitoring']['prometheus_port']}/metrics")

                # Espera próxima coleta
                time.sleep(30)  # Cada 30 segundos

            except KeyboardInterrupt:
                logger.info("Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"Erro no monitoramento: {e}")
                time.sleep(60)  # Espera extra em caso de erro

    # Inicia monitoramento
    continuous_monitoring()

def create_prometheus_config():
    """Gera configuração de exemplo para Prometheus"""

    config = f"""
# prometheus.yml - Exemplo de configuração
global:
  scrape_interval: 30s
  evaluation_interval: 30s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'megaemu'
    static_configs:
      - targets: ['localhost:{CONFIG['monitoring']['prometheus_port']}']
        labels:
          service: 'megaemu_db'
          environment: 'development'

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
        labels:
          service: 'node_exporter'
          environment: 'development'
"""

    # Salva configuração
    with open('prometheus.yml.example', 'w') as f:
        f.write(config.strip())

    print(f"📄 Configuração Prometheus gerada: prometheus.yml.example")
    print("🎯 Configure seu ambiente Prometheus/Grafana com essas métricas!")

# Configuração inicial
create_prometheus_config()

# Inicia dashboard (pressione Ctrl+C para parar)
try:
    setup_monitoring_dashboard()
except KeyboardInterrupt:
    print("\n🛑 Monitoramento parado")
```

---

## 🎨 Casos Avançados

### Sistema de Filas com Priorização

```python
from queue import PriorityQueue
import threading

class PrioritizedProcessor:
    """Processador com sistema de prioridades"""

    def __init__(self):
        self.queue = PriorityQueue()
        self.worker_lock = threading.Lock()
        self.processing = False

    def add_game(self, game_name: str, priority: int = 1):
        """Adiciona jogo na fila com prioridade"""
        self.queue.put((priority, game_name))

    def process_queue(self):
        """Processa fila por prioridade"""

        with self.worker_lock:
            if self.processing:
                return

            self.processing = True

        try:
            processor = BatchProcessor(max_workers=1)

            while not self.queue.empty():
                priority, game_name = self.queue.get()

                print(f"🎯 Processando prioridade {priority}: {game_name}")
                result = processor.process_game_batch([game_name])

                if result and result[0]['success']:
                    print(f"   ✅ {game_name} processado com sucesso")
                else:
                    print(f"   ❌ {game_name} falhou")

        finally:
            self.processing = False

# Demonstração
def demo_priority_queue():
    """Demonstração de fila prioritária"""

    prioritized = PrioritizedProcessor()

    # Adiciona jogos com diferentes prioridades
    game_queue = [
        ("Super Mario World", 1),       # Baixa prioridade
        ("The Witcher 3", 3),           # Alta prioridade
        ("Final Fantasy VII", 2),       # Média prioridade
        ("Last of Us Part II", 3),      # Alta prioridade
        ("Sonic the Hedgehog", 1)       # Baixa prioridade
    ]

    for game_name, priority in game_queue:
        prioritized.add_game(game_name, priority)

    print("🎯 FILA PRIORITÁRIA CRIADA:")
    print("   🟢 Prioridade 3 (alta): Jogos principais")
    print("   🟡 Prioridade 2 (média): Jogos intermediários")
    print("   🔴 Prioridade 1 (baixa): Jogos para later")

    # Processa fila (por prioridade)
    prioritized.process_queue()

# Execução
demo_priority_queue()
```

---

## 🔧 Scripts Úteis

### Script de Limpeza de Cache

```python
def cleanup_old_cache():
    """Remove dados antigos do cache"""

    scraper = system['scraper']

    try:
        # Remove entradas com mais de 30 dias
        import sqlite3

        cache_path = scraper.config.get('cache_path', 'web_scraper_cache.db')

        with sqlite3.connect(cache_path) as conn:
            old_time = time.time() - (30 * 24 * 3600)  # 30 dias atrás

            cursor = conn.cursor()
            cursor.execute("DELETE FROM cache WHERE timestamp < ?", (old_time,))

            deleted_count = cursor.rowcount
            conn.commit()

        print(f"🗑️  {deleted_count} entradas antigas removidas do cache")

    except Exception as e:
        print(f"❌ Erro na limpeza do cache: {e}")

# Execução periódica recomendada
cleanup_old_cache()
```

### Exportador de Dados

```python
def export_processed_data():
    """Exporta dados processados para JSON"""

    if not system['database']:
        print("❌ Database não configurado")
        return

    try:
        # Consulta dados processados
        system['database'].connect(CONFIG['database']['path'])

        cursor = system['database'].connection_pool.get_connection()
        cursor.connection.cursor().execute("""
            SELECT name, metadata_json, status, created_at
            FROM roms
            WHERE status IN ('scraped', 'enriched', 'batch_processed')
            ORDER BY created_at DESC
        """)

        data = cursor.connection.cursor().fetchall()

        # Formata para export
        export_data = []

        for row in data:
            name, metadata_json, status, created_at = row

            try:
                metadata = json.loads(metadata_json) if metadata_json else {}

                export_data.append({
                    'name': name,
                    'status': status,
                    'created_at': created_at,
                    'metadata': metadata
                })

            except json.JSONDecodeError:
                continue

        # Salva arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_data_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(".2f"        print(f"📊 Status distribution:")

        status_counts = {}
        for item in export_data:
            status = item.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            print(f"   • {status}: {count} ROMs")

    except Exception as e:
        print(f"❌ Erro na exportação: {e}")

# Exporta dados atuais
export_processed_data()
```

---

## 📝 Notas de Produção

### Configurações Recomendadas

#### Ambientes Pequenos (< 1k ROMs)
```python
config = {
    'web_scraper': {'rate_limit': 0.5},
    'ai_enricher': {'daily_quota': 50},
    'database': {'max_connections': 5}
}
```

#### Ambientes Médios (1k-10k ROMs)
```python
config = {
    'web_scraper': {'rate_limit': 2.0, 'cache_ttl': 7*24*3600},
    'ai_enricher': {'daily_quota': 200, 'monthly_quota': 5000},
    'database': {'max_connections': 15}
}
```

#### Ambientes Grandes (> 10k ROMs)
```python
config = {
    'web_scraper': {'rate_limit': 5.0},
    'ai_enricher': {'daily_quota': 500, 'monthly_quota': 10000},
    'database': {'max_connections': 50, 'enable_partitions': True}
}
```

### Troubleshooting Comum

1. **Quota IA Esgotada**
   ```python
   # Verificou quota antes de processar
   quota = enricher.get_quota_info()
   if quota['daily_remaining'] < 10:
       logger.warning("Pouca quota - considere pausar processamento IA")
   ```

2. **Rate Limit WebScraper**
   ```python
   # Aumentar intervalo
   config['rate_limit'] = 0.2  # 1 req/5s muito conservador
   ```

3. **Problemas de Banco**
   ```python
   # Verificar integridade
   if db_manager.check_database_integrity()[0]:
       print("✅ Banco íntegro")
   else:
       print("❌ Problemas de integridade detectados")
   ```

---

**🎯 Próximos Exemplos:**
- Pipeline ML para classificação automática
- API REST completa
- Dashboard web com Grafana
- Processamento distribuído

**📚 Documentação relacionada:**
- [`docs/API.md`](docs/API.md) - Referência completa de APIs
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Visão da arquitetura
- [`README.md`](../README.md) - Documentação principal