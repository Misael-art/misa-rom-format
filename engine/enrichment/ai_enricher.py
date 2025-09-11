import abc
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from datetime import datetime, timedelta


# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Exceções customizadas
class EnrichmentError(Exception):
    """Exceção base para erros de enriquecimento"""
    pass


class APIError(EnrichmentError):
    """Erro relacionado a APIs de IA"""
    pass


class QuotaExceededError(EnrichmentError):
    """Erro quando limite de uso da API é excedido"""
    pass


class ValidationError(EnrichmentError):
    """Erro de validação de entrada"""
    pass


class TimeoutError(EnrichmentError):
    """Erro de timeout nas chamadas de API"""
    pass


class EnrichmentResult:
    """Resultado do processo de enriquecimento"""

    def __init__(
        self,
        original_metadata: Dict[str, Any],
        enriched_metadata: Dict[str, Any],
        confidence_score: float,
        used_strategy: str,
        processing_time: float,
        fallback_applied: bool = False
    ):
        self.original_metadata = original_metadata
        self.enriched_metadata = enriched_metadata
        self.confidence_score = confidence_score
        self.used_strategy = used_strategy
        self.processing_time = processing_time
        self.fallback_applied = fallback_applied


class EnrichmentStrategy(ABC):
    """Interface abstrata para estratégias de enriquecimento de IA"""

    @abstractmethod
    def enrich(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece metadados usando IA

        Args:
            metadata: Metadados originais para enriquecer

        Returns:
            Metadados enriquecidos
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Nome da estratégia"""
        pass

    @abstractmethod
    def validate_api_access(self) -> bool:
        """Valida acesso à API"""
        pass


class OpenAIStrategy(EnrichmentStrategy):
    """Estratégia de enriquecimento usando OpenAI API"""

    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.max_retries = max_retries
        self.strategy_name_value = "OpenAI"

    @property
    def strategy_name(self) -> str:
        return self.strategy_name_value

    def validate_api_access(self) -> bool:
        """Simulação de validação de acesso à API OpenAI"""
        return bool(self.api_key)

    def enrich(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece metadados usando OpenAI (simulação)"""
        title = metadata.get('title', 'Unknown Title')
        description = metadata.get('description', '')

        # Simulação de chamada à API OpenAI
        logger.info(f"[OpenAI] Enriquecendo: {title}")
        time.sleep(0.1)  # Simulação de delay

        # Enriquecimento simulado
        enriched = metadata.copy()
        enriched['description'] = f"{description} [Enriquecido por IA: Descrição expandida baseada em padrões similares]."
        enriched['genres'] = enriched.get('genres', []) + ['Aventura', 'RPG']
        enriched['tags'] = enriched.get('tags', []) + ['IA-Enriched', 'Curated']
        enriched['translations'] = {
            'pt-BR': f"{title} [Tradução automática IA]",
            'es-ES': f"{title} [Traducción automática IA]"
        }

        return enriched


class GeminiStrategy(EnrichmentStrategy):
    """Estratégia de enriquecimento usando Gemini API"""

    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.max_retries = max_retries
        self.strategy_name_value = "Gemini"

    @property
    def strategy_name(self) -> str:
        return self.strategy_name_value

    def validate_api_access(self) -> bool:
        """Simulação de validação de acesso à API Gemini"""
        return bool(self.api_key)

    def enrich(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece metadados usando Gemini (simulação)"""
        title = metadata.get('title', 'Unknown Title')
        description = metadata.get('description', '')

        # Simulação de chamada à API Gemini
        logger.info(f"[Gemini] Enriquecendo: {title}")
        time.sleep(0.1)  # Simulação de delay

        # Enriquecimento simulado
        enriched = metadata.copy()
        enriched['description'] = f"{description} [Enriquecido por Gemini: Análise contextual baseada em clusters similares]."
        enriched['genres'] = enriched.get('genres', []) + ['Puzzle', 'Arcade']
        enriched['tags'] = enriched.get('tags', []) + ['AI-Driven', 'Adaptive']
        enriched['translations'] = {
            'pt-BR': f"{title} [Tradução assistida Gemini]",
            'es-ES': f"{title} [Traducción asistida Gemini]"
        }

        return enriched


class QuotaManager:
    """Gerenciador de cotas para APIs de IA"""

    def __init__(self, daily_limit: int = 100, monthly_limit: int = 3000):
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.daily_usage = 0
        self.monthly_usage = 0
        self.last_reset_daily = datetime.now()
        self.last_reset_monthly = datetime.now()

    def check_and_increment(self) -> bool:
        """Verifica limite e incrementa contador

        Returns:
            True se pode usar, False se quota excedida
        """
        now = datetime.now()

        # Reset diário se necessário
        if now.date() > self.last_reset_daily.date():
            self.daily_usage = 0
            self.last_reset_daily = now

        # Reset mensal se necessário
        if now.month > self.last_reset_monthly.month or now.year > self.last_reset_monthly.year:
            self.monthly_usage = 0
            self.last_reset_monthly = now

        # Verifica limites
        if self.daily_usage >= self.daily_limit:
            logger.warning("Limite diário de API excedido")
            return False
        if self.monthly_usage >= self.monthly_limit:
            logger.error("Limite mensal de API excedido")
            return False

        # Incrementa contador
        self.daily_usage += 1
        self.monthly_usage += 1

        logger.info(f"Uso atual: Diário {self.daily_usage}/{self.daily_limit}, Mensal {self.monthly_usage}/{self.monthly_limit}")
        return True

    def get_usage_info(self) -> Dict[str, Any]:
        """Retorna informações de uso"""
        return {
            'daily_usage': self.daily_usage,
            'daily_limit': self.daily_limit,
            'monthly_usage': self.monthly_usage,
            'monthly_limit': self.monthly_limit,
            'daily_remaining': max(0, self.daily_limit - self.daily_usage),
            'monthly_remaining': max(0, self.monthly_limit - self.monthly_usage)
        }


class AIEnricher:
    """Enriquecedor principal de metadados usando IA com múltiplas estratégias"""

    def __init__(
        self,
        config: Dict[str, Any],
        strategies: List[EnrichmentStrategy],
        enable_fallback: bool = True,
        max_retries: int = 3,
        daily_quota: int = 100,
        monthly_quota: int = 3000
    ):
        """Inicializa o enriquecedor

        Args:
            config: Configuração do enriquecedor
            strategies: Lista de estratégias disponíveis
            enable_fallback: Se deve aplicar fallback determinístico
            max_retries: Máximo de tentativas por estratégia
            daily_quota: Limite diário de uso da API
            monthly_quota: Limite mensal de uso da API
        """
        self.config = config
        self.strategies = strategies
        self.enable_fallback = enable_fallback
        self.max_retries = max_retries
        self.quota_manager = QuotaManager(daily_quota, monthly_quota)
        self.logger = logger

    def validate_input(self, metadata: Dict[str, Any]) -> None:
        """Valida entrada dos metadados"""
        if not isinstance(metadata, dict):
            raise ValidationError("Metadados devem ser um dicionário")

        # Validação básica de hashes se presentes
        hashes = metadata.get('hashes', {})
        if not isinstance(hashes, dict):
            raise ValidationError("Hashes devem estar em formato de dicionário")

        # Verifica conflitos em fontes
        sources = metadata.get('sources', [])
        if len(sources) > 1:
            conflicts = self._detect_conflicts(sources)
            if conflicts:
                self.logger.warning(f"Conflitos detectados: {conflicts}")

    def _detect_conflicts(self, sources: List[Dict[str, Any]]) -> List[str]:
        """Detecta conflitos entre fontes (simplificado)"""
        conflicts = []
        primary_sources = ['No-Intro', 'Redump', 'GoodTools']

        official_count = sum(1 for s in sources if s.get('source') in primary_sources)

        if len(sources) > 1 and official_count == 0:
            conflicts.append("Nenhuma fonte oficial detectada")

        return conflicts

    def enrich(self, metadata: Dict[str, Any]) -> EnrichmentResult:
        """Processa o enriquecimento de metadados"""
        start_time = time.time()

        # Validação
        self.validate_input(metadata)

        # Verifica quota
        if not self.quota_manager.check_and_increment():
            raise QuotaExceededError("Quota da API excedida")

        enriched = metadata.copy()
        used_strategy = "none"
        fallback_applied = False

        # Tenta estratégias em ordem
        for strategy in self.strategies:
            try:
                if not strategy.validate_api_access():
                    self.logger.warning(f"Estratégia {strategy.strategy_name} inválida")
                    continue

                # Retry com backoff
                for attempt in range(self.max_retries):
                    try:
                        enriched = strategy.enrich(metadata)
                        used_strategy = strategy.strategy_name
                        break
                    except (APIError, TimeoutError) as e:
                        if attempt < self.max_retries - 1:
                            backoff = (2 ** attempt) * 0.1
                            self.logger.warning(f"Tentativa {attempt+1} falhou, backoff {backoff}s: {e}")
                            time.sleep(backoff)
                        else:
                            raise

                # Sucesso na estratégia
                break

            except (APIError, TimeoutError, QuotaExceededError) as e:
                self.logger.error(f"Estratégia {strategy.strategy_name} falhou: {e}")
                continue

        # Fallback se necessário
        if fallback_applied or used_strategy == "none":
            if self.enable_fallback:
                enriched = self._apply_deterministic_fallback(metadata)
                used_strategy = "deterministic_fallback"
                fallback_applied = True
                self.logger.info("Fallback determinístico aplicado")

        processing_time = time.time() - start_time
        confidence_score = self._calculate_confidence(enriched, fallback_applied)

        result = EnrichmentResult(
            original_metadata=metadata,
            enriched_metadata=enriched,
            confidence_score=confidence_score,
            used_strategy=used_strategy,
            processing_time=processing_time,
            fallback_applied=fallback_applied
        )

        self.logger.info(f"Enriquecimento concluído em {processing_time:.2f}s")
        return result

    def _apply_deterministic_fallback(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica fallback determinístico baseado em regras simples"""
        enriched = metadata.copy()
        description = metadata.get('description', '')

        # Extrai gêneros baseados em palavras-chaves (simplificado)
        genre_keywords = {
            'Aventura': ['adventure', 'explore', 'quest'],
            'RPG': ['role', 'character', 'level'],
            'Ação': ['action', 'combat', 'fight'],
            'Esporte': ['sport', 'game', 'play']
        }

        detected_genres = []
        for genre, keywords in genre_keywords.items():
            if any(kw in description.lower() for kw in keywords):
                detected_genres.append(genre)

        enriched['genres'] = enriched.get('genres', []) + detected_genres
        enriched['tags'] = enriched.get('tags', []) + ['Fallback-Processed']

        # Tradução simples simulada
        enriched['translations'] = {
            'pt-BR': description + ' [Tradução automática]',
            'es-ES': description + ' [Traducción automática]'
        }

        return enriched

    def _calculate_confidence(self, metadata: Dict[str, Any], fallback_applied: bool) -> float:
        """Calcula score de confiança baseado nos metadados enriquecidos"""
        base_score = 0.7  # Base média

        # Ajustes baseados em qualidade
        if metadata.get('hashes'):
            base_score += 0.1
        if metadata.get('description', ''):
            base_score += 0.1
        if len(metadata.get('genres', [])) > 0:
            base_score += 0.1
        if metadata.get('translations'):
            base_score += 0.1

        # Penalização para fallback
        if fallback_applied:
            base_score -= 0.2

        return min(1.0, max(0.0, base_score))

    def get_quota_info(self) -> Dict[str, Any]:
        """Retorna informações de quota"""
        return self.quota_manager.get_usage_info()


# Exemplo de uso
def exemplo_uso():
    """Exemplo prático de uso do AIEnricher"""

    # Configuração
    config = {
        'api_keys': {
            'openai': 'sk-simulated-key',
            'gemini': 'gemini-simulated-key'
        },
        'use_fallback': True
    }

    # Estratégias
    strategies = [
        OpenAIStrategy(config['api_keys']['openai']),
        GeminiStrategy(config['api_keys']['gemini'])
    ]

    # Enriquecedor
    enricher = AIEnricher(
        config=config,
        strategies=strategies,
        enable_fallback=True,
        daily_quota=10  # Baixo para teste
    )

    # Metadados mockados
    mock_metadata = {
        'title': 'Super Mario Bros',
        'description': 'A classic platformer game',
        'genres': ['Platform'],
        'hashes': {
            'md5': '1234567890abcdef',
            'sha1': 'abcdef1234567890'
        },
        'sources': [{'source': 'No-Intro', 'verified': True}],
        'tags': []
    }

    try:
        result = enricher.enrich(mock_metadata)

        print("=== RESULTADO DO ENRIQUECIMENTO ===")
        print(f"Título: {result.enriched_metadata['title']}")
        print(f"Descrição: {result.enriched_metadata['description']}")
        print(f"Gêneros: {result.enriched_metadata['genres']}")
        print(f"Tags: {result.enriched_metadata['tags']}")
        print(f"Confiança: {result.confidence_score:.2f}")
        print(f"Estratégia: {result.used_strategy}")
        print(f"Fallback: {result.fallback_applied}")
        print(f"Tempo: {result.processing_time:.2f}s")

        quota_info = enricher.get_quota_info()
        print(f"\nUso API - Diário: {quota_info['daily_usage']}/{quota_info['daily_limit']}")

    except EnrichmentError as e:
        print(f"Erro no enriquecimento: {e}")


if __name__ == "__main__":
    exemplo_uso()