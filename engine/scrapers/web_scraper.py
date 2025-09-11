"""
Módulo de Raspagem Web Ética para Enriquecimento de Metadados

Este módulo implementa um scraper ético para coletar metadados de jogos/ROMs
de fontes externas como TheGamesDB, IGDB e sites oficiais. Foca em práticas
éticas com rate limiting, user-agent rotation, cache e tratamento robusto de erros.

Princípios implementados:
- Rate limiting mínimo (1 req/segundo por padrão)
- Respeito aTerms of Service de fontes
- Cache local para minimizar requisições
- Tratamento ético de dados oficiais (No-Intro preferencial)
- Logging estruturado para auditoria

Autor: Roo, Engenheiro de Software Especializado
Data: 2024
"""

import abc
import json
import logging
import random
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError


# Configuração de logging
logger = logging.getLogger(__name__)

# Tipos de dados para metadados
@dataclass
class GameMetadata:
    """Modelo de dados para metadados de jogo extraídos."""
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    release_date: Optional[str] = None  # ISO 8601 format
    genres: List[str] = None
    platforms: List[str] = None

    def __post_init__(self):
        if self.genres is None:
            self.genres = []
        if self.platforms is None:
            self.platforms = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Exceções customizadas
class ScraperError(Exception):
    """Exceção base para erros de scraping."""
    pass


class NetworkError(ScraperError):
    """Erro de rede ou conexão."""
    pass


class RateLimitError(ScraperError):
    """Erro por excesso de requisições."""
    pass


class ParsingError(ScraperError):
    """Erro de parsing de dados."""
    pass


class ExternalAPIError(ScraperError):
    """Erro de API externa (não autorizado, serviço indisponível, etc.)."""
    pass


# Sistema de Rate Limiting
class RateLimiter:
    """
    Controla a frequência de requisições para evitar sobrecarga em fontes externas.

    Args:
        requests_per_second (float): Número máximo de requisições por segundo.
    """

    def __init__(self, requests_per_second: float = 1.0):
        self.delay = 1.0 / requests_per_second
        self.last_request_time = 0.0

    def wait_if_needed(self) -> None:
        """Aguarda se necessário para respeitar o limite de taxa."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            time.sleep(self.delay - time_since_last)

        self.last_request_time = time.time()


# Sistema de User-Agent Rotation
class UserAgentRotator:
    """
    Rotaciona user-agents para simular usuários únicos.
    """

    DEFAULT_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]

    def __init__(self, user_agents: Optional[List[str]] = None):
        self.user_agents = user_agents or self.DEFAULT_USER_AGENTS

    def get_random_user_agent(self) -> str:
        """Retorna um user-agent aleatório."""
        return random.choice(self.user_agents)


# Sistema de Cache Local
class LocalCache:
    """
    Cache local usando SQLite para armazenar respostas recentes.

    Args:
        db_path (str): Caminho para o arquivo de cache SQLite.
        ttl_seconds (int): Tempo de vida dos dados em segundos (padrão: 24h).
    """

    def __init__(self, db_path: str = "web_scraper_cache.db", ttl_seconds: int = 86400):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _init_db(self) -> None:
        """Inicializa o banco de dados de cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                timestamp REAL NOT NULL
            )''')

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Recupera dados do cache se válidos."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT data, timestamp FROM cache WHERE key = ?',
                (key,)
            )
            result = cursor.fetchone()

            if result:
                data_str, timestamp = result
                if time.time() - timestamp < self.ttl_seconds:
                    try:
                        return json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Dados corrompidos no cache para chave: {key}")

        return None

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Armazena dados no cache."""
        with sqlite3.connect(self.db_path) as conn:
            data_json = json.dumps(data)
            timestamp = time.time()
            conn.execute(
                'INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)',
                (key, data_json, timestamp)
            )


# Estratégia Base de Scraping
class ScrapingStrategy(abc.ABC):
    """
    Estratégia abstrata para implementar diferentes fontes de dados.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session = requests.Session()
        self.user_agent_rotator = UserAgentRotator(config.get('user_agents', None))
        self.rate_limiter = RateLimiter(config.get('requests_per_second', 1.0))

    @abc.abstractmethod
    def search_game(self, query: str) -> Optional[GameMetadata]:
        """
        Busca metadados de um jogo por query.

        Args:
            query (str): Nome do jogo ou identificador.

        Returns:
            Optional[GameMetadata]: Metadados encontrados ou None.
        """
        pass

    def _make_request(self, url: str, method: str = 'GET', params: Optional[Dict] = None,
                     data: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
        """
        Faz uma requisição HTTP com rate limiting e rotation de user-agent.

        Args:
            url (str): URL da requisição.
            method (str): Método HTTP.
            params (Optional[Dict]): Parâmetros de query.
            data (Optional[Dict]): Dados do corpo.
            headers (Optional[Dict]): Headers customizados.

        Returns:
            requests.Response: Resposta da requisição.

        Raises:
            NetworkError: Problema de rede.
            RateLimitError: Limite de taxa atingido.
            ExternalAPIError: Erro da API externa.
        """
        self.rate_limiter.wait_if_needed()

        if headers is None:
            headers = {}
        headers['User-Agent'] = self.user_agent_rotator.get_random_user_agent()

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=self.config.get('timeout_seconds', 10)
            )

            if response.status_code == 429:
                raise RateLimitError(f"Rate limit atingido para {url}")
            if response.status_code >= 400:
                raise ExternalAPIError(f"Erro HTTP {response.status_code}: {response.text}")

            return response

        except Timeout as e:
            raise NetworkError(f"Timeout na requisição para {url}") from e
        except ConnectionError as e:
            raise NetworkError(f"Erro de conexão para {url}") from e
        except RequestException as e:
            raise NetworkError(f"Erro de rede para {url}") from e


# Estratégia para TheGamesDB
class TheGamesDBStrategy(ScrapingStrategy):
    """
    Estratégia para TheGamesDB API.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = "https://api.thegamesdb.net/v1.1/"

    def search_game(self, query: str) -> Optional[GameMetadata]:
        """
        Busca jogo na TheGamesDB API.

        Args:
            query (str): Nome do jogo.

        Returns:
            Optional[GameMetadata]: Metadados ou None se não encontrado.
        """
        try:
            response = self._make_request(
                url=f"{self.base_url}Games/ByGameName",
                params={"name": query}
            )

            data = response.json()

            if 'data' in data and 'games' in data['data'] and data['data']['games']:
                game = data['data']['games'][0]  # Primeiro resultado

                return GameMetadata(
                    title=game.get('game_title', ''),
                    description=game.get('overview', ''),
                    developer=game.get('developer', ''),
                    publisher=game.get('publisher', ''),
                    release_date=game.get('release_date', ''),
                    genres=[game.get('genre', '')],
                    platforms=[game.get('platform', '')]
                )

        except (ScraperError, KeyError, ValueError) as e:
            logger.error(f"Erro ao buscar {query} no TheGamesDB: {e}")

        return None


# Estratégia para IGDB (usando API)
class IGDBStrategy(ScrapingStrategy):
    """
    Estratégia para IGDB API (requer chave de API).
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = "https://api.igdb.com/v4/"
        self.api_key = config.get('igdb_api_key', '')

        if not self.api_key:
            logger.warning("Chave IGDB não fornecida - estratégia limitada")

    def _authenticate(self) -> str:
        """Obtém token de autenticação (placeholder - implementation depends on IGDB auth)."""
        # Nota: IGDB requer OAuth2/authorization code flow
        # Esta é uma implementação simplificada
        return self.api_key

    def search_game(self, query: str) -> Optional[GameMetadata]:
        """
        Busca jogo na IGDB API.

        Args:
            query (str): Nome do jogo.

        Returns:
            Optional[GameMetadata]: Metadados ou None.
        """
        if not self.api_key:
            return None

        try:
            token = self._authenticate()

            response = self._make_request(
                url=f"{self.base_url}games",
                method="POST",
                data=f"""
                search "{query}";
                fields name, summary, cover.url, developers.name, publishers.name,
                       first_release_date, genres.name, platforms.name;
                limit 1;
                """,
                headers={"Authorization": f"Bearer {token}"}
            )

            data = response.json()

            if data:
                game = data[0]

                return GameMetadata(
                    title=game.get('name', ''),
                    description=game.get('summary', ''),
                    cover_url=game.get('cover', {}).get('url', ''),
                    developer=game.get('developers', [{}])[0].get('name', ''),
                    publisher=game.get('publishers', [{}])[0].get('name', ''),
                    release_date=str(game.get('first_release_date', '')) if game.get('first_release_date') else None,
                    genres=[g.get('name', '') for g in game.get('genres', [])],
                    platforms=[p.get('name', '') for p in game.get('platforms', [])]
                )

        except (ScraperError, KeyError, ValueError) as e:
            logger.error(f"Erro ao buscar {query} no IGDB: {e}")

        return None


# WebScraper Principal
class WebScraper:
    """
    Orquestrador principal para scraping ético de metadados de jogos.

    Args:
        config (Dict[str, Any]): Configuração com:
            - strategies: Lista de estratégias para usar ('thegamesdb', 'igdb')
            - rate_limit: Requisições por segundo
            - user_agents: Lista de user-agents
            - cache_enabled: Habilitar cache (True)
            - cache_ttl: TTL do cache em segundos
            - retry_attempts: Número de tentativas de retry
            - retry_backoff: Multiplicador de backoff
            - igdb_api_key: Chave para IGDB (opcional)
    """

    STRATEGY_CLASSES = {
        'thegamesdb': TheGamesDBStrategy,
        'igdb': IGDBStrategy
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strategies = []
        self.cache = None
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_backoff = config.get('retry_backoff', 2.0)
        self.logger = logging.getLogger(__name__)

        self._init_cache()
        self._init_strategies()

    def _init_cache(self) -> None:
        """Inicializa o sistema de cache."""
        if self.config.get('cache_enabled', True):
            cache_path = self.config.get('cache_path', 'web_scraper_cache.db')
            cache_ttl = self.config.get('cache_ttl', 86400)
            self.cache = LocalCache(cache_path, cache_ttl)

    def _init_strategies(self) -> None:
        """Inicializa as estratégias de scraping."""
        strategies_config = self.config.get('strategies', ['thegamesdb'])

        for strategy_name in strategies_config:
            if strategy_name in self.STRATEGY_CLASSES:
                strategy_class = self.STRATEGY_CLASSES[strategy_name]
                strategy = strategy_class(self.config)
                self.strategies.append(strategy)

    def scrape_metadata(self, query: str) -> Optional[GameMetadata]:
        """
        Raspa metadados para um jogo usando múltiplas estratégias.

        Args:
            query (str): Nome do jogo ou identificador.

        Returns:
            Optional[GameMetadata]: Metadados encontrados ou None.
        """
        cache_key = f"game:{query}"

        # Verifica cache
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.info(f"Dados encontrados no cache para: {query}")
                return GameMetadata(**cached)

        # Tenta cada estratégia com retry
        for strategy in self.strategies:
            result = self._try_with_retry(strategy.search_game, query)

            if result:
                # Armazena no cache
                if self.cache:
                    self.cache.set(cache_key, result.to_dict())

                self.logger.info(f"Metadados encontrados para {query} usando {strategy.__class__.__name__}")
                return result

        self.logger.warning(f"Nenhum metadado encontrado para: {query}")
        return None

    def _try_with_retry(self, func, *args, **kwargs) -> Optional[Any]:
        """
        Tenta executar uma função com retry em caso de erro.

        Args:
            func: Função a executar.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Returns:
            Optional[Any]: Resultado da função ou None.
        """
        backoff = 1.0

        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except NetworkError as e:
                if attempt == self.retry_attempts - 1:
                    self.logger.error(f"Tentativas esgotadas: {e}")
                    break

                sleep_time = backoff * random.uniform(0.5, 1.5)
                self.logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Aguardando {sleep_time}s")
                time.sleep(sleep_time)
                backoff *= self.retry_backoff

            except (RateLimitError, ExternalAPIError) as e:
                self.logger.error(f"Erro não recuperável: {e}")
                break

            except ScraperError as e:
                self.logger.error(f"Erro de scraping: {e}")
                break

        return None


# Exemplo de configuração
default_config = {
    'strategies': ['thegamesdb'],  # Exclua 'igdb' se não tiver chave
    'rate_limit': 1.0,  # 1 req/s
    'user_agents': None,  # Usa padrão
    'cache_enabled': True,
    'cache_ttl': 86400,  # 24h
    'retry_attempts': 3,
    'retry_backoff': 2.0,
    'timeout_seconds': 10,
    'igdb_api_key': 'your_igdb_api_key_here'  # Substitua pela chave real
}


# Exemplo de uso independente
if __name__ == "__main__":
    # Configuração básica de logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Exemplo de uso
    scraper = WebScraper(default_config)
    result = scraper.scrape_metadata("Super Mario World")

    if result:
        print("Metadados encontrados:")
        print(f"Título: {result.title}")
        print(f"Descrição: {result.description[:100] if result.description else 'N/A'}...")
        print(f"Desenvolvedor: {result.developer or 'N/A'}")
    else:
        print("Nenhum metadado encontrado.")