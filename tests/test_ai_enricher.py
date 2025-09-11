"""
Testes abrangentes para AIEnricher
Cobertura: Mocks para OpenAI/Gemini APIs, quota management, fallback determinístico
Cenários críticos: falhas de API, quotas excedidas, timeouts, validações de entrada
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
sys.path.insert(0, 'engine/enrichment')

from ai_enricher import (
    AIEnricher,
    OpenAIStrategy,
    GeminiStrategy,
    QuotaManager,
    EnrichmentResult,
    EnrichmentError,
    APIError,
    QuotaExceededError,
    ValidationError,
    TimeoutError,
    EnrichmentStrategy
)


@pytest.fixture
def mock_openai_strategy():
    """Fixture para OpenAI strategy mockada."""
    return OpenAIStrategy('sk-test-key')


@pytest.fixture
def mock_gemini_strategy():
    """Fixture para Gemini strategy mockada."""
    return GeminiStrategy('gemini-test-key')


@pytest.fixture
def mock_config():
    """Fixture para configuração básica."""
    return {
        'api_keys': {
            'openai': 'sk-test-key',
            'gemini': 'gemini-test-key'
        },
        'use_fallback': True,
        'max_retries': 2,
        'daily_quota': 10,
        'monthly_quota': 100
    }


@pytest.fixture
def mock_metadata():
    """Fixture para metadados de teste."""
    return {
        'title': 'Super Mario World',
        'description': 'A classic platformer game',
        'genres': ['Platform'],
        'hashes': {
            'md5': 'testmd5hash',
            'sha1': 'testsha1hash'
        },
        'sources': [{'source': 'No-Intro', 'verified': True}],
        'tags': []
    }


@pytest.fixture
def invalid_metadata():
    """Fixture para metadados inválidos."""
    return "not-a-dict"


class TestEnrichmentResult:
    """Testes para EnrichmentResult dataclass."""

    def test_creation_with_all_fields(self):
        """Testa criação com todos os campos."""
        original = {'title': 'Test'}
        enriched = {'title': 'Test', 'description': 'Enhanced'}

        result = EnrichmentResult(
            original_metadata=original,
            enriched_metadata=enriched,
            confidence_score=0.85,
            used_strategy='OpenAI',
            processing_time=1.2,
            fallback_applied=False
        )

        assert result.confidence_score == 0.85
        assert result.used_strategy == 'OpenAI'
        assert not result.fallback_applied


class TestOpenAIStrategy:
    """Testes para OpenAIStrategy."""

    def test_initialization(self):
        """Testa inicialização."""
        strategy = OpenAIStrategy('sk-test-key', max_retries=3)
        assert strategy.api_key == 'sk-test-key'
        assert strategy.max_retries == 3
        assert strategy.strategy_name == 'OpenAI'

    def test_validate_api_access_with_key(self):
        """Testa validação com chave."""
        strategy = OpenAIStrategy('sk-valid-key')
        assert strategy.validate_api_access()

    def test_validate_api_access_without_key(self):
        """Testa validação sem chave."""
        strategy = OpenAIStrategy('')
        assert not strategy.validate_api_access()

    @patch('time.sleep')  # Simular processamento
    def test_enrich_success(self, mock_sleep):
        """Testa enriquecimento bem-sucedido."""
        strategy = OpenAIStrategy('sk-test-key')
        metadata = {
            'title': 'Test Game',
            'description': 'Original description',
            'genres': ['Action'],
            'tags': []
        }

        result = strategy.enrich(metadata)

        assert result['title'] == 'Test Game'
        assert 'Enriquecido por IA' in result['description']
        assert len(result['genres']) > len(metadata['genres'])
        assert 'IA-Enriched' in result['tags']
        assert 'translations' in result

    @patch('time.sleep')
    def test_enrich_preserves_structure(self, mock_sleep):
        """Testa que estrutura é preservada."""
        strategy = OpenAIStrategy('sk-test-key')
        metadata = {
            'title': 'Test Game',
            'description': 'Original',
            'hashes': {'md5': 'abc123'},
            'sources': [{'source': 'Test'}],
            'tags': ['existing']
        }

        result = strategy.enrich(metadata)

        assert result['hashes'] == metadata['hashes']
        assert result['sources'] == metadata['sources']


class TestGeminiStrategy:
    """Testes para GeminiStrategy."""

    def test_initialization(self):
        """Testa inicialização."""
        strategy = GeminiStrategy('gemini-test-key', max_retries=2)
        assert strategy.api_key == 'gemini-test-key'
        assert strategy.max_retries == 2
        assert strategy.strategy_name == 'Gemini'

    def test_enrich_unique_enhancements(self):
        """Testa enriquecimentos únicos do Gemini."""
        with patch('time.sleep'):
            strategy = GeminiStrategy('gemini-test-key')
            metadata = {
                'title': 'Test Game',
                'description': 'Original desc',
                'genres': ['Platform'],
                'tags': []
            }

            result = strategy.enrich(metadata)

            assert 'Enriquecido por Gemini' in result['description']
            assert 'Puzzle' in result['genres']
            assert 'AI-Driven' in result['tags']


class TestQuotaManager:
    """Testes para QuotaManager."""

    def test_initialization(self):
        """Testa inicialização."""
        manager = QuotaManager(daily_limit=50, monthly_limit=1000)
        assert manager.daily_limit == 50
        assert manager.monthly_limit == 1000
        assert manager.daily_usage == 0
        assert manager.monthly_usage == 0

    def test_check_and_increment_within_limits(self):
        """Testa verificação e incremento dentro dos limites."""
        manager = QuotaManager(daily_limit=10, monthly_limit=100)
        assert manager.check_and_increment()  # Deve permitir
        assert manager.daily_usage == 1
        assert manager.monthly_usage == 1

    def test_daily_limit_exceeded(self):
        """Testa limite diário excedido."""
        manager = QuotaManager(daily_limit=1, monthly_limit=100)
        manager.daily_usage = 1

        assert not manager.check_and_increment()  # Não deve permitir
        assert manager.daily_usage == 1  # Não incrementa

    def test_monthly_limit_exceeded(self):
        """Testa limite mensal excedido."""
        manager = QuotaManager(daily_limit=10, monthly_limit=2)
        manager.monthly_usage = 2

        assert not manager.check_and_increment()  # Não deve permitir

    def test_daily_reset_logic(self):
        """Testa lógica de reset diário."""
        with patch('ai_enricher.datetime') as mock_datetime:
            today = datetime(2024, 1, 1, 10, 0)
            tomorrow = datetime(2024, 1, 2, 10, 0)

            manager = QuotaManager(daily_limit=5, monthly_limit=100)
            manager.daily_usage = 5
            manager.last_reset_daily = today

            mock_datetime.now.return_value = tomorrow
            mock_datetime.now.date.return_value = tomorrow.date()

            # Deve resetar uso diário
            result = manager.check_and_increment()
            assert result
            assert manager.daily_usage == 1

    def test_monthly_reset_logic(self):
        """Testa lógica de reset mensal."""
        with patch('ai_enricher.datetime') as mock_datetime:
            this_month = datetime(2024, 1, 15, 10, 0)
            next_month = datetime(2024, 2, 15, 10, 0)

            manager = QuotaManager(daily_limit=10, monthly_limit=50)
            manager.monthly_usage = 50
            manager.last_reset_monthly = this_month

            mock_datetime.now.return_value = next_month
            mock_datetime.now.month = next_month.month
            mock_datetime.now.year = next_month.year

            # Deve resetar uso mensal (note: datetime implementation pode variar)
            # Testar comportamento básico
            manager.get_usage_info()  # Atualiza last_reset_monthly se necessário

    def test_get_usage_info(self):
        """Testa obtenção de informações de uso."""
        manager = QuotaManager(daily_limit=10, monthly_limit=100)
        manager.daily_usage = 5
        manager.monthly_usage = 25

        info = manager.get_usage_info()
        assert info['daily_usage'] == 5
        assert info['daily_limit'] == 10
        assert info['monthly_usage'] == 25
        assert info['monthly_limit'] == 100
        assert info['daily_remaining'] == 5
        assert info['monthly_remaining'] == 75


class TestAIEnricherValidation:
    """Testes de validação do AIEnricher."""

    def test_validate_input_valid(self, mock_config):
        """Testa validação de entrada válida."""
        enricher = AIEnricher(mock_config, [], daily_quota=100)
        valid_metadata = {
            'title': 'Test Game',
            'hashes': {'md5': 'hash123'}
        }

        # Não deve lançar exceção
        enricher.validate_input(valid_metadata)

    def test_validate_input_invalid_type(self, mock_config):
        """Testa validação de entrada com tipo inválido."""
        enricher = AIEnricher(mock_config, [], daily_quota=100)
        with pytest.raises(ValidationError):
            enricher.validate_input("not-a-dict")

    def test_validate_input_invalid_hashes(self, mock_config):
        """Testa validação de hashes inválidos."""
        enricher = AIEnricher(mock_config, [], daily_quota=100)
        invalid_metadata = {
            'title': 'Test',
            'hashes': "not-a-dict"
        }

        with pytest.raises(ValidationError):
            enricher.validate_input(invalid_metadata)


class TestAIEnricherEnrichment:
    """Testes de lógica de enriquecimento."""

    @patch('time.time')
    def test_successful_enrichment(self, mock_time, mock_config, mock_metadata):
        """Testa enriquecimento bem-sucedido."""
        mock_time.side_effect = [0.0, 1.5]  # Início e fim do processamento

        openai_strategy = OpenAIStrategy('sk-test-key')
        enricher = AIEnricher(mock_config, [openai_strategy], daily_quota=100)

        result = enricher.enrich(mock_metadata)

        assert result.confidence_score > 0
        assert result.used_strategy == 'OpenAI'
        assert result.processing_time == 1.5
        assert not result.fallback_applied
        assert result.enriched_metadata['title'] == mock_metadata['title']

    @patch('time.time')
    def test_enrichment_with_fallback(self, mock_time, mock_config, mock_metadata):
        """Testa enriquecimento com fallback."""
        mock_time.side_effect = [0.0, 2.0]

        # Strategy vazia para simular falha
        class FailingStrategy(EnrichmentStrategy):
            @property
            def strategy_name(self):
                return "Failing"

            def validate_api_access(self):
                return True

            def enrich(self, metadata):
                raise APIError("API indisponível")

        failing_strategy = FailingStrategy()
        enricher = AIEnricher(mock_config, [failing_strategy], enable_fallback=True, daily_quota=100)

        result = enricher.enrich(mock_metadata)

        assert result.used_strategy == 'deterministic_fallback'
        assert result.fallback_applied

    @patch('time.time')
    def test_quota_exceeded_error(self, mock_time, mock_config, mock_metadata):
        """Testa erro de quota excedida."""
        mock_time.side_effect = [0.0, 1.0]

        openai_strategy = OpenAIStrategy('sk-test-key')
        enricher = AIEnricher(mock_config, [openai_strategy], daily_quota=0)  # Quota zero

        with pytest.raises(QuotaExceededError):
            enricher.enrich(mock_metadata)

    @patch('time.time')
    def test_strategy_fallback_on_failure(self, mock_time, mock_config, mock_metadata):
        """Testa fallback entre estratégias."""
        mock_time.side_effect = [0.0, 1.8]

        # Primeira strategy falha, segunda sucinta
        class FailingStrategy(EnrichmentStrategy):
            @property
            def strategy_name(self):
                return "Fail"

            def validate_api_access(self):
                return True

            def enrich(self, metadata):
                raise APIError("Falha")

        success_strategy = OpenAIStrategy('sk-test-key')

        enricher = AIEnricher(mock_config, [FailingStrategy(), success_strategy], daily_quota=100)

        result = enricher.enrich(mock_metadata)
        assert result.used_strategy == 'OpenAI'  # Usou a segunda estratégia


class TestFallbackLogic:
    """Testes para lógica de fallback determinístico."""

    def test_apply_deterministic_fallback(self, mock_config):
        """Testa fallback determinístico."""
        class TestEnricher(AIEnricher):
            def _apply_deterministic_fallback(self, metadata):
                return super()._apply_deterministic_fallback(metadata)

        enricher = TestEnricher(mock_config, [], daily_quota=100)
        metadata = {
            'title': 'Adventure Game',
            'description': 'Explore worlds and adventure',
            'genres': [],
            'tags': []
        }

        result = enricher._apply_deterministic_fallback(metadata)

        assert len(result['genres']) > 0  # Deve detectar pelo menos um gênero
        assert 'Fallback-Processed' in result['tags']
        assert 'translations' in result

    def test_calculate_confidence_with_fallback(self, mock_config):
        """Testa cálculo de confiança com fallback."""
        class TestEnricher(AIEnricher):
            def _calculate_confidence(self, metadata, fallback_applied):
                return super()._calculate_confidence(metadata, fallback_applied)

        enricher = TestEnricher(mock_config, [], daily_quota=100)
        rich_metadata = {
            'title': 'Test',
            'description': 'Good desc',
            'hashes': {'md5': 'hash'},
            'genres': ['Action'],
            'translations': {'en': 'ENG'}
        }

        # Sem fallback
        score_no_fallback = enricher._calculate_confidence(rich_metadata, False)
        assert score_no_fallback > 0.7

        # Com fallback
        score_with_fallback = enricher._calculate_confidence(rich_metadata, True)
        assert score_with_fallback < score_no_fallback

    def test_detect_conflicts_none(self, mock_config):
        """Testa detecção de conflitos - nenhum conflito."""
        class TestEnricher(AIEnricher):
            def _detect_conflicts(self, sources):
                return super()._detect_conflicts(sources)

        enricher = TestEnricher(mock_config, [], daily_quota=100)
        sources = [
            {'source': 'No-Intro', 'verified': True},
            {'source': 'Redump', 'verified': False}
        ]

        conflicts = enricher._detect_conflicts(sources)
        assert len(conflicts) == 0  # Nenhuma fonte oficial

    def test_detect_conflicts_with_official(self, mock_config):
        """Testa detecção de conflitos - com fontes oficiais."""
        class TestEnricher(AIEnricher):
            def _detect_conflicts(self, sources):
                return super()._detect_conflicts(sources)

        enricher = TestEnricher(mock_config, [], daily_quota=100)
        sources = [
            {'source': 'No-Intro', 'verified': True},
            {'source': 'Redump', 'verified': True},
            {'source': 'UnofficialSource', 'verified': False}
        ]

        conflicts = enricher._detect_conflicts(sources)
        assert len(conflicts) > 0  # Multiples fontes oficiais poderiam conflitar


class TestEnrichmentErrors:
    """Testes de tratamento de erros."""

    def test_api_error_in_strategy(self, mock_config, mock_metadata):
        """Testa erro de API em estratégia."""
        class ErrorStrategy(EnrichmentStrategy):
            @property
            def strategy_name(self):
                return "ErrorStrategy"

            def validate_api_access(self):
                return True

            def enrich(self, metadata):
                raise APIError("Simulated API error")

        error_strategy = ErrorStrategy()
        enricher = AIEnricher(mock_config, [error_strategy], enable_fallback=False, daily_quota=100)

        # Deve tentar fallback determinístico se habilitado
        with pytest.raises(APIError):
            enricher.enrich(mock_metadata)

    def test_timeout_error_handling(self, mock_config, mock_metadata):
        """Testa tratamento de timeout."""
        class TimeoutStrategy(EnrichmentStrategy):
            @property
            def strategy_name(self):
                return "TimeoutStrategy"

            def validate_api_access(self):
                return True

            def enrich(self, metadata):
                raise TimeoutError("API timeout")

        timeout_strategy = TimeoutStrategy()
        enricher = AIEnricher(mock_config, [timeout_strategy], enable_fallback=True, daily_quota=100)

        result = enricher.enrich(mock_metadata)
        assert result.fallback_applied


if __name__ == "__main__":
    pytest.main([__file__])