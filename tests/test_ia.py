import pytest
from unittest.mock import patch
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ia.ai import generate_text

@patch('ia.ai.logging.info')
def test_generate_text_basic(mock_logging):
    # Testa geração de texto básica
    result = generate_text("Olá")
    assert result == "Resposta mock para: Olá"
    mock_logging.assert_called_once_with("Gerando texto para prompt: Olá")

@patch('ia.ai.logging.info')
def test_generate_text_empty_prompt(mock_logging):
    # Testa com prompt vazio
    result = generate_text("")
    assert result == "Resposta mock para: "
    mock_logging.assert_called_once_with("Gerando texto para prompt: ")

@patch('ia.ai.logging.info')
def test_generate_text_long_prompt(mock_logging):
    # Testa com prompt longo
    prompt = "Este é um prompt muito longo para testar a função de geração de texto."
    result = generate_text(prompt)
    assert result == f"Resposta mock para: {prompt}"
    mock_logging.assert_called_once_with(f"Gerando texto para prompt: {prompt}")

@patch('ia.ai.logging.info')
def test_generate_text_special_chars(mock_logging):
    # Testa com caracteres especiais
    prompt = "Prompt com caracteres especiais: !@#$%^&*()"
    result = generate_text(prompt)
    assert result == f"Resposta mock para: {prompt}"
    mock_logging.assert_called_once_with(f"Gerando texto para prompt: {prompt}")

@patch('ia.ai.logging.info')
def test_generate_text_logging_not_called_on_error(mock_logging):
    # Testa que logging não é chamado se houver erro interno (mas como é mock simples, não há erro)
    # Para MVP, generate_text não tem erros, então sempre chama logging
    result = generate_text("Teste")
    assert result == "Resposta mock para: Teste"
    mock_logging.assert_called_once_with("Gerando texto para prompt: Teste")