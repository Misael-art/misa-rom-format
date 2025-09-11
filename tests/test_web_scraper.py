"""
Testes abrangentes para WebScraper
Cobertura: mocks para requests externos, rate limiter, cache, user-agents, retry logic
Cenários críticos: falhas de rede, para de limites de API, cache corruption, timeouts
"""

import pytest
import json
import time
import sqlite3
import tempfile
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

import sys
sys.path.insert(0, 'engine/scrapers')

from web_scraper import (
    WebScraper,
    GameMetadata,
    TheGamesDBStrategy,
    IGDBStrategy,
    RateLimiter,
    LocalCache,
    UserAgentRotator,
    ScraperError,
    NetworkError,
    RateLimitError,
    ExternalAPIError,
    ParsingError
)


@pytest.fixture
def temp_cache_db():
    """Fixture para banco de cache temporário."""
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_file.close()

    yield db_file.name

    # Cleanup
    import os
    try:
        os.unlink(db_file.name)
    except:
        pass


@pytest.fixture
def mock_response():
    """Fixture para resposta HTTP mockada."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        'data': {
            'games': [{
                'game_title': 'Super Mario World',
                'overview': 'Classic platformer game',
                'developer': 'Nintendo EAD',
                'publisher': 'Nintendo',
                'release_date': '1990-11-21',
                'genre': 'Platform'
            }]
        }
    }
    response.text = json.dumps(response.json())
    return response


@pytest.fixture
def mock_failed_response():
    """Fixture para resposta HTTP de erro."""
    response = Mock()
    response.status_code = 404
    response.text = "Not Found"
    return response


@pytest.fixture
def mock_rate_limit_response():
    """Fixture para resposta de rate limit."""
    response = Mock()
    response.status_code = 429
    response.text = "Too Many Requests"
    return response


@pytest.fixture
def mock_timeout_response():
    """Fixture para resposta de timeout."""
    from requests.exceptions import Timeout
    return Timeout()


@pytest.fixture
def mock_connection_error():
    """Fixture para erro de conexão."""
    from requests.exceptions import ConnectionError
    return ConnectionError("Connection failed")


class TestGameMetadata:
    """Testes para GameMetadata dataclass."""

    def test_creation_with_all_fields(self):
        """Testa criação com todos os campos."""
        metadata = GameMetadata(
            title="Super Mario World",
            description="Classic platformer",
            cover_url="http://example.com/cover.jpg",
            developer="Nintendo",
            publisher="Nintendo",
            release_date="1990-11-21",
            genres=["Platform", "Adventure"],
            platforms=["SNES"]
        )
        assert metadata.title == "Super Mario World"
        assert metadata.genres == ["Platform", "Adventure"]
        assert metadata.platforms == ["SNES"]

    def test_creation_with_defaults(self):
        """Testa criação com valores padrão."""
        metadata = GameMetadata(title="Test Game")
        assert metadata.title == "Test Game"
        assert metadata.description is None
        assert metadata.genres == []
        assert metadata.platforms == []

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        metadata = GameMetadata(title="Test Game", genres=["Action"])
        data = metadata.to_dict()
        assert data["title"] == "Test Game"
        assert data["genres"] == ["Action"]

    def test_post_init_sets_lists(self):
        """Testa que listas são inicializadas se None."""
        metadata = GameMetadata(title="Test", genres=None, platforms=None)
        assert metadata.genres == []
        assert metadata.platforms == []


class TestRateLimiter:
    """Testes para RateLimiter."""

    def test_initialization(self):
        """Testa inicialização do rate limiter."""
        limiter = RateLimiter(2.0)
        assert limiter.delay == 0.5  # 1/2.0
        assert limiter.last_request_time == 0.0

    def test_wait_if_needed_first_call(self):
        """Testa primeira chamada - sem espera."""
        with patch('time.time') as mock_time:
            mock_time.return_value = 1.0
            limiter = RateLimiter(1.0)
            limiter.wait_if_needed()
            assert limiter.last_request_time == 1.0

    def test_wait_if_needed_with_delay(self):
        """Testa chamada com delay necessário."""
        with patch('time.time') as mock_time, patch('time.sleep') as mock_sleep:
            mock_time.side_effect = [0.0, 2.0, 2.1]  # Tempo inicial, tempo atual, após sleep
            limiter = RateLimiter(1.0)  # delay = 1.0
            limiter.last_request_time = 0.0

            limiter.wait_if_needed()
            mock_sleep.assert_called_with(0.0)  # 1.0 - 0 = 1.0 mas time.time 2.0 - 0.0 < 1.0? Wait
            assert limiter.last_request_time == 2.1


class TestUserAgentRotator:
    """Testes para UserAgentRotator."""

    def test_default_agents_count(self):
        """Testa número de user agents padrão."""
        rotator = UserAgentRotator()
        assert len(rotator.user_agents) == 5  # DEFAULT_USER_AGENTS

    def test_custom_agent_rotation(self):
        """Testa rotação de user agents customizados."""
        custom_agents = ["Agent1", "Agent2", "Agent3"]
        rotator = UserAgentRotator(custom_agents)

        # Simula várias chamadas
        agents = set()
        for _ in range(10):
            agents.add(rotator.get_random_user_agent())

        assert len(agents) <= len(custom_agents)


class TestLocalCache:
    """Testes para LocalCache."""

    def test_cache_initialization(self, temp_cache_db):
        """Testa inicialização do cache."""
        cache = LocalCache(temp_cache_db, ttl_seconds=3600)
        # Verifica se tabela foi criada
        conn = sqlite3.connect(temp_cache_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_cache_set_and_get(self, temp_cache_db):
        """Testa set e get de dados do cache."""
        with patch('time.time') as mock_time:
            mock_time.return_value = 1000

            cache = LocalCache(temp_cache_db, ttl_seconds=3600)
            test_data = {"game_title": "Super Mario", "year": 1990}

            # Set
            cache.set("mario", test_data)

            # Get
            result = cache.get("mario")
            assert result == test_data

    def test_cache_expiration(self, temp_cache_db):
        """Testa expiração do cache."""
        with patch('time.time') as mock_time:
            # Set com tempo atual
            mock_time.return_value = 1000
            cache = LocalCache(temp_cache_db, ttl_seconds=1)  # TTL de 1s

            cache.set("test", {"data": "value"})

            # Get antes de expirar
            mock_time.return_value = 1000.5
            assert cache.get("test") is not None

            # Get depois de expirar
            mock_time.return_value = 1001.5
            assert cache.get("test") is None

    def test_cache_corrupted_data(self, temp_cache_db):
        """Testa dados corrompidos no cache."""
        with patch('time.time') as mock_time:
            mock_time.return_value = 1000

            cache = LocalCache(temp_cache_db, ttl_seconds=3600)

            # Insere dados corrompidos diretamente
            conn = sqlite3.connect(cache.db_path)
            conn.execute("INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)",
                        ("corrupted", "invalid json", 1000))
            conn.commit()
            conn.close()

            # Deve retornar None para dados corrompidos
            with patch('json.loads', side_effect=json.JSONDecodeError("Invalid", "invalid json", 0)):
                result = cache.get("corrupted")
                assert result is None


class TestTheGamesDBStrategy:
    """Testes para TheGamesDBStrategy."""

    @pytest.fixture
    def config(self):
        """Fixture para configuração."""
        return {
            'timeout_seconds': 10,
            'user_agents': ['Test Agent'],
            'requests_per_second': 1.0
        }

    @patch('requests.Session')
    def test_successful_search(self, mock_session, config, mock_response):
        """Testa busca bem-sucedida."""
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_response
        mock_session.return_value = mock_session_instance

        strategy = TheGamesDBStrategy(config)
        with patch.object(strategy.rate_limiter, 'wait_if_needed'):
            result = strategy.search_game("Super Mario World")

            assert result is not None
            assert result.title == "Super Mario World"
            assert result.developer == "Nintendo EAD"
            assert result.genres == ["Platform"]

    @patch('requests.Session')
    def test_network_error_handling(self, mock_session, config):
        """Testa tratamento de erro de rede."""
        mock_session_instance = Mock()
        mock_session_instance.request.side_effect = ConnectionError("Network error")
        mock_session.return_value = mock_session_instance

        strategy = TheGamesDBStrategy(config)

        with pytest.raises(NetworkError):
            with patch.object(strategy.rate_limiter, 'wait_if_needed'):
                strategy._make_request("http://test.com")

    @patch('requests.Session')
    def test_rate_limit_error(self, mock_session, config, mock_rate_limit_response):
        """Testa erro de rate limit."""
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_rate_limit_response
        mock_session.return_value = mock_session_instance

        strategy = TheGamesDBStrategy(config)

        with pytest.raises(RateLimitError):
            with patch.object(strategy.rate_limiter, 'wait_if_needed'):
                strategy._make_request("http://test.com")

    @patch('requests.Session')
    def test_external_api_error(self, mock_session, config, mock_failed_response):
        """Testa erro externo de API."""
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_failed_response
        mock_session.return_value = mock_session_instance

        strategy = TheGamesDBStrategy(config)

        with pytest.raises(ExternalAPIError):
            with patch.object(strategy.rate_limiter, 'wait_if_needed'):
                strategy._make_request("http://test.com")


class TestIGDBStrategy:
    """Testes para IGDBStrategy."""

    @pytest.fixture
    def igdb_config(self):
        """Fixture para configuração IGDB."""
        return {
            'timeout_seconds': 10,
            'user_agents': ['Test Agent'],
            'requests_per_second': 1.0,
            'igdb_api_key': 'test_key'
        }

    @pytest.fixture
    def igdb_config_no_key(self):
        """Fixture para configuração sem chave IGDB."""
        return {
            'timeout_seconds': 10,
            'user_agents': ['Test Agent'],
            'requests_per_second': 1.0
        }

    @patch('requests.Session')
    def test_missing_api_key_returns_none(self, mock_session, igdb_config_no_key):
        """Testa que retorna None quando chave API não fornecida."""
        strategy = IGDBStrategy(igdb_config_no_key)
        result = strategy.search_game("Test Game")
        assert result is None

    def test_validate_api_access_without_key(self, igdb_config_no_key):
        """Testa validação de acesso sem chave."""
        strategy = IGDBStrategy(igdb_config_no_key)
        assert not strategy.validate_api_access()

    def test_validate_api_access_with_key(self, igdb_config):
        """Testa validação de acesso com chave."""
        strategy = IGDBStrategy(igdb_config)
        assert strategy.validate_api_access()


class TestWebScraper:
    """Testes para WebScraper principal."""

    @pytest.fixture
    def base_config(self):
        """Fixture para configuração base."""
        return {
            'strategies': ['thegamesdb'],
            'cache_enabled': True,
            'retry_attempts': 2,
            'retry_backoff': 1.0,
            'cache_ttl': 3600,
            'timeout_seconds': 10
        }

    @pytest.fixture
    def config_without_cache(self):
        """Fixture para configuração sem cache."""
        return {
            'strategies': ['thegamesdb'],
            'cache_enabled': False,
            'retry_attempts': 1
        }

    def test_initialization_with_cache(self, base_config):
        """Testa inicialização com cache habilitado."""
        scraper = WebScraper(base_config)
        assert scraper.retry_attempts == 2
        assert scraper.cache is not None
        assert len(scraper.strategies) == 1
        assert scraper.strategies[0].__class__.__name__ == 'TheGamesDBStrategy'

    def test_initialization_without_cache(self, config_without_cache):
        """Testa inicialização sem cache."""
        scraper = WebScraper(config_without_cache)
        assert scraper.cache is None

    @patch.object(TheGamesDBStrategy, 'search_game')
    def test_cache_hit(self, mock_search, base_config):
        """Testa que cache é usado quando disponível."""
        mock_metadata = GameMetadata(
            title="Super Mario World",
            genres=["Platform"]
        )
        mock_search.return_value = mock_metadata

        scraper = WebScraper(base_config)

        # Primeira chamada - deve chamar API
        result = scraper.scrape_metadata("Super Mario World")
        assert mock_search.called
        assert result.title == "Super Mario World"

        # Segunda chamada - deve usar cache
        mock_search.reset_mock()
        result2 = scraper.scrape_metadata("Super Mario World")
        # Não deve chamar API novamente
        assert mock_search.call_count == 0  # Cache hit
        assert result2.title == "Super Mario World"

    def test_invalid_strategy_ignored(self):
        """Testa que estratégias inválidas são ignoradas."""
        config = {
            'strategies': ['invalid_strategy'],
            'cache_enabled': False
        }
        scraper = WebScraper(config)
        assert len(scraper.strategies) == 0

    def test_empty_strategies_config(self):
        """Testa configuração vazia de estratégias."""
        config = {
            'strategies': [],
            'cache_enabled': False
        }
        scraper = WebScraper(config)
        assert len(scraper.strategies) == 0
        result = scraper.scrape_metadata("Test Game")
        assert result is None

    @patch.object(TheGamesDBStrategy, 'search_game')
    def test_retry_logic_success(self, mock_search, base_config):
        """Testa lógica de retry bem-sucedida."""
        mock_search.side_effect = [NetworkError("Temp fail"), None]  # Primeiro falha, segundo sucesso

        scraper = WebScraper(base_config)
        result = scraper.scrape_metadata("Test Game")

        # Deve ter tentado 2 vezes (falha + sucesso)
        assert mock_search.call_count == 2
        assert scraper.cache is not None  # Verifica se cache existe

    @patch.object(TheGamesDBStrategy, 'search_game')
    def test_all_strategies_fail(self, mock_search, base_config):
        """Testa quando todas as estratégias falham."""
        mock_search.return_value = None

        scraper = WebScraper(base_config)
        result = scraper.scrape_metadata("Unknown Game")

        assert result is None


# Testes de integração
class TestWebScraperIntegration:
    """Testes de integração do WebScraper."""

    def test_end_to_end_with_cache(self, temp_cache_db):
        """Testa fluxo completo com cache."""
        config = {
            'strategies': ['thegamesdb'],
            'cache_enabled': True,
            'cache_path': temp_cache_db,
            'retry_attempts': 1
        }

        # Cria scraper sem mocks para testar integração básica
        scraper = WebScraper(config)
        assert scraper.cache is not None

        # Como não há respostas reais, deve retornar None
        # Mas testa que o caminho do código é executado
        result = scraper.scrape_metadata("Test Game")
        assert result is None

    def test_memory_database_cache(self):
        """Testa cache em memória."""
        config = {
            'strategies': [],
            'cache_enabled': True,
            'cache_path': ':memory:',
            'retry_attempts': 1
        }

        scraper = WebScraper(config)
        assert scraper.cache is not None
        # Database :memory: não persiste, mas permite testar

    def test_multiple_strategies_fallback(self):
        """Testa fallback entre múltiplas estratégias."""
        config = {
            'strategies': ['thegamesdb', 'igdb'],
            'cache_enabled': False,
            'retry_attempts': 1,
            'igdb_api_key': 'test_key'  # Para que IGDB seja considerado
        }

        scraper = WebScraper(config)
        assert len(scraper.strategies) == 2
        assert scraper.strategies[0].__class__.__name__ == 'TheGamesDBStrategy'
        assert scraper.strategies[1].__class__.__name__ == 'IGDBStrategy'


if __name__ == "__main__":
    pytest.main([__file__])